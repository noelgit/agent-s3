"""JSON schema validation utilities for planner."""
from typing import Dict, Any, List, Tuple


def validate_json_schema(data: Dict[str, Any]) -> Tuple[bool, str, List[int]]:
    """Validate JSON data against the required schema."""
    if not isinstance(data, dict):
        return False, "Data must be a dictionary", []

    if "feature_groups" not in data:
        return False, "Missing 'feature_groups' key", []

    feature_groups = data.get("feature_groups", [])
    if not isinstance(feature_groups, list):
        return False, "'feature_groups' must be an array", []

    if not feature_groups:
        return False, "'feature_groups' array is empty", []

    valid_indices: List[int] = []
    for i, group in enumerate(feature_groups):
        if not isinstance(group, dict):
            continue
        if "group_name" not in group:
            continue
        if "features" not in group or not isinstance(group["features"], list):
            continue
        if not group["features"]:
            continue

        features_valid = True
        for feature in group["features"]:
            if not isinstance(feature, dict):
                features_valid = False
                break
            required_fields = ["name", "description"]
            if not all(field in feature for field in required_fields):
                features_valid = False
                break
        if features_valid:
            valid_indices.append(i)

    if not valid_indices:
        return False, "No valid feature groups found", []

    if len(valid_indices) < len(feature_groups):
        return (
            False,
            f"Only {len(valid_indices)} of {len(feature_groups)} feature groups are valid",
            valid_indices,
        )
    return True, "", valid_indices
