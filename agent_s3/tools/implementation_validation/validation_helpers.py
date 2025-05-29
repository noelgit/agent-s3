"""Validation helper functions for implementation validation.

This module contains general helper functions used across the implementation
validation process, including extraction utilities and basic validation checks.
"""

import re
import logging
from typing import Dict, Any, List, Set

logger = logging.getLogger(__name__)


def extract_element_ids_from_system_design(system_design: Dict[str, Any]) -> Set[str]:
    """
    Extract all element IDs from system design.

    Args:
        system_design: System design data containing code elements

    Returns:
        Set of element IDs found in the system design
    """
    element_ids = set()

    if not isinstance(system_design, dict):
        return element_ids

    # Check for code_elements in various locations
    code_elements = system_design.get("code_elements", [])
    if isinstance(code_elements, list):
        for element in code_elements:
            if isinstance(element, dict) and "element_id" in element:
                element_ids.add(element["element_id"])

    # Check for nested structures that might contain elements
    for key, value in system_design.items():
        if isinstance(value, dict):
            nested_ids = extract_element_ids_from_system_design(value)
            element_ids.update(nested_ids)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested_ids = extract_element_ids_from_system_design(item)
                    element_ids.update(nested_ids)

    return element_ids


def extract_architecture_issues(architecture_review: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract architecture issues from the architecture review.

    Args:
        architecture_review: Architecture review data

    Returns:
        List of architecture issues
    """
    issues = []

    if not isinstance(architecture_review, dict):
        return issues

    # Extract logical gaps
    logical_gaps = architecture_review.get("logical_gaps", [])
    if isinstance(logical_gaps, list):
        for gap in logical_gaps:
            if isinstance(gap, dict):
                gap["issue_type"] = "logical_gap"
                issues.append(gap)

    # Extract security concerns
    security_review = architecture_review.get("security_review", {})
    if isinstance(security_review, dict):
        security_concerns = security_review.get("security_concerns", [])
        if isinstance(security_concerns, list):
            for concern in security_concerns:
                if isinstance(concern, dict):
                    concern["issue_type"] = "security_concern"
                    issues.append(concern)

    # Extract optimization suggestions
    optimization_suggestions = architecture_review.get("optimization_suggestions", [])
    if isinstance(optimization_suggestions, list):
        for suggestion in optimization_suggestions:
            if isinstance(suggestion, dict):
                suggestion["issue_type"] = "optimization_suggestion"
                issues.append(suggestion)

    # Extract any other issues
    for key, value in architecture_review.items():
        if key.endswith("_issues") and isinstance(value, list):
            for issue in value:
                if isinstance(issue, dict):
                    issue["issue_type"] = key
                    issues.append(issue)

    return issues


def extract_test_requirements(test_implementations: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract test requirements organized by type.

    Args:
        test_implementations: Test implementation data

    Returns:
        Dictionary mapping test types to their requirements
    """
    test_requirements = {
        "unit_tests": [],
        "acceptance_tests": [],
        "edge_cases": [],
        "error_scenarios": []
    }

    if not isinstance(test_implementations, dict):
        return test_requirements

    # Extract from test_implementations structure
    test_data = test_implementations.get("test_implementations", {})
    if isinstance(test_data, dict):
        for test_file, test_content in test_data.items():
            if isinstance(test_content, str):
                # Parse test content to extract requirements
                _parse_test_content_for_requirements(test_content, test_requirements, test_file)
            elif isinstance(test_content, dict):
                # Extract from structured test data
                _extract_structured_test_requirements(test_content, test_requirements, test_file)

    return test_requirements


def validate_single_function(
    function: Dict[str, Any],
    file_path: str,
    system_design_element_ids: Set[str],
    architecture_issues: List[Dict[str, Any]],
    test_requirements: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Validate a single function in the implementation plan.

    Args:
        function: Function definition to validate
        file_path: Path to the file containing the function
        system_design_element_ids: Set of valid element IDs from system design
        architecture_issues: List of architecture issues to check against
        test_requirements: Test requirements to validate against

    Returns:
        List of validation issues for this function
    """
    issues = []

    if not isinstance(function, dict):
        issues.append({
            "type": "invalid_function_structure",
            "severity": "high",
            "message": "Function is not a dictionary",
            "file_path": file_path
        })
        return issues

    # Check required fields
    required_fields = ["function", "description", "implementation_steps"]
    for field in required_fields:
        if field not in function:
            issues.append({
                "type": "missing_required_field",
                "severity": "high",
                "message": f"Function missing required field: {field}",
                "file_path": file_path,
                "function": function.get("function", "unknown")
            })

    # Validate element_id references
    element_id = function.get("element_id")
    if element_id and element_id not in system_design_element_ids:
        issues.append({
            "type": "invalid_element_id",
            "severity": "medium",
            "message": f"Function references unknown element_id: {element_id}",
            "file_path": file_path,
            "function": function.get("function", "unknown"),
            "element_id": element_id
        })

    # Validate implementation steps
    impl_steps = function.get("implementation_steps", [])
    if not isinstance(impl_steps, list):
        issues.append({
            "type": "invalid_implementation_steps",
            "severity": "medium",
            "message": "Implementation steps must be a list",
            "file_path": file_path,
            "function": function.get("function", "unknown")
        })
    elif len(impl_steps) == 0:
        issues.append({
            "type": "empty_implementation_steps",
            "severity": "medium",
            "message": "Function has no implementation steps",
            "file_path": file_path,
            "function": function.get("function", "unknown")
        })

    # Validate function signature
    function_signature = function.get("function", "")
    if function_signature:
        signature_issues = _validate_function_signature(function_signature, file_path)
        issues.extend(signature_issues)

    # Check error handling
    error_handling = function.get("error_handling", [])
    if not error_handling:
        issues.append({
            "type": "missing_error_handling",
            "severity": "low",
            "message": "Function has no error handling specified",
            "file_path": file_path,
            "function": function.get("function", "unknown")
        })

    return issues


def validate_architecture_issue_coverage(
    implementation_plan: Dict[str, Any],
    architecture_issues: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate that architecture issues are properly addressed.

    Args:
        implementation_plan: The implementation plan to validate
        architecture_issues: List of architecture issues from review

    Returns:
        List of validation issues related to architecture coverage
    """
    issues = []

    if not architecture_issues:
        return issues

    # Map architecture issues by ID for easy lookup
    issues_by_id = {}
    for issue in architecture_issues:
        issue_id = issue.get("id")
        if issue_id:
            issues_by_id[issue_id] = issue

    # Track which issues are addressed
    addressed_issues = set()

    # Check each function for architecture issue coverage
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check if function addresses any architecture issues
            architecture_issues_addressed = function.get("architecture_issues_addressed", [])
            for issue_id in architecture_issues_addressed:
                if issue_id in issues_by_id:
                    addressed_issues.add(issue_id)
                else:
                    issues.append({
                        "type": "invalid_architecture_issue_reference",
                        "severity": "medium",
                        "message": f"Function references unknown architecture issue: {issue_id}",
                        "file_path": file_path,
                        "function": function.get("function", "unknown"),
                        "issue_id": issue_id
                    })

    # Check for unaddressed critical and high severity issues
    unaddressed_critical = []
    unaddressed_high = []
    unaddressed_other = []

    for issue_id, issue in issues_by_id.items():
        if issue_id not in addressed_issues:
            severity = issue.get("severity", "unknown").lower()
            if severity == "critical":
                unaddressed_critical.append(issue)
            elif severity == "high":
                unaddressed_high.append(issue)
            else:
                unaddressed_other.append(issue)

    # Report unaddressed issues
    if unaddressed_critical:
        issues.append({
            "type": "unaddressed_critical_issues",
            "severity": "critical",
            "message": f"{len(unaddressed_critical)} critical architecture issues not addressed",
            "details": {
                "unaddressed_issues": unaddressed_critical,
                "recommendation": "All critical issues must be addressed in implementation"
            }
        })

    if unaddressed_high:
        issues.append({
            "type": "unaddressed_high_issues",
            "severity": "high",
            "message": f"{len(unaddressed_high)} high-severity architecture issues not addressed",
            "details": {
                "unaddressed_issues": unaddressed_high,
                "recommendation": "High-severity issues should be addressed in implementation"
            }
        })

    if len(unaddressed_other) > len(issues_by_id) * 0.3:  # More than 30% unaddressed
        issues.append({
            "type": "low_architecture_coverage",
            "severity": "medium",
            "message": f"{len(unaddressed_other)} architecture issues not addressed",
            "details": {
                "unaddressed_count": len(unaddressed_other),
                "total_issues": len(issues_by_id),
                "coverage_percentage": f"{(len(addressed_issues) / len(issues_by_id) * 100):.1f}%",
                "recommendation": "Consider addressing more architecture issues for better coverage"
            }
        })

    return issues


def element_needs_implementation(element_id: str, system_design: Dict[str, Any]) -> bool:
    """
    Check if a system design element needs implementation.

    Args:
        element_id: The element ID to check
        system_design: System design data

    Returns:
        True if the element needs implementation, False otherwise
    """
    if not isinstance(system_design, dict):
        return False

    # Find the element in system design
    code_elements = system_design.get("code_elements", [])
    if isinstance(code_elements, list):
        for element in code_elements:
            if isinstance(element, dict) and element.get("element_id") == element_id:
                # Check if element type requires implementation
                element_type = element.get("type", "")
                implementation_types = ["function", "class", "method", "component", "module"]
                return element_type.lower() in implementation_types

    return False


def _validate_function_signature(signature: str, file_path: str) -> List[Dict[str, Any]]:
    """Validate a function signature."""
    issues = []

    # Check for basic function structure
    if not signature.strip().startswith(("def ", "class ", "async def ")):
        issues.append({
            "type": "invalid_function_signature",
            "severity": "high",
            "message": "Function signature must start with 'def', 'class', or 'async def'",
            "file_path": file_path,
            "signature": signature
        })

    # Check for proper naming convention
    if signature.strip().startswith("def "):
        name_match = re.search(r'def\\s+(\\w+)', signature)
        if name_match:
            function_name = name_match.group(1)
            if not re.match(r'^[a-z_][a-z0-9_]*$', function_name):
                issues.append({
                    "type": "invalid_function_naming",
                    "severity": "low",
                    "message": f"Function name '{function_name}' doesn't follow snake_case convention",
                    "file_path": file_path,
                    "function_name": function_name
                })

    # Check for type hints (recommended but not required)
    if "->" not in signature and "def " in signature:
        issues.append({
            "type": "missing_return_type_hint",
            "severity": "low",
            "message": "Function signature missing return type hint",
            "file_path": file_path,
            "signature": signature
        })

    return issues


def _parse_test_content_for_requirements(
    test_content: str,
    test_requirements: Dict[str, List[Dict[str, Any]]],
    test_file: str
) -> None:
    """Parse test content string to extract requirements."""
    # Look for test functions and their requirements
    test_function_pattern = r'def\\s+test_([^(]+)\\s*\\([^)]*\\):'
    matches = re.findall(test_function_pattern, test_content)

    for test_name in matches:
        # Determine test type based on name patterns
        if any(keyword in test_name.lower() for keyword in ['unit', 'single', 'isolated']):
            test_type = 'unit_tests'
        elif any(keyword in test_name.lower() for keyword in ['integration', 'combined', 'workflow']):
            test_type = 'acceptance_tests'
        elif any(keyword in test_name.lower() for keyword in ['acceptance', 'end_to_end', 'e2e']):
            test_type = 'acceptance_tests'
        elif any(keyword in test_name.lower() for keyword in ['edge', 'boundary', 'limit']):
            test_type = 'edge_cases'
        elif any(keyword in test_name.lower() for keyword in ['error', 'exception', 'failure']):
            test_type = 'error_scenarios'
        else:
            test_type = 'unit_tests'  # Default

        test_requirements[test_type].append({
            "test_name": test_name,
            "test_file": test_file,
            "description": f"Test function: {test_name}"
        })


def _extract_structured_test_requirements(
    test_content: Dict[str, Any],
    test_requirements: Dict[str, List[Dict[str, Any]]],
    test_file: str
) -> None:
    """Extract requirements from structured test data."""
    # Handle different structured formats
    test_cases = test_content.get("test_cases", [])
    if isinstance(test_cases, list):
        for test_case in test_cases:
            if isinstance(test_case, dict):
                test_type = test_case.get("type", "unit_tests")
                if test_type not in test_requirements:
                    test_type = "unit_tests"

                test_requirements[test_type].append({
                    "test_name": test_case.get("name", "unknown"),
                    "test_file": test_file,
                    "description": test_case.get("description", ""),
                    "test_case": test_case
                })
