import os
import hashlib
import faiss
import json
import numpy as np
import logging
import shutil
import time  # Adding missing import for time functions
import gzip  # Adding import for gzip compression
import textwrap  # Adding import for text formatting
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

CACHE_DIR_NAME = ".cache"
FAISS_INDEX_FILE = "vector_store.v1.faiss"
METADATA_FILE = "vector_metadata.v1.json"

class EmbeddingClient:
    """Client for managing embeddings using FAISS with enhanced embedding management."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, router_agent=None):
        """Initialize the FAISS index and metadata mapping."""
        # Allow no config to use defaults
        config = config or {}
        self.dim = config.get('embedding_dim', 768)
        self.store_path_base = Path(config.get("workspace_path", ".")).resolve() / CACHE_DIR_NAME
        self.index_path = self.store_path_base / FAISS_INDEX_FILE
        self.metadata_path = self.store_path_base / METADATA_FILE
        self.top_k = config.get('top_k_retrieval', 5)
        
        # Cache configuration
        self.cache_enabled = config.get('embedding_cache_enabled', True)
        self.cache_ttl_seconds = config.get('embedding_cache_ttl_seconds', 3600 * 24 * 7)  # Default 7 days
        
        # Progressive eviction strategy configuration
        self.max_embeddings = config.get('max_embeddings', 10000)  # Max number of embeddings to keep
        self.eviction_threshold = config.get('eviction_threshold', 0.8)  # Trigger eviction at 80% capacity
        self.eviction_batch_size = config.get('eviction_batch_size', 100)  # Number to evict at once
        self.min_access_keep = config.get('min_access_keep', 2)  # Minimum access count to avoid eviction
        self.max_idle_time = config.get('max_idle_time_seconds', 3600 * 24 * 30)  # Default 30 days
        
        # Router agent for specialized LLM roles
        self.router_agent = router_agent

        self.store_path_base.mkdir(exist_ok=True)

        self.index: Optional[faiss.Index] = None
        self.id_map: Dict[int, Dict[str, Any]] = {}
        self.next_id = 0

        self._load_state()

        if self.index is None:
            logger.info("Initializing new FAISS index.")
            self.index = faiss.IndexIDMap(faiss.IndexFlatIP(self.dim))
            self.id_map = {}
            self.next_id = 0

    def _load_state(self):
        """Load the FAISS index and metadata map from disk."""
        if self.index_path.exists():
            try:
                # Load FAISS index with memory-mapped file for large datasets
                self.index = faiss.read_index(str(self.index_path), faiss.IO_FLAG_MMAP)
                logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors from {self.index_path}")
            except Exception as e:
                logger.error(f"Error memory-mapping FAISS index from {self.index_path}: {e}. Falling back to load.")
                try:
                    self.index = faiss.read_index(str(self.index_path))
                except Exception as e2:
                    logger.error(f"Error loading FAISS index from {self.index_path}: {e2}. Will create a new index.")
                
        if self.metadata_path.exists():
            try:
                # Auto-detect gzip for metadata
                with open(self.metadata_path, 'rb') as mf:
                    sig = mf.read(2)
                if sig == b"\x1f\x8b":
                    meta_open = gzip.open; mode = 'rt'
                else:
                    meta_open = open;   mode = 'r'
                with meta_open(self.metadata_path, mode, encoding='utf-8') as f:
                    metadata_state = json.load(f)
                # Integrity check if checksum provided
                checksum = metadata_state.get("checksum")
                if checksum:
                    id_map_json = json.dumps(metadata_state.get('id_map', {}), sort_keys=True).encode('utf-8')
                    if hashlib.md5(id_map_json).hexdigest() != checksum:
                        raise ValueError("Metadata checksum mismatch, resetting metadata.")
                self.id_map = metadata_state.get('id_map', {})
                self.next_id = metadata_state.get('next_id', 0)
                if self.id_map:
                    logger.info(f"Loaded metadata for {len(self.id_map)} vectors from {self.metadata_path}")
                    # Update access timestamps for eviction strategy
                    current_time = time.time()
                    for key, meta in self.id_map.items():
                        if "last_access" not in meta:
                            meta["last_access"] = current_time
                        if "access_count" not in meta:
                            meta["access_count"] = 1
            except Exception as e:
                logger.error(f"Error loading metadata from {self.metadata_path}: {e}. Will create new metadata.")
                self.id_map = {}
                
    def _save_state(self):
        """Save the FAISS index and metadata map to disk atomically."""
        if self.index is None:
            logger.error("Cannot save state: FAISS index is not initialized.")
            return

        self.store_path_base.mkdir(exist_ok=True)

        # Snapshot existing index and metadata before saving
        archive_dir = self.store_path_base / "snapshots"
        archive_dir.mkdir(exist_ok=True)
        timestamp = int(time.time())
        # Archive current files
        if self.index_path.exists():
            shutil.copy(self.index_path, archive_dir / f"{FAISS_INDEX_FILE}.{timestamp}")
        if self.metadata_path.exists():
            shutil.copy(self.metadata_path, archive_dir / f"{METADATA_FILE}.{timestamp}")

        try:
            # Save FAISS index atomically
            temp_index_path = self.index_path.with_suffix(self.index_path.suffix + ".tmp")
            faiss.write_index(self.index, str(temp_index_path))
            shutil.move(str(temp_index_path), str(self.index_path))
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors to {self.index_path}")
        except Exception as e:
            logger.error(f"Error saving FAISS index to {self.index_path}: {e}")

        try:
            # Save metadata atomically with gzip compression
            metadata_state = {
                'next_id': self.next_id,
                'id_map': {str(k): v for k, v in self.id_map.items()},
                'checksum': hashlib.md5(json.dumps({str(k): v for k, v in self.id_map.items()}, sort_keys=True).encode('utf-8')).hexdigest()
            }
            temp_metadata_path = self.metadata_path.with_suffix(self.metadata_path.suffix + ".tmp")
            with gzip.open(temp_metadata_path, 'wt', encoding='utf-8') as f:
                json.dump(metadata_state, f, indent=2)
            shutil.move(str(temp_metadata_path), str(self.metadata_path))
            logger.info(f"Saved metadata map with {len(self.id_map)} entries to {self.metadata_path}")
        except (OSError, TypeError) as e:
            logger.error(f"Error saving metadata map to {self.metadata_path}: {e}")

    def evict_embeddings(self, eviction_count=None):
        """
        Evict embeddings using the progressive embedding eviction strategy.
        
        Args:
            eviction_count: Number of embeddings to evict. If None, uses configured batch size.
            
        Returns:
            Number of embeddings evicted
        """
        if not self.cache_enabled:
            logger.info("Cache is disabled. No eviction performed.")
            return 0
            
        if not self.index or self.index.ntotal == 0:
            logger.debug("No embeddings to evict.")
            return 0
            
        if eviction_count is None:
            eviction_count = self.eviction_batch_size
            
        # If we're not above the threshold, no need to evict
        if self.index.ntotal <= self.max_embeddings * self.eviction_threshold:
            logger.debug(f"Index size ({self.index.ntotal}) below threshold. No eviction needed.")
            return 0
            
        logger.info(f"Starting embedding eviction. Current size: {self.index.ntotal}, target eviction: {eviction_count}")
        
        # Scoring factors for eviction
        current_time = time.time()
        candidates = []
        
        # Calculate eviction scores for each embedding
        for id_str, metadata in self.id_map.items():
            id_int = int(id_str)  # Convert string key back to int
            
            # Skip protected embeddings with high access counts
            if metadata.get("access_count", 0) > self.min_access_keep:
                continue
                
            # Calculate idle time factor (0-1), higher means more idle
            last_access = metadata.get("last_access", 0)
            idle_time = current_time - last_access
            idle_factor = min(1.0, idle_time / self.max_idle_time) if self.max_idle_time > 0 else 0.5
            
            # Access count factor (0-1), lower means less accessed
            access_count = metadata.get("access_count", 0)
            access_factor = 1.0 / (access_count + 1)  # +1 to avoid division by zero
            
            # Age factor (newer embeddings get some protection)
            age = current_time - metadata.get("timestamp", 0)
            age_factor = min(1.0, age / (self.max_idle_time / 2)) if self.max_idle_time > 0 else 0.5
            
            # Combine factors (higher score means more likely to be evicted)
            # We weight idle time the most, then access count, then age
            eviction_score = (0.6 * idle_factor) + (0.3 * access_factor) + (0.1 * age_factor)
            
            candidates.append((id_int, eviction_score))
            
        if not candidates:
            logger.info("No candidates for eviction found.")
            return 0
            
        # Sort by eviction score (descending)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Take only as many as we need to evict
        to_evict = candidates[:min(eviction_count, len(candidates))]
        
        if not to_evict:
            return 0
            
        # Collect IDs to evict
        evict_ids = np.array([id_int for id_int, _ in to_evict])
        
        try:
            # Remove from FAISS index
            self.index.remove_ids(evict_ids)
            
            # Remove from metadata
            for id_int, _ in to_evict:
                if str(id_int) in self.id_map:
                    del self.id_map[str(id_int)]
                    
            # Save state after eviction
            self._save_state()
            
            logger.info(f"Successfully evicted {len(evict_ids)} embeddings.")
            return len(evict_ids)
            
        except Exception as e:
            logger.error(f"Error during embedding eviction: {e}")
            return 0

    def update_access_patterns(self, file_paths: List[str]):
        """
        Update access patterns for the provided file paths to inform progressive eviction strategy.
        
        Args:
            file_paths: List of file paths that were accessed in the current operation
        """
        if not self.cache_enabled or not self.id_map:
            return
            
        current_time = time.time()
        updated_ids = set()
        
        # Update metadata for all embeddings matching these file paths
        for id_str, metadata in self.id_map.items():
            path = metadata.get("file_path")
            if path and path in file_paths:
                # Update access count and timestamp
                metadata["access_count"] = metadata.get("access_count", 0) + 1
                metadata["last_access"] = current_time
                updated_ids.add(id_str)
                
        # If we updated any metadata entries, save the state
        if updated_ids:
            logger.debug(f"Updated access patterns for {len(updated_ids)} embedding entries")
            self._save_state()

    def add_embedding(self, embedding: np.ndarray, metadata: Dict[str, Any]) -> None:
        """
        Add one or more embeddings to the FAISS index with associated metadata.
        """
        # Handle batch or single embedding
        vectors = embedding if hasattr(embedding, 'ndim') and embedding.ndim == 2 else embedding.reshape(1, -1)
        num = vectors.shape[0]
        ids = np.arange(self.next_id, self.next_id + num, dtype='int64')
        # Add to FAISS index
        self.index.add_with_ids(vectors, ids)
        now = time.time()
        # Store metadata entries
        for idx, vec_id in enumerate(ids):
            entry = (metadata.copy() if num == 1 else metadata[idx].copy())
            # Preserve provided metadata fields if present
            if 'timestamp' not in entry:
                entry['timestamp'] = now
            if 'last_access' not in entry:
                entry['last_access'] = now
            if 'access_count' not in entry:
                entry['access_count'] = 0
            self.id_map[str(int(vec_id))] = entry
        self.next_id += num
        # Persist state
        self._save_state()

    def add_embeddings(self, embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        """
        Add a batch of embeddings in one operation to reduce API calls.
        
        This is the primary method called by memory_manager.py.
        
        Args:
            embeddings: NumPy array of embeddings, shape (n, dim)
            metadatas: List of metadata dictionaries, one per embedding
            
        Raises:
            TypeError: If metadatas is not a list
        """
        if not isinstance(metadatas, list):
            raise TypeError("metadatas must be a list of dictionaries")
        
        self.add_embedding(embeddings, metadatas)
        
    def add_embeddings_batch(self, embeddings: np.ndarray, metadatas: List[Dict[str, Any]]) -> None:
        """
        Add a batch of embeddings in one operation to reduce API calls.
        
        Note: This is an alias for add_embeddings for backward compatibility.
        """
        self.add_embeddings(embeddings, metadatas)

    async def add_embedding_async(self, embedding: np.ndarray, metadata: Dict[str, Any]) -> None:
        """
        Asynchronously add embeddings to avoid blocking operations.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.add_embedding, embedding, metadata)

    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Generate an embedding for the given text using the specialized 'embedder' role if available.
        
        Args:
            text: The text to generate an embedding for
            
        Returns:
            A numpy array containing the embedding vector, or None if generation failed
        """
        start_time = time.time()
        
        # Truncate long texts to prevent context window issues
        max_text_length = 8000  # Set a reasonable limit that most models can handle
        if len(text) > max_text_length:
            logger.warning(f"Text too long ({len(text)} chars), truncating to {max_text_length} chars")
            text = text[:max_text_length]
        
        # Use specialized embedder role if router agent is available
        if self.router_agent and hasattr(self.router_agent, 'call_llm_by_role'):
            try:
                # System prompt for embedding generation
                system_prompt = "You are an embedding generator. Return ONLY a JSON object with a single key 'embedding' containing an array of floating-point numbers representing the semantic embedding of the provided text."
                
                # User prompt for embedding generation
                user_prompt = textwrap.dedent(f"""
                    Generate a semantic vector embedding for the following text.
                    The embedding should capture the core concepts, entities, relationships, and semantics of the text.
                    Return ONLY a JSON object with the key 'embedding' containing an array of {self.dim} floating-point numbers.
                    Do not include any explanations, just the JSON object.
                    
                    TEXT TO EMBED:
                    {text}
                """).strip()
                
                # Get configuration from the router agent if available
                config = getattr(self.router_agent, 'config', {})
                
                # Create a simple logger if scratchpad not available
                class SimpleLogger:
                    def log(self, source, message, level="info"):
                        log_func = getattr(logger, level.lower(), logger.info)
                        log_func(f"[{source}] {message}")
                
                scratchpad = SimpleLogger()
                
                # Call the specialized 'embedder' role with exponential backoff retry
                max_retries = 3
                retry_delay = 1.0
                                
                for attempt in range(max_retries):
                    try:
                        embedding_json = self.router_agent.call_llm_by_role(
                            role="embedder",  # Use the specialized embedder role
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            config=config,
                            scratchpad=scratchpad,
                            fallback_role="default",  # Fall back to default role if embedder not available
                            temperature=0.1,  # Low temperature for deterministic outputs
                            response_format={"type": "json_object"}  # Request JSON format
                        )
                        
                        # Break the retry loop if successful
                        if embedding_json:
                            break
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.warning(f"Embedding generation attempt {attempt+1} failed: {e}. Retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error(f"All embedding generation attempts failed. Last error: {e}")
                            raise
                
                if embedding_json:
                    try:
                        # Parse the JSON response
                        embedding_data = json.loads(embedding_json)
                        if isinstance(embedding_data, dict) and "embedding" in embedding_data:
                            # Extract the embedding array
                            embedding_array = embedding_data["embedding"]
                            if isinstance(embedding_array, list) and len(embedding_array) > 0:
                                # Convert to numpy array and normalize
                                embedding = np.array(embedding_array, dtype=np.float32)
                                # Ensure proper dimensionality
                                if embedding.shape[0] != self.dim:
                                    logger.warning(
                                        f"Embedding dimension mismatch: got {embedding.shape[0]}, "
                                        f"expected {self.dim}. Adjusting..."
                                    )
                                    # Handle dimension mismatch using more robust methods
                                    if embedding.shape[0] < self.dim:
                                        # Use linear interpolation to upscale embedding
                                        # This is better than padding with zeros which can distort similarity
                                        indices = np.round(np.linspace(0, embedding.shape[0] - 1, self.dim)).astype(int)
                                        embedding = embedding[indices]
                                    else:
                                        # If embedding is too large, use dimensionality reduction
                                        # Simple approach: use evenly spaced values
                                        indices = np.round(np.linspace(0, embedding.shape[0] - 1, self.dim)).astype(int)
                                        embedding = embedding[indices]
                                
                                # Normalize the vector
                                norm = np.linalg.norm(embedding)
                                if norm > 0:
                                    embedding = embedding / norm
                                
                                duration = time.time() - start_time
                                logger.info(f"Successfully generated embedding using 'embedder' role in {duration:.2f}s")
                                
                                # Record metrics if available
                                if hasattr(self, '_metrics') and hasattr(self._metrics, 'record_embedding'):
                                    self._metrics.record_embedding(
                                        success=True,
                                        duration=duration,
                                        text_length=len(text),
                                        specialized_role=True
                                    )
                                
                                return embedding
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse embedding from 'embedder' role response: {e}")
                
                logger.warning("'embedder' role did not return a valid embedding, falling back to default method")
            except Exception as e:
                logger.warning(f"Failed to use specialized embedder role: {e}. Falling back to default embedding method.")
        
        # Fall back to default embedding method
        try:
            # If an alternative embedding method is available, use it here
            # For example, using OpenAI embeddings API directly
            from agent_s3 import config as app_config
            from agent_s3.llm_utils import get_embedding
            
            # Get embedding using the default method
            embedding = get_embedding(text)
            
            if embedding is not None:
                duration = time.time() - start_time
                logger.info(f"Generated embedding using fallback method in {duration:.2f}s")
                
                # Record metrics if available
                if hasattr(self, '_metrics') and hasattr(self._metrics, 'record_embedding'):
                    self._metrics.record_embedding(
                        success=True,
                        duration=duration,
                        text_length=len(text),
                        specialized_role=False
                    )
                
                return embedding
        except ImportError:
            logger.error("Fallback embedding method (get_embedding) not available")
        except Exception as e:
            logger.error(f"Fallback embedding generation failed: {e}")
        
        # If all methods failed
        logger.error("All embedding generation methods failed")
        
        # Record metrics if available
        if hasattr(self, '_metrics') and hasattr(self._metrics, 'record_embedding'):
            self._metrics.record_embedding(
                success=False,
                duration=time.time() - start_time,
                text_length=len(text),
                specialized_role=False
            )
            
        return None