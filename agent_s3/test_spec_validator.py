"""
Test Specification Validator Module

This module provides utilities to validate and repair test specifications.
It focuses on element ID validation, architecture issue coverage verification,
test priority consistency, and enhanced JSON repair capabilities.
"""

import json
import logging
from difflib import SequenceMatcher
from typing import Dict, Any, List, Set, Tuple, Optional

import numpy as np

from agent_s3.progress_tracker import progress_tracker, Status

logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """Exception raised when validation of test specifications fails."""
    pass

def extract_element_ids_from_system_design(system_design: Dict[str, Any]) -> Set[str]:
    """
    Extract all element IDs from the system design.

    Args:
        system_design: The system design dictionary

    Returns:
        Set of element IDs found in the system design
    """
    element_ids = set()

    # Extract from code_elements
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "element_id" in element:
            element_ids.add(element["element_id"])

    # Extract from architecture sections if present
    architecture = system_design.get("architecture", {})
    for section in architecture.values():
        if isinstance(section, list):
            for item in section:
                if isinstance(item, dict) and "element_id" in item:
                    element_ids.add(item["element_id"])

    return element_ids

def extract_architecture_issues(architecture_review: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract all architecture issues from the architecture review.

    Args:
        architecture_review: The architecture review dictionary

    Returns:
        List of architecture issues with their severity and ID
    """
    issues = []

    # Extract from logical_gaps section
    for issue in architecture_review.get("logical_gaps", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "Medium"),
                "issue_type": "logical_gap"
            })

    # Extract from security_concerns section
    for issue in architecture_review.get("security_concerns", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "High"),  # Security concerns default to high
                "issue_type": "security_concern"
            })

    # Extract from optimization_opportunities section
    for issue in architecture_review.get("optimization_opportunities", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "Medium"),
                "issue_type": "optimization"
            })

    # Extract from additional_considerations section
    for issue in architecture_review.get("additional_considerations", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "Low"),  # Additional considerations default to low
                "issue_type": "consideration"
            })

    return issues

def extract_referenced_element_ids(test_specs: Dict[str, Any]) -> Set[str]:
    """
    Extract all element IDs referenced in the test specifications.

    Args:
        test_specs: The refined test specifications dictionary

    Returns:
        Set of element IDs referenced in test specs
    """
    referenced_ids = set()

    # Extract from unit tests
    for test in test_specs.get("unit_tests", []):
        if isinstance(test, dict):
            element_id = test.get("target_element_id")
            if element_id:
                referenced_ids.add(element_id)

    # Extract from integration tests
    for test in test_specs.get("integration_tests", []):
        if isinstance(test, dict):
            element_ids = test.get("target_element_ids", [])
            if isinstance(element_ids, list):
                referenced_ids.update(element_ids)

    # Extract from property-based tests
    for test in test_specs.get("property_based_tests", []):
        if isinstance(test, dict):
            element_id = test.get("target_element_id")
            if element_id:
                referenced_ids.add(element_id)

    # Extract from acceptance tests
    for test in test_specs.get("acceptance_tests", []):
        if isinstance(test, dict):
            element_ids = test.get("target_element_ids", [])
            if isinstance(element_ids, list):
                referenced_ids.update(element_ids)

    # Extract from test strategy critical paths
    for path in test_specs.get("test_strategy", {}).get("critical_paths", []):
        if isinstance(path, dict):
            element_ids = path.get("element_ids", [])
            if isinstance(element_ids, list):
                referenced_ids.update(element_ids)

    return referenced_ids

def extract_addressed_issues(test_specs: Dict[str, Any]) -> Set[str]:
    """
    Extract all architecture issues addressed in the test specifications.

    Args:
        test_specs: The refined test specifications dictionary

    Returns:
        Set of architecture issue IDs or descriptions addressed
    """
    addressed_issues = set()

    # Helper function to extract from each test
    def extract_from_test(test):
        if isinstance(test, dict):
            issue = test.get("architecture_issue_addressed")
            if issue:
                addressed_issues.add(issue)

    # Extract from all test types
    for test_type in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
        for test in test_specs.get(test_type, []):
            extract_from_test(test)

    return addressed_issues

def validate_element_ids(
    test_specs: Dict[str, Any],
    system_design: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate that all element IDs in test specifications exist in the system design.

    Args:
        test_specs: The refined test specifications
        system_design: The system design dictionary

    Returns:
        List of validation issues with their details
    """
    validation_issues = []

    # Get all valid element IDs from the system design
    valid_element_ids = extract_element_ids_from_system_design(system_design)

    # Get all referenced element IDs from the test specifications
    referenced_ids = extract_referenced_element_ids(test_specs)

    # Check for invalid element IDs
    invalid_ids = referenced_ids - valid_element_ids

    if invalid_ids:
        for invalid_id in invalid_ids:
            validation_issues.append({
                "issue_type": "invalid_element_id",
                "severity": "High",
                "message": f"Element ID '{invalid_id}' referenced in tests does not exist in system design",
                "element_id": invalid_id
            })

    return validation_issues

def validate_architecture_issue_coverage(
    test_specs: Dict[str, Any],
    architecture_review: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate that all critical architecture issues are addressed by tests.

    Args:
        test_specs: The refined test specifications
        architecture_review: The architecture review

    Returns:
        List of validation issues with their details
    """
    validation_issues = []

    # Get all architecture issues, especially critical ones
    arch_issues = extract_architecture_issues(architecture_review)
    critical_issues = [i for i in arch_issues if i.get("severity") in ["Critical", "High"]]

    # Get all addressed issues from test specifications
    addressed_issues = extract_addressed_issues(test_specs)

    # Check for unaddressed critical issues
    for issue in critical_issues:
        issue_id = issue.get("id", "")
        description = issue.get("description", "")
        issue_type = issue.get("issue_type", "")

        # Check if issue ID or description is addressed
        is_addressed = False
        if issue_id and issue_id in addressed_issues:
            is_addressed = True
        elif description and any(description in addr for addr in addressed_issues):
            is_addressed = True

        if not is_addressed:
            # Higher severity for security concerns
            issue_severity = "Critical" if issue_type == "security_concern" else "High"

            validation_issues.append({
                "issue_type": "unaddressed_critical_issue",
                "severity": issue_severity,
                "message": f"Critical architecture issue '{issue_id or description}' is not addressed by any test",
                "issue": issue
            })

    # Check that each security concern is addressed by appropriate test types
    security_issues = [i for i in arch_issues if i.get("issue_type") == "security_concern"]
    for issue in security_issues:
        issue_id = issue.get("id", "")
        if not issue_id:
            continue

        # Check if security issue is addressed by appropriate tests
        found_in_test_types = []
        for test_type in test_specs:
            if test_type not in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
                continue

            for test in test_specs[test_type]:
                addressed_issue = test.get("architecture_issue_addressed", "")
                if issue_id in addressed_issue:
                    found_in_test_types.append(test_type)
                    break

        # Security concerns should ideally have both unit and integration tests
        if issue.get("severity") in ["Critical", "High"] and len(found_in_test_types) < 2:
            missing_test_types = []
            if "unit_tests" not in found_in_test_types:
                missing_test_types.append("unit tests")
            if "integration_tests" not in found_in_test_types:
                missing_test_types.append("integration tests")

            if missing_test_types:
                validation_issues.append({
                    "issue_type": "insufficient_security_test_coverage",
                    "severity": "High",
                    "message": f"Security concern '{issue_id}' needs more comprehensive testing coverage",
                    "issue": issue,
                    "current_coverage": found_in_test_types,
                    "missing_test_types": missing_test_types
                })

    return validation_issues

def validate_test_priority_consistency(
    test_specs: Dict[str, Any],
    architecture_review: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate that test priorities align with architecture issue severity.

    Args:
        test_specs: The refined test specifications
        architecture_review: The architecture review

    Returns:
        List of validation issues with their details
    """
    validation_issues = []
    severity_priority_map = {
        "Critical": "Critical",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low"
    }

    # Get all architecture issues with their severity
    arch_issues = extract_architecture_issues(architecture_review)
    issue_severity_map = {i.get("id", i.get("description", "")): i.get("severity", "Medium")
                           for i in arch_issues if isinstance(i, dict)}

    # Helper function to check priority consistency for a test
    def check_test_priority(test, test_type):
        if not isinstance(test, dict):
            return

        addressed_issue = test.get("architecture_issue_addressed")
        test_priority = test.get("priority")

        if not addressed_issue or not test_priority:
            return

        # Get expected priority from issue severity
        issue_severity = issue_severity_map.get(addressed_issue)
        if not issue_severity:
            # Try to match by substring in keys
            for issue_id, severity in issue_severity_map.items():
                if issue_id in addressed_issue or addressed_issue in issue_id:
                    issue_severity = severity
                    break

        if not issue_severity:
            return

        expected_priority = severity_priority_map.get(issue_severity)

        # Check if the priority is consistent with severity
        if expected_priority == "Critical" and test_priority != "Critical":
            validation_issues.append({
                "issue_type": "priority_mismatch",
                "severity": "Medium",
                "message": (f"{test_type} addressing critical issue '{addressed_issue}' "
                           f"has {test_priority} priority instead of Critical"),
                "test_description": test.get("description", ""),
                "expected_priority": expected_priority,
                "actual_priority": test_priority
            })
        elif expected_priority == "High" and test_priority not in ["High", "Critical"]:
            validation_issues.append({
                "issue_type": "priority_mismatch",
                "severity": "Medium",
                "message": (f"{test_type} addressing high severity issue '{addressed_issue}' "
                           f"has {test_priority} priority instead of High or Critical"),
                "test_description": test.get("description", ""),
                "expected_priority": expected_priority,
                "actual_priority": test_priority
            })

    # Check all test types
    for test_type in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
        for test in test_specs.get(test_type, []):
            check_test_priority(test, test_type.rstrip('s').replace('_', ' ').title())

    return validation_issues


def validate_test_completeness(
    test_specs: Dict[str, Any],
    system_design: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Validate that each system design element has at least one test."""
    validation_issues = []

    valid_ids = extract_element_ids_from_system_design(system_design)
    referenced_ids = extract_referenced_element_ids(test_specs)
    missing = valid_ids - referenced_ids

    for element_id in missing:
        validation_issues.append(
            {
                "issue_type": "missing_test_coverage",
                "severity": "Medium",
                "message": f"No tests reference element '{element_id}'",
                "element_id": element_id,
            }
        )

    return validation_issues


def generate_missing_tests_with_llm(
    router_agent,
    missing_issues: List[Dict[str, Any]],
    system_design: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Use the LLM to generate tests for missing critical issues."""
    if not router_agent or not missing_issues:
        return {}

    try:
        from .json_utils import get_openrouter_json_params, extract_json_from_text

        system_prompt = (
            "You are a test planner. Generate additional test specifications in JSON format "
            "that cover the provided critical architecture issues."
        )
        user_prompt = json.dumps(
            {
                "system_design": system_design,
                "missing_issues": missing_issues,
                "context": context or {},
            },
            indent=2,
        )

        params = get_openrouter_json_params()
        response = router_agent.call_llm_by_role(
            role="test_planner",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=params,
            scratchpad=router_agent,
        )
        json_str = extract_json_from_text(response)
        if json_str:
            data = json.loads(json_str)
            return data.get("refined_test_requirements", data)
    except Exception as e:  # pragma: no cover - best effort
        logger.error("%s", "LLM repair failed: %s", e)

    return {}

def validate_priority_alignment(
    test_specs: Dict[str, Any],
    architecture_review: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Validate that priority assignments in tests align with the architecture issues they address.

    Args:
        test_specs: The refined test specifications
        architecture_review: The architecture review

    Returns:
        List of validation issues with their details
    """
    validation_issues = []

    # Get all architecture issues with their severity and categorize by ID
    arch_issues = extract_architecture_issues(architecture_review)
    issues_by_id = {issue["id"]: issue for issue in arch_issues if issue.get("id")}

    # Define severity-to-priority mapping (with fallback priorities)
    severity_to_priority = {
        "Critical": ["Critical"],
        "High": ["Critical", "High"],
        "Medium": ["Critical", "High", "Medium"],
        "Low": ["Critical", "High", "Medium", "Low"]
    }

    # Define test type to expected thoroughness mapping
    # Higher numbers mean more thorough testing expected
    test_type_thoroughness = {
        "unit_tests": 1,
        "integration_tests": 2,
        "property_based_tests": 3,
        "acceptance_tests": 2
    }

    # Process all tests that address architecture issues
    for test_type, tests in test_specs.items():
        if test_type not in test_type_thoroughness:
            continue

        thoroughness_level = test_type_thoroughness[test_type]

        for test in tests:
            # Skip tests that don't address architecture issues
            addressed_issue_id = test.get("architecture_issue_addressed")
            if not addressed_issue_id:
                continue

            # Try to find the issue in our catalog
            issue = None
            for issue_id, issue_data in issues_by_id.items():
                if issue_id == addressed_issue_id or issue_id in addressed_issue_id or addressed_issue_id in issue_id:
                    issue = issue_data
                    break

            if not issue:
                continue  # Skip if we can't find the issue (could be referenced by description instead of ID)

            # Get test priority and issue severity
            test_priority = test.get("priority", "Medium")  # Default if not specified
            issue_severity = issue.get("severity", "Medium")
            issue_type = issue.get("issue_type", "")

            # Check if the test priority aligns with the issue severity
            allowed_priorities = severity_to_priority.get(issue_severity, ["Medium"])
            if test_priority not in allowed_priorities:
                validation_issues.append({
                    "issue_type": "priority_alignment",
                    "severity": "High" if issue_severity in ["Critical", "High"] else "Medium",
                    "message": f"{test_type.rstrip('s').replace('_', ' ').title()} addressing {issue_severity} issue '{addressed_issue_id}' has {test_priority} priority",
                    "test_id": test.get("id", ""),
                    "test_description": test.get("description", ""),
                    "issue_severity": issue_severity,
                    "test_priority": test_priority,
                    "allowed_priorities": allowed_priorities
                })

            # For critical and high severity issues, check if the test type is appropriate
            if issue_severity in ["Critical", "High"]:
                # Critical issues should have more thorough testing
                min_thoroughness = 2  # At least integration level

                if thoroughness_level < min_thoroughness and issue_type == "security_concern":
                    validation_issues.append({
                        "issue_type": "insufficient_test_coverage",
                        "severity": "High",
                        "message": f"{issue_severity} security issue '{addressed_issue_id}' has only {test_type} coverage, needs more thorough testing",
                        "test_id": test.get("id", ""),
                        "test_description": test.get("description", ""),
                        "issue_severity": issue_severity,
                        "test_type": test_type,
                        "recommended_test_types": ["integration_tests", "property_based_tests"]
                    })

    return validation_issues

def repair_invalid_element_ids(
    test_specs: Dict[str, Any],
    system_design: Dict[str, Any],
    validation_issues: List[Dict[str, Any]],
    embedding_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Attempt to repair invalid element IDs by finding closest matches.

    Args:
        test_specs: The test specifications to repair
        system_design: The system design with valid element IDs
        validation_issues: The validation issues to address

    Returns:
        Repaired test specifications
    """
    # Get valid element IDs for potential replacements
    valid_element_ids = list(extract_element_ids_from_system_design(system_design))

    # Get element name to ID mapping for better replacement suggestions
    element_name_to_id = {}
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "element_id" in element and "name" in element:
            element_name_to_id[element["name"]] = element["element_id"]

    # Track invalid IDs and their replacements
    invalid_id_replacements = {}

    # Find the most likely replacement for each invalid ID
    for issue in validation_issues:
        if issue["issue_type"] == "invalid_element_id":
            invalid_id = issue["element_id"]

            # Try semantic similarity first if embedding client available
            best_match = None
            highest_score = 0.0

            if embedding_client and hasattr(embedding_client, "generate_embedding"):
                try:
                    invalid_vec = embedding_client.generate_embedding(invalid_id)
                    for valid_id in valid_element_ids:
                        valid_vec = embedding_client.generate_embedding(valid_id)
                        if invalid_vec is not None and valid_vec is not None:
                            sim = float(np.dot(invalid_vec, valid_vec) / (np.linalg.norm(invalid_vec) * np.linalg.norm(valid_vec) + 1e-8))
                            if sim > highest_score:
                                highest_score = sim
                                best_match = valid_id
                except Exception as e:  # pragma: no cover - best effort
                    logger.error("%s", Semantic matching failed for '{invalid_id}': {e})

            # Fallback to substring/SequenceMatcher
            if not best_match:
                for valid_id in valid_element_ids:
                    ratio = SequenceMatcher(None, invalid_id.lower(), valid_id.lower()).ratio()
                    if ratio > highest_score:
                        highest_score = ratio
                        best_match = valid_id

            # If invalid ID looks like an element name, try to map to real ID
            for name, element_id in element_name_to_id.items():
                if invalid_id.lower() in name.lower() or name.lower() in invalid_id.lower():
                    if best_match is None or len(name) > highest_score * 10:  # Bias toward name matches
                        best_match = element_id

            # Set replacement if found and score is reasonable
            if best_match and highest_score > 0.3:
                invalid_id_replacements[invalid_id] = best_match
                logger.info("%s", Will replace invalid element ID '{invalid_id}' with '{best_match}')
            else:
                logger.warning("%s", Could not find suitable replacement for invalid element ID '{invalid_id}')

    # Create a deep copy of test_specs
    repaired_specs = json.loads(json.dumps(test_specs))

    # Replace invalid IDs with valid ones
    def replace_element_id(obj, key):
        if isinstance(obj, dict) and key in obj and obj[key] in invalid_id_replacements:
            old_id = obj[key]
            obj[key] = invalid_id_replacements[old_id]
            logger.info("%s", Replaced element ID '{old_id}' with '{obj[key]}')

    def replace_element_ids(obj, key):
        if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
            for i, element_id in enumerate(obj[key]):
                if element_id in invalid_id_replacements:
                    old_id = obj[key][i]
                    obj[key][i] = invalid_id_replacements[old_id]
                    logger.info("%s", Replaced element ID '{old_id}' with '{obj[key][i]}')

    # Process each test type
    for test_type, id_key in [
        ("unit_tests", "target_element_id"),
        ("property_based_tests", "target_element_id")
    ]:
        for test in repaired_specs.get(test_type, []):
            replace_element_id(test, id_key)

    for test_type, ids_key in [
        ("integration_tests", "target_element_ids"),
        ("acceptance_tests", "target_element_ids")
    ]:
        for test in repaired_specs.get(test_type, []):
            replace_element_ids(test, ids_key)

    # Process critical paths in test strategy
    for path in repaired_specs.get("test_strategy", {}).get("critical_paths", []):
        replace_element_ids(path, "element_ids")

    return repaired_specs

def assign_priorities_to_address_critical_issues(
    test_specs: Dict[str, Any],
    architecture_review: Dict[str, Any],
    validation_issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Update test priorities to ensure critical issues have appropriate priority.

    Args:
        test_specs: The test specifications to update
        architecture_review: The architecture review
        validation_issues: The validation issues to address

    Returns:
        Updated test specifications with corrected priorities
    """
    # Create a deep copy of test_specs
    updated_specs = json.loads(json.dumps(test_specs))

    # Get all architecture issues with their severity
    arch_issues = extract_architecture_issues(architecture_review)
    issue_severity_map = {i.get("id", i.get("description", "")): i.get("severity", "Medium")
                           for i in arch_issues if isinstance(i, dict)}

    severity_priority_map = {
        "Critical": "Critical",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low"
    }

    # Process priority mismatches from validation issues
    priority_updates = {}
    test_id_updates = {}

    for issue in validation_issues:
        if issue["issue_type"] in ["priority_mismatch", "priority_alignment"]:
            test_desc = issue.get("test_description", "")
            test_id = issue.get("test_id", "")

            # Handle different validation issue structures
            if "expected_priority" in issue:
                expected_priority = issue["expected_priority"]
            elif "allowed_priorities" in issue and issue["allowed_priorities"]:
                # Take the highest priority from allowed priorities
                priorities_order = ["Critical", "High", "Medium", "Low"]
                for priority in priorities_order:
                    if priority in issue["allowed_priorities"]:
                        expected_priority = priority
                        break
                else:
                    expected_priority = issue["allowed_priorities"][0]
            else:
                # Default to matching severity if no specific priority is provided
                issue_severity = issue.get("issue_severity", "Medium")
                expected_priority = severity_priority_map.get(issue_severity, "Medium")

            if test_desc:
                priority_updates[test_desc] = expected_priority
            if test_id:
                test_id_updates[test_id] = expected_priority

    # Helper function to update test priority
    def update_test_priority(test):
        if not isinstance(test, dict):
            return

        desc = test.get("description", "")
        test_id = test.get("id", "")

        # Update based on either description or ID
        if desc in priority_updates:
            old_priority = test.get("priority", "Medium")
            test["priority"] = priority_updates[desc]
            logger.info("%s", Updated test '{desc}' priority from '{old_priority}' to '{test['priority']}')
        elif test_id in test_id_updates:
            old_priority = test.get("priority", "Medium")
            test["priority"] = test_id_updates[test_id]
            logger.info("%s", Updated test ID '{test_id}' priority from '{old_priority}' to '{test['priority']}')

        # Also check if test addresses a critical issue but has no priority set
        addressed_issue = test.get("architecture_issue_addressed")
        if addressed_issue and not test.get("priority"):
            # Find severity of addressed issue
            issue_severity = None
            for issue_id, severity in issue_severity_map.items():
                if issue_id in addressed_issue or addressed_issue in issue_id:
                    issue_severity = severity
                    break

            if issue_severity:
                test["priority"] = severity_priority_map.get(issue_severity, "Medium")
                logger.info("%s", Assigned priority '{test['priority']}' to test '{desc}' based on addressed issue severity)

    # Update all test types
    for test_type in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
        for test in updated_specs.get(test_type, []):
            update_test_priority(test)

    return updated_specs

def validate_and_repair_test_specifications(
    test_specs: Dict[str, Any],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any],
    router_agent: Optional[Any] = None,
    embedding_client: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """
    Validate test specifications against system design and architecture review,
    and attempt to repair issues.

    Args:
        test_specs: The test specifications to validate
        system_design: The system design dictionary
        architecture_review: The architecture review dictionary

    Returns:
        Tuple of (repaired_specs, validation_issues, was_repaired)
    """
    all_validation_issues = []
    was_repaired = False

    # 1. Validate element IDs
    element_id_issues = validate_element_ids(test_specs, system_design)
    all_validation_issues.extend(element_id_issues)

    # 2. Validate architecture issue coverage
    coverage_issues = validate_architecture_issue_coverage(test_specs, architecture_review)
    all_validation_issues.extend(coverage_issues)

    # 3. Validate completeness relative to system design
    completeness_issues = validate_test_completeness(test_specs, system_design)
    all_validation_issues.extend(completeness_issues)

    # 4. Validate test priority consistency
    priority_issues = validate_test_priority_consistency(test_specs, architecture_review)
    all_validation_issues.extend(priority_issues)

    # 5. Validate priority alignment with architecture issues
    priority_alignment_issues = validate_priority_alignment(test_specs, architecture_review)
    all_validation_issues.extend(priority_alignment_issues)

    # Log all validation issues
    for issue in all_validation_issues:
        log_level = logging.WARNING if issue["severity"] in ["Critical", "High"] else logging.INFO
        logger.log(log_level, f"{issue['issue_type']}: {issue['message']}")

    # Return early if no issues
    if not all_validation_issues:
        return test_specs, all_validation_issues, False

    # Attempt repairs
    repaired_specs = test_specs

    # Repair invalid element IDs
    if element_id_issues:
        repaired_specs = repair_invalid_element_ids(
            repaired_specs,
            system_design,
            element_id_issues,
            embedding_client=embedding_client,
        )
        was_repaired = True

    # Update test priorities for consistency with architecture issues
    priority_related_issues = [
        i for i in all_validation_issues if i.get("issue_type") in ["priority_mismatch", "priority_alignment"]
    ]
    if priority_related_issues:
        repaired_specs = assign_priorities_to_address_critical_issues(
            repaired_specs, architecture_review, priority_related_issues
        )
        was_repaired = True

    # If critical issues are unaddressed, attempt LLM-driven repair
    missing_issue_data = [i for i in coverage_issues if i.get("issue_type") == "unaddressed_critical_issue"]
    if missing_issue_data:
        new_tests = generate_missing_tests_with_llm(router_agent, missing_issue_data, system_design, context)
        if new_tests:
            for key, tests in new_tests.items():
                if key not in repaired_specs:
                    repaired_specs[key] = []
                if isinstance(tests, list):
                    repaired_specs[key].extend(tests)
            was_repaired = True

    try:
        summary = f"{len(all_validation_issues)} issues found; repaired={was_repaired}"
        progress_tracker.update_progress({
            "phase": "test_validation",
            "status": Status.COMPLETED,
            "details": summary,
        })
    except Exception:  # pragma: no cover - best effort
        logger.debug("Failed to update progress tracker for validation results")

    return repaired_specs, all_validation_issues, was_repaired
