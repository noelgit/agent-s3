"""Repair utilities for pre-planning data."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def ensure_element_id_consistency(pre_planning_data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all element_ids are present and unique within pre-planning data."""
    if not isinstance(pre_planning_data, dict) or "feature_groups" not in pre_planning_data:
        logger.warning("Invalid pre-planning data structure for element_id validation")
        return pre_planning_data

    assigned_ids = set()

    for group_idx, group in enumerate(pre_planning_data["feature_groups"]):
        if not isinstance(group, dict) or "features" not in group:
            continue

        for feature_idx, feature in enumerate(group["features"]):
            if not isinstance(feature, dict):
                continue

            if "system_design" in feature and isinstance(feature["system_design"], dict) and "code_elements" in feature["system_design"]:
                code_elements = feature["system_design"]["code_elements"]
                if isinstance(code_elements, list):
                    for elem_idx, element in enumerate(code_elements):
                        if not isinstance(element, dict):
                            continue

                        if "element_id" not in element or not element["element_id"] or not isinstance(element["element_id"], str):
                            element_name = element.get("name", f"element_{elem_idx}")
                            base_id = f"{element_name.lower().replace(' ', '_')}_{group_idx}_{feature_idx}_{elem_idx}"
                            element_id = base_id
                            counter = 1
                            while element_id in assigned_ids:
                                element_id = f"{base_id}_{counter}"
                                counter += 1

                            element["element_id"] = element_id
                            assigned_ids.add(element_id)
                            logger.info("Generated element_id %s for element %s", element_id, element_name)
                        else:
                            element_id = element["element_id"]
                            if element_id in assigned_ids:
                                base_id = element_id
                                counter = 1
                                while element_id in assigned_ids:
                                    element_id = f"{base_id}_{counter}"
                                    counter += 1
                                element["element_id"] = element_id
                                logger.info("Renamed duplicate element_id from %s to %s", base_id, element_id)
                            assigned_ids.add(element_id)

                    if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                        if "unit_tests" in feature["test_requirements"] and isinstance(feature["test_requirements"]["unit_tests"], list):
                            for test in feature["test_requirements"]["unit_tests"]:
                                if not isinstance(test, dict):
                                    continue
                                if "target_element" in test and isinstance(test["target_element"], str):
                                    target_element = test["target_element"]
                                    matched_element = None
                                    for element in code_elements:
                                        if isinstance(element, dict) and element.get("name") == target_element:
                                            matched_element = element
                                            break
                                    if matched_element and "element_id" in matched_element:
                                        test["target_element_id"] = matched_element["element_id"]
                                        logger.info("Linked test to element_id %s based on target_element %s", matched_element["element_id"], target_element)

                        if "property_based_tests" in feature["test_requirements"] and isinstance(feature["test_requirements"]["property_based_tests"], list):
                            for test in feature["test_requirements"]["property_based_tests"]:
                                if not isinstance(test, dict):
                                    continue
                                if "target_element" in test and isinstance(test["target_element"], str):
                                    target_element = test["target_element"]
                                    matched_element = None
                                    for element in code_elements:
                                        if isinstance(element, dict) and element.get("name") == target_element:
                                            matched_element = element
                                            break
                                    if matched_element and "element_id" in matched_element:
                                        test["target_element_id"] = matched_element["element_id"]
                                        logger.info("Linked property test to element_id %s based on target_element %s", matched_element["element_id"], target_element)

    return pre_planning_data


def repair_preplanning_data(data: Dict[str, Any], errors: List[str]) -> Tuple[Dict[str, Any], bool]:
    """Attempt to repair invalid pre-planning data using the JSON validator."""
    from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator

    validator = PrePlannerJsonValidator()
    return validator.repair_plan(data, errors)


