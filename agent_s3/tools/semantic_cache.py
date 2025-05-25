"""
Advanced semantic caching for LLM calls with vectorized similarity search.

This module provides a drop-in replacement for any LLM provider with intelligent caching
based on semantic similarity rather than exact key matching.
"""

import os
import time
import json
import hashlib
import logging
import inspect
from typing import Dict, Any, Optional, Union, Callable, TypeVar
from functools import wraps
import numpy as np
from pathlib import Path
import threading
import faiss
import shutil
import stat

# Import our embedding client for vector similarity
from agent_s3.tools.embedding_client import EmbeddingClient
from agent_s3.config import get_config, ConfigModel

# Type variables for generic function signatures
T = TypeVar('T')
R = TypeVar('R')

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CACHE_TTL = 3600 * 24 * 7  # 7 days in seconds
DEFAULT_SIMILARITY_THRESHOLD = 0.85  # Minimum cosine similarity to consider a cache hit
DEFAULT_CACHE_DIR = ".cache/semantic_cache"
CACHE_VERSION = "v1.0"

class SemanticCache:
    """
    Advanced semantic caching for LLM calls with vector similarity search.

    This cache stores both exact matches (using hash keys) and semantic matches
    (using vector embeddings for similarity search). It supports both synchronous
    and asynchronous interfaces, TTL-based expiration, and flexible similarity thresholds.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(
        cls, config: Optional[Union[Dict[str, Any], "ConfigModel"]] = None
    ) -> "SemanticCache":
        """
        Get the singleton instance of the semantic cache.

        Args:
            config: Optional configuration dictionary

        Returns:
            The singleton instance of SemanticCache
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config)
            elif config is not None:
                cls._instance.update_config(config)
            return cls._instance

    def __init__(self, config: Optional[Union[Dict[str, Any], 'ConfigModel']] = None):
        """
        Initialize the semantic cache.

        Args:
            config: Configuration dictionary with cache settings
        """
        # Use provided config or get from global config
        if config is None:
            self.config: ConfigModel = get_config()
        elif isinstance(config, dict):
            self.config = ConfigModel(**config)
        else:
            self.config = config

        # Cache directory configuration
        workspace_path = Path(getattr(self.config, "workspace_path", ".")).resolve()
        cache_dir_name = getattr(self.config, "semantic_cache_dir", DEFAULT_CACHE_DIR)
        self.cache_dir = workspace_path / cache_dir_name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache parameters
        self.ttl = getattr(self.config, "semantic_cache_ttl", DEFAULT_CACHE_TTL)
        self.similarity_threshold = getattr(self.config, "semantic_similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD)
        self.max_cache_entries = getattr(self.config, "semantic_cache_max_entries", 10000)

        # Embedding dimension from config or default
        self.embedding_dim = getattr(self.config, "embedding_dim", 768)

        # Cache statistics
        self.hits = 0
        self.misses = 0
        self.semantic_hits = 0

        # Initialize embedding client for semantic similarity
        self._init_embedding_client()

        # Initialize FAISS index for vector search
        self._init_vector_store()

        # Memory cache for fast lookups (prompt_hash -> cached_response)
        self.mem_cache: Dict[str, Dict[str, Any]] = {}

        # Load cache from disk if available
        self._load_cache()

        logger.info(
            "Initialized semantic cache in %s with threshold %s",
            self.cache_dir,
            self.similarity_threshold,
        )

    def update_config(self, config: Union[Dict[str, Any], ConfigModel]) -> None:
        """
        Update the cache configuration.

        Args:
            config: New configuration dictionary
        """
        if isinstance(config, dict):
            self.config = ConfigModel(**{**self.config.dict(), **config})
        else:
            self.config = config

        self.ttl = getattr(self.config, "semantic_cache_ttl", self.ttl)
        self.similarity_threshold = getattr(self.config, "semantic_similarity_threshold", self.similarity_threshold)
        self.max_cache_entries = getattr(self.config, "semantic_cache_max_entries", self.max_cache_entries)

        logger.info(
            "Updated semantic cache config: ttl=%ss, threshold=%s",
            self.ttl,
            self.similarity_threshold,
        )

    def _init_embedding_client(self) -> None:
        """Initialize the embedding client for semantic similarity."""
        try:
            self.embedding_client = EmbeddingClient(self.config)
            logger.info("Initialized embedding client for semantic cache")
        except Exception as e:
            logger.error(
                "Failed to initialize embedding client: %s. Semantic matching will be disabled.",
                e,
            )
            self.embedding_client = None

    def _init_vector_store(self) -> None:
        """Initialize FAISS index for vector similarity search."""
        try:
            # Initialize an in-memory FAISS index with cosine similarity
            self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product (normalized vectors = cosine similarity)
            self.index_lookup: Dict[int, str] = {}  # Maps FAISS index position to cache key
            self.next_id = 0
            logger.info(
                "Initialized FAISS index with dimension %s",
                self.embedding_dim,
            )
        except Exception as e:
            logger.error(
                "Failed to initialize FAISS index: %s. Semantic matching will be disabled.",
                e,
            )
            self.index = None

    def _load_cache(self) -> None:
        """Load cache entries from disk."""
        cache_file = self.cache_dir / f"semantic_cache_{CACHE_VERSION}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)

                # Load metadata
                self.hits = cache_data.get("stats", {}).get("hits", 0)
                self.misses = cache_data.get("stats", {}).get("misses", 0)
                self.semantic_hits = cache_data.get("stats", {}).get("semantic_hits", 0)

                # Load cache entries
                entries = cache_data.get("entries", {})
                current_time = time.time()

                # Process all entries, skipping expired ones
                valid_entries = {}
                for key, entry in entries.items():
                    # Skip expired entries
                    if current_time - entry.get("timestamp", 0) > self.ttl:
                        continue

                    # Add to memory cache
                    valid_entries[key] = entry
                    self.mem_cache[key] = entry

                    # Add to vector index if embedding is available
                    embedding_data = entry.get("embedding")
                    if embedding_data and self.index is not None:
                        try:
                            embedding = np.array(embedding_data, dtype=np.float32).reshape(1, -1)
                            # Skip if embedding dimension doesn't match
                            if embedding.shape[1] != self.embedding_dim:
                                continue

                            # Add to FAISS index
                            self.index.add(embedding)
                            self.index_lookup[self.next_id] = key
                            self.next_id += 1
                        except Exception as e:
                            logger.warning(
                                "Failed to add embedding for cache key %s: %s",
                                key,
                                e,
                            )

                logger.info(
                    "Loaded %d valid cache entries from disk",
                    len(valid_entries),
                )

            except Exception as e:
                logger.error("Failed to load cache from disk: %s", e)
                # Initialize empty cache
                self.mem_cache = {}

    def _save_cache(self) -> None:
        """Save cache entries to disk."""
        cache_file = self.cache_dir / f"semantic_cache_{CACHE_VERSION}.json"
        temp_file = cache_file.with_suffix(".tmp")

        try:
            # Prepare cache data with statistics
            cache_data = {
                "version": CACHE_VERSION,
                "stats": {
                    "hits": self.hits,
                    "misses": self.misses,
                    "semantic_hits": self.semantic_hits,
                    "timestamp": time.time()
                },
                "entries": self.mem_cache
            }

            # Write to temporary file first
            with open(temp_file, 'w') as f:
                json.dump(cache_data, f)
            # Move temp file to actual file atomically
            shutil.move(str(temp_file), str(cache_file))
            # Restrict permissions to owner read/write
            os.chmod(cache_file, stat.S_IRUSR | stat.S_IWUSR)

            logger.debug(
                "Saved %d cache entries to disk",
                len(self.mem_cache),
            )

        except Exception as e:
            logger.error("Failed to save cache to disk: %s", e)
            # Clean up temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self.mem_cache.clear()
            if self.index is not None:
                # Reset FAISS index
                self.index = faiss.IndexFlatIP(self.embedding_dim)
                self.index_lookup.clear()
                self.next_id = 0

            # Reset statistics
            self.hits = 0
            self.misses = 0
            self.semantic_hits = 0

            # Save empty cache
            self._save_cache()

            logger.info("Cleared semantic cache")

    def get_cache_key(self, prompt_data: Dict[str, Any]) -> str:
        """
        Generate a deterministic cache key for the given prompt data.

        Args:
            prompt_data: Dictionary containing prompt data

        Returns:
            A string hash key
        """
        # Create a normalized, sorted copy of the input dictionary
        # This ensures consistent hashing regardless of key order
        prompt_copy = json.loads(json.dumps(prompt_data, sort_keys=True))

        # Extract only the essential parts that affect the output
        essential_data = {}

        # Extract messages if present (OpenAI-style APIs)
        if "messages" in prompt_copy:
            essential_data["messages"] = prompt_copy["messages"]

        # Extract prompt if present (older APIs)
        if "prompt" in prompt_copy:
            essential_data["prompt"] = prompt_copy["prompt"]

        # Add model information if present
        if "model" in prompt_copy:
            essential_data["model"] = prompt_copy["model"]

        # Include temperature as it affects output
        if "temperature" in prompt_copy:
            essential_data["temperature"] = prompt_copy["temperature"]

        # Include any other parameters that affect output
        for param in ["max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
            if param in prompt_copy:
                essential_data[param] = prompt_copy[param]

        # Create a hash of the essential data
        key_str = json.dumps(essential_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get_prompt_text(self, prompt_data: Dict[str, Any]) -> str:
        """
        Extract the actual prompt text from the prompt data.

        Args:
            prompt_data: Dictionary containing prompt data

        Returns:
            The prompt text as a string
        """
        # Extract from messages if present (OpenAI-style APIs)
        if "messages" in prompt_data and isinstance(prompt_data["messages"], list):
            # Join all user messages
            return " ".join(
                msg.get("content", "")
                for msg in prompt_data["messages"]
                if msg.get("role", "") == "user" and isinstance(msg.get("content"), str)
            )

        # Extract from prompt if present (older APIs)
        elif "prompt" in prompt_data and isinstance(prompt_data["prompt"], str):
            return prompt_data["prompt"]

        # Fall back to string representation
        return str(prompt_data)

    def get(self, prompt_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get a cached response for the given prompt data.

        Args:
            prompt_data: Dictionary containing prompt data

        Returns:
            Cached response if found, None otherwise
        """
        with self._lock:
            # Generate cache key
            key = self.get_cache_key(prompt_data)

            # Check for exact match in memory cache
            if key in self.mem_cache:
                entry = self.mem_cache[key]

                # Check if entry is expired
                if time.time() - entry.get("timestamp", 0) > self.ttl:
                    # Remove expired entry
                    del self.mem_cache[key]
                    logger.debug("Removed expired cache entry: %s", key[:8])
                    return None

                # Update access timestamp
                entry["last_access"] = time.time()

                # Increment hit counter
                self.hits += 1

                logger.debug("Cache hit for key: %s", key[:8])
                return {'response': entry.get("response"), 'cached': True}

            # No exact match, try semantic search
            if self.embedding_client is not None and self.index is not None and self.index.ntotal > 0:
                # Get prompt text for embedding
                prompt_text = self.get_prompt_text(prompt_data)

                try:
                    # Generate embedding
                    query_embedding = self.embedding_client.generate_embedding(prompt_text)

                    if query_embedding is not None:
                        # Normalize embedding for cosine similarity
                        query_embedding = query_embedding / np.linalg.norm(query_embedding)

                        # Search for similar prompts
                        distances, indices = self.index.search(
                            query_embedding.reshape(1, -1).astype('float32'),
                            k=5  # Get top 5 matches
                        )

                        # Check if we have a semantic match above threshold
                        if distances.size > 0 and distances[0][0] > self.similarity_threshold:
                            best_idx = indices[0][0]
                            match_key = self.index_lookup.get(best_idx)

                            if match_key and match_key in self.mem_cache:
                                entry = self.mem_cache[match_key]

                                # Check if entry is expired
                                if time.time() - entry.get("timestamp", 0) > self.ttl:
                                    return None

                                # Update access timestamp
                                entry["last_access"] = time.time()

                                # Increment semantic hit counter
                                self.semantic_hits += 1

                                logger.info(
                                    "Semantic cache hit with similarity %.3f > threshold %s",
                                    distances[0][0],
                                    self.similarity_threshold,
                                )
                                return {'response': entry.get("response"), 'cached': True}

                except Exception as e:
                    logger.warning("Error during semantic search: %s", e)

            # No match found
            self.misses += 1
            return None

    def set(self, prompt_data: Dict[str, Any], response: Any) -> None:
        """
        Store a response in the cache.

        Args:
            prompt_data: Dictionary containing prompt data
            response: Response to cache
        """
        with self._lock:
            # Generate cache key
            key = self.get_cache_key(prompt_data)

            # Extract prompt text for embedding
            prompt_text = self.get_prompt_text(prompt_data)

            # Prepare cache entry
            entry = {
                "timestamp": time.time(),
                "last_access": time.time(),
                "response": response,
                "prompt_text": prompt_text[:1000],  # Store truncated prompt text for debugging
                "embedding": None  # Will be filled if embedding generation succeeds
            }

            # Generate embedding if embedding client is available
            if self.embedding_client is not None and self.index is not None:
                try:
                    embedding = self.embedding_client.generate_embedding(prompt_text)

                    if embedding is not None:
                        # Normalize embedding for cosine similarity
                        embedding = embedding / np.linalg.norm(embedding)

                        # Add to FAISS index
                        self.index.add(embedding.reshape(1, -1).astype('float32'))

                        # Map index position to cache key
                        self.index_lookup[self.next_id] = key
                        self.next_id += 1

                        # Store embedding in cache entry
                        entry["embedding"] = embedding.tolist()

                        # Log successful embedding generation
                        logger.debug("Successfully generated embedding for cache entry: %s", key[:8])
                except Exception as e:
                    # Log the error but continue storing the entry without an embedding
                    logger.warning("Failed to generate embedding for cache entry: %s", e)

                    # Check if embedding client initialization failed
                    if self.embedding_client is None:
                        logger.error("Embedding client is not initialized - semantic search will be disabled")
                    elif self.index is None:
                        logger.error("FAISS index is not initialized - semantic search will be disabled")

                    # We still store the entry in memory cache, just without embedding
                    # This allows exact match cache hits to work even when embeddings fail

            # Add to memory cache
            self.mem_cache[key] = entry

            # Check if we need to evict entries
            if len(self.mem_cache) > self.max_cache_entries:
                self._evict_entries()

            # Periodically save cache to disk (every 10 entries)
            if len(self.mem_cache) % 10 == 0:
                self._save_cache()

            logger.debug("Added new cache entry: %s", key[:8])

    def _evict_entries(self) -> None:
        """
        Evict least recently used cache entries efficiently.
        Performs partial index updates instead of rebuilding the entire index.
        """
        # Identify entries to evict using LRU strategy
        sorted_entries = sorted(
            self.mem_cache.items(),
            key=lambda x: x[1].get("last_access", 0)
        )
        num_to_evict = max(1, len(sorted_entries) - int(self.max_cache_entries * 0.9))
        logger.info("Evicting %d cache entries from semantic cache", num_to_evict)

        # Track IDs to remove from the FAISS index
        entries_to_evict = sorted_entries[:num_to_evict]
        keys_to_evict = [item[0] for item in entries_to_evict]

        # Find indices to remove from FAISS
        index_positions_to_remove = []
        for idx, key in list(self.index_lookup.items()):
            if key in keys_to_evict:
                index_positions_to_remove.append(idx)
                # Remove from lookup map
                self.index_lookup.pop(idx)

        # Remove entries from memory cache
        for key in keys_to_evict:
            self.mem_cache.pop(key, None)

        # If FAISS index needs updating and we have entries to remove
        if self.index is not None and index_positions_to_remove and hasattr(self.index, 'remove_ids'):
            try:
                # Convert to numpy array of the correct type
                remove_ids = np.array(index_positions_to_remove, dtype=np.int64)
                # Remove directly from index instead of rebuilding
                self.index.remove_ids(remove_ids)
                logger.debug(
                    "Removed %d entries from FAISS index",
                    len(remove_ids),
                )
            except Exception as e:
                logger.warning("Error removing entries from FAISS index: %s", e)

                # If partial removal fails, rebuild index as fallback
                if len(self.mem_cache) > 0:
                    try:
                        self._rebuild_index()
                    except Exception as rebuild_error:
                        logger.error(
                            "Failed to rebuild index after eviction: %s",
                            rebuild_error,
                        )

        # Save cache state after eviction
        self._save_cache()

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from scratch using current cache entries."""
        import faiss
        import numpy as np

        logger.info("Rebuilding FAISS index from scratch")

        # Count entries with embeddings
        entries_with_embeddings = sum(1 for entry in self.mem_cache.values() if entry.get("embedding") is not None)

        if entries_with_embeddings == 0:
            logger.warning("No cache entries with embeddings found, skipping index rebuild")
            return

        # Initialize a new empty index with the right dimensions
        sample_embedding = next((np.array(entry["embedding"], dtype=np.float32)
                               for entry in self.mem_cache.values()
                               if entry.get("embedding") is not None), None)

        if sample_embedding is None:
            logger.warning("Could not find any valid embeddings to determine dimensions")
            return

        dimension = len(sample_embedding)
        self.index = faiss.IndexFlatL2(dimension)

        # Reset lookup dictionary
        self.index_lookup = {}
        self.next_id = 0

        # Add all existing embeddings to the new index
        for key, entry in self.mem_cache.items():
            if entry.get("embedding") is not None:
                try:
                    # Convert to numpy array and reshape
                    embedding = np.array(entry["embedding"], dtype=np.float32).reshape(1, -1)

                    # Add to index
                    self.index.add(embedding)

                    # Map to cache key
                    self.index_lookup[self.next_id] = key
                    self.next_id += 1
                except Exception as e:
                    logger.warning("Error adding entry to rebuilt index: %s", e)

        logger.info("FAISS index rebuilt with %s entries", self.index.ntotal)

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Return cache statistics: hits, misses, and semantic_hits.
        """
        return {"hits": self.hits, "misses": self.misses, "semantic_hits": self.semantic_hits}


def cache_decorator(ttl: Optional[int] = None, similarity_threshold: Optional[float] = None):
    """
    A decorator that applies semantic caching to a function.

    Args:
        ttl: Time-to-live in seconds for cache entries (overrides default)
        similarity_threshold: Minimum similarity threshold for semantic matching (overrides default)

    Returns:
        A decorator function
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get or initialize the cache
            cache = SemanticCache.get_instance()

            # Override TTL and threshold if specified
            if ttl is not None:
                original_ttl = cache.ttl
                cache.ttl = ttl

            if similarity_threshold is not None:
                original_threshold = cache.similarity_threshold
                cache.similarity_threshold = similarity_threshold

            # Combine args and kwargs into a single dictionary for caching
            # This is tricky because we need to map positional args to param names
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)

            # Create prompt_data from the function arguments
            prompt_data = dict(bound_args.arguments)

            # Try to get from cache
            cached_result = cache.get(prompt_data)
            if cached_result is not None:
                # Restore original settings if overridden
                if ttl is not None:
                    cache.ttl = original_ttl
                if similarity_threshold is not None:
                    cache.similarity_threshold = original_threshold

                return cached_result

            # Cache miss, call the original function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(prompt_data, result)

            # Restore original settings if overridden
            if ttl is not None:
                cache.ttl = original_ttl
            if similarity_threshold is not None:
                cache.similarity_threshold = original_threshold

            return result

        return wrapper

    return decorator


# This function is meant to be a drop-in replacement for traditional LLM call functions
def cached_llm_call(
    llm_client: Any,
    prompt_data: Dict[str, Any],
    ttl: Optional[int] = None,
    similarity_threshold: Optional[float] = None
) -> Any:
    """
    Make an LLM call with semantic caching.

    Args:
        llm_client: The LLM client object
        prompt_data: Dictionary containing prompt data
        ttl: Optional TTL override for this specific call
        similarity_threshold: Optional similarity threshold override for this call

    Returns:
        The LLM response (from cache or fresh)
    """
    # Get or initialize the cache
    cache = SemanticCache.get_instance()

    # Override settings if specified
    original_ttl = cache.ttl
    original_threshold = cache.similarity_threshold

    if ttl is not None:
        cache.ttl = ttl
    if similarity_threshold is not None:
        cache.similarity_threshold = similarity_threshold

    try:
        # Try to get from cache
        cached_result = cache.get(prompt_data)
        if cached_result is not None:
            return cached_result

        # Cache miss, make actual LLM call
        if hasattr(llm_client, "generate"):
            # Typical interface for many LLM clients
            response = llm_client.generate(**prompt_data)
        elif hasattr(llm_client, "__call__"):
            # Some clients are callable
            response = llm_client(prompt_data)
        else:
            # Try a few common method names
            for method_name in ["complete", "create_completion", "chat_completion", "completion"]:
                if hasattr(llm_client, method_name):
                    method = getattr(llm_client, method_name)
                    if callable(method):
                        response = method(**prompt_data)
                        break
            else:
                raise AttributeError("Could not find a suitable method on the LLM client")

        # Store in cache
        cache.set(prompt_data, response)

        return response
    finally:
        # Restore original settings
        if ttl is not None:
            cache.ttl = original_ttl
        if similarity_threshold is not None:
            cache.similarity_threshold = original_threshold


# Helper function for async usage (if needed in the future)
async def cached_llm_call_async(
    llm_client: Any,
    prompt_data: Dict[str, Any],
    ttl: Optional[int] = None,
    similarity_threshold: Optional[float] = None
) -> Any:
    """
    Make an async LLM call with semantic caching.

    Args:
        llm_client: The LLM client object
        prompt_data: Dictionary containing prompt data
        ttl: Optional TTL override for this specific call
        similarity_threshold: Optional similarity threshold override for this call

    Returns:
        The LLM response (from cache or fresh)
    """
    import asyncio

    # Get or initialize the cache
    cache = SemanticCache.get_instance()

    # Override settings if specified
    original_ttl = cache.ttl
    original_threshold = cache.similarity_threshold

    if ttl is not None:
        cache.ttl = ttl
    if similarity_threshold is not None:
        cache.similarity_threshold = similarity_threshold

    try:
        # Try to get from cache
        cached_result = cache.get(prompt_data)
        if cached_result is not None:
            return cached_result

        # Cache miss, make actual LLM call
        if hasattr(llm_client, "generate_async"):
            response = await llm_client.generate_async(**prompt_data)
        elif hasattr(llm_client, "acreate") or hasattr(llm_client, "acreate_completion"):
            method = getattr(llm_client, "acreate", None) or getattr(llm_client, "acreate_completion")
            response = await method(**prompt_data)
        else:
            # Fall back to running the sync version in a thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: cached_llm_call(llm_client, prompt_data, None, None)
            )

        # Store in cache
        cache.set(prompt_data, response)

        return response
    finally:
        # Restore original settings
        if ttl is not None:
            cache.ttl = original_ttl
        if similarity_threshold is not None:
            cache.similarity_threshold = original_threshold
