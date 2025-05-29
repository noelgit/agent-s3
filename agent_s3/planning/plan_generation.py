"""Utilities supporting the multi-phase planning workflow.

These helpers generate and regenerate planning artifacts used throughout the
five-step process:
1. Architecture review
2. Test specification refinement
3. Test implementation
4. Implementation planning
5. Semantic validation and consolidation.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List

from .llm_integration import call_llm_with_retry, parse_and_validate_json
from .prompt_templates import (
    get_stage_system_prompt,
)

logger = logging.getLogger(__name__)


def generate_refined_test_specifications(
    router_agent,
    feature_group: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate refined test specifications based on architecture review and system design.

    Args:
        router_agent: The LLM router agent for making LLM calls
        feature_group: The feature group data
        architecture_review: The architecture review data
        task_description: Original task description
        context: Optional additional context

    Returns:
        Dictionary containing refined test specifications
    """
    logger.info(
        "Generating refined test specifications for feature group: %s",
        feature_group.get("group_name", "Unknown"),
    )

    # Extract test requirements and system design from the feature group
    test_requirements = _extract_test_requirements_from_group(feature_group)
    system_design = _extract_system_design_from_group(feature_group)

    # Create user prompt for test specification refinement
    user_prompt = _create_test_specification_user_prompt(
        feature_group, architecture_review, task_description,
        test_requirements, system_design, context
    )

    # Get system prompt for test specification refinement
    from ..planner_json_enforced import get_test_specification_refinement_system_prompt

    system_prompt = get_test_specification_refinement_system_prompt()

    # Get LLM configuration with reasonable defaults
    config = _get_test_specification_config()

    try:
        # Call LLM to generate refined test specifications
        response = call_llm_with_retry(
            router_agent,
            system_prompt,
            user_prompt,
            config
        )

        # Parse and validate the JSON response
        refined_specs = parse_and_validate_json(
            response,
            enforce_schema=False,  # Test specs have flexible schema
            repair_mode=True
        )

        logger.info("Successfully generated refined test specifications")
        return refined_specs

    except Exception as e:
        logger.error("Failed to generate refined test specifications: %s", e)
        return _create_fallback_test_specifications(feature_group)


def regenerate_consolidated_plan_with_modifications(
    router_agent,
    original_plan: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    modifications: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Regenerate a consolidated plan with specific modifications.

    Args:
        router_agent: The LLM router agent for making LLM calls
        original_plan: The original plan to modify
        architecture_review: Architecture review data
        task_description: Original task description
        modifications: Specific modifications to apply
        context: Optional additional context

    Returns:
        Dictionary containing the regenerated plan
    """
    logger.info("Regenerating consolidated plan with modifications")

    # Create user prompt with modifications
    user_prompt = _create_modification_user_prompt(
        original_plan, architecture_review, task_description, modifications, context
    )

    # Get system prompt
    system_prompt = _get_system_prompt()

    # Get LLM configuration
    config = _get_plan_generation_config()

    try:
        # Call LLM to regenerate plan
        response = call_llm_with_retry(
            router_agent,
            system_prompt,
            user_prompt,
            config
        )

        # Parse and validate the JSON response
        regenerated_plan = parse_and_validate_json(
            response,
            enforce_schema=True,
            repair_mode=True
        )

        logger.info("Successfully regenerated consolidated plan")
        return regenerated_plan

    except Exception as e:
        logger.error("Failed to regenerate consolidated plan: %s", e)
        return _create_fallback_plan(original_plan, task_description)


def validate_pre_planning_for_planner(pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that pre-planning output is compatible with the planner stage.

    This mirrors the Planner.validate_pre_planning_for_planner method to keep a
    symmetrical interface between pre-planner and planner modules.

    Args:
        pre_plan_data: Pre-planning data to validate.

    Returns:
        Tuple (is_compatible, message) describing compatibility.
    """
    compatibility_issues: List[str] = []

    if not isinstance(pre_plan_data, dict):
        return False, "Pre-planning data is not a dictionary"

    feature_groups = pre_plan_data.get("feature_groups")
    if not isinstance(feature_groups, list):
        return False, "Pre-planning data missing feature_groups or it's not a list"

    if not feature_groups:
        return False, "No feature groups in pre-planning data"

    for group_idx, group in enumerate(feature_groups):
        if not isinstance(group, dict):
            compatibility_issues.append(f"Feature group {group_idx} is not a dictionary")
            continue

        # Check required group fields
        if "group_name" not in group:
            compatibility_issues.append(f"Feature group {group_idx} missing group_name")

        features = group.get("features")
        if not isinstance(features, list):
            compatibility_issues.append(f"Feature group {group_idx} missing features or it's not a list")
            continue

        # Validate features within the group
        for feature_idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                compatibility_issues.append(
                    f"Feature {feature_idx} in group {group_idx} is not a dictionary"
                )
                continue

            # Check required feature fields
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in feature:
                    compatibility_issues.append(
                        f"Feature {feature_idx} in group {group_idx} missing {field}"
                    )

            # Check optional but important fields
            _validate_feature_structure(feature, group_idx, feature_idx, compatibility_issues)

    if compatibility_issues:
        return False, "; ".join(compatibility_issues)

    return True, "Pre-planning data is compatible with planner"


def _extract_test_requirements_from_group(feature_group: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and merge test requirements from all features in a group."""
    test_requirements = {}

    for feature in feature_group.get("features", []):
        if isinstance(feature, dict):
            feature_test_req = feature.get("test_requirements", {})
            if feature_test_req:
                for test_type, tests in feature_test_req.items():
                    if test_type not in test_requirements:
                        test_requirements[test_type] = []
                    if isinstance(tests, list):
                        test_requirements[test_type].extend(tests)
                    elif isinstance(tests, dict):
                        if test_type not in test_requirements:
                            test_requirements[test_type] = {}
                        test_requirements[test_type].update(tests)

    return test_requirements


def _extract_system_design_from_group(feature_group: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and merge system design elements from all features in a group."""
    system_design = {}

    for feature in feature_group.get("features", []):
        if isinstance(feature, dict):
            feature_sys_design = feature.get("system_design", {})
            if feature_sys_design:
                for key, value in feature_sys_design.items():
                    if key not in system_design:
                        system_design[key] = value

    return system_design


def _create_test_specification_user_prompt(
    feature_group: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    test_requirements: Dict[str, Any],
    system_design: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Create user prompt for test specification refinement."""
    context_info = ""
    if context:
        context_info = f"\\n\\nAdditional Context:\\n{context}"

    return f"""
Task Description: {task_description}

Feature Group: {feature_group.get("group_name", "Unknown")}
Group Description: {feature_group.get("group_description", "No description")}

Current Test Requirements:
{test_requirements}

System Design Elements:
{system_design}

Architecture Review Findings:
{architecture_review}

Please refine the test specifications based on the architecture review findings and system design.
{context_info}
"""


def _create_modification_user_prompt(
    original_plan: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    modifications: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Create user prompt for plan modification."""
    context_info = ""
    if context:
        context_info = f"\\n\\nAdditional Context:\\n{context}"

    return f"""
Task Description: {task_description}

Original Plan:
{original_plan}

Architecture Review Findings:
{architecture_review}

Requested Modifications:
{modifications}

Please regenerate the consolidated plan incorporating the requested modifications and addressing any architecture review findings.
{context_info}
"""


def _validate_feature_structure(
    feature: Dict[str, Any],
    group_idx: int,
    feature_idx: int,
    compatibility_issues: List[str]
) -> None:
    """Validate the structure of a feature."""
    # Check for system_design structure
    if "system_design" in feature:
        sys_design = feature["system_design"]
        if not isinstance(sys_design, dict):
            compatibility_issues.append(
                f"Feature {feature_idx} in group {group_idx} has invalid system_design (not a dict)"
            )

    # Check for test_requirements structure
    if "test_requirements" in feature:
        test_req = feature["test_requirements"]
        if not isinstance(test_req, dict):
            compatibility_issues.append(
                f"Feature {feature_idx} in group {group_idx} has invalid test_requirements (not a dict)"
            )


def _get_test_specification_config() -> Dict[str, Any]:
    """Get configuration for test specification generation."""
    return {
        "max_tokens": 4000,
        "temperature": 0.3,
        "top_p": 0.9
    }


def _get_plan_generation_config() -> Dict[str, Any]:
    """Get configuration for plan generation."""
    return {
        "max_tokens": 8000,
        "temperature": 0.2,
        "top_p": 0.8
    }


def _create_fallback_test_specifications(feature_group: Dict[str, Any]) -> Dict[str, Any]:
    """Create fallback test specifications when generation fails."""
    logger.warning("Creating fallback test specifications")

    return {
        "feature_group_name": feature_group.get("group_name", "Unknown"),
        "refined_test_specifications": {
            "unit_tests": ["Basic unit tests for core functionality"],
            "test_strategy": {
                "coverage_goal": "80%",
                "approach": "standard"
            }
        },
        "test_implementation_plan": {
            "priority": "high",
            "estimated_effort": "medium"
        }
    }


def _create_fallback_plan(original_plan: Dict[str, Any], task_description: str) -> Dict[str, Any]:
    """Create fallback plan when regeneration fails."""
    logger.warning("Creating fallback plan")

    # Return the original plan with a modification note
    fallback_plan = original_plan.copy()
    fallback_plan["modification_status"] = "fallback"
    fallback_plan["modification_note"] = f"Could not regenerate plan for: {task_description}"

    return fallback_plan


# Helper function to get consolidated plan system prompt
def _get_system_prompt() -> str:
    """Get system prompt for generating the full consolidated plan."""
    return get_stage_system_prompt("consolidated")
