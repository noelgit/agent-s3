"""Checkpoint manager for tracking and managing workflow checkpoints.

This module provides functions to save, load, and validate checkpoints
across different phases of the workflow, ensuring consistency between phases.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Set
import difflib
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

def save_checkpoint(checkpoint_type: str, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
    """Save a checkpoint of the current workflow state.
    
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
    
    logger.info(f"Saved {checkpoint_type} checkpoint: {checkpoint_id}")
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
            logger.warning(f"Error loading checkpoint metadata {checkpoint_id}: {e}")
    
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

def ensure_checkpoint_consistency(base_checkpoint_id: str, new_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Ensure consistency between a base checkpoint and new data.
    
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
