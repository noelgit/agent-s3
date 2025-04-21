import os
import faiss
import json
import numpy as np
from pathlib import Path
from typing import List, Any
import time
from shutil import copyfile

class EmbeddingClient:
    """
    EmbeddingClient for FAISS vector store management.

    - Chunking strategies
    - Incremental indexing
    - Eviction policies
    - Top-K retrieval
    """
    def __init__(self, store_path: str = "./data/vector_store.faiss", dim: int = 384, top_k: int = 5, eviction_threshold: float = 0.90):
        self.store_path = store_path
        self.dim = dim
        self.top_k = top_k
        self.eviction_threshold = eviction_threshold

        # Auto-backup threshold for embeddings
        self.shard_threshold = int(os.environ.get('VECTOR_SHARD_THRESHOLD', '10000'))

        # Ensure directory exists
        Path(self.store_path).parent.mkdir(parents=True, exist_ok=True)

        # Load or initialize FAISS index and metadata
        if os.path.exists(self.store_path):
            self.index = faiss.read_index(self.store_path)
            self.id_map = self._load_metadata()
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            self.id_map = []  # maps index positions to metadata

    def _load_metadata(self) -> List[Any]:
        meta_path = self.store_path + ".meta"
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                return json.load(f)
        return []

    def _save_metadata(self) -> None:
        meta_path = self.store_path + ".meta"
        with open(meta_path, 'w') as f:
            json.dump(self.id_map, f)

    def add_embeddings(self, embeddings: np.ndarray, metadata: List[Any]) -> None:
        """Incrementally add embeddings and metadata with auto-backup support."""
        # Add to index
        self.index.add(embeddings)
        # Append metadata
        self.id_map.extend(metadata)
        # Persist
        faiss.write_index(self.index, self.store_path)
        self._save_metadata()

        # After persisting, backup if too many embeddings
        try:
            total = self.index.ntotal
            if total >= self.shard_threshold:
                timestamp = int(time.time())
                backup_path = f"{self.store_path}.bak.{timestamp}"
                copyfile(self.store_path, backup_path)
                print(f"Embedding index backed up to {backup_path}")
                # Increase threshold to avoid repeated backups
                self.shard_threshold = total * 2
        except Exception as e:
            print(f"Error during embedding backup: {e}")

    def query(self, query_embedding: np.ndarray, top_k: int = None) -> List[Any]:
        """Retrieve top_k metadata for the query."""
        k = top_k or self.top_k
        # Normalize query for IP
        faiss.normalize_L2(query_embedding)
        distances, indices = self.index.search(query_embedding, k)
        results = []
        for idx in indices[0]:
            if idx < len(self.id_map):
                results.append(self.id_map[idx])
        return results

    def evict_low_similarity(self):
        """Evict embeddings below a similarity threshold."""
        # Compute norms or recency; simplified: drop oldest when size>threshold
        current_size = self.index.ntotal
        if current_size > 0 and current_size > (1/self.eviction_threshold):
            # Remove oldest embedding: not directly supported by FAISS flat
            # Simplest: rebuild without oldest
            keep = int(current_size * self.eviction_threshold)
            embeddings = self.index.reconstruct_n(0, current_size)
            metadata = self.id_map
            # Keep most recent embeddings
            keep_emb = embeddings[-keep:]
            keep_meta = metadata[-keep:]
            self.index = faiss.IndexFlatIP(self.dim)
            self.index.add(np.array(keep_emb))
            self.id_map = keep_meta
            faiss.write_index(self.index, self.store_path)
            self._save_metadata()