"""JSON repair utilities for planner."""
from typing import Dict, Any


def repair_json_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt to repair a JSON structure to match the expected schema."""
    repaired: Dict[str, Any] = {}

    if "original_request" not in data:
        repaired["original_request"] = "Unknown request"
    else:
        repaired["original_request"] = data["original_request"]

    if "feature_groups" not in data or not isinstance(data.get("feature_groups"), list):
        repaired["feature_groups"] = []
    else:
        repaired["feature_groups"] = []
        for group in data["feature_groups"]:
            if not isinstance(group, dict):
                continue
            repaired_group: Dict[str, Any] = {}
            if "group_name" not in group:
                continue
            repaired_group["group_name"] = group["group_name"]
            if "group_description" not in group:
                repaired_group["group_description"] = f"Description for {group['group_name']}"
            else:
                repaired_group["group_description"] = group["group_description"]
            if "features" not in group or not isinstance(group["features"], list):
                repaired_group["features"] = []
            else:
                repaired_group["features"] = []
                for feature in group["features"]:
                    if not isinstance(feature, dict):
                        continue
                    repaired_feature: Dict[str, Any] = {}
                    if "name" not in feature:
                        continue
                    repaired_feature["name"] = feature["name"]
                    if "description" not in feature:
                        repaired_feature["description"] = f"Description for {feature['name']}"
                    else:
                        repaired_feature["description"] = feature["description"]
                    if "files_affected" not in feature or not isinstance(feature.get("files_affected"), list):
                        repaired_feature["files_affected"] = []
                    else:
                        repaired_feature["files_affected"] = feature["files_affected"]
                    if "test_requirements" not in feature or not isinstance(feature.get("test_requirements"), dict):
                        repaired_feature["test_requirements"] = {
                            "unit_tests": [],
                            "integration_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": [],
                            "test_strategy": {"coverage_goal": "80%", "ui_test_approach": "manual"},
                        }
                    else:
                        repaired_feature["test_requirements"] = feature["test_requirements"]
                        if "test_strategy" not in repaired_feature["test_requirements"]:
                            repaired_feature["test_requirements"]["test_strategy"] = {
                                "coverage_goal": "80%",
                                "ui_test_approach": "manual",
                            }
                    if "dependencies" not in feature or not isinstance(feature.get("dependencies"), dict):
                        repaired_feature["dependencies"] = {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": [],
                        }
                    else:
                        repaired_feature["dependencies"] = feature["dependencies"]
                    if "risk_assessment" not in feature or not isinstance(feature.get("risk_assessment"), dict):
                        repaired_feature["risk_assessment"] = {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": ["unit"],
                                "required_keywords": [],
                                "suggested_libraries": [],
                            },
                        }
                    else:
                        repaired_feature["risk_assessment"] = feature["risk_assessment"]
                    if "system_design" not in feature or not isinstance(feature.get("system_design"), dict):
                        repaired_feature["system_design"] = {
                            "overview": f"Implementation of {feature['name']}",
                            "code_elements": [],
                            "data_flow": "Standard data flow",
                            "key_algorithms": [],
                        }
                    else:
                        repaired_feature["system_design"] = feature["system_design"]
                        if "code_elements" not in repaired_feature["system_design"]:
                            repaired_feature["system_design"]["code_elements"] = []
                    repaired_group["features"].append(repaired_feature)
            if repaired_group["features"]:
                repaired["feature_groups"].append(repaired_group)
    if not repaired["feature_groups"]:
        repaired["feature_groups"] = [
            {
                "group_name": "Repaired Feature Group",
                "group_description": "Automatically created during repair",
                "features": [
                    {
                        "name": "Main Feature",
                        "description": "Automatically created feature",
                        "files_affected": [],
                        "test_requirements": {
                            "unit_tests": [],
                            "integration_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": [],
                            "test_strategy": {"coverage_goal": "80%", "ui_test_approach": "manual"},
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": [],
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": ["unit"],
                                "required_keywords": [],
                                "suggested_libraries": [],
                            },
                        },
                        "system_design": {
                            "overview": "Basic implementation",
                            "code_elements": [],
                            "data_flow": "Standard data flow",
                            "key_algorithms": [],
                        },
                    }
                ],
            }
        ]
    return repaired
