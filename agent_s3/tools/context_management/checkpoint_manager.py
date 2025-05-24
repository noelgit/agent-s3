"""Checkpoint manager for tracking and managing workflow checkpoints.

This module provides functions to save, load, and validate checkpoints
across different phases of the workflow, ensuring consistency between phases.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def get_checkpoints_dir() -> str:
    """Get the directory to store checkpoints.

    Uses AGENT_CHECKPOINTS_DIR environment variable if set, otherwise
    creates a 'checkpoints' directory in the current working directory.

    Returns:
        Path to the checkpoints directory
    """
    checkpoints_dir = os.environ.get('AGENT_CHECKPOINTS_DIR', os.path.join(os.getcwd(), 'checkpoints'))
    os.makedirs(checkpoints_dir, exist_ok=True)
    return checkpoints_dir

def save_checkpoint(checkpoint_type: str, data: Dict[str, Any], metadata: Optional[Dict[str,
     Any]] = None) -> str:    """Save a checkpoint of the current workflow state.

    Args:
        checkpoint_type: Type of checkpoint (pre_planning, planning, implementation, etc.)
        data: Data to save in the checkpoint
        metadata: Optional metadata for the checkpoint

    Returns:
        Checkpoint ID
    """
    checkpoint_id = str(uuid.uuid4())
    checkpoints_dir = get_checkpoints_dir()

    # Prepare metadata
    timestamp = datetime.now().isoformat()
    checkpoint_metadata = {
        "checkpoint_id": checkpoint_id,
        "checkpoint_type": checkpoint_type,
        "timestamp": timestamp
    }

    # Add custom metadata if provided
    if metadata:
        checkpoint_metadata.update(metadata)

    # Create checkpoint directory
    checkpoint_dir = os.path.join(checkpoints_dir, checkpoint_id)
    os.makedirs(checkpoint_dir, exist_ok=True)

    # Save data and metadata
    with open(os.path.join(checkpoint_dir, "data.json"), "w") as f:
        json.dump(data, f, indent=2)

    with open(os.path.join(checkpoint_dir, "metadata.json"), "w") as f:
        json.dump(checkpoint_metadata, f, indent=2)

    logger.info("%s", Saved {checkpoint_type} checkpoint: {checkpoint_id})
    return checkpoint_id

def load_checkpoint(checkpoint_id: str, include_metadata: bool = False) -> Any:
    """Load a checkpoint by ID.

    Args:
        checkpoint_id: ID of the checkpoint to load
        include_metadata: Whether to include checkpoint metadata in the result

    Returns:
        Checkpoint data, or (data, metadata) tuple if include_metadata is True
    """
    checkpoints_dir = get_checkpoints_dir()
    checkpoint_dir = os.path.join(checkpoints_dir, checkpoint_id)

    # Load data
    data_path = os.path.join(checkpoint_dir, "data.json")
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Checkpoint data not found: {checkpoint_id}")

    with open(data_path, "r") as f:
        data = json.load(f)

    if not include_metadata:
        return data

    # Load metadata if requested
    metadata_path = os.path.join(checkpoint_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        metadata = {"checkpoint_id": checkpoint_id}
    else:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

    return data, metadata

def list_checkpoints(checkpoint_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """List available checkpoints, optionally filtered by type.

    Args:
        checkpoint_type: Optional type to filter by

    Returns:
        List of checkpoint metadata dictionaries, ordered by timestamp (newest first)
    """
    checkpoints_dir = get_checkpoints_dir()
    result = []

    # Walk through checkpoint directories
    for checkpoint_id in os.listdir(checkpoints_dir):
        checkpoint_dir = os.path.join(checkpoints_dir, checkpoint_id)
        if not os.path.isdir(checkpoint_dir):
            continue

        # Load metadata
        metadata_path = os.path.join(checkpoint_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            continue

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Filter by type if requested
            if checkpoint_type and metadata.get("checkpoint_type") != checkpoint_type:
                continue

            result.append(metadata)
        except Exception as e:
            logger.warning("%s", Error loading checkpoint metadata {checkpoint_id}: {e})

    # Sort by timestamp (newest first)
    result.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return result

def get_checkpoint_diff(checkpoint_id1: str, checkpoint_id2: str) -> Dict[str, Any]:
    """Generate a diff between two checkpoints.

    Args:
        checkpoint_id1: ID of the first checkpoint
        checkpoint_id2: ID of the second checkpoint

    Returns:
        Diff dictionary with 'added', 'removed', and 'modified' sections
    """
    # Load checkpoints
    checkpoint1 = load_checkpoint(checkpoint_id1)
    checkpoint2 = load_checkpoint(checkpoint_id2)

    # Extract features from feature groups
    def extract_features(checkpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        features = []
        for feature_group in checkpoint.get("feature_groups", []):
            features.extend(feature_group.get("features", []))
        return features

    features1 = extract_features(checkpoint1)
    features2 = extract_features(checkpoint2)

    # Map features by name for easy comparison
    feature_map1 = {f.get("name"): f for f in features1}
    feature_map2 = {f.get("name"): f for f in features2}

    # Find features that were added, removed, or modified
    added = []
    removed = []
    modified = []

    for name, feature in feature_map2.items():
        if name not in feature_map1:
            added.append(feature)
        elif feature != feature_map1[name]:
            modified.append({
                "old": feature_map1[name],
                "new": feature,
                "name": name
            })

    for name, feature in feature_map1.items():
        if name not in feature_map2:
            removed.append(feature)

    return {
        "added": added,
        "removed": removed,
        "modified": modified
    }

def ensure_checkpoint_consistency(base_checkpoint_id: str, new_data: Dict[str, Any]) -> Tuple[bool,
     str]:    """Ensure consistency between a base checkpoint and new data.

    This function checks that the new data does not remove features from the base checkpoint.
    It's used to prevent accidental removal of features between phases.

    Args:
        base_checkpoint_id: ID of the base checkpoint
        new_data: New data to validate against the base checkpoint

    Returns:
        (is_valid, message) tuple
    """
    # Load base checkpoint
    try:
        base_checkpoint = load_checkpoint(base_checkpoint_id)
    except Exception as e:
        return False, f"Error loading base checkpoint: {e}"

    # Extract feature groups and features
    base_feature_groups = base_checkpoint.get("feature_groups", [])
    new_feature_groups = new_data.get("feature_groups", [])

    # Compare feature groups - check for missing groups
    base_group_names = {group.get("group_name") for group in base_feature_groups}
    new_group_names = {group.get("group_name") for group in new_feature_groups}

    missing_groups = base_group_names - new_group_names
    if missing_groups:
        return False, f"Missing feature groups: {', '.join(missing_groups)}"

    # Compare features within each group
    issues = []

    for base_group in base_feature_groups:
        group_name = base_group.get("group_name")

        # Find corresponding group in new data
        new_group = next((g for g in new_feature_groups if g.get("group_name") == group_name), None)
        if not new_group:
            continue  # Already reported as missing group

        # Extract feature names
        base_features = {f.get("name") for f in base_group.get("features", [])}
        new_features = {f.get("name") for f in new_group.get("features", [])}

        # Check for missing features
        missing_features = base_features - new_features
        if missing_features:
            issues.append(f"Group '{group_name}' is missing features: {', '.join(missing_features)}")

    if issues:
        return False, "; ".join(issues)

    return True, "Checkpoint is consistent"

def get_latest_checkpoint(checkpoint_type: str) -> Optional[str]:
    """Get the ID of the latest checkpoint of a specific type.

    Args:
        checkpoint_type: Type of checkpoint to find

    Returns:
        Checkpoint ID or None if no checkpoints of the specified type exist
    """
    checkpoints = list_checkpoints(checkpoint_type)
    if not checkpoints:
        return None

    # Return the ID of the newest checkpoint
    return checkpoints[0].get("checkpoint_id")

def create_checkpoint_version(checkpoint_id: str, data: Dict[str, Any],
                            version_type: str, version_details: Dict[str, Any]) -> str:
    """Create a new versioned checkpoint based on an existing one.

    This is particularly useful for tracking plan modifications over time.

    Args:
        checkpoint_id: ID of the base checkpoint
        data: Updated data
        version_type: Type of version (e.g., 'user_modification')
        version_details: Details about the version change

    Returns:
        New checkpoint ID
    """
    # Load base checkpoint metadata
    _, metadata = load_checkpoint(checkpoint_id, include_metadata=True)

    # Create new metadata
    new_metadata = metadata.copy()
    new_metadata.pop("checkpoint_id", None)
    new_metadata["base_checkpoint_id"] = checkpoint_id
    new_metadata["version_type"] = version_type
    new_metadata["version_details"] = version_details

    # Create new checkpoint with enhanced metadata
    return save_checkpoint(
        checkpoint_type=f"{metadata.get('checkpoint_type', 'unknown')}_versioned",
        data=data,
        metadata=new_metadata
    )


class ContextCheckpoint:
    """Represents a saved snapshot of context information."""

    def __init__(
        self,
        context: Dict[str, Any],
        checkpoint_id: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.context = context
        self.checkpoint_id = checkpoint_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now().isoformat()
        self.description = description or "checkpoint"
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the checkpoint to a dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp,
            "description": self.description,
            "metadata": self.metadata,
            "context": self.context,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ContextCheckpoint":
        """Create a ContextCheckpoint from a dictionary."""
        return ContextCheckpoint(
            context=data.get("context", {}),
            checkpoint_id=data.get("checkpoint_id"),
            description=data.get("description"),
            metadata=data.get("metadata"),
            timestamp=data.get("timestamp"),
        )

    def compress(self) -> Dict[str, Any]:
        """Return a compressed representation using zlib+base64."""
        import base64
        import zlib

        data_bytes = json.dumps(self.to_dict()).encode("utf-8")
        compressed = base64.b64encode(zlib.compress(data_bytes)).decode("utf-8")
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp,
            "description": self.description,
            "compression": "zlib+base64",
            "data": compressed,
        }

    @staticmethod
    def decompress(data: Dict[str, Any]) -> "ContextCheckpoint":
        """Create a checkpoint from compressed data."""
        import base64
        import zlib

        if data.get("compression") != "zlib+base64":
            raise ValueError("Unsupported compression format")
        raw = zlib.decompress(base64.b64decode(data["data"]))
        return ContextCheckpoint.from_dict(json.loads(raw.decode("utf-8")))

    def diff(self, other: "ContextCheckpoint") -> Dict[str, Any]:
        """Compute a diff between this checkpoint and another."""

        differences: Dict[str, Any] = {}

        def _diff(prefix: str, left: Any, right: Any) -> None:
            if isinstance(left, dict) and isinstance(right, dict):
                keys = set(left.keys()) | set(right.keys())
                for key in keys:
                    _diff(f"{prefix}.{key}" if prefix else key, left.get(key), right.get(key))
            else:
                if left != right:
                    if left is None:
                        differences[prefix] = {"status": "added", "value": right}
                    elif right is None:
                        differences[prefix] = {"status": "removed", "value": left}
                    else:
                        differences[prefix] = {
                            "status": "changed",
                            "old_value": left,
                            "new_value": right,
                        }

        _diff("", self.context, other.context)

        return {
            "checkpoint_id_1": self.checkpoint_id,
            "checkpoint_id_2": other.checkpoint_id,
            "differences": differences,
        }


class CheckpointManager:
    """Manage ContextCheckpoint instances on disk."""

    def __init__(
        self,
        checkpoint_dir: Optional[str] = None,
        max_checkpoints: int = 10,
        auto_checkpoint_interval: Optional[int] = None,
        compression: bool = True,
    ) -> None:
        self.checkpoint_dir = checkpoint_dir or get_checkpoints_dir()
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self.max_checkpoints = max_checkpoints
        self.auto_checkpoint_interval = auto_checkpoint_interval
        self.compression = compression
        self.checkpoints: Dict[str, ContextCheckpoint] = {}
        self._last_auto_checkpoint = datetime.now()

    def _checkpoint_path(self, checkpoint_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")

    def _prune_checkpoints(self) -> None:
        existing = self.list_checkpoints()
        while len(existing) > self.max_checkpoints:
            oldest = existing.pop(0)
            self.delete_checkpoint(oldest["checkpoint_id"])

    def create_checkpoint(
        self,
        context: Dict[str, Any],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        checkpoint = ContextCheckpoint(context, description=description, metadata=metadata)
        with open(self._checkpoint_path(checkpoint.checkpoint_id), "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        self.checkpoints[checkpoint.checkpoint_id] = checkpoint
        self._prune_checkpoints()
        return checkpoint.checkpoint_id

    def get_checkpoint(self, checkpoint_id: str) -> Optional[ContextCheckpoint]:
        if checkpoint_id in self.checkpoints:
            return self.checkpoints[checkpoint_id]
        path = self._checkpoint_path(checkpoint_id)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        checkpoint = ContextCheckpoint.from_dict(data)
        self.checkpoints[checkpoint_id] = checkpoint
        return checkpoint

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        checkpoints = []
        for filename in os.listdir(self.checkpoint_dir):
            if not filename.endswith(".json"):
                continue
            cid = filename[:-5]
            cp = self.get_checkpoint(cid)
            if cp:
                checkpoints.append(cp.to_dict())
        checkpoints.sort(key=lambda x: x.get("timestamp", ""))
        return checkpoints

    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        checkpoint = self.get_checkpoint(checkpoint_id)
        return checkpoint.context if checkpoint else None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        self.checkpoints.pop(checkpoint_id, None)
        path = self._checkpoint_path(checkpoint_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def check_auto_checkpoint(self, context: Dict[str, Any]) -> Optional[str]:
        if self.auto_checkpoint_interval is None:
            return None
        now = datetime.now()
        elapsed = (now - self._last_auto_checkpoint).total_seconds()
        if elapsed >= self.auto_checkpoint_interval:
            self._last_auto_checkpoint = now
            return self.create_checkpoint(context)
        return None

    def diff_checkpoints(self, checkpoint_id1: str, checkpoint_id2: str) -> Optional[Dict[str,
         Any]]:        cp1 = self.get_checkpoint(checkpoint_id1)
        cp2 = self.get_checkpoint(checkpoint_id2)
        if not cp1 or not cp2:
            return None
        return cp1.diff(cp2)
