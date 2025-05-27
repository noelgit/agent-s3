"""Implements static code analysis and embedding-based retrieval.

This module provides embedding-based code search capabilities as specified in instructions.md.
"""

import os
import re
import time
import logging
import traceback
import hashlib
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
try:
    import tomllib as toml
except Exception:  # pragma: no cover - python <3.11 or missing
    try:
        import toml  # type: ignore
    except Exception:
        toml = None

from rank_bm25 import BM25Okapi  # Ensure dependency is present, import will fail otherwise
from agent_s3.tools.embedding_client import EmbeddingClient
from agent_s3.tools.parsing.parser_registry import ParserRegistry

# Check if faiss is available without importing it to avoid optional dependency issues
FAISS_AVAILABLE = importlib.util.find_spec("faiss") is not None

# Import StaticAnalyzer for structural analysis if possible
try:
    from agent_s3.tools.static_analyzer import StaticAnalyzer
    STATIC_ANALYZER_AVAILABLE = True
except ImportError:
    STATIC_ANALYZER_AVAILABLE = False
    # Note: logger not available yet, so we'll log this later

# Define weights for hybrid search
DENSE_WEIGHT = 0.7  # Weight for dense embedding-based search
SPARSE_WEIGHT = 0.3  # Weight for sparse BM25-based search

# Multi-signal fusion weights
SEMANTIC_WEIGHT = 0.3  # Weight for semantic search (embeddings)
LEXICAL_WEIGHT = 0.2   # Weight for lexical search (BM25)
STRUCTURAL_WEIGHT = 0.4  # Weight for structural relevance
EVOLUTIONARY_WEIGHT = 0.1  # Weight for evolutionary coupling

# Threshold for considering queries semantically similar (0.0-1.0)
QUERY_SIMILARITY_THRESHOLD = 0.85  # High threshold to avoid false positives

# Flag to control whether to use enhanced context analysis
USE_ENHANCED_ANALYSIS = True  # Can be configured via config

logger = logging.getLogger(__name__)

if not STATIC_ANALYZER_AVAILABLE:
    logger.info("Static analyzer not available - using only semantic search")

DEFAULT_QUERY_CACHE_MAX_AGE = 3600  # Default to 1 hour in seconds
DEFAULT_MAX_QUERY_THEMES = 50       # Default max number of query themes to cache
BM25_AVAILABLE = True   # Assume BM25 is available since we import it above

class CodeAnalysisTool:
    """
    Tool for code analysis and searching using embeddings.
    Provides semantic search over codebase with context-aware prioritization.

    Enhanced with structural code analysis capabilities for deeper understanding
    of code relationships, dependencies, and evolutionary coupling.
    """

    def __init__(
        self,
        coordinator: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        file_tool: Optional[Any] = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the code analysis tool.

        Args:
            coordinator: Optional coordinator providing other tools
            config: Optional configuration dictionary
            file_tool: Optional file tool instance
        """
        self.coordinator = coordinator
        self.embedding_client = coordinator.embedding_client if coordinator else EmbeddingClient(config)
        self.file_tool = file_tool if file_tool else (coordinator.file_tool if coordinator else None)
        self.git_tool = coordinator.git_tool if coordinator and hasattr(coordinator, 'git_tool') else None

        # Initialize embedding cache
        self._embedding_cache = {}

        # Enhanced query cache with theme support
        self._query_cache = {
            "themes": {},     # Map theme_id -> {query_embedding, results, timestamp, expiry_timestamp}
            "embeddings": {}, # Map query hash -> embedding vector
            "recent": []      # List of recent theme_ids (for LRU cache eviction)
        }

        # Cache configuration - use values from config or defaults
        self._max_cache_size = config.get('max_embedding_cache_size', 100) if config else 100
        self._max_query_themes = config.get('max_query_themes', DEFAULT_MAX_QUERY_THEMES) if config else DEFAULT_MAX_QUERY_THEMES
        self.query_cache_max_age = config.get('query_cache_ttl_seconds', DEFAULT_QUERY_CACHE_MAX_AGE) if config else DEFAULT_QUERY_CACHE_MAX_AGE

        # Progressive eviction settings from config
        self.eviction_threshold = config.get('embedding_eviction_threshold', 0.8) if config else 0.8
        self.eviction_check_interval = config.get('eviction_check_interval', 20) if config else 20
        self._operation_count = 0

        # Initialize static analyzer for structural code analysis if available
        self.static_analyzer = None
        if STATIC_ANALYZER_AVAILABLE:
            workspace_path = None
            if coordinator and hasattr(coordinator, 'project_root'):
                workspace_path = coordinator.project_root

            # Create static analyzer instance with coordinator components
            self.static_analyzer = StaticAnalyzer(
                project_root=workspace_path,
                file_tool=self.file_tool
            )

            # Set fusion weights from config if available
            if config and 'fusion_weights' in config:
                weights = config.get('fusion_weights', {})
                self.static_analyzer.fusion_weights = {
                    'structural': weights.get('structural', STRUCTURAL_WEIGHT),
                    'semantic': weights.get('semantic', SEMANTIC_WEIGHT),
                    'lexical': weights.get('lexical', LEXICAL_WEIGHT),
                    'evolutionary': weights.get('evolutionary', EVOLUTIONARY_WEIGHT)
                }
            else:
                # Use default weights
                self.static_analyzer.fusion_weights = {
                    'structural': STRUCTURAL_WEIGHT,
                    'semantic': SEMANTIC_WEIGHT,
                    'lexical': LEXICAL_WEIGHT,
                    'evolutionary': EVOLUTIONARY_WEIGHT
                }

        # Flag to control whether to use enhanced context analysis
        self.use_enhanced_analysis = config.get('use_enhanced_analysis', USE_ENHANCED_ANALYSIS) if config else USE_ENHANCED_ANALYSIS

        # Initialize parser registry
        if coordinator and hasattr(coordinator, 'parser_registry'):
            self.parser_registry = coordinator.parser_registry
        else:
            self.parser_registry = ParserRegistry()
            logging.info("CodeAnalysisTool initialized its own ParserRegistry instance.")
        if not self.file_tool:
            logging.warning("FileTool not available to CodeAnalysisTool during __init__. Some operations might fail if not set later.")


    def find_relevant_files(self, query: str, top_n: int = 5, query_theme: Optional[str] = None,
                            use_hybrid: bool = True) -> List[Dict[str, Any]]:
        """
        Find relevant files based on a natural language query using hybrid search.
        """
        current_time = self._get_current_timestamp()
        # Enforce hybrid search requires BM25
        if use_hybrid and not BM25_AVAILABLE:
            raise ImportError("rank_bm25 is required for hybrid search; please install it.")
        # Generate query embedding first for cache matching
        query_embedding = None
        if self.embedding_client:
            query_embedding = self.embedding_client.get_embedding(query)
            if query_embedding is None:
                logging.error("Failed to generate query embedding")

        # Try to find a matching query theme if none provided
        theme_id = query_theme

        if query_embedding is not None and theme_id is None:
            # Try to find similar cached query by embedding similarity
            similar_theme = self._find_similar_query_theme(query_embedding)
            if similar_theme:
                theme_id = similar_theme
                logging.info(f"Found similar cached query theme: {theme_id}")

        # Check for a cached result with the theme ID
        if theme_id and theme_id in self._query_cache["themes"]:
            cache_entry = self._query_cache["themes"][theme_id]

            # Use expiry_timestamp written when the entry was cached
            expiry = cache_entry.get("expiry_timestamp")
            if expiry and current_time <= expiry:
                # Update access recency for LRU cache management
                self._update_theme_recency(theme_id)

                logging.info(f"Using cached results for query theme: {theme_id}")
                return cache_entry["results"][:top_n]
            else:
                # Cache entry is expired, remove it
                logging.info(f"Query theme cache expired: {theme_id}")
                self._remove_theme_from_cache(theme_id)

        # If we get here, we need to perform a new search

        # Get file embeddings
        if not self.embedding_client or not self.file_tool:
            logging.error("Embedding client or file tool not available")
            return []

        # Get code files
        code_files = self._get_code_files()
        if not code_files:
            logging.warning("No code files found")
            return []

        # Get file contents and generate embeddings
        file_contents = {}
        file_embeddings = {}

        for file_path in code_files:
            try:
                # Check if we already have an embedding for this file
                file_hash = self._get_file_hash(file_path)

                if file_hash in self._embedding_cache:
                    # Use cached embedding
                    file_embeddings[file_path] = self._embedding_cache[file_hash]["embedding"]
                    file_contents[file_path] = self._embedding_cache[file_hash]["content"]
                else:
                    # Read the file content
                    content = self.file_tool.read_file(file_path)
                    if not content:
                        continue

                    # Generate embedding
                    embedding = self.embedding_client.get_embedding(content)
                    if not embedding:
                        continue

                    # Store in cache
                    file_embeddings[file_path] = embedding
                    file_contents[file_path] = content

                    # Update embedding cache
                    self._embedding_cache[file_hash] = {
                        "embedding": embedding,
                        "content": content,
                        "timestamp": current_time
                    }

                    # Prune cache if it's too large
                    self._prune_cache_if_needed()
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}")

        # Calculate dense similarity scores (embedding-based)
        dense_scores = {}

        for file_path, file_embedding in file_embeddings.items():
            try:
                score = self._calculate_similarity(query_embedding, file_embedding)

                if score is not None:
                    dense_scores[file_path] = score
            except Exception as e:
                logging.error(f"Error calculating similarity for {file_path}: {e}")

        # For hybrid search, calculate sparse similarity scores (BM25-based)
        sparse_scores = {}
        if use_hybrid and BM25_AVAILABLE:
            try:
                # Prepare corpus for BM25
                tokenized_corpus = []
                corpus_file_paths = []

                for file_path, content in file_contents.items():
                    # Tokenize content (using specialized code tokenization)
                    tokens = self._tokenize_code(content)
                    if tokens:
                        tokenized_corpus.append(tokens)
                        corpus_file_paths.append(file_path)

                # Create BM25 index
                if tokenized_corpus:
                    bm25 = BM25Okapi(tokenized_corpus)

                    # Tokenize query the same way
                    tokenized_query = self._tokenize_code(query)

                    # Get BM25 scores
                    bm25_scores = bm25.get_scores(tokenized_query)

                    # Normalize scores to 0-1 range if we have any non-zero scores
                    max_score = max(bm25_scores) if bm25_scores.size > 0 and max(bm25_scores) > 0 else 1.0
                    for i, file_path in enumerate(corpus_file_paths):
                        sparse_scores[file_path] = bm25_scores[i] / max_score
            except Exception as e:
                logging.error(f"Error in BM25 calculation: {e}")
                logging.error(traceback.format_exc())

        # Combine scores for hybrid search
        results = []

        for file_path in file_contents.keys():
            try:
                # Get dense and sparse scores (default to 0 if not available)
                dense_score = dense_scores.get(file_path, 0.0)
                sparse_score = sparse_scores.get(file_path, 0.0)

                # Calculate combined score
                if use_hybrid and BM25_AVAILABLE and sparse_scores:
                    # Combine scores using weighted average
                    combined_score = (DENSE_WEIGHT * dense_score) + (SPARSE_WEIGHT * sparse_score)
                else:
                    # Fall back to dense-only if sparse not available
                    combined_score = dense_score

                results.append({
                    "file_path": file_path,
                    "content": file_contents[file_path],
                    "score": combined_score,
                    "dense_score": dense_score,
                    "sparse_score": sparse_score if sparse_scores else None
                })
            except Exception as e:
                logging.error(f"Error combining scores for {file_path}: {e}")

        # Sort by combined score (descending)
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Return top N results
        top_results = results[:top_n]

        # Store in query cache if embedding available
        if query_embedding is not None:
            # Create a new theme ID if none provided
            if not theme_id:
                theme_id = self._generate_query_theme_id(query)

            # Store in cache
            self._add_query_to_cache(theme_id, query_embedding, top_results, current_time)
            logging.info(f"Cached query results with theme ID: {theme_id}")

        return top_results

    def search(self, query: str, k: int = 5, paths: Optional[List[str]] = None) -> List[Dict]:
        """
        Search for code related to the query using embeddings.
        Returns a list of relevant code chunks with their file paths and line numbers.

        Args:
            query: Natural language query
            k: Number of results to return
            paths: Optional list of paths to search in

        Returns:
            List of relevant files with their content and relevance scores
        """
        # Check if we need to run cache eviction
        self._check_and_evict_cache_if_needed()

        # Get the embedding for the query
        query_embedding = self.embedding_client.get_embedding(query)
        if not query_embedding:
            logger.error("Failed to generate query embedding")
            return []

        # Find the most semantically similar files
        results = self.find_relevant_files(
            query=query,
            top_n=k,
            query_theme=self._generate_query_theme_id(query),
            use_hybrid=True
        )

        # If enhanced analysis is enabled and static analyzer is available,
        # enhance results with structural information
        if (
            self.use_enhanced_analysis
            and self.static_analyzer
            and hasattr(self.static_analyzer, "enhance_search_results")
            and results
        ):
            # Get the top files to use as structural query files
            query_files = [result["file_path"] for result in results[:3]]

            try:
                # Enhance results with structural relevance
                enhanced_results = self.static_analyzer.enhance_search_results(
                    semantic_results=results,
                    query_files=query_files
                )

                # Replace results with enhanced results
                results = enhanced_results

                logger.info(
                    "Enhanced search results with structural analysis for query: %s...",
                    query[:50],
                )
            except Exception as e:
                logger.error("Error enhancing search results with structural analysis: %s", e)

        # Update access patterns for progressive eviction
        if hasattr(self.embedding_client, 'update_access_patterns'):
            # Pass the file paths that were accessed during this search
            file_paths = [result["file_path"] for result in results]
            self.embedding_client.update_access_patterns(file_paths)

        return results

    def find_structurally_relevant_files(self, paths: List[str], k: int = 5) -> List[Dict]:
        """
        Find files that are structurally related to the given paths using static analysis.

        Args:
            paths: List of file paths to analyze
            k: Number of results to return

        Returns:
            List of relevant files with their content and relevance scores
        """
        if not self.static_analyzer or not paths:
            return []

        # Use static analyzer to find structurally relevant files
        try:
            if hasattr(self.static_analyzer, "find_structurally_relevant_files"):
                results = self.static_analyzer.find_structurally_relevant_files(
                    query_files=paths
                )
            else:
                results = []

            # Return top k results
            return results[:k]
        except Exception as e:
            logger.error("Error finding structurally relevant files: %s", e)
            return []

    def compute_multi_signal_relevance(self, file_path: str, query: str = None,
                                       target_files: List[str] = None) -> Dict[str, float]:
        """
        Compute relevance using multiple signals (fusion strategy).

        Args:
            file_path: Path to the file to analyze
            query: Optional natural language query
            target_files: Optional list of target files to compare against

        Returns:
            Dictionary with different relevance scores
        """
        if not self.static_analyzer or not hasattr(self.static_analyzer, "compute_multi_signal_relevance"):
            # Return simplified scores if static analyzer not available
            return {
                'semantic': 0.0,
                'structural': 0.0,
                'lexical': 0.0,
                'evolutionary': 0.0,
                'combined': 0.0
            }

        try:
            # Delegate to static analyzer
            return self.static_analyzer.compute_multi_signal_relevance(
                file_path=file_path,
                query=query,
                target_files=target_files,
            )
        except Exception as e:
            logger.error("Error computing multi-signal relevance: %s", e)
            return {
                'semantic': 0.0,
                'structural': 0.0,
                'lexical': 0.0,
                'evolutionary': 0.0,
                'combined': 0.0
            }

    def _check_and_evict_cache_if_needed(self):
        """
        Check cache size and trigger eviction if needed based on operation count
        and configured eviction check interval.
        """
        self._operation_count += 1

        # Only check periodically to avoid overhead
        if self._operation_count % self.eviction_check_interval == 0:
            # Delegate eviction to the embedding client
            if hasattr(self.embedding_client, 'evict_embeddings'):
                evicted = self.embedding_client.evict_embeddings()
                if evicted > 0:
                    logger.info("Evicted %s embeddings during code analysis operation", evicted)

            # Also clean up the local query cache if it's too large
            self._clean_query_cache()

    def invalidate_cache_for_file(self, file_path: str):
        """Remove cache entries containing results for the specified file path."""
        abs_file_path = str(Path(file_path).resolve())
        themes_to_invalidate = []
        for theme_id, cache_entry in self._query_cache["themes"].items():
            results = cache_entry.get("results", [])
            if any(result.get("file_path") == abs_file_path for result in results):
                themes_to_invalidate.append(theme_id)

        if themes_to_invalidate:
            logger.info("Invalidating cache themes %s due to change in %s", themes_to_invalidate, abs_file_path)
            for theme_id in themes_to_invalidate:
                self._remove_theme_from_cache(theme_id)
        else:
            logger.debug("No cache themes found containing %s to invalidate.", abs_file_path)

    def _add_query_to_cache(self, theme_id: str, query_embedding: List[float],
                            results: List[Dict[str, Any]], timestamp: int) -> None:
        """
        Add a query and its results to the theme cache with TTL.

        Args:
            theme_id: Theme identifier
            query_embedding: Embedding vector of the query
            results: Search results to cache
            timestamp: Current timestamp
        """
        expiry_timestamp = timestamp + self.query_cache_max_age
        if theme_id in self._query_cache["themes"]:
            # Theme already exists, update results and expiry
            self._query_cache["themes"][theme_id].update({
                "query_embedding": query_embedding,
                "results": results,
                "timestamp": timestamp,
                "expiry_timestamp": expiry_timestamp
            })
            self._update_theme_recency(theme_id)
        else:
            # New theme, add entry
            self._prune_theme_cache_if_needed()
            self._query_cache["themes"][theme_id] = {
                "query_embedding": query_embedding,
                "results": results,
                "timestamp": timestamp,
                "expiry_timestamp": expiry_timestamp
            }
            self._query_cache["recent"].append(theme_id)
            logging.info(f"Cached results for new theme: {theme_id}")

    def _update_theme_recency(self, theme_id: str) -> None:
        """
        Update the recency list for LRU cache management.

        Args:
            theme_id: Theme identifier to update
        """
        # Remove from current position if exists
        if theme_id in self._query_cache["recent"]:
            self._query_cache["recent"].remove(theme_id)

        # Add to front of list (most recent)
        self._query_cache["recent"].insert(0, theme_id)

    def _remove_theme_from_cache(self, theme_id: str) -> None:
        """
        Remove a theme from the cache.

        Args:
            theme_id: Theme identifier to remove
        """
        if theme_id in self._query_cache["themes"]:
            del self._query_cache["themes"][theme_id]

        if theme_id in self._query_cache["recent"]:
            self._query_cache["recent"].remove(theme_id)

    def _prune_theme_cache_if_needed(self) -> None:
        """Prune the theme cache if it exceeds the maximum size."""
        themes = self._query_cache["themes"]
        if len(themes) > self._max_query_themes:
            # Use the recency list to identify least recently used themes
            themes_to_remove = len(themes) - self._max_query_themes

            # Get the oldest themes from the end of the recency list
            oldest_themes = self._query_cache["recent"][-themes_to_remove:]

            # Remove them from the cache
            for theme_id in oldest_themes:
                self._remove_theme_from_cache(theme_id)

            logging.info(f"Pruned {themes_to_remove} themes from cache")

    def _clean_query_cache(self) -> None:
        """Remove expired query themes from the cache."""
        current_time = self._get_current_timestamp()
        expired = []

        for theme_id, cache_entry in list(self._query_cache["themes"].items()):
            expiry = cache_entry.get("expiry_timestamp")
            if expiry and current_time > expiry:
                expired.append(theme_id)

        for theme_id in expired:
            self._remove_theme_from_cache(theme_id)

        if expired:
            logging.debug(f"Removed expired themes from cache: {expired}")

    def _get_code_files(self) -> List[str]:
        """
        Get a list of code files in the project.

        Returns:
            List of file paths
        """
        if not self.file_tool:
            return []

        # Get code files
        extensions = [".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".html", ".css", ".scss", ".jsx", ".tsx"]

        try:
            code_files = self.file_tool.list_files(extensions=extensions)
            return code_files
        except Exception as e:
            logging.error(f"Error getting code files: {e}")
            return []

    def _calculate_similarity(self, embedding1, embedding2) -> Optional[float]:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score (0-1) or None if calculation fails
        """

        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Ensure the result is between 0 and 1
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            logging.error(f"Error calculating similarity: {e}")
            return None

    def _get_file_hash(self, file_path: str) -> str:
        """
        Generate a hash for a file based on its path and modification time.

        Args:
            file_path: Path to the file

        Returns:
            Hash string
        """
        try:
            # Get file modification time
            mod_time = os.path.getmtime(file_path)

            # Combine file path and mod time for the hash
            hash_input = f"{file_path}:{mod_time}"

            # Generate SHA-256 hash
            return hashlib.sha256(hash_input.encode()).hexdigest()
        except Exception as e:
            logging.error(f"Error generating file hash for {file_path}: {e}")
            return hashlib.sha256(file_path.encode()).hexdigest()

    def _get_current_timestamp(self) -> int:
        """
        Get current timestamp in seconds.

        Returns:
            Current timestamp
        """
        return int(time.time())

    def _prune_cache_if_needed(self):
        """Prune the embedding cache if it's too large."""
        self._operation_count += 1
        if self._operation_count % self.eviction_check_interval == 0:
            cache_size = len(self._embedding_cache)
            if cache_size > self._max_cache_size * self.eviction_threshold:
                # Find oldest entries based on timestamp
                sorted_cache = sorted(
                    self._embedding_cache.items(),
                    key=lambda x: x[1].get("timestamp", 0)
                )

                # Remove oldest entries to get below max size
                entries_to_remove = cache_size - self._max_cache_size
                for i in range(entries_to_remove):
                    if i < len(sorted_cache):
                        key = sorted_cache[i][0]
                        del self._embedding_cache[key]

    def analyze_code_complexity(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze the complexity of a code file.

        Args:
            file_path: Path to the code file

        Returns:
            Dict with complexity metrics
        """
        if not self.file_tool:
            return {"error": "File tool not available"}

        try:
            # Read the file
            content = self.file_tool.read_file(file_path)
            if not content:
                return {"error": "Could not read file"}

            # Get file extension
            _, ext = os.path.splitext(file_path)

            # Basic metrics
            metrics = {
                "file_path": file_path,
                "lines": content.count("\n") + 1,
                "characters": len(content),
                "file_type": ext,
            }

            # Count functions/methods
            if ext in [".py", ".js", ".ts", ".jsx", ".tsx"]:
                # Count function definitions
                function_count = 0

                if ext == ".py":
                    # Python functions
                    function_count += content.count("def ")
                else:
                    # JavaScript/TypeScript functions
                    function_count += content.count("function ")
                    function_count += len([line for line in content.split("\n") if "=>" in line])

                metrics["function_count"] = function_count

            # Count classes
            if ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".java"]:
                # Count class definitions
                class_count = content.count("class ")
                metrics["class_count"] = class_count

            # Count imports
            if ext == ".py":
                import_count = len([line for line in content.split("\n") if line.strip().startswith("import ") or line.strip().startswith("from ")])
                metrics["import_count"] = import_count
            elif ext in [".js", ".ts", ".jsx", ".tsx"]:
                import_count = len([line for line in content.split("\n") if line.strip().startswith("import ")])
                metrics["import_count"] = import_count

            return metrics
        except Exception as e:
            logging.error(f"Error analyzing code complexity for {file_path}: {e}")
            return {"error": str(e)}

    def _generate_query_theme_id(self, query: str) -> str:
        """
        Generate a theme ID for a query based on a hash of a normalized version of the query.

        Args:
            query: The query string

        Returns:
            Theme ID string
        """
        # Normalize query: lowercase, remove extra whitespace, punctuation
        normalized = re.sub(r'[^\w\s]', '', query.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        # Create a short hash for the theme ID
        theme_hash = hashlib.sha256(normalized.encode()).hexdigest()[:10]

        # Add a prefix for readability
        return f"theme_{theme_hash}"

    def _find_similar_query_theme(self, query_embedding: List[float]) -> Optional[str]:
        """
        Find an existing query theme that is semantically similar to the given query embedding.

        Args:
            query_embedding: The embedding vector of the query

        Returns:
            Theme ID of a similar query if found, None otherwise
        """
        if not query_embedding:
            return None

        best_similarity = 0.0
        best_theme = None

        # Compare with all cached theme embeddings
        for theme_id, theme_data in self._query_cache["themes"].items():
            theme_embedding = theme_data.get("query_embedding")
            if not theme_embedding:
                continue

            similarity = self._calculate_similarity(query_embedding, theme_embedding)
            if similarity and similarity > best_similarity:
                best_similarity = similarity
                best_theme = theme_id

        # Return the most similar theme if it's above the threshold
        if best_similarity >= QUERY_SIMILARITY_THRESHOLD:
            return best_theme

        return None

    def get_cached_query_themes(self) -> List[Dict[str, Any]]:
        """
        Get information about all cached query themes.

        Returns:
            List of dictionaries with theme information
        """
        result = []
        current_time = self._get_current_timestamp()

        for theme_id, theme_data in self._query_cache["themes"].items():
            age_seconds = current_time - theme_data.get("timestamp", 0)
            age_hours = age_seconds / 3600

            result.append({
                "theme_id": theme_id,
                "age_hours": round(age_hours, 1),
                "result_count": len(theme_data.get("results", [])),
                "is_recent": theme_id in self._query_cache["recent"][:5]  # Is in 5 most recent
            })

        return result

    def get_theme_info(self, theme_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific cached query theme.

        Args:
            theme_id: Theme identifier

        Returns:
            Dictionary with theme information
        """
        if theme_id not in self._query_cache["themes"]:
            return {"error": f"Theme {theme_id} not found in cache"}

        theme_data = self._query_cache["themes"][theme_id]
        current_time = self._get_current_timestamp()
        age_seconds = current_time - theme_data.get("timestamp", 0)

        return {
            "theme_id": theme_id,
            "age_seconds": age_seconds,
            "age_hours": round(age_seconds / 3600, 1),
            "result_count": len(theme_data.get("results", [])),
            "results": [r.get("file_path") for r in theme_data.get("results", [])],
            "is_recent": theme_id in self._query_cache["recent"][:5]
        }

    def clear_query_cache(self) -> Dict[str, Any]:
        """
        Clear all cached query themes.

        Returns:
            Status information
        """
        theme_count = len(self._query_cache["themes"])

        # Reset cache
        self._query_cache = {
            "themes": {},
            "embeddings": {},
            "recent": []
        }

        return {
            "status": "success",
            "cleared_themes": theme_count,
            "message": f"Cleared {theme_count} cached query themes"
        }

    def _tokenize_code(self, text: str) -> List[str]:
        """
        Tokenize code text for BM25 indexing.
        Handles code-specific tokenization including camelCase and snake_case splitting.

        Args:
            text: The code text to tokenize

        Returns:
            List of tokens
        """
        if not text:
            return []
        # Normalize whitespace and split on non-word boundaries
        tokens = re.findall(r"\b\w{2,}\b", text)
        return tokens

    def analyze_file_structure(self, file_path: str, language: str = None) -> dict:
        """
        Analyze the structure of a code file using language-specific parsers from ParserRegistry.
        Always use the new parser system; legacy regex-based parsing is removed.
        """
        if not self.file_tool:
            logger.error("FileTool is not available. Cannot analyze file structure.")
            return {'error': 'FileTool not available', 'file_path': file_path, 'elements': [], 'status': 'error'}
        if not self.parser_registry:
            logger.error("ParserRegistry not available. Cannot analyze file structure.")
            return {'error': 'ParserRegistry not available', 'file_path': file_path, 'elements': [], 'status': 'error'}
        try:
            content = self.file_tool.read_file(file_path)
            if content is None:
                logger.warning("Could not read content of file: %s", file_path)
                return {'error': 'Could not read file', 'file_path': file_path, 'elements': [], 'status': 'error'}
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            return {'error': f'Error reading file: {str(e)}', 'file_path': file_path, 'elements': [], 'status': 'error'}
        # Language detection
        if not language:
            if hasattr(self.file_tool, 'get_language_from_extension'):
                language = self.file_tool.get_language_from_extension(file_path)
            if not language:
                language = Path(file_path).suffix[1:].lower() if Path(file_path).suffix else 'unknown'
        parser = self.parser_registry.get_parser(language_name=language, file_path=file_path)
        if parser:
            try:
                logger.info("Analyzing %s with %s for language '%s'.", file_path, type(parser).__name__, language)
                structure = parser.parse_code(content, file_path)
                return {
                    'file_path': file_path,
                    'language': language,
                    'parser_used': type(parser).__name__,
                    'status': 'success',
                    'structure': structure
                }
            except Exception as e:
                logger.error(f"Error during analysis of {file_path} with {type(parser).__name__}: {e}", exc_info=True)
                return {'error': f'Analysis error with {type(parser).__name__}: {str(e)}', 'file_path': file_path, 'language': language, 'elements': [], 'status': 'analysis_error'}
        else:
            logger.error("No parser found for language '%s' for file %s.", language, file_path)
            return {
                'file_path': file_path,
                'language': language,
                'parser_used': None,
                'status': 'unsupported_language_or_no_parser',
                'elements': [], 'relations': [], 'functions': [], 'classes': [], 'imports': []
            }
