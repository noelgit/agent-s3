"""Test alignment helpers for implementation validation.

This module contains functions for validating alignment between implementation plans
and test requirements, including test coverage and assertion mapping.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def validate_implementation_test_alignment(
    implementation_plan: Dict[str, Any],
    test_implementations: Dict[str, Any],
    architecture_review: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Validate that the implementation plan aligns with test implementations.

    Args:
        implementation_plan: The implementation plan to validate
        test_implementations: Test implementations to check against
        architecture_review: Optional architecture review for additional context

    Returns:
        List of validation issues related to test alignment
    """
    issues = []

    if not test_implementations or "test_implementations" not in test_implementations:
        issues.append({
            "type": "missing_test_implementations",
            "severity": "medium",
            "message": "No test implementations provided for alignment validation",
            "details": {
                "recommendation": "Provide test implementations to validate alignment"
            }
        })
        return issues

    test_data = test_implementations["test_implementations"]

    # Track functions and their test coverage
    implementation_functions = _extract_implementation_functions(implementation_plan)
    test_coverage = _analyze_test_coverage(test_data, implementation_functions)

    # Check function coverage
    coverage_issues = _check_function_coverage(test_coverage, implementation_functions)
    issues.extend(coverage_issues)

    # Check assertion alignment
    assertion_issues = _check_assertion_alignment(implementation_plan, test_data)
    issues.extend(assertion_issues)

    # Check edge case coverage
    edge_case_issues = _check_edge_case_coverage(implementation_plan, test_data)
    issues.extend(edge_case_issues)

    # Check error handling alignment
    error_handling_issues = _check_error_handling_alignment(implementation_plan, test_data)
    issues.extend(error_handling_issues)

    return issues


def extract_assertions(test_implementations: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract assertions from test implementations.

    Args:
        test_implementations: Test implementation data

    Returns:
        Dictionary mapping test files to their assertions
    """
    assertions = {}

    if "test_implementations" not in test_implementations:
        return assertions

    test_data = test_implementations["test_implementations"]

    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            # Extract assertions from test code
            file_assertions = _extract_assertions_from_code(test_content)
            if file_assertions:
                assertions[test_file] = file_assertions

        elif isinstance(test_content, dict):
            # Extract from structured test data
            test_cases = test_content.get("test_cases", [])
            file_assertions = []

            for test_case in test_cases:
                if isinstance(test_case, dict):
                    test_assertions = test_case.get("assertions", [])
                    file_assertions.extend(test_assertions)

            if file_assertions:
                assertions[test_file] = file_assertions

    return assertions


def extract_edge_cases(test_implementations: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract edge cases from test implementations.

    Args:
        test_implementations: Test implementation data

    Returns:
        Dictionary mapping test files to their edge cases
    """
    edge_cases = {}

    if "test_implementations" not in test_implementations:
        return edge_cases

    test_data = test_implementations["test_implementations"]

    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            # Extract edge cases from test code
            file_edge_cases = _extract_edge_cases_from_code(test_content)
            if file_edge_cases:
                edge_cases[test_file] = file_edge_cases

        elif isinstance(test_content, dict):
            # Extract from structured test data
            test_cases = test_content.get("test_cases", [])
            file_edge_cases = []

            for test_case in test_cases:
                if isinstance(test_case, dict):
                    case_edge_cases = test_case.get("edge_cases", [])
                    file_edge_cases.extend(case_edge_cases)

            if file_edge_cases:
                edge_cases[test_file] = file_edge_cases

    return edge_cases


def extract_expected_behaviors(test_implementations: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Extract expected behaviors from test implementations.

    Args:
        test_implementations: Test implementation data

    Returns:
        Dictionary mapping test files to their expected behaviors
    """
    behaviors = {}

    if "test_implementations" not in test_implementations:
        return behaviors

    test_data = test_implementations["test_implementations"]

    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            # Extract behaviors from test descriptions and docstrings
            file_behaviors = _extract_behaviors_from_code(test_content)
            if file_behaviors:
                behaviors[test_file] = file_behaviors

        elif isinstance(test_content, dict):
            # Extract from structured test data
            test_cases = test_content.get("test_cases", [])
            file_behaviors = []

            for test_case in test_cases:
                if isinstance(test_case, dict):
                    description = test_case.get("description", "")
                    expected = test_case.get("expected_behavior", "")
                    if description:
                        file_behaviors.append(description)
                    if expected:
                        file_behaviors.append(expected)

            if file_behaviors:
                behaviors[test_file] = file_behaviors

    return behaviors


def _extract_implementation_functions(implementation_plan: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract functions from implementation plan by file."""
    functions_by_file = {}

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        file_functions = []
        for function in functions:
            if isinstance(function, dict) and "function" in function:
                function_signature = function["function"]
                # Extract function name from signature
                name_match = re.search(r'(?:def|class)\\s+(\\w+)', function_signature)
                if name_match:
                    file_functions.append(name_match.group(1))

        if file_functions:
            functions_by_file[file_path] = file_functions

    return functions_by_file


def _analyze_test_coverage(test_data: Dict[str, Any], implementation_functions: Dict[str, List[str]]) -> Dict[str, Dict[str, bool]]:
    """Analyze which functions are covered by tests."""
    coverage = {}

    for impl_file, functions in implementation_functions.items():
        file_coverage = {}

        for function_name in functions:
            # Check if function is tested
            is_tested = _function_has_tests(function_name, test_data)
            file_coverage[function_name] = is_tested

        coverage[impl_file] = file_coverage

    return coverage


def _check_function_coverage(test_coverage: Dict[str, Dict[str, bool]], implementation_functions: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Check test coverage for implementation functions."""
    issues = []

    total_functions = 0
    tested_functions = 0
    untested_functions = []

    for file_path, functions in implementation_functions.items():
        file_coverage = test_coverage.get(file_path, {})

        for function_name in functions:
            total_functions += 1
            if file_coverage.get(function_name, False):
                tested_functions += 1
            else:
                untested_functions.append(f"{file_path}::{function_name}")

    # Calculate coverage percentage
    coverage_percentage = (tested_functions / total_functions * 100) if total_functions > 0 else 0

    if coverage_percentage < 80:  # Less than 80% coverage
        issues.append({
            "type": "low_test_coverage",
            "severity": "high" if coverage_percentage < 50 else "medium",
            "message": f"Test coverage is only {coverage_percentage:.1f}% ({tested_functions}/{total_functions} functions)",
            "details": {
                "untested_functions": untested_functions[:10],  # Show first 10
                "total_untested": len(untested_functions),
                "recommendation": "Add tests for uncovered functions to improve test coverage"
            }
        })

    return issues


def _check_assertion_alignment(implementation_plan: Dict[str, Any], test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check if implementation steps align with test assertions."""
    issues = []

    # Extract assertions from tests
    test_assertions = {}
    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            assertions = _extract_assertions_from_code(test_content)
            test_assertions[test_file] = assertions

    # Check if implementation addresses assertions
    unaddressed_assertions = []

    for test_file, assertions in test_assertions.items():
        for assertion in assertions:
            # Check if any implementation step addresses this assertion
            if not _assertion_addressed_in_implementation(assertion, implementation_plan):
                unaddressed_assertions.append(f"{test_file}: {assertion}")

    if unaddressed_assertions:
        issues.append({
            "type": "unaddressed_assertions",
            "severity": "medium",
            "message": f"{len(unaddressed_assertions)} test assertions not addressed in implementation",
            "details": {
                "unaddressed_assertions": unaddressed_assertions[:5],
                "total_unaddressed": len(unaddressed_assertions),
                "recommendation": "Ensure implementation steps address all test assertions"
            }
        })

    return issues


def _check_edge_case_coverage(implementation_plan: Dict[str, Any], test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check if implementation covers edge cases tested."""
    issues = []

    # Extract edge cases from tests
    test_edge_cases = {}
    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            edge_cases = _extract_edge_cases_from_code(test_content)
            test_edge_cases[test_file] = edge_cases

    # Check if implementation handles edge cases
    unhandled_edge_cases = []

    for test_file, edge_cases in test_edge_cases.items():
        for edge_case in edge_cases:
            # Check if implementation handles this edge case
            if not _edge_case_handled_in_implementation(edge_case, implementation_plan):
                unhandled_edge_cases.append(f"{test_file}: {edge_case}")

    if unhandled_edge_cases:
        issues.append({
            "type": "unhandled_edge_cases",
            "severity": "medium",
            "message": f"{len(unhandled_edge_cases)} edge cases not handled in implementation",
            "details": {
                "unhandled_edge_cases": unhandled_edge_cases[:5],
                "total_unhandled": len(unhandled_edge_cases),
                "recommendation": "Add edge case handling to implementation"
            }
        })

    return issues


def _check_error_handling_alignment(implementation_plan: Dict[str, Any], test_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check if error handling aligns with tests."""
    issues = []

    # Extract expected errors from tests
    expected_errors = _extract_expected_errors_from_tests(test_data)

    # Extract implemented error handling
    implemented_errors = _extract_implemented_error_handling(implementation_plan)

    # Check alignment
    missing_error_handling = []
    for expected_error in expected_errors:
        if not any(expected_error.lower() in impl_error.lower() for impl_error in implemented_errors):
            missing_error_handling.append(expected_error)

    if missing_error_handling:
        issues.append({
            "type": "missing_error_handling",
            "severity": "medium",
            "message": f"{len(missing_error_handling)} expected error cases not implemented",
            "details": {
                "missing_errors": missing_error_handling[:5],
                "recommendation": "Implement error handling for all expected error cases"
            }
        })

    return issues


# Helper functions for parsing test content
def _extract_assertions_from_code(code: str) -> List[str]:
    """Extract assertion statements from test code."""
    assertions = []

    # Common assertion patterns
    patterns = [
        r'assert\\s+(.+)',
        r'assertEqual\\s*\\((.+?)\\)',
        r'assertTrue\\s*\\((.+?)\\)',
        r'assertFalse\\s*\\((.+?)\\)',
        r'expect\\s*\\((.+?)\\)',
        r'\\.toEqual\\s*\\((.+?)\\)',
        r'\\.toBe\\s*\\((.+?)\\)'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, code, re.MULTILINE)
        assertions.extend(matches)

    return assertions


def _extract_edge_cases_from_code(code: str) -> List[str]:
    """Extract edge cases from test code."""
    edge_cases = []

    # Look for edge case indicators
    patterns = [
        r'edge\\s+case[:\\s]+(.+)',
        r'boundary[:\\s]+(.+)',
        r'limit[:\\s]+(.+)',
        r'empty\\s+(.+)',
        r'null\\s+(.+)',
        r'invalid\\s+(.+)'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, code.lower(), re.MULTILINE)
        edge_cases.extend(matches)

    return edge_cases


def _extract_behaviors_from_code(code: str) -> List[str]:
    """Extract expected behaviors from test descriptions."""
    behaviors = []

    # Look for test descriptions
    patterns = [
        r'"""([^"]+)"""',
        r"'''([^']+)'''",
        r'#\\s*(.+)',
        r'describe\\s*\\(["\']([^"\']+)["\']',
        r'it\\s*\\(["\']([^"\']+)["\']'
    ]

    for pattern in patterns:
        matches = re.findall(pattern, code, re.MULTILINE | re.DOTALL)
        behaviors.extend(matches)

    return behaviors


def _function_has_tests(function_name: str, test_data: Dict[str, Any]) -> bool:
    """Check if a function has tests."""
    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            if function_name in test_content:
                return True
    return False


def _assertion_addressed_in_implementation(assertion: str, implementation_plan: Dict[str, Any]) -> bool:
    """Check if an assertion is addressed in the implementation."""
    assertion_keywords = assertion.lower().split()

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check implementation steps and description
            impl_text = f"{function.get('description', '')} {' '.join(function.get('implementation_steps', []))}"

            # Simple keyword matching
            if any(keyword in impl_text.lower() for keyword in assertion_keywords if len(keyword) > 3):
                return True

    return False


def _edge_case_handled_in_implementation(edge_case: str, implementation_plan: Dict[str, Any]) -> bool:
    """Check if an edge case is handled in the implementation."""
    edge_case_keywords = edge_case.lower().split()

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check error handling and implementation steps
            error_handling = function.get('error_handling', [])
            impl_steps = function.get('implementation_steps', [])

            all_text = f"{' '.join(impl_steps)} {' '.join(str(eh) for eh in error_handling)}"

            # Check for edge case handling
            if any(keyword in all_text.lower() for keyword in edge_case_keywords if len(keyword) > 3):
                return True

    return False


def _extract_expected_errors_from_tests(test_data: Dict[str, Any]) -> List[str]:
    """Extract expected errors from test implementations."""
    expected_errors = []

    for test_file, test_content in test_data.items():
        if isinstance(test_content, str):
            # Look for error expectations in tests
            patterns = [
                r'expect.*Error',
                r'assertRaises\\s*\\(([^)]+)\\)',
                r'pytest\\.raises\\s*\\(([^)]+)\\)',
                r'throws?\\s*\\(([^)]+)\\)'
            ]

            for pattern in patterns:
                matches = re.findall(pattern, test_content)
                expected_errors.extend(matches)

    return expected_errors


def _extract_implemented_error_handling(implementation_plan: Dict[str, Any]) -> List[str]:
    """Extract implemented error handling from implementation plan."""
    implemented_errors = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            error_handling = function.get('error_handling', [])
            for error_case in error_handling:
                if isinstance(error_case, dict):
                    error_type = error_case.get('type', '')
                    if error_type:
                        implemented_errors.append(error_type)
                elif isinstance(error_case, str):
                    implemented_errors.append(error_case)

    return implemented_errors
