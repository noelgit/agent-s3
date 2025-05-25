"""
Index Partition Manager for Agent-S3.

This module implements partitioning strategies for the code search index,
enabling more efficient and scalable incremental updates.
"""

import os
import time
import json
import logging
import shutil
from typing import Dict, List, Set, Optional, Any
import hashlib

logger = logging.getLogger(__name__)

# Import numpy if available for vector operations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy not available. Using fallback for vector operations.")

class IndexPartition:
    """
    Represents a single partition of the code search index.

    A partition contains a subset of the embeddings and metadata for files
    that match certain criteria (language, directory, etc.).
    """

    def __init__(
        self,
        partition_id: str,
        storage_path: str,
        criteria: Dict[str, Any]
    ):
        """
        Initialize an index partition.

        Args:
            partition_id: Unique identifier for this partition
            storage_path: Path to store partition data
            criteria: Criteria that defines what goes in this partition
        """
        self.partition_id = partition_id
        self.storage_path = os.path.join(storage_path, f"partition_{partition_id}")
        self.criteria = criteria

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        # File data
        self.file_embeddings: Dict[str, List[float]] = {}
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

        # Partition metadata
        self.metadata = {
            "id": partition_id,
            "criteria": criteria,
            "created": time.time(),
            "last_updated": time.time(),
            "file_count": 0,
            "version": 1
        }

        # Load existing data if available
        self._load_data()

    def _load_data(self) -> None:
        """Load partition data from disk."""
        # Load metadata
        metadata_path = os.path.join(self.storage_path, "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.error("Error loading partition metadata: %s", e)

        # Load file metadata
        file_metadata_path = os.path.join(self.storage_path, "file_metadata.json")
        if os.path.exists(file_metadata_path):
            try:
                with open(file_metadata_path, 'r') as f:
                    self.file_metadata = json.load(f)
            except Exception as e:
                logger.error("Error loading file metadata: %s", e)

        # Load embeddings
        embeddings_path = os.path.join(self.storage_path, "embeddings.json")
        if os.path.exists(embeddings_path):
            try:
                with open(embeddings_path, 'r') as f:
                    self.file_embeddings = json.load(f)
                # Convert string keys to actual file paths if they were stored with an encoding
                if self.file_embeddings:
                    # Check if keys are encoded (e.g., have a special prefix)
                    key_sample = next(iter(self.file_embeddings.keys()))
                    if key_sample.startswith("path:"):
                        decoded_embeddings = {}
                        for k, v in self.file_embeddings.items():
                            real_path = k.replace("path:", "", 1)
                            decoded_embeddings[real_path] = v
                        self.file_embeddings = decoded_embeddings
            except Exception as e:
                logger.error("Error loading file embeddings: %s", e)

    def _save_data(self) -> None:
        """Save partition data to disk."""
        try:
            # Update metadata
            self.metadata["last_updated"] = time.time()
            self.metadata["file_count"] = len(self.file_metadata)
            self.metadata["version"] += 1

            # Save metadata (atomic)
            metadata_path = os.path.join(self.storage_path, "metadata.json")
            temp_path = metadata_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.metadata, f)
            os.replace(temp_path, metadata_path)

            # Save file metadata (atomic)
            file_metadata_path = os.path.join(self.storage_path, "file_metadata.json")
            temp_path = file_metadata_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.file_metadata, f)
            os.replace(temp_path, file_metadata_path)

            # Save embeddings (atomic)
            embeddings_path = os.path.join(self.storage_path, "embeddings.json")
            temp_path = embeddings_path + ".tmp"
            # Encode file paths as keys to avoid issues with special characters
            encoded_embeddings = {}
            for k, v in self.file_embeddings.items():
                encoded_key = f"path:{k}"
                encoded_embeddings[encoded_key] = v
            with open(temp_path, 'w') as f:
                json.dump(encoded_embeddings, f)
            os.replace(temp_path, embeddings_path)

            logger.debug("Saved partition %s with %d files", self.partition_id, len(self.file_metadata))
        except Exception as e:
            logger.error("Error saving partition data: %s", e)

    def add_file(
        self,
        file_path: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add a file to this partition.

        Args:
            file_path: Path to the file
            embedding: Embedding vector for the file
            metadata: Additional metadata about the file

        Returns:
            True if file was added, False otherwise
        """
        # Check if file matches partition criteria
        if not self._file_matches_criteria(file_path, metadata):
            return False

        try:
            # Add file data
            self.file_embeddings[file_path] = embedding
            self.file_metadata[file_path] = metadata

            return True
        except Exception as e:
            logger.error("Error adding file to partition: %s", e)
            return False

    def remove_file(self, file_path: str) -> bool:
        """
        Remove a file from this partition.

        Args:
            file_path: Path to the file

        Returns:
            True if file was removed, False otherwise
        """
        try:
            # Check if file exists in this partition
            if file_path not in self.file_metadata:
                return False

            # Remove file data
            if file_path in self.file_embeddings:
                del self.file_embeddings[file_path]
            del self.file_metadata[file_path]

            return True
        except Exception as e:
            logger.error("Error removing file from partition: %s", e)
            return False

    def update_file(
        self,
        file_path: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Update a file in this partition.

        Args:
            file_path: Path to the file
            embedding: Embedding vector for the file
            metadata: Additional metadata about the file

        Returns:
            True if file was updated, False otherwise
        """
        # If file doesn't match criteria anymore, remove it
        if not self._file_matches_criteria(file_path, metadata):
            if file_path in self.file_metadata:
                return self.remove_file(file_path)
            return False

        # Otherwise update it
        try:
            self.file_embeddings[file_path] = embedding
            self.file_metadata[file_path] = metadata
            return True
        except Exception as e:
            logger.error("Error updating file in partition: %s", e)
            return False

    def contains_file(self, file_path: str) -> bool:
        """
        Check if this partition contains a file.

        Args:
            file_path: Path to the file

        Returns:
            True if file is in this partition, False otherwise
        """
        return file_path in self.file_metadata

    def get_file_count(self) -> int:
        """
        Get the number of files in this partition.

        Returns:
            Number of files
        """
        return len(self.file_metadata)

    def get_all_files(self) -> List[str]:
        """
        Get all file paths in this partition.

        Returns:
            List of file paths
        """
        return list(self.file_metadata.keys())

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search this partition for files similar to the query embedding.

        Args:
            query_embedding: Embedding vector for the query
            top_k: Maximum number of results to return

        Returns:
            List of result dictionaries with file path, score, and metadata
        """
        if not self.file_embeddings:
            return []

        try:
            # Calculate similarities
            similarities = []

            if NUMPY_AVAILABLE:
                # Vectorized calculation with numpy
                query_vec = np.array(query_embedding)

                for file_path, embedding in self.file_embeddings.items():
                    file_vec = np.array(embedding)

                    # Calculate cosine similarity
                    similarity = np.dot(query_vec, file_vec) / (
                        np.linalg.norm(query_vec) * np.linalg.norm(file_vec)
                    )

                    similarities.append((file_path, float(similarity)))
            else:
                # Fallback for when numpy is not available
                for file_path, embedding in self.file_embeddings.items():
                    # Calculate dot product
                    dot_product = sum(q * f for q, f in zip(query_embedding, embedding))

                    # Calculate magnitudes
                    query_mag = sum(q * q for q in query_embedding) ** 0.5
                    file_mag = sum(f * f for f in embedding) ** 0.5

                    # Calculate cosine similarity
                    if query_mag > 0 and file_mag > 0:
                        similarity = dot_product / (query_mag * file_mag)
                    else:
                        similarity = 0.0

                    similarities.append((file_path, similarity))

            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Get top-k results
            top_results = similarities[:top_k]

            # Format results
            results = []
            for file_path, score in top_results:
                results.append({
                    'file_path': file_path,
                    'score': score,
                    'metadata': self.file_metadata.get(file_path, {})
                })

            return results
        except Exception as e:
            logger.error("Error searching partition: %s", e)
            return []

    def _file_matches_criteria(self, file_path: str, metadata: Dict[str, Any]) -> bool:
        """
        Check if a file matches the criteria for this partition.

        Args:
            file_path: Path to the file
            metadata: Additional metadata about the file

        Returns:
            True if file matches, False otherwise
        """
        if not self.criteria:
            return True  # No criteria means everything matches

        # Check language criteria
        if 'language' in self.criteria and metadata.get('language') != self.criteria['language']:
            return False

        # Check directory criteria
        if 'directory' in self.criteria:
            target_dir = self.criteria['directory']
            file_dir = os.path.dirname(file_path)

            if not file_dir.startswith(target_dir):
                return False

        # Check file extension criteria
        if 'extensions' in self.criteria:
            valid_extensions = self.criteria['extensions']
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext not in valid_extensions:
                return False

        # All criteria passed
        return True

    def commit(self) -> bool:
        """
        Save partition data to disk.

        Returns:
            True if successful, False otherwise
        """
        try:
            self._save_data()
            return True
        except Exception as e:
            logger.error("Error committing partition data: %s", e)
            return False


class IndexPartitionManager:
    """
    Manages partitioned indexes for code search.

    This class handles the creation, maintenance, and querying of
    index partitions to enable efficient incremental updates.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the index partition manager.

        Args:
            storage_path: Path to store partition data (defaults to ~/.agent_s3/index)
        """
        self.storage_path = storage_path
        if not self.storage_path:
            # Default to a hidden directory in the user's home
            home = os.path.expanduser("~")
            self.storage_path = os.path.join(home, ".agent_s3", "index")

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        # Partitions
        self.partitions: Dict[str, IndexPartition] = {}

        # File to partition mapping (for fast lookup)
        self.file_to_partition: Dict[str, str] = {}

        # Manager metadata
        self.metadata = {
            "created": time.time(),
            "last_updated": time.time(),
            "partition_count": 0,
            "total_files": 0,
            "version": 1
        }

        # Load existing partitions
        self._load_partitions()

    def _load_partitions(self) -> None:
        """Load existing partitions from disk."""
        # Load manager metadata
        metadata_path = os.path.join(self.storage_path, "manager_metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            except Exception as e:
                logger.error("Error loading partition manager metadata: %s", e)

        # Find partition directories
        try:
            for item in os.listdir(self.storage_path):
                if item.startswith("partition_"):
                    partition_dir = os.path.join(self.storage_path, item)

                    if os.path.isdir(partition_dir):
                        # Extract partition ID from directory name
                        partition_id = item.replace("partition_", "", 1)

                        # Load partition metadata to get criteria
                        partition_metadata_path = os.path.join(partition_dir, "metadata.json")
                        if os.path.exists(partition_metadata_path):
                            try:
                                with open(partition_metadata_path, 'r') as f:
                                    partition_metadata = json.load(f)

                                # Create partition object
                                criteria = partition_metadata.get("criteria", {})
                                partition = IndexPartition(
                                    partition_id=partition_id,
                                    storage_path=self.storage_path,
                                    criteria=criteria
                                )

                                # Add to partitions dictionary
                                self.partitions[partition_id] = partition

                                # Update file-to-partition mapping
                                for file_path in partition.get_all_files():
                                    self.file_to_partition[file_path] = partition_id
                            except Exception as e:
                                logger.error("Error loading partition %s: %s", partition_id, e)

            logger.info(f"Loaded {len(self.partitions)} partitions with "
                        f"{sum(p.get_file_count() for p in self.partitions.values())} files")
        except Exception as e:
            logger.error("Error loading partitions: %s", e)

    def _save_metadata(self) -> None:
        """Save manager metadata to disk."""
        try:
            # Update metadata
            self.metadata["last_updated"] = time.time()
            self.metadata["partition_count"] = len(self.partitions)
            self.metadata["total_files"] = sum(p.get_file_count() for p in self.partitions.values())
            self.metadata["version"] += 1

            # Save metadata (atomic)
            metadata_path = os.path.join(self.storage_path, "manager_metadata.json")
            temp_path = metadata_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(self.metadata, f)
            os.replace(temp_path, metadata_path)
        except Exception as e:
            logger.error("Error saving partition manager metadata: %s", e)

    def create_partition(
        self,
        criteria: Dict[str, Any],
        partition_id: Optional[str] = None
    ) -> str:
        """
        Create a new index partition.

        Args:
            criteria: Criteria for what files go in this partition
            partition_id: Optional ID for the partition (generated if not provided)

        Returns:
            ID of the created partition
        """
        # Generate ID if not provided
        if not partition_id:
            # Create a hash of the criteria for the ID
            criteria_str = json.dumps(criteria, sort_keys=True)
            criteria_hash = hashlib.sha256(criteria_str.encode()).hexdigest()[:8]
            partition_id = f"{criteria_hash}_{int(time.time())}"

        try:
            # Check if partition with same ID already exists
            if partition_id in self.partitions:
                return partition_id  # Return existing partition

            # Create new partition
            partition = IndexPartition(
                partition_id=partition_id,
                storage_path=self.storage_path,
                criteria=criteria
            )

            # Add to partitions dictionary
            self.partitions[partition_id] = partition

            # Save metadata
            self._save_metadata()

            logger.info("Created new partition: %s", partition_id)
            return partition_id
        except Exception as e:
            logger.error("Error creating partition: %s", e)
            return ""

    def get_partition_for_file(
        self,
        file_path: str,
        metadata: Dict[str, Any]
    ) -> Optional[IndexPartition]:
        """
        Find the appropriate partition for a file.

        Args:
            file_path: Path to the file
            metadata: File metadata used for partition matching

        Returns:
            Matching partition or None if no match found
        """
        # Check if file is already in a partition
        if file_path in self.file_to_partition:
            partition_id = self.file_to_partition[file_path]
            if partition_id in self.partitions:
                return self.partitions[partition_id]

        # Find a matching partition based on criteria
        for partition in self.partitions.values():
            if partition._file_matches_criteria(file_path, metadata):
                return partition

        return None

    def add_or_update_file(
        self,
        file_path: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add or update a file in the appropriate partition.

        Args:
            file_path: Path to the file
            embedding: Embedding vector for the file
            metadata: Additional metadata about the file

        Returns:
            True if file was added/updated, False otherwise
        """
        try:
            # Get appropriate partition
            partition = self.get_partition_for_file(file_path, metadata)

            # If no matching partition, create a default one
            if not partition:
                # Create a language-based partition
                language = metadata.get('language', 'unknown')
                criteria = {'language': language}
                partition_id = self.create_partition(criteria)

                if not partition_id:
                    return False

                partition = self.partitions[partition_id]

            # Check if file is in a different partition
            if file_path in self.file_to_partition:
                current_partition_id = self.file_to_partition[file_path]

                if current_partition_id != partition.partition_id:
                    # Remove from old partition
                    if current_partition_id in self.partitions:
                        old_partition = self.partitions[current_partition_id]
                        old_partition.remove_file(file_path)
                        old_partition.commit()

            # Add/update file in the partition
            result = partition.update_file(file_path, embedding, metadata)

            # Update mapping
            if result:
                self.file_to_partition[file_path] = partition.partition_id
                partition.commit()

            return result
        except Exception as e:
            logger.error("Error adding/updating file: %s", e)
            return False

    def remove_file(self, file_path: str) -> bool:
        """
        Remove a file from its partition.

        Args:
            file_path: Path to the file

        Returns:
            True if file was removed, False otherwise
        """
        try:
            # Check if file is in a partition
            if file_path not in self.file_to_partition:
                return False

            partition_id = self.file_to_partition[file_path]

            if partition_id not in self.partitions:
                # Clean up mapping
                del self.file_to_partition[file_path]
                return False

            # Get partition
            partition = self.partitions[partition_id]

            # Remove file
            result = partition.remove_file(file_path)

            # Update mapping
            if result:
                del self.file_to_partition[file_path]
                partition.commit()

            return result
        except Exception as e:
            logger.error("Error removing file: %s", e)
            return False

    def search_all_partitions(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        partition_ids: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across all partitions (or specified ones).

        Args:
            query_embedding: Embedding vector for the query
            top_k: Maximum number of results to return
            partition_ids: Optional list of partition IDs to search

        Returns:
            List of result dictionaries with file path, score, and metadata
        """
        all_results = []

        try:
            # Determine which partitions to search
            partitions_to_search = []

            if partition_ids:
                # Search only specified partitions
                for partition_id in partition_ids:
                    if partition_id in self.partitions:
                        partitions_to_search.append(self.partitions[partition_id])
            else:
                # Search all partitions
                partitions_to_search = list(self.partitions.values())

            # Search each partition
            for partition in partitions_to_search:
                results = partition.search(query_embedding, top_k)
                all_results.extend(results)

            # Sort by score (highest first)
            all_results.sort(key=lambda x: x['score'], reverse=True)

            # Return top-k overall results
            return all_results[:top_k]
        except Exception as e:
            logger.error("Error searching partitions: %s", e)
            return []

    def select_partitions_for_query(self, query: str) -> List[str]:
        """
        Select relevant partitions for a query.

        Args:
            query: The search query

        Returns:
            List of partition IDs that might contain relevant results
        """
        query_l = query.lower()
        selected: List[str] = []

        language_hints = []
        if any(tok in query_l for tok in ["python", ".py", "def "]):
            language_hints.append("python")
        if any(tok in query_l for tok in ["javascript", ".js", "console."]):
            language_hints.append("javascript")
        if any(tok in query_l for tok in ["typescript", ".ts"]):
            language_hints.append("typescript")
        if any(tok in query_l for tok in ["php", ".php"]):
            language_hints.append("php")

        for pid, partition in self.partitions.items():
            crit = partition.criteria
            lang = crit.get("language")
            if language_hints and lang and lang.lower() in language_hints:
                selected.append(pid)
                continue
            if "directory" in crit and crit["directory"] and crit["directory"].lower() in query_l:
                selected.append(pid)

        if not selected:
            selected = list(self.partitions.keys())

        return selected

    def get_partition_stats(self) -> Dict[str, Any]:
        """
        Get statistics about partitions.

        Returns:
            Dictionary with partition statistics
        """
        stats = {
            "total_partitions": len(self.partitions),
            "total_files": sum(p.get_file_count() for p in self.partitions.values()),
            "partitions": {}
        }

        for partition_id, partition in self.partitions.items():
            stats["partitions"][partition_id] = {
                "file_count": partition.get_file_count(),
                "criteria": partition.criteria,
                "last_updated": partition.metadata.get("last_updated")
            }

        return stats

    def commit_all(self) -> bool:
        """
        Save all partition data to disk.

        Returns:
            True if successful, False otherwise
        """
        success = True

        for partition in self.partitions.values():
            if not partition.commit():
                success = False

        # Save manager metadata
        self._save_metadata()

        return success

    def clear_all(self) -> bool:
        """
        Clear all partition data.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove all partition directories
            for partition_id in list(self.partitions.keys()):
                partition_dir = os.path.join(self.storage_path, f"partition_{partition_id}")
                if os.path.exists(partition_dir):
                    shutil.rmtree(partition_dir)

            # Clear data structures
            self.partitions = {}
            self.file_to_partition = {}

            # Reset metadata
            self.metadata = {
                "created": time.time(),
                "last_updated": time.time(),
                "partition_count": 0,
                "total_files": 0,
                "version": 1
            }

            # Save empty metadata
            self._save_metadata()

            return True
        except Exception as e:
            logger.error("Error clearing partitions: %s", e)
            return False

    def optimize_partitions(self, max_files_per_partition: int = 1000) -> bool:
        """
        Optimize partitions by rebalancing files.

        Args:
            max_files_per_partition: Maximum files per partition

        Returns:
            True if optimization was successful, False otherwise
        """
        try:
            changed = False

            # Split large partitions
            for pid in list(self.partitions.keys()):
                partition = self.partitions[pid]
                if partition.get_file_count() > max_files_per_partition:
                    files = partition.get_all_files()
                    half = len(files) // 2
                    new_pid = self.create_partition(partition.criteria)
                    new_part = self.partitions[new_pid]
                    for fp in files[half:]:
                        emb = partition.file_embeddings.pop(fp)
                        meta = partition.file_metadata.pop(fp)
                        new_part.add_file(fp, emb, meta)
                        self.file_to_partition[fp] = new_pid
                    partition.commit()
                    new_part.commit()
                    changed = True

            # Merge small partitions with identical criteria
            ids = list(self.partitions.keys())
            for pid in ids:
                if pid not in self.partitions:
                    continue
                p = self.partitions[pid]
                if p.get_file_count() >= max_files_per_partition // 2:
                    continue
                for pid2 in ids:
                    if pid2 == pid or pid2 not in self.partitions:
                        continue
                    p2 = self.partitions[pid2]
                    if p2.criteria == p.criteria and p2.get_file_count() + p.get_file_count() <= max_files_per_partition:
                        for fp in p.get_all_files():
                            emb = p.file_embeddings[fp]
                            meta = p.file_metadata[fp]
                            p2.add_file(fp, emb, meta)
                            self.file_to_partition[fp] = pid2
                        p2.commit()
                        del self.partitions[pid]
                        changed = True
                        break

            if changed:
                self._save_metadata()

            return True
        except Exception as e:
            logger.error("Error optimizing partitions: %s", e)
            return False

    def prune_unused_entries(self, valid_files: Set[str]) -> int:
        """Remove index entries for files not present in ``valid_files``."""
        removed = 0

        try:
            for pid, partition in list(self.partitions.items()):
                for fp in list(partition.get_all_files()):
                    if fp not in valid_files or not os.path.exists(fp):
                        if partition.remove_file(fp):
                            removed += 1
                partition.commit()

            if removed:
                self._save_metadata()
        except Exception as e:
            logger.error("Error pruning unused entries: %s", e)

        return removed

    def merge_from_path(self, other_path: str) -> bool:
        """Merge partitions from another index manager stored at ``other_path``."""
        try:
            other = IndexPartitionManager(other_path)
            for pid, part in other.partitions.items():
                if pid not in self.partitions:
                    # copy entire partition directory
                    target_dir = os.path.join(self.storage_path, f"partition_{pid}")
                    shutil.copytree(part.storage_path, target_dir, dirs_exist_ok=True)
                    self.partitions[pid] = IndexPartition(pid, self.storage_path, part.criteria)
                    self.partitions[pid]._load_data()
                    for fp in part.get_all_files():
                        self.file_to_partition[fp] = pid
                else:
                    target = self.partitions[pid]
                    for fp in part.get_all_files():
                        emb = part.file_embeddings[fp]
                        meta = part.file_metadata[fp]
                        target.add_file(fp, emb, meta)
                        self.file_to_partition[fp] = pid
                    target.commit()

            self._save_metadata()
            return True
        except Exception as e:
            logger.error("Error merging partitions from %s: %s", other_path, e)
            return False
