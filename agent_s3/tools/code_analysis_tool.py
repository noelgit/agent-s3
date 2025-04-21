"""Implements static code analysis and embedding-based retrieval.

This module provides embedding-based code search capabilities as specified in instructions.md.
"""

import os
import subprocess
import tempfile
import json
import re
import time
import logging
import traceback
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union, Set
import numpy as np
import toml  # Added for pyproject.toml parsing

# Try to import faiss, but provide graceful degradation if not available
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# Try to import rank_bm25 for BM25 sparse retrieval
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning("rank_bm25 package not found. Hybrid search will fall back to embedding-only search.")

# Constants for query theme caching
QUERY_SIMILARITY_THRESHOLD = 0.85  # Threshold for considering queries similar
QUERY_CACHE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds

# Hybrid search weight parameters (0.0 to 1.0)
DENSE_WEIGHT = 0.7  # Weight for embedding-based similarity
SPARSE_WEIGHT = 0.3  # Weight for BM25 text similarity


class CodeAnalysisTool:
    """
    Tool for analyzing code files in a project and finding relevant code.
    Implements optimized embedding caching and semantic search capabilities.
    """
    
    def __init__(self, coordinator=None):
        """Initialize the code analysis tool with a coordinator for access to other tools."""
        self.coordinator = coordinator
        self.embedding_client = coordinator.embedding_client if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        
        # Initialize embedding cache
        self._embedding_cache = {}
        
        # Enhanced query cache with theme support
        self._query_cache = {
            "themes": {},     # Map theme_id -> {query_embedding, results, timestamp}
            "embeddings": {}, # Map query hash -> embedding vector
            "recent": []      # List of recent theme_ids (for LRU cache eviction)
        }
        
        # Cache configuration
        self._max_cache_size = 100
        self._max_query_themes = 50
    
    def find_relevant_files(self, query: str, top_n: int = 5, query_theme: Optional[str] = None, 
                            use_hybrid: bool = True) -> List[Dict[str, Any]]:
        """
        Find relevant files based on a natural language query using hybrid search.
        
        Args:
            query: The natural language query
            top_n: Number of top results to return
            query_theme: Optional theme identifier for caching query results by semantic theme
            use_hybrid: Whether to use hybrid search (dense + sparse) or just dense embeddings
            
        Returns:
            List of dicts with file_path, content, and score
        """
        current_time = self._get_current_timestamp()
        
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
            
            # Check if cache is still valid (not expired)
            if current_time - cache_entry["timestamp"] < QUERY_CACHE_MAX_AGE:
                # Update access recency for LRU cache management
                self._update_theme_recency(theme_id)
                
                logging.info(f"Using cached results for query theme: {theme_id}")
                return cache_entry["results"]
            else:
                # Cache entry is too old, remove it
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
        import numpy as np
        
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
            
            # Generate MD5 hash
            return hashlib.md5(hash_input.encode()).hexdigest()
        except Exception as e:
            logging.error(f"Error generating file hash for {file_path}: {e}")
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def _get_current_timestamp(self) -> int:
        """
        Get current timestamp in seconds.
        
        Returns:
            Current timestamp
        """
        import time
        return int(time.time())
    
    def _prune_cache_if_needed(self):
        """Prune the embedding cache if it's too large."""
        if len(self._embedding_cache) > self._max_cache_size:
            # Find oldest entries based on timestamp
            sorted_cache = sorted(
                self._embedding_cache.items(),
                key=lambda x: x[1].get("timestamp", 0)
            )
            
            # Remove oldest entries to get below max size
            entries_to_remove = len(self._embedding_cache) - self._max_cache_size
            
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
        theme_hash = hashlib.md5(normalized.encode()).hexdigest()[:10]
        
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
    
    def _add_query_to_cache(self, theme_id: str, query_embedding: List[float], results: List[Dict[str, Any]], timestamp: int) -> None:
        """
        Add a query and its results to the theme cache.
        
        Args:
            theme_id: Theme identifier
            query_embedding: Embedding vector of the query
            results: Search results to cache
            timestamp: Current timestamp
        """
        # Store the results in the theme cache
        self._query_cache["themes"][theme_id] = {
            "query_embedding": query_embedding,
            "results": results,
            "timestamp": timestamp
        }
        
        # Update recency (for LRU eviction)
        self._update_theme_recency(theme_id)
        
        # Prune theme cache if needed
        self._prune_theme_cache_if_needed()
    
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
        
        # Convert to lowercase for case-insensitive matching
        text = text.lower()
        
        # Split camelCase identifiers
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
        
        # Split snake_case identifiers
        text = re.sub(r'_', ' ', text)
        
        # Handle common programming constructs and punctuation
        text = re.sub(r'[(){}\[\]<>.,;:+=\-*/&|!?]', ' ', text)
        
        # Remove common programming language keywords to reduce noise
        tokens = text.split()
        common_keywords = {
            'if', 'else', 'for', 'while', 'return', 'function', 'class', 'import', 
            'from', 'def', 'var', 'let', 'const', 'public', 'private', 'protected',
            'static', 'void', 'int', 'string', 'bool', 'true', 'false', 'null',
            'undefined', 'this', 'self', 'new', 'try', 'catch', 'finally', 'throw',
            'async', 'await', 'export', 'default', 'extends', 'implements'
        }
        
        # Filter out common short tokens and keywords
        filtered_tokens = [token for token in tokens if len(token) > 1 and token not in common_keywords]
        
        # Add special handling for important code identifiers even if they're in common keywords
        # For example, if someone is specifically searching for "class" or "function"
        for important_term in ['class', 'function', 'def']:
            if important_term in text.split() and important_term not in filtered_tokens:
                filtered_tokens.append(important_term)
        
        return filtered_tokens
    
    def prune_context_by_relevance(self, context_chunks: List[Dict[str, Any]], 
                                   query: str, 
                                   target_token_count: int,
                                   llm_client=None) -> List[Dict[str, Any]]:
        """
        Prunes context chunks based on their relevance to the query as determined by an LLM.
        
        Args:
            context_chunks: List of context chunks with content to assess
            query: The original query or planning objective
            target_token_count: Desired token count after pruning
            llm_client: Optional LLM client (uses coordinator's client if None)
            
        Returns:
            Pruned list of context chunks, retaining the most relevant ones
        """
        if not context_chunks:
            return []
            
        # Track start time for performance monitoring
        start_time = time.time()
            
        # Use coordinator's LLM client if none provided
        client = llm_client or (self.coordinator.llm if self.coordinator else None)
        if not client:
            logging.warning("No LLM client available for relevance scoring, falling back to hybrid search scores")
            # Fall back to using the search scores if available
            return sorted(context_chunks, key=lambda x: x.get("score", 0), reverse=True)
        
        # Calculate current token count (approximate)
        current_tokens = 0
        for chunk in context_chunks:
            content = chunk.get("content", "")
            # Use token estimator if available, otherwise use word count as approximation
            if self.coordinator and hasattr(self.coordinator, "memory_manager"):
                chunk_tokens = self.coordinator.memory_manager.estimate_token_count(content)
            else:
                chunk_tokens = len(content.split())
            
            # Store token count in chunk for later use
            chunk["token_count"] = chunk_tokens
            current_tokens += chunk_tokens
            
        if current_tokens <= target_token_count:
            # No pruning needed
            logging.info(f"Context already within token limit ({current_tokens}/{target_token_count}), no pruning needed")
            return context_chunks
        
        logging.info(f"Pruning context from {current_tokens} to {target_token_count} tokens using relevance scoring")
        
        # Prepare chunks for scoring
        chunks_to_score = []
        for i, chunk in enumerate(context_chunks):
            # Create a truncated version of content for scoring (to save tokens)
            content = chunk.get("content", "")
            
            # Extract key information (first part, variable/function names, comments)
            # This is a content summarization strategy to reduce tokens while preserving key information
            lines = content.split("\n")
            first_lines = lines[:10]  # First 10 lines often contain important context
            
            # Extract comments
            comments = []
            for line in lines:
                line = line.strip()
                if line.startswith("//") or line.startswith("#"):
                    comments.append(line)
                elif "/*" in line or "*/" in line or "'''" in line or '"""' in line:
                    comments.append(line)
            
            # Extract function and class definitions
            definitions = []
            for line in lines:
                line = line.strip()
                if re.search(r'(def|class|function|interface|struct)\s+\w+', line):
                    definitions.append(line)
            
            # Combine the most informative parts
            info_content = "\n".join(first_lines)
            if definitions:
                info_content += "\n\nKey definitions:\n" + "\n".join(definitions[:5])
            if comments:
                info_content += "\n\nKey comments:\n" + "\n".join(comments[:5])
                
            # Truncate if still too long
            if len(info_content) > 800:
                info_content = info_content[:800] + "..."
            
            chunks_to_score.append({
                "id": i,
                "content": info_content,
                "file_path": chunk.get("file_path", "unknown")
            })
        
        # Create prompt for LLM to score relevance
        prompt = f"""
        TASK: Score the relevance of each code snippet for addressing this query:
        "{query}"
        
        INSTRUCTIONS:
        - Assign each snippet a relevance score from 0 to 10
        - Consider how directly it relates to the query's core concepts
        - Higher scores mean higher relevance
        - Focus on code functionality, not just keyword matches
        - Consider both implementation details and structural elements
        - Return ONLY a JSON array with ID and score for each snippet
        
        RESPONSE FORMAT:
        [
          {{"id": 0, "score": 5}},
          {{"id": 1, "score": 9}},
          ...
        ]
        
        CODE SNIPPETS:
        """
        
        for chunk in chunks_to_score:
            prompt += f"\n--- SNIPPET {chunk['id']} (from {chunk['file_path']}) ---\n{chunk['content']}\n"
        
        # Call LLM to get relevance scores
        try:
            # Use a lower temperature for more consistent scoring
            response = client.generate(prompt, temperature=0.1, max_tokens=500)
            
            # Parse the JSON response
            import json
            import re
            
            # Extract JSON array from response (handle cases where LLM includes extra text)
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                logging.error("Failed to extract JSON from LLM response for relevance scoring")
                # Fallback to search scores
                logging.info("Falling back to hybrid search scores for pruning")
                return sorted(context_chunks, key=lambda x: x.get("score", 0), reverse=True)
                
            json_str = json_match.group(0)
            
            # Clean up any potential JSON issues (like trailing commas)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            try:
                scores = json.loads(json_str)
            except json.JSONDecodeError as je:
                logging.error(f"JSON parsing error: {je}")
                logging.error(f"Raw JSON: {json_str}")
                # Fallback to search scores
                return sorted(context_chunks, key=lambda x: x.get("score", 0), reverse=True)
            
            # Create a mapping of chunk ID to relevance score
            score_map = {item["id"]: item["score"] for item in scores if "id" in item and "score" in item}
            
            # Assign relevance scores to original chunks
            for i, chunk in enumerate(context_chunks):
                relevance_score = score_map.get(i, 0)
                chunk["relevance_score"] = relevance_score
                logging.debug(f"Chunk {i} ({chunk.get('file_path', 'unknown')}) scored {relevance_score}/10")
            
            # Sort by relevance score (descending)
            sorted_chunks = sorted(context_chunks, key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            # Keep chunks until we hit the target token count
            result_chunks = []
            current_tokens = 0
            
            for chunk in sorted_chunks:
                chunk_tokens = chunk.get("token_count", 0)
                if current_tokens + chunk_tokens <= target_token_count or not result_chunks:
                    result_chunks.append(chunk)
                    current_tokens += chunk_tokens
                    
                    # If this is the first chunk and already exceeds the token count,
                    # we might need to truncate its content
                    if len(result_chunks) == 1 and current_tokens > target_token_count:
                        # Simply indicate truncation needed (actual truncation happens elsewhere)
                        chunk["needs_truncation"] = True
                        chunk["target_tokens"] = target_token_count
                else:
                    break
            
            # Record processing time for performance monitoring
            processing_time = time.time() - start_time
            logging.info(f"Relevance-based pruning completed in {processing_time:.2f}s. "
                         f"Pruned from {len(context_chunks)} to {len(result_chunks)} chunks.")
            
            return result_chunks
            
        except Exception as e:
            logging.error(f"Error during relevance-based pruning: {e}")
            logging.error(traceback.format_exc())
            # Fall back to hybrid search scores if LLM scoring fails
            return sorted(context_chunks, key=lambda x: x.get("score", 0), reverse=True)
