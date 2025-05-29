"""JSON validation and repair utilities for planning module."""

from typing import Dict, Any, List, Tuple


def validate_json_schema(data: Dict[str, Any]) -> Tuple[bool, str, List[int]]:
    """
    Validate JSON data against the required schema.

    Args:
        data: The JSON data to validate

    Returns:
        Tuple of (is_valid, error_message, valid_indices)
    """
    # Check for required top-level keys
    if not isinstance(data, dict):
        return False, "Data must be a dictionary", []

    # Check for feature_groups array
    if "feature_groups" not in data:
        return False, "Missing 'feature_groups' key", []

    feature_groups = data.get("feature_groups", [])
    if not isinstance(feature_groups, list):
        return False, "'feature_groups' must be an array", []

    if not feature_groups:
        return False, "'feature_groups' array is empty", []

    # Track which feature groups are valid
    valid_indices = []

    # Validate each feature group
    for i, group in enumerate(feature_groups):
        if not isinstance(group, dict):
            continue

        # Check required group fields
        if "group_name" not in group:
            continue

        if "features" not in group or not isinstance(group["features"], list):
            continue

        # Check if features array is empty
        if not group["features"]:
            continue

        # Check each feature in the group
        features_valid = True
        for feature in group["features"]:
            if not isinstance(feature, dict):
                features_valid = False
                break

            # Check required feature fields
            required_fields = ["name", "description"]
            if not all(field in feature for field in required_fields):
                features_valid = False
                break

        if features_valid:
            valid_indices.append(i)

    # If no valid feature groups found, return error
    if not valid_indices:
        return False, "No valid feature groups found", []

    # If some feature groups are valid but not all, return partial success
    if len(valid_indices) < len(feature_groups):
        return False, f"Only {len(valid_indices)} of {len(feature_groups)} feature groups are valid", valid_indices

    # All feature groups are valid
    return True, "", valid_indices


def repair_json_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to repair a JSON structure to match the expected schema.

    Args:
        data: The JSON data to repair

    Returns:
        Repaired JSON data
    """
    repaired = {}

    # Ensure original_request exists
    if "original_request" not in data:
        repaired["original_request"] = "Unknown request"
    else:
        repaired["original_request"] = data["original_request"]

    # Ensure feature_groups exists and is a list
    if "feature_groups" not in data or not isinstance(data["feature_groups"], list):
        repaired["feature_groups"] = []
    else:
        repaired["feature_groups"] = []

        # Process each feature group
        for group in data["feature_groups"]:
            if not isinstance(group, dict):
                continue

            repaired_group = _repair_feature_group(group)
            if repaired_group and repaired_group["features"]:
                repaired["feature_groups"].append(repaired_group)

    # If no valid feature groups were found, create a minimal valid structure
    if not repaired["feature_groups"]:
        repaired["feature_groups"] = [_create_default_feature_group()]

    return repaired


def _repair_feature_group(group: Dict[str, Any]) -> Dict[str, Any]:
    """Repair a single feature group."""
    repaired_group = {}

    # Ensure group_name exists
    if "group_name" not in group:
        return None  # Skip groups without names
    repaired_group["group_name"] = group["group_name"]

    # Ensure group_description exists
    if "group_description" not in group:
        repaired_group["group_description"] = f"Description for {group['group_name']}"
    else:
        repaired_group["group_description"] = group["group_description"]

    # Ensure features exists and is a list
    if "features" not in group or not isinstance(group["features"], list):
        repaired_group["features"] = []
    else:
        repaired_group["features"] = []

        # Process each feature
        for feature in group["features"]:
            if not isinstance(feature, dict):
                continue

            repaired_feature = _repair_feature(feature)
            if repaired_feature:
                repaired_group["features"].append(repaired_feature)

    return repaired_group


def _repair_feature(feature: Dict[str, Any]) -> Dict[str, Any]:
    """Repair a single feature."""
    repaired_feature = {}

    # Ensure name exists
    if "name" not in feature:
        return None  # Skip features without names
    repaired_feature["name"] = feature["name"]

    # Ensure description exists
    if "description" not in feature:
        repaired_feature["description"] = f"Description for {feature['name']}"
    else:
        repaired_feature["description"] = feature["description"]

    # Ensure files_affected exists
    if "files_affected" not in feature or not isinstance(feature["files_affected"], list):
        repaired_feature["files_affected"] = []
    else:
        repaired_feature["files_affected"] = feature["files_affected"]

    # Ensure test_requirements exists
    repaired_feature["test_requirements"] = _repair_test_requirements(
        feature.get("test_requirements", {})
    )

    # Ensure dependencies exists
    repaired_feature["dependencies"] = _repair_dependencies(
        feature.get("dependencies", {})
    )

    # Ensure risk_assessment exists
    repaired_feature["risk_assessment"] = _repair_risk_assessment(
        feature.get("risk_assessment", {})
    )

    # Ensure system_design exists
    repaired_feature["system_design"] = _repair_system_design(
        feature.get("system_design", {}), feature["name"]
    )

    return repaired_feature


def _repair_test_requirements(test_requirements: Dict[str, Any]) -> Dict[str, Any]:
    """Repair test requirements structure."""
    if not isinstance(test_requirements, dict):
        test_requirements = {}

    repaired = {
        "unit_tests": test_requirements.get("unit_tests", []),
        "property_based_tests": test_requirements.get("property_based_tests", []),
        "acceptance_tests": test_requirements.get("acceptance_tests", []),
        "test_strategy": test_requirements.get("test_strategy", {
            "coverage_goal": "80%",
            "ui_test_approach": "manual"
        })
    }

    # Ensure test_strategy exists
    if "test_strategy" not in repaired or not isinstance(repaired["test_strategy"], dict):
        repaired["test_strategy"] = {
            "coverage_goal": "80%",
            "ui_test_approach": "manual"
        }

    return repaired


def _repair_dependencies(dependencies: Dict[str, Any]) -> Dict[str, Any]:
    """Repair dependencies structure."""
    if not isinstance(dependencies, dict):
        dependencies = {}

    return {
        "internal": dependencies.get("internal", []),
        "external": dependencies.get("external", []),
        "feature_dependencies": dependencies.get("feature_dependencies", [])
    }


def _repair_risk_assessment(risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
    """Repair risk assessment structure."""
    if not isinstance(risk_assessment, dict):
        risk_assessment = {}

    return {
        "critical_files": risk_assessment.get("critical_files", []),
        "potential_regressions": risk_assessment.get("potential_regressions", []),
        "backward_compatibility_concerns": risk_assessment.get("backward_compatibility_concerns", []),
        "mitigation_strategies": risk_assessment.get("mitigation_strategies", []),
        "required_test_characteristics": risk_assessment.get("required_test_characteristics", {
            "required_types": ["unit"],
            "required_keywords": [],
            "suggested_libraries": []
        })
    }


def _repair_system_design(system_design: Dict[str, Any], feature_name: str) -> Dict[str, Any]:
    """Repair system design structure."""
    if not isinstance(system_design, dict):
        system_design = {}

    repaired = {
        "overview": system_design.get("overview", f"Implementation of {feature_name}"),
        "code_elements": system_design.get("code_elements", []),
        "data_flow": system_design.get("data_flow", "Standard data flow"),
        "key_algorithms": system_design.get("key_algorithms", [])
    }

    # Ensure code_elements exists
    if "code_elements" not in repaired:
        repaired["code_elements"] = []

    return repaired


def _create_default_feature_group() -> Dict[str, Any]:
    """Create a default feature group for fallback scenarios."""
    return {
        "group_name": "Repaired Feature Group",
        "group_description": "Automatically created during repair",
        "features": [{
            "name": "Main Feature",
            "description": "Automatically created feature",
            "files_affected": [],
            "test_requirements": {
                "unit_tests": [],
                "property_based_tests": [],
                "acceptance_tests": [],
                "test_strategy": {
                    "coverage_goal": "80%",
                    "ui_test_approach": "manual"
                }
            },
            "dependencies": {
                "internal": [],
                "external": [],
                "feature_dependencies": []
            },
            "risk_assessment": {
                "critical_files": [],
                "potential_regressions": [],
                "backward_compatibility_concerns": [],
                "mitigation_strategies": [],
                "required_test_characteristics": {
                    "required_types": ["unit"],
                    "required_keywords": [],
                    "suggested_libraries": []
                }
            },
            "system_design": {
                "overview": "Basic implementation",
                "code_elements": [],
                "data_flow": "Standard data flow",
                "key_algorithms": []
            }
        }]
    }
