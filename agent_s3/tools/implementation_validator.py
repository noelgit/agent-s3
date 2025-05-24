"""
Implementation Plan Validator Module

This module provides validation and repair functions for implementation plans.
It focuses on ensuring implementation plans are structurally correct, comprehensive,
aligned with the system design, and address issues raised in architecture review.
"""

import json
import logging
import re
import difflib
from typing import Dict, Any, List, Set, Tuple

from .validation_result import ValidationResult
from collections import defaultdict

# Import canonical and coherence validators
from agent_s3.tools.canonical_validator import (
    validate_canonical_implementations,
    repair_duplicate_implementations,
    repair_missing_canonical_paths
)
from agent_s3.tools.coherence_validator import (
    validate_implementation_coherence,
    calculate_coherence_metrics,
    repair_inconsistent_patterns
)

logger = logging.getLogger(__name__)


class ImplementationPlanValidationError(Exception):
    """Exception raised when validation of implementation plans fails."""
    pass


def validate_implementation_plan(
    implementation_plan: Dict[str, Any],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any],
    test_implementations: Dict[str, Any]
) -> ValidationResult:
    """
    Validate implementation plan against system design, architecture review, and test implementations.

    Args:
        implementation_plan: The implementation plan to validate
        system_design: The system design data
        architecture_review: The architecture review data
        test_implementations: The test implementations data

    Returns:
        ValidationResult containing the validated plan and issues
    """
    validation_issues = []
    needs_repair = False

    # Extract element IDs from system design for validation
    element_ids = _extract_element_ids_from_system_design(system_design)

    # Extract architecture issues for validation
    architecture_issues = _extract_architecture_issues(architecture_review)

    # Extract test requirements for validation
    test_requirements = _extract_test_requirements(test_implementations)

    # Create a deep copy of implementation plan for potential repairs
    validated_plan = json.loads(json.dumps(implementation_plan))

    # Validate overall structure
    if not isinstance(implementation_plan, dict):
        validation_issues.append({
            "issue_type": "structure",
            "severity": "critical",
            "description": "Implementation plan must be a dictionary mapping file paths to function lists"
        })
        needs_repair = True
        # Early return since the structure is fundamentally wrong
        return validated_plan, validation_issues, needs_repair

    # Check for empty implementation plan
    if not implementation_plan:
        validation_issues.append({
            "issue_type": "empty_plan",
            "severity": "critical",
            "description": "Implementation plan is empty"
        })
        needs_repair = True
        return validated_plan, validation_issues, needs_repair

    # Track element IDs that have been implemented
    implemented_element_ids = set()

    # Validate each file in the implementation plan
    for file_path, functions in implementation_plan.items():
        # Validate file path
        if not isinstance(file_path, str):
            validation_issues.append({
                "issue_type": "invalid_file_path",
                "severity": "critical",
                "description": f"File path must be a string, got {type(file_path)}"
            })
            needs_repair = True
            continue

        # Validate functions list
        if not isinstance(functions, list):
            validation_issues.append({
                "issue_type": "invalid_functions_format",
                "severity": "critical",
                "description": f"Functions for file '{file_path}' must be a list, got {type(functions)}"
            })
            needs_repair = True
            continue

        # Validate each function in the file
        for idx, function in enumerate(functions):
            function_issues = _validate_single_function(
                function,
                file_path,
                idx,
                element_ids,
                architecture_issues,
                test_requirements
            )

            # Add any issues found
            for issue in function_issues:
                validation_issues.append(issue)
                if issue["severity"] in ["critical", "high"]:
                    needs_repair = True

            # Track implemented element IDs
            if "element_id" in function:
                implemented_element_ids.add(function["element_id"])

    # Check for missing element implementations
    for element_id in element_ids:
        if element_id not in implemented_element_ids:
            # Check if this element is required to be implemented
            # Some elements might be interfaces or abstract classes that don't need direct implementation
            element_needs_implementation = _element_needs_implementation(element_id, system_design)
            if element_needs_implementation:
                validation_issues.append({
                    "issue_type": "missing_element_implementation",
                    "severity": "high",
                    "description": f"No implementation found for element_id: {element_id}",
                    "element_id": element_id
                })
                needs_repair = True

    # Validate canonical implementations
    canonical_result = validate_canonical_implementations(validated_plan, element_ids)
    validation_issues.extend(canonical_result.issues)
    if canonical_result.needs_repair:
        needs_repair = True

    # Validate implementation coherence
    coherence_result = validate_implementation_coherence(validated_plan)
    validation_issues.extend(coherence_result.issues)
    if coherence_result.needs_repair:
        needs_repair = True

    # Validate coverage of architecture issues
    coverage_issues = _validate_architecture_issue_coverage(
        validated_plan,
        architecture_issues
    )

    for issue in coverage_issues:
        validation_issues.append(issue)
        if issue["severity"] in ["critical", "high"]:
            needs_repair = True

    # Calculate implementation plan metrics
    metrics = _calculate_implementation_metrics(
        validated_plan,
        element_ids,
        architecture_issues,
        test_requirements
    )

    # Run additional validation checks with new specialized functions

    # Validate implementation quality based on metrics
    quality_issues = _validate_implementation_quality(validated_plan, metrics)
    for issue in quality_issues:
        validation_issues.append(issue)
        if issue["severity"] in ["critical", "high"]:
            needs_repair = True

    # Validate security implementation
    security_issues = _validate_implementation_security(validated_plan, architecture_issues)
    for issue in security_issues:
        validation_issues.append(issue)
        if issue["severity"] in ["critical", "high"]:
            needs_repair = True

    # Validate test alignment
    test_alignment_issues = _validate_implementation_test_alignment(validated_plan, test_requirements)
    for issue in test_alignment_issues:
        validation_issues.append(issue)
        if issue["severity"] in ["critical", "high"]:
            needs_repair = True

    # Add metrics to validation results
    if metrics["overall_score"] < 0.7:  # threshold for needing improvement
        validation_issues.append({
            "issue_type": "low_quality_score",
            "severity": "medium",
            "description": f"Implementation plan quality score is low: {metrics['overall_score']:.2f}",
            "metrics": metrics,
        })

    return ValidationResult(
        data=validated_plan,
        issues=validation_issues,
        needs_repair=needs_repair,
        metrics=metrics,
    )


def repair_implementation_plan(
    implementation_plan: Dict[str, Any],
    validation_issues: List[Dict[str, Any]],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any],
    test_implementations: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Attempt to repair implementation plan based on validation issues.

    Args:
        implementation_plan: The implementation plan to repair
        validation_issues: List of validation issues to address
        system_design: The system design data
        architecture_review: The architecture review data
        test_implementations: The test implementations data

    Returns:
        Repaired implementation plan
    """
    # Create a deep copy for repairs
    repaired_plan = json.loads(json.dumps(implementation_plan))

    # Ensure the basic structure exists
    if not isinstance(repaired_plan, dict):
        repaired_plan = {}

    # Group issues by type for targeted repairs
    issues_by_type = defaultdict(list)
    for issue in validation_issues:
        issues_by_type[issue.get("issue_type", "")].append(issue)

    # Fix structural issues first
    if "structure" in issues_by_type or "empty_plan" in issues_by_type:
        repaired_plan = _repair_structure(repaired_plan, system_design)

    # Fix invalid file paths
    if "invalid_file_path" in issues_by_type:
        repaired_plan = _repair_file_paths(repaired_plan, issues_by_type["invalid_file_path"])

    # Fix invalid function formats
    if "invalid_functions_format" in issues_by_type:
        repaired_plan = _repair_functions_format(repaired_plan, issues_by_type["invalid_functions_format"])

    # Fix missing element implementations
    if "missing_element_implementation" in issues_by_type:
        repaired_plan = _repair_missing_elements(
            repaired_plan,
            issues_by_type["missing_element_implementation"],
            system_design
        )

    # Fix invalid element IDs
    if "invalid_element_id" in issues_by_type:
        repaired_plan = _repair_element_id_references(
            repaired_plan,
            issues_by_type["invalid_element_id"],
            system_design
        )

    # Fix incomplete function implementations
    if "incomplete_implementation" in issues_by_type or "missing_steps" in issues_by_type:
        repaired_plan = _repair_incomplete_implementations(
            repaired_plan,
            issues_by_type.get("incomplete_implementation", []) +
                 issues_by_type.get("missing_steps", []),            system_design,
            test_implementations
        )

    # Fix unaddressed architecture issues
    if "unaddressed_critical_issue" in issues_by_type:
        repaired_plan = _repair_architecture_issue_coverage(
            repaired_plan,
            issues_by_type["unaddressed_critical_issue"],
            architecture_review
        )

    # Fix duplicate implementations
    if "duplicate_implementation" in issues_by_type:
        repaired_plan = repair_duplicate_implementations(
            repaired_plan,
            issues_by_type["duplicate_implementation"]
        )

    # Fix missing canonical paths
    if "missing_canonical_path" in issues_by_type or "missing_canonical_paths_section" in issues_by_type:
        missing_path_issues = issues_by_type.get("missing_canonical_path", []) +
             issues_by_type.get("missing_canonical_paths_section", [])        repaired_plan = repair_missing_canonical_paths(
            repaired_plan,
            missing_path_issues
        )

    # Fix inconsistent patterns
    pattern_issue_types = [
        "inconsistent_naming_convention",
        "inconsistent_error_handling",
        "inconsistent_api_design",
        "inconsistent_data_flow"
    ]

    pattern_issues = []
    for issue_type in pattern_issue_types:
        if issue_type in issues_by_type:
            pattern_issues.extend(issues_by_type[issue_type])

    if pattern_issues:
        repaired_plan = repair_inconsistent_patterns(
            repaired_plan,
            pattern_issues
        )

    return repaired_plan


def _extract_element_ids_from_system_design(system_design: Dict[str, Any]) -> Set[str]:
    """Extract all element IDs from the system design."""
    element_ids = set()

    # Extract from code_elements
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "element_id" in element:
            element_ids.add(element["element_id"])

    return element_ids


def _extract_architecture_issues(architecture_review: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all architecture issues from the architecture review."""
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
                "severity": issue.get("severity", "High"),
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

    return issues


def _extract_test_requirements(test_implementations: Dict[str, Any]) -> Dict[str, List[Dict[str,
     Any]]]:    """Extract test requirements from test implementations."""
    requirements = defaultdict(list)

    if not isinstance(test_implementations, dict) or "tests" not in test_implementations:
        return requirements

    for category in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
        for test in test_implementations.get("tests", {}).get(category, []):
            if isinstance(test, dict) and "target_element_ids" in test:
                for element_id in test.get("target_element_ids", []):
                    # Extract assertions and behaviors from test code
                    requirements[element_id].append({
                        "test_name": test.get("name", ""),
                        "test_category": category,
                        "assertions": _extract_assertions_from_test(test.get("code", "")),
                        "code": test.get("code", "")
                    })

    return requirements


def _extract_assertions_from_test(test_code: str) -> List[str]:
    """Extract assertions from test code."""
    assertions = []
    assertion_pattern = r'assert\w*\s*\(.*?\)'

    matches = re.findall(assertion_pattern, test_code)
    for match in matches:
        assertions.append(match.strip())

    return assertions


def _validate_single_function(
    function: Dict[str, Any],
    file_path: str,
    function_index: int,
    element_ids: Set[str],
    architecture_issues: List[Dict[str, Any]],
    test_requirements: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """Validate a single function implementation."""
    issues = []

    # Check required fields
    required_fields = ["function", "description", "element_id", "steps"]
    for field in required_fields:
        if field not in function:
            issues.append({
                "issue_type": "missing_field",
                "severity": "high",
                "description": f"Function at index {function_index} in file '{file_path}' missing required field: {field}",
                "file_path": file_path,
                "function_index": function_index
            })

    # Skip further validation if essential fields are missing
    if "element_id" not in function or "steps" not in function:
        return issues

    # Validate element ID
    element_id = function.get("element_id", "")
    if element_id not in element_ids:
        issues.append({
            "issue_type": "invalid_element_id",
            "severity": "high",
            "description": f"Function references non-existent element_id: {element_id}",
            "file_path": file_path,
            "function_index": function_index,
            "invalid_id": element_id
        })

    # Validate steps
    steps = function.get("steps", [])
    if not isinstance(steps, list):
        issues.append({
            "issue_type": "invalid_steps_format",
            "severity": "high",
            "description": f"Steps must be a list, got {type(steps)}",
            "file_path": file_path,
            "function_index": function_index
        })
    elif not steps:
        issues.append({
            "issue_type": "missing_steps",
            "severity": "high",
            "description": "Function has empty steps list",
            "file_path": file_path,
            "function_index": function_index,
            "element_id": element_id
        })
    else:
        # Validate each step
        for step_idx, step in enumerate(steps):
            if not isinstance(step, dict):
                issues.append({
                    "issue_type": "invalid_step_format",
                    "severity": "medium",
                    "description": f"Step at index {step_idx} must be a dictionary, got {type(step)}",
                    "file_path": file_path,
                    "function_index": function_index,
                    "step_index": step_idx
                })
                continue

            if "step_description" not in step:
                issues.append({
                    "issue_type": "missing_step_description",
                    "severity": "medium",
                    "description": f"Step at index {step_idx} missing required field: step_description",
                    "file_path": file_path,
                    "function_index": function_index,
                    "step_index": step_idx
                })

    # Validate edge cases
    edge_cases = function.get("edge_cases", [])
    if not isinstance(edge_cases, list):
        issues.append({
            "issue_type": "invalid_edge_cases_format",
            "severity": "medium",
            "description": f"Edge cases must be a list, got {type(edge_cases)}",
            "file_path": file_path,
            "function_index": function_index
        })

    # Validate architecture issues addressed
    architecture_issues_addressed = function.get("architecture_issues_addressed", [])
    if not isinstance(architecture_issues_addressed, list):
        issues.append({
            "issue_type": "invalid_architecture_issues_format",
            "severity": "medium",
            "description": f"Architecture issues addressed must be a list, got {type(architecture_issues_addressed)}",
            "file_path": file_path,
            "function_index": function_index
        })
    else:
        # Validate each architecture issue reference
        arch_issue_ids = {issue["id"] for issue in architecture_issues if issue["id"]}
        for issue_id in architecture_issues_addressed:
            if issue_id not in arch_issue_ids:
                issues.append({
                    "issue_type": "invalid_architecture_issue",
                    "severity": "medium",
                    "description": f"Function references non-existent architecture issue: {issue_id}",
                    "file_path": file_path,
                    "function_index": function_index,
                    "invalid_issue_id": issue_id
                })

    # Check if implementation matches test requirements
    if element_id in test_requirements:
        test_reqs = test_requirements[element_id]
        # Check if edge cases from tests are covered
        test_edge_cases = _extract_edge_cases_from_tests(test_reqs)
        for edge_case in test_edge_cases:
            if not any(re.search(re.escape(edge_case), ec, re.IGNORECASE) for ec in edge_cases):
                issues.append({
                    "issue_type": "missing_edge_case",
                    "severity": "medium",
                    "description": f"Implementation doesn't handle edge case from tests: {edge_case}",
                    "file_path": file_path,
                    "function_index": function_index,
                    "element_id": element_id,
                    "edge_case": edge_case
                })

    return issues


def _validate_architecture_issue_coverage(
    implementation_plan: Dict[str, Any],
    architecture_issues: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Validate coverage of architecture issues by implementation plan."""
    issues = []

    # Extract all addressed issues from implementation plan
    addressed_issues = set()
    for file_path, functions in implementation_plan.items():
        for function in functions:
            for issue_id in function.get("architecture_issues_addressed", []):
                addressed_issues.add(issue_id)

    # Find critical/high severity issues that are not addressed
    for arch_issue in architecture_issues:
        if arch_issue["severity"].lower() in ["critical", "high"] and arch_issue["id"] and arch_issue["id"] not in addressed_issues:
            issues.append({
                "issue_type": "unaddressed_critical_issue",
                "severity": "critical" if arch_issue["severity"].lower() == "critical" else "high",
                "description": f"Critical/high severity architecture issue not addressed in implementation: {arch_issue['id']}",
                "arch_issue_id": arch_issue["id"],
                "arch_issue_description": arch_issue["description"]
            })

    return issues


def _calculate_implementation_metrics(
    implementation_plan: Dict[str, Any],
    element_ids: Set[str],
    architecture_issues: List[Dict[str, Any]],
    test_requirements: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, float]:
    """
    Calculate quality metrics for the implementation plan.

    Metrics include:
    - element_coverage_score: Percentage of system design elements covered in implementation
    - architecture_issue_addressal_score: Percentage of architecture issues explicitly addressed
    - step_specificity_score: Average level of detail in implementation steps
    - error_handling_completeness_score: Percentage of functions with error handling
    - edge_case_coverage_score: Average number of edge cases handled per function
    - overall_score: Combined weighted score of all metrics

    Args:
        implementation_plan: The implementation plan to score
        element_ids: Set of element IDs from system design
        architecture_issues: List of architecture issues from review
        test_requirements: Dictionary of test requirements by element ID

    Returns:
        Dictionary of metric scores (0.0 to 1.0)
    """
    metrics = {}

    # Calculate element coverage score
    implemented_elements = set()
    total_functions = 0
    functions_with_error_handling = 0
    total_edge_cases = 0
    total_steps = 0
    step_detail_score = 0

    # Track architecture issues addressed
    addressed_architecture_issues = set()
    priority_architecture_issues = {issue["id"] for issue in architecture_issues if issue.get("severity", "").lower() in ["critical", "high"]}

    # Extract implemented elements and calculate step detail scores
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            total_functions += 1

            # Track element coverage
            if isinstance(function, dict) and "element_id" in function and function["element_id"] in element_ids:
                implemented_elements.add(function["element_id"])

            # Track error handling
            has_error_handling = False

            # Calculate step specificity
            steps = function.get("steps", [])
            if isinstance(steps, list):
                total_steps += len(steps)

                for step in steps:
                    if isinstance(step, dict):
                        # Calculate step detail score (0-5 scale)
                        step_detail = 1  # Base score for having a step

                        if step.get("step_description", "").strip():
                            step_detail += 1

                        if step.get("pseudo_code", "").strip():
                            step_detail += 1

                        if step.get("relevant_data_structures", []):
                            step_detail += 1

                        if step.get("api_calls_made", []):
                            step_detail += 0.5

                        if step.get("error_handling_notes", "").strip():
                            step_detail += 1
                            has_error_handling = True

                        step_detail_score += step_detail

            # Track error handling completeness
            if has_error_handling:
                functions_with_error_handling += 1

            # Track edge cases
            edge_cases = function.get("edge_cases", [])
            if isinstance(edge_cases, list):
                total_edge_cases += len(edge_cases)

            # Track architecture issues
            arch_issues = function.get("architecture_issues_addressed", [])
            if isinstance(arch_issues, list):
                for issue in arch_issues:
                    if isinstance(issue, str):
                        addressed_architecture_issues.add(issue)

    # Calculate metrics
    # Element coverage score (percentage of system design elements implemented)
    if element_ids:
        metrics["element_coverage_score"] = len(implemented_elements) / len(element_ids)
    else:
        metrics["element_coverage_score"] = 0.0

    # Architecture issue addressal score (percentage of high/critical issues addressed)
    if priority_architecture_issues:
        addressed_priority_issues = addressed_architecture_issues.intersection(priority_architecture_issues)
        metrics["architecture_issue_addressal_score"] = len(addressed_priority_issues) / len(priority_architecture_issues)
    else:
        metrics["architecture_issue_addressal_score"] = 1.0  # No critical issues to address

    # Step specificity score (average detail level of steps, normalized to 0-1)
    if total_steps > 0:
        avg_step_detail = step_detail_score / total_steps
        metrics["step_specificity_score"] = min(avg_step_detail / 5.0, 1.0)  # Normalize to 0-1 range
    else:
        metrics["step_specificity_score"] = 0.0

    # Error handling completeness (percentage of functions with error handling)
    if total_functions > 0:
        metrics["error_handling_completeness_score"] = functions_with_error_handling / total_functions
    else:
        metrics["error_handling_completeness_score"] = 0.0

    # Edge case coverage (average number of edge cases per function, capped at 1.0)
    if total_functions > 0:
        avg_edge_cases = total_edge_cases / total_functions
        metrics["edge_case_coverage_score"] = min(avg_edge_cases / 3.0, 1.0)  # Assuming 3+
             edge cases is comprehensive    else:
        metrics["edge_case_coverage_score"] = 0.0

    # Calculate coherence metrics
    coherence_metrics = calculate_coherence_metrics(implementation_plan)

    # Add coherence metrics to the overall metrics
    metrics.update(coherence_metrics)

    # Calculate overall score (weighted average of all metrics)
    weights = {
        "element_coverage_score": 0.20,
        "architecture_issue_addressal_score": 0.25,
        "step_specificity_score": 0.15,
        "error_handling_completeness_score": 0.10,
        "edge_case_coverage_score": 0.10,
        "naming_consistency_score": 0.05,
        "error_handling_consistency_score": 0.05,
        "api_design_consistency_score": 0.05,
        "data_flow_consistency_score": 0.05
    }

    overall_score = sum(metrics.get(metric, 0.0) * weight for metric, weight in weights.items())
    metrics["overall_score"] = overall_score

    return metrics


def _validate_implementation_quality(
    implementation_plan: Dict[str, Any],
    metrics: Dict[str, float]
) -> List[Dict[str, Any]]:
    """
    Validate implementation quality based on calculated metrics and additional quality checks
    including code consistency, maintainability, and modularity.

    Args:
        implementation_plan: The implementation plan to validate
        metrics: Quality metrics calculated for the plan

    Returns:
        List of validation issues related to quality
    """
    issues = []

    # Define thresholds for quality metrics
    thresholds = {
        "element_coverage_score": 0.95,  # 95% of elements should be covered
        "architecture_issue_addressal_score": 0.98,  # 98% of critical/high issues should be addressed
        "step_specificity_score": 0.8,  # Steps should have 80% of possible detail
        "error_handling_completeness_score": 0.9,  # 90% of functions should have error handling
        "edge_case_coverage_score": 0.75,  # Should have at least 75% of expected edge case coverage
        "naming_consistency_score": 0.85,  # 85% naming convention consistency
        "error_handling_consistency_score": 0.8,  # 80% error handling approach consistency
        "api_design_consistency_score": 0.75,  # 75% API design pattern consistency
        "data_flow_consistency_score": 0.75,  # 75% data flow pattern consistency
        "pattern_consistency_score": 0.8,  # 80% overall pattern consistency
        "overall_score": 0.85  # Overall quality score should be at least 85%
    }

    # Check each metric against its threshold
    for metric, threshold in thresholds.items():
        score = metrics.get(metric, 0.0)
        if score < threshold:
            severity = "critical" if metric in ["element_coverage_score", "architecture_issue_addressal_score"] else "medium"

            issues.append({
                "issue_type": f"low_{metric}",
                "severity": severity,
                "description": f"{metric.replace('_', ' ').title()} is below threshold: {score:.2f} < {threshold}",
                "score": score,
                "threshold": threshold
            })

    # Enhanced quality checks

    # 1. Check function name consistency
    function_naming_issues = _check_function_naming_consistency(implementation_plan)
    issues.extend(function_naming_issues)

    # 2. Check implementation complexity and size
    complexity_issues = _check_implementation_complexity(implementation_plan)
    issues.extend(complexity_issues)

    # 3. Check dependency management
    dependency_issues = _check_dependency_management(implementation_plan)
    issues.extend(dependency_issues)

    # 4. Check error handling patterns
    error_handling_issues = _check_error_handling_patterns(implementation_plan)
    issues.extend(error_handling_issues)

    # 5. Check SOLID principles adherence
    solid_issues = _check_solid_principles(implementation_plan)
    issues.extend(solid_issues)

    return issues


def _check_function_naming_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check function naming consistency across the implementation plan.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to naming consistency
    """
    issues = []

    # Extract all function names
    function_names = []
    function_name_to_path = {}

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict) or "function" not in function:
                continue

            function_signature = function["function"]

            # Extract just the name part from the signature
            name_match = re.search(r'(?:def|class)\s+(\w+)', function_signature)
            if name_match:
                name = name_match.group(1)
                function_names.append(name)
                function_name_to_path[name] = file_path

    # Check for consistent naming patterns
    snake_case_pattern = r'^[a-z][a-z0-9_]*$'
    camel_case_pattern = r'^[a-z][a-zA-Z0-9]*$'
    pascal_case_pattern = r'^[A-Z][a-zA-Z0-9]*$'

    # Count occurrences of each naming style
    naming_styles = {
        "snake_case": 0,
        "camel_case": 0,
        "pascal_case": 0,
        "other": 0
    }

    for name in function_names:
        if re.match(snake_case_pattern, name):
            naming_styles["snake_case"] += 1
        elif re.match(camel_case_pattern, name):
            naming_styles["camel_case"] += 1
        elif re.match(pascal_case_pattern, name):
            naming_styles["pascal_case"] += 1
        else:
            naming_styles["other"] += 1

    # Determine dominant style
    dominant_style = max(naming_styles, key=naming_styles.get)
    dominant_count = naming_styles[dominant_style]
    total_names = len(function_names)

    # Check if there's inconsistency
    if dominant_count < total_names * 0.8 and total_names > 3:
        inconsistent_names = []

        # Find names that don't match the dominant style
        pattern_map = {
            "snake_case": snake_case_pattern,
            "camel_case": camel_case_pattern,
            "pascal_case": pascal_case_pattern
        }

        dominant_pattern = pattern_map.get(dominant_style)
        if dominant_pattern:
            for name in function_names:
                if not re.match(dominant_pattern, name):
                    inconsistent_names.append((name, function_name_to_path.get(name, "Unknown")))

        # Report the issue
        if inconsistent_names:
            issues.append({
                "issue_type": "inconsistent_naming_style",
                "severity": "low",
                "description": f"Inconsistent function naming styles detected. Dominant style is {dominant_style} ({dominant_count}/{total_names})",
                "dominant_style": dominant_style,
                "inconsistent_names": [{"name": name, "file_path": path} for name, path in inconsistent_names[:5]]
            })

    return issues


def _check_implementation_complexity(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check implementation complexity and size for each function.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to complexity
    """
    issues = []

    # Define complexity thresholds
    thresholds = {
        "max_steps": 15,  # Maximum number of steps for a single function
        "max_edge_cases": 10,  # Maximum number of edge cases to handle in a single function
        "max_step_length": 100  # Maximum character length for a step description
    }

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            function_name = function.get("function", "Unknown function")

            # Check number of steps
            steps = function.get("steps", [])
            if isinstance(steps, list) and len(steps) > thresholds["max_steps"]:
                issues.append({
                    "issue_type": "high_function_complexity",
                    "severity": "medium",
                    "description": f"Function has {len(steps)} steps, exceeding the recommended maximum of {thresholds['max_steps']}",
                    "file_path": file_path,
                    "function": function_name,
                    "recommendation": "Consider breaking this function into smaller, more focused functions"
                })

            # Check step length
            for i, step in enumerate(steps):
                if isinstance(step, dict) and "step_description" in step:
                    if len(step["step_description"]) > thresholds["max_step_length"]:
                        issues.append({
                            "issue_type": "overly_complex_step",
                            "severity": "low",
                            "description": f"Step {i+1} in function is too complex or detailed",
                            "file_path": file_path,
                            "function": function_name,
                            "step_index": i,
                            "recommendation": "Break this step into multiple smaller steps"
                        })

            # Check edge cases
            edge_cases = function.get("edge_cases", [])
            if isinstance(edge_cases, list) and len(edge_cases) > thresholds["max_edge_cases"]:
                issues.append({
                    "issue_type": "excessive_edge_cases",
                    "severity": "low",
                    "description": f"Function handles {len(edge_cases)} edge cases, suggesting it may be doing too much",
                    "file_path": file_path,
                    "function": function_name,
                    "recommendation": "Consider splitting functionality or delegating handling of some edge cases"
                })

    return issues


def _check_dependency_management(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check for dependency management issues in the implementation plan.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to dependencies
    """
    issues = []

    # Track function dependencies across files
    file_dependencies = defaultdict(set)
    element_to_file_map = {}

    # Build element to file map
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            element_id = function.get("element_id")
            if element_id:
                element_to_file_map[element_id] = file_path

    # Analyze dependencies in steps
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            steps = function.get("steps", [])
            for step in steps:
                if not isinstance(step, dict):
                    continue

                # Look for API calls that might reference other files
                api_calls = step.get("api_calls_made", [])
                if isinstance(api_calls, list):
                    for call in api_calls:
                        if not isinstance(call, str):
                            continue

                        # Try to match the call to an element
                        for element_id, elem_file in element_to_file_map.items():
                            if element_id in call and elem_file != file_path:
                                file_dependencies[file_path].add(elem_file)

    # Check for circular dependencies
    circular_deps = _find_circular_dependencies(file_dependencies)

    for cycle in circular_deps:
        issues.append({
            "issue_type": "circular_dependency",
            "severity": "high",
            "description": f"Circular dependency detected between files: {' -> '.join(cycle)}",
            "affected_files": cycle,
            "recommendation": "Refactor to break circular dependencies, possibly using dependency injection or intermediate interfaces"
        })

    # Check for excessive dependencies
    for file_path, dependencies in file_dependencies.items():
        if len(dependencies) > 5:  # Arbitrary threshold for excessive dependencies
            issues.append({
                "issue_type": "excessive_dependencies",
                "severity": "medium",
                "description": f"File {file_path} depends on {len(dependencies)} other files, which may indicate poor modularity",
                "file_path": file_path,
                "dependencies": list(dependencies),
                "recommendation": "Consider refactoring to reduce coupling between modules"
            })

    return issues


def _find_circular_dependencies(dependencies: Dict[str, Set[str]]) -> List[List[str]]:
    """
    Find circular dependencies in the dependency graph.

    Args:
        dependencies: Dictionary mapping files to their dependencies

    Returns:
        List of cycles in the dependency graph
    """
    cycles = []
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for neighbor in dependencies.get(node, set()):
            dfs(neighbor)

        path.pop()

    # Run DFS from each node
    for node in dependencies:
        dfs(node)

    return cycles


def _check_error_handling_patterns(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check for consistent and appropriate error handling patterns.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to error handling
    """
    issues = []

    # Track functions with error handling and their patterns
    functions_with_error_handling = 0
    total_functions = 0
    error_handling_types = {
        "exceptions": 0,
        "return_codes": 0,
        "result_objects": 0,
        "logging": 0
    }

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            total_functions += 1
            has_error_handling = False

            # Check for error handling in steps
            steps = function.get("steps", [])
            for step in steps:
                if not isinstance(step, dict):
                    continue

                error_notes = step.get("error_handling_notes", "").lower()
                pseudo_code = step.get("pseudo_code", "").lower()

                if error_notes:
                    has_error_handling = True

                    # Identify error handling type
                    if "raise" in error_notes or "exception" in error_notes or "except" in error_notes or "try" in error_notes:
                        error_handling_types["exceptions"] += 1
                    elif "return none" in error_notes or "return false" in error_notes or "return -1" in error_notes:
                        error_handling_types["return_codes"] += 1
                    elif "result" in error_notes and ("success" in error_notes or "failure" in error_notes):
                        error_handling_types["result_objects"] += 1
                    elif "log" in error_notes:
                        error_handling_types["logging"] += 1

                if pseudo_code:
                    if "try" in pseudo_code or "except" in pseudo_code or "raise" in pseudo_code:
                        has_error_handling = True
                        error_handling_types["exceptions"] += 1

            if has_error_handling:
                functions_with_error_handling += 1

    # Determine dominant error handling style
    dominant_style = max(error_handling_types, key=error_handling_types.get) if error_handling_types else None
    dominant_count = error_handling_types.get(dominant_style, 0) if dominant_style else 0

    # Check for inconsistent error handling styles
    if dominant_style and dominant_count > 0:
        total_styles_used = sum(1 for count in error_handling_types.values() if count > 0)

        if total_styles_used > 2:  # More than 2 distinct styles
            issues.append({
                "issue_type": "inconsistent_error_handling",
                "severity": "medium",
                "description": f"Inconsistent error handling patterns detected. Dominant style is '{dominant_style}' but {total_styles_used} different styles are used.",
                "error_handling_types": dict(error_handling_types),
                "recommendation": "Standardize on a consistent error handling approach across the codebase"
            })

    # Check for insufficient error handling
    if functions_with_error_handling < total_functions * 0.7 and total_functions > 3:
        issues.append({
            "issue_type": "insufficient_error_handling",
            "severity": "high",
            "description": f"Only {functions_with_error_handling}/{total_functions} functions ({functions_with_error_handling/total_functions:.1%}) have error handling",
            "recommendation": "Add proper error handling to all functions, especially those that can fail"
        })

    return issues


def _check_solid_principles(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check for adherence to SOLID principles in the implementation plan.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to SOLID principles
    """
    issues = []

    # Track classes and their methods
    classes = {}

    # First pass: identify classes
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict) or "function" not in function:
                continue

            function_signature = function["function"]

            # Check if this is a class definition
            class_match = re.search(r'class\s+(\w+)', function_signature)
            if class_match:
                class_name = class_match.group(1)
                classes[class_name] = {
                    "file_path": file_path,
                    "methods": [],
                    "responsibilities": set(),
                    "description": function.get("description", "")
                }

    # Second pass: identify methods belonging to classes
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict) or "function" not in function:
                continue

            function_signature = function["function"]

            # Check if this is a method (has self parameter)
            method_match = re.search(r'def\s+(\w+)\s*\(\s*self', function_signature)
            if method_match:
                method_name = method_match.group(1)

                # Try to find which class this belongs to
                for class_name, class_info in classes.items():
                    if class_info["file_path"] == file_path:
                        class_info["methods"].append({
                            "name": method_name,
                            "signature": function_signature,
                            "description": function.get("description", ""),
                            "steps": function.get("steps", [])
                        })

                        # Extract responsibilities from method description
                        desc = function.get("description", "").lower()
                        for responsibility in ["validation", "calculation", "persistence", "presentation",
                                              "authorization", "authentication", "logging", "networking",
                                              "formatting", "parsing", "processing"]:
                            if responsibility in desc:
                                class_info["responsibilities"].add(responsibility)

    # Check Single Responsibility Principle
    for class_name, class_info in classes.items():
        if len(class_info["responsibilities"]) > 2 and len(class_info["methods"]) > 3:
            issues.append({
                "issue_type": "single_responsibility_violation",
                "severity": "medium",
                "description": f"Class '{class_name}' may have too many responsibilities: {', '.join(class_info['responsibilities'])}",
                "file_path": class_info["file_path"],
                "class_name": class_name,
                "responsibilities": list(class_info["responsibilities"]),
                "recommendation": "Consider splitting this class into multiple classes, each with a single responsibility"
            })

    return issues


def _validate_implementation_security(
    implementation_plan: Dict[str, Any],
    architecture_issues: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate that the implementation properly addresses security issues identified in the architecture review
    and follows security best practices.

    Args:
        implementation_plan: The implementation plan to validate
        architecture_issues: List of architecture issues from review

    Returns:
        List of validation issues related to security
    """
    issues = []

    # Extract security concerns from architecture issues
    security_concerns = [issue for issue in architecture_issues if issue.get("issue_type") == "security_concern"]

    # Map security concerns by ID
    security_concerns_by_id = {concern["id"]: concern for concern in security_concerns if "id" in concern} if security_concerns else {}

    # Track which security concerns are addressed
    addressed_concerns = set()

    # Define security best practices categories with corresponding keywords and patterns
    security_best_practices = {
        "input_validation": {
            "keywords": ["validate", "sanitize", "escape", "filter", "clean", "parse", "encoding"],
            "patterns": [r"input.*validat", r"validat.*input", r"sanitiz.*input", r"input.*sanitiz",
                         r"check.*parameter", r"parameter.*check", r"validate.*(?:param|arg|input|data)"],
            "owasp_category": "A03:2021-Injection",
            "required_coverage": 0.8  # 80% of functions that handle external input should have input validation
        },
        "authentication": {
            "keywords": ["authenticate", "login", "password", "credential", "token", "session", "jwt", "oauth"],
            "patterns": [r"auth[a-z]*", r"check.*credent", r"credent.*check", r"verif.*(?:user|login|token)"],
            "owasp_category": "A07:2021-Identification and Authentication Failures",
            "required_coverage": 0.9  # 90% of auth-related functions should have proper security measures
        },
        "authorization": {
            "keywords": ["authorize", "permission", "access control", "rbac", "acl", "role", "privilege"],
            "patterns": [r"auth[a-z]*", r"check.*(?:permission|access|role)", r"(?:permission|access|role).*check"],
            "owasp_category": "A01:2021-Broken Access Control",
            "required_coverage": 0.9  # 90% of functions that require authorization should have proper checks
        },
        "data_protection": {
            "keywords": ["encrypt", "hash", "salt", "pbkdf2", "bcrypt", "argon2", "sha", "hmac", "sensitive", "pii"],
            "patterns": [r"encrypt.*data", r"data.*encrypt", r"hash.*password", r"password.*hash",
                         r"protect.*(?:data|credential|secret)"],
            "owasp_category": "A02:2021-Cryptographic Failures",
            "required_coverage": 0.95  # 95% of functions handling sensitive data should have protection measures
        },
        "error_handling": {
            "keywords": ["try", "except", "catch", "finally", "error", "exception", "fault", "fail"],
            "patterns": [r"try.*except", r"catch.*error", r"handle.*except", r"except.*handle"],
            "owasp_category": "A09:2021-Security Logging and Monitoring Failures",
            "required_coverage": 0.7  # 70% of functions should have proper error handling
        },
        "secure_communication": {
            "keywords": ["https", "tls", "ssl", "secure", "certificate"],
            "patterns": [r"secure.*connect", r"secure.*communication", r"tls.*connect", r"https.*request"],
            "owasp_category": "A02:2021-Cryptographic Failures",
            "required_coverage": 0.8  # 80% of network communication should be secure
        },
        "xss_prevention": {
            "keywords": ["xss", "cross-site scripting", "html escape", "sanitize", "content-security-policy", "csp"],
            "patterns": [r"prevent.*xss", r"xss.*prevent", r"escape.*html", r"html.*escape"],
            "owasp_category": "A03:2021-Injection",
            "required_coverage": 0.9  # 90% of functions rendering content should prevent XSS
        },
        "csrf_protection": {
            "keywords": ["csrf", "cross-site request forgery", "token", "same-origin", "samesite"],
            "patterns": [r"csrf.*token", r"token.*csrf", r"protect.*csrf", r"csrf.*protect"],
            "owasp_category": "A01:2021-Broken Access Control",
            "required_coverage": 0.8  # 80% of form submission handlers should have CSRF protection
        }
    }

    # Track coverage for each security category
    security_coverage = {category: {"needed": 0, "implemented": 0} for category in security_best_practices}

    # Check each function for security concern addressal and security best practices
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check architecture_issues_addressed field
            arch_issues = function.get("architecture_issues_addressed", [])
            if isinstance(arch_issues, list):
                for issue_id in arch_issues:
                    if issue_id in security_concerns_by_id:
                        addressed_concerns.add(issue_id)

            # Convert function data to text for analysis
            function_name = function.get("function", "").lower()
            description = function.get("description", "").lower()
            steps_text = ""
            edge_cases_text = ""

            # Extract text from steps
            steps = function.get("steps", [])
            if isinstance(steps, list):
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    steps_text += json.dumps(step).lower() + " "

            # Extract text from edge cases
            edge_cases = function.get("edge_cases", [])
            if isinstance(edge_cases, list):
                for edge_case in edge_cases:
                    if isinstance(edge_case, str):
                        edge_cases_text += edge_case.lower() + " "

            # Combined text for security analysis
            combined_text = function_name + " " + description + " " + steps_text + " " +
                 edge_cases_text
            # Check security best practices implementation
            for category, details in security_best_practices.items():
                # Check if this function needs this security category based on its nature
                needs_category = False

                # Function name-based heuristics for determining if a function needs a security practice
                if category == "input_validation" and any(term in function_name for term in ["get", "process", "handle", "parse", "read", "load"]):
                    needs_category = True

                elif category == "authentication" and any(term in function_name for term in ["login", "auth", "sign", "user"]):
                    needs_category = True

                elif category == "authorization" and any(term in function_name for term in ["access", "permission", "role", "admin"]):
                    needs_category = True

                elif category == "data_protection" and any(term in function_name for term in ["password", "secret", "key", "credential", "token", "personal"]):
                    needs_category = True

                # Also check description for needs determination
                if not needs_category:
                    for keyword in details["keywords"]:
                        if keyword in description:
                            needs_category = True
                            break

                # If function needs this security category, check if it's implemented
                if needs_category:
                    security_coverage[category]["needed"] += 1

                    # Check if the security practice is implemented
                    has_implementation = False

                    # Check keywords
                    for keyword in details["keywords"]:
                        if keyword in combined_text:
                            has_implementation = True
                            break

                    # Check patterns
                    if not has_implementation:
                        for pattern in details["patterns"]:
                            if re.search(pattern, combined_text):
                                has_implementation = True
                                break

                    if has_implementation:
                        security_coverage[category]["implemented"] += 1
                    else:
                        # This function needs security practice but doesn't implement it
                        issues.append({
                            "issue_type": f"missing_{category}_security",
                            "severity": "high",
                            "description": f"Function appears to need {category.replace('_', ' ')} but doesn't implement it",
                            "file_path": file_path,
                            "function": function.get("function", "Unknown function"),
                            "owasp_category": details["owasp_category"]
                        })

    # Report any security concerns that are not addressed
    for concern_id, concern in security_concerns_by_id.items():
        if concern_id not in addressed_concerns:
            severity = concern.get("severity", "Medium")
            issue_severity = "critical" if severity.lower() in ["critical", "high"] else "high"

            issues.append({
                "issue_type": "unaddressed_security_concern",
                "severity": issue_severity,
                "description": f"Security concern not explicitly addressed: {concern_id} - {concern.get('description', 'No description')}",
                "concern_id": concern_id
            })

    # Check coverage for each security category
    for category, coverage in security_coverage.items():
        if coverage["needed"] > 0:
            coverage_ratio = coverage["implemented"] / coverage["needed"]
            required_coverage = security_best_practices[category]["required_coverage"]

            if coverage_ratio < required_coverage:
                issues.append({
                    "issue_type": f"insufficient_{category}_coverage",
                    "severity": "medium",
                    "description": f"Insufficient {category.replace('_', ' ')} coverage: {coverage_ratio:.2f} < {required_coverage}",
                    "owasp_category": security_best_practices[category]["owasp_category"],
                    "current_coverage": coverage_ratio,
                    "required_coverage": required_coverage
                })

    return issues


def _validate_implementation_test_alignment(
    implementation_plan: Dict[str, Any],
    test_requirements: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Validate that the implementation will satisfy test requirements with enhanced analysis
    of test coverage, edge cases, and behavior alignment.

    Args:
        implementation_plan: The implementation plan to validate
        test_requirements: Dictionary of test requirements by element ID

    Returns:
        List of validation issues related to test alignment
    """
    issues = []

    # Track overall test alignment metrics
    metrics = {
        "total_tested_elements": 0,
        "elements_with_implementations": 0,
        "total_assertions": 0,
        "covered_assertions": 0,
        "total_edge_cases": 0,
        "covered_edge_cases": 0,
        "test_categories": {
            "unit": {"covered": 0, "total": 0},
            "integration": {"covered": 0, "total": 0},
            "property": {"covered": 0, "total": 0},
            "acceptance": {"covered": 0, "total": 0}
        }
    }

    # Check each element with test requirements
    for element_id, tests in test_requirements.items():
        metrics["total_tested_elements"] += 1

        # Extract test type information (unit, integration, etc.)
        test_types = {}
        for test in tests:
            test_category = test.get("test_category", "unit")
            test_types.setdefault(test_category, 0)
            test_types[test_category] += 1

        # Update test category metrics
        for category, count in test_types.items():
            if category in metrics["test_categories"]:
                metrics["test_categories"][category]["total"] += count

        # Extract edge cases from tests
        test_edge_cases = set(_extract_edge_cases_from_tests(tests))
        metrics["total_edge_cases"] += len(test_edge_cases)

        # Extract expected behaviors and assertions from tests
        expected_behaviors = _extract_expected_behaviors(tests)
        test_assertions = []
        for test in tests:
            test_assertions.extend(test.get("assertions", []))
        metrics["total_assertions"] += len(test_assertions)

        # Find functions implementing this element
        implementing_functions = []
        for file_path, functions in implementation_plan.items():
            if not isinstance(functions, list):
                continue

            for function in functions:
                if isinstance(function, dict) and function.get("element_id") == element_id:
                    implementing_functions.append((file_path, function))

        # If no implementations found for an element with tests, report an issue
        if not implementing_functions:
            issues.append({
                "issue_type": "missing_implementation_for_tested_element",
                "severity": "high",
                "description": f"No implementation found for element_id {element_id} which has {len(tests)} tests",
                "element_id": element_id,
                "test_types": test_types
            })
            continue

        # Element has implementations
        metrics["elements_with_implementations"] += 1

        # Track covered assertions and edge cases for this element
        element_covered_assertions = 0
        element_covered_edge_cases = 0

        # For each implementing function, check if the implementation covers the assertions and behaviors
        for file_path, function in implementing_functions:
            # Extract steps and edge cases text for analysis
            implementation_text = function.get("description", "") + " "

            for step in function.get("steps", []):
                if isinstance(step, dict):
                    implementation_text += step.get("step_description", "") + " "
                    implementation_text += step.get("pseudo_code", "") + " "

            implementation_edge_cases = []
            for edge_case in function.get("edge_cases", []):
                if isinstance(edge_case, str):
                    implementation_text += edge_case + " "
                    implementation_edge_cases.append(edge_case.lower())

            implementation_text = implementation_text.lower()

            # Check assertion coverage
            covered_assertions = []
            uncovered_assertions = []

            for assertion in test_assertions:
                # Extract key terms from assertion with improved pattern matching
                assertion_text = assertion.lower()
                assertion_key_terms = []

                # Extract values being asserted with more comprehensive patterns
                value_patterns = [
                    r'assert\w*\s*\((.*?)[,=<>]',  # Basic pattern
                    r'assert\w*\s*\(\s*([\w\.]+)',  # Extract just the variable/method name
                    r'assert\w*\s*\(\s*.*\s+(\w+)\s*\(',  # Extract function being called
                    r'assert\w*\s*\(\s*(\w+)\s*\.', # Extract object name
                    r'assert\w*\s*\(\s*not\s+(\w+)',  # Extract negated variable
                    r'equal\w*\(\s*(.*?)\s*,'  # Extract first argument of equal
                ]

                # Try multiple patterns for better extraction
                for pattern in value_patterns:
                    value_match = re.search(pattern, assertion_text)
                    if value_match:
                        assertion_key_terms.append(value_match.group(1).strip())

                # Extract message text
                message_pattern = r',[^,]*[\'"]([^\'"]*)[\'"]'
                message_match = re.search(message_pattern, assertion_text)
                if message_match:
                    assertion_key_terms.append(message_match.group(1).strip())

                # Extract significant terms from the assertion
                significant_terms = [term for term in re.findall(r'\b(\w{4,})\b', assertion_text)
                                    if term not in ['assert', 'equal', 'true', 'false', 'none', 'should', 'would', 'could']]
                assertion_key_terms.extend(significant_terms)

                # Deduplicate terms
                assertion_key_terms = list(set(assertion_key_terms))

                # Check if key terms are covered in implementation
                is_covered = False
                covered_terms = []

                for term in assertion_key_terms:
                    if term and len(term) > 3 and term in implementation_text:
                        is_covered = True
                        covered_terms.append(term)

                # Consider assertions semantically equivalent to covered terms
                if not is_covered and covered_terms:
                    for behavior in expected_behaviors:
                        if any(term in behavior.lower() for term in covered_terms):
                            is_covered = True
                            break

                if is_covered:
                    covered_assertions.append(assertion)
                    element_covered_assertions += 1
                else:
                    uncovered_assertions.append(assertion)

            # Check edge case coverage
            covered_edge_cases_list = []
            uncovered_edge_cases = []

            for edge_case in test_edge_cases:
                edge_case_lower = edge_case.lower()
                is_covered = False

                # Direct match in implementation edge cases
                if any(ec for ec in implementation_edge_cases if edge_case_lower in ec or ec in edge_case_lower):
                    is_covered = True

                # Check in implementation text
                if not is_covered:
                    # Extract significant terms from edge case
                    edge_case_terms = set(re.findall(r'\b(\w{4,})\b', edge_case_lower))
                    significant_terms = edge_case_terms - {'case', 'edge', 'test', 'when', 'with', 'should', 'would'}

                    # Consider covered if multiple significant terms appear in the implementation
                    term_matches = sum(1 for term in significant_terms if term in implementation_text)
                    is_covered = term_matches >= min(2, len(significant_terms))

                if is_covered:
                    covered_edge_cases_list.append(edge_case)
                    element_covered_edge_cases += 1
                else:
                    uncovered_edge_cases.append(edge_case)

            # Report specific uncovered assertions if any
            if uncovered_assertions:
                uncovered_pct = len(uncovered_assertions) / len(test_assertions) if test_assertions else 0
                severity = "high" if uncovered_pct > 0.5 else "medium"

                issues.append({
                    "issue_type": "implementation_may_not_satisfy_tests",
                    "severity": severity,
                    "description": f"Implementation may not satisfy {len(uncovered_assertions)} test assertions for element {element_id} ({uncovered_pct:.1%} uncovered)",
                    "element_id": element_id,
                    "file_path": file_path,
                    "function": function.get("function", "Unknown function"),
                    "uncovered_assertions": uncovered_assertions[:5],  # Include a few examples
                    "coverage_percentage": 1 - uncovered_pct
                })

            # Report specific uncovered edge cases if any
            if uncovered_edge_cases:
                uncovered_pct = len(uncovered_edge_cases) / len(test_edge_cases) if test_edge_cases else 0
                severity = "high" if uncovered_pct > 0.7 else "medium"

                issues.append({
                    "issue_type": "implementation_missing_edge_cases",
                    "severity": severity,
                    "description": f"Implementation doesn't handle {len(uncovered_edge_cases)} edge cases from tests for element {element_id}",
                    "element_id": element_id,
                    "file_path": file_path,
                    "function": function.get("function", "Unknown function"),
                    "uncovered_edge_cases": uncovered_edge_cases[:5],  # Include a few examples
                    "coverage_percentage": 1 - uncovered_pct
                })

            # Update test category coverage
            for category, count in test_types.items():
                if category in metrics["test_categories"]:
                    # Consider a category covered if we have more than 70% assertion coverage
                    category_coverage = len(covered_assertions) / len(test_assertions) if test_assertions else 0
                    if category_coverage >= 0.7:
                        metrics["test_categories"][category]["covered"] += count

        # Update overall metrics
        metrics["covered_assertions"] += element_covered_assertions
        metrics["covered_edge_cases"] += element_covered_edge_cases

    # Generate overall test alignment metrics report
    if metrics["total_tested_elements"] > 0:
        # Calculate overall coverage percentages
        element_coverage = metrics["elements_with_implementations"] / metrics["total_tested_elements"]
        assertion_coverage = metrics["covered_assertions"] / metrics["total_assertions"] if metrics["total_assertions"] > 0 else 1.0
        edge_case_coverage = metrics["covered_edge_cases"] / metrics["total_edge_cases"] if metrics["total_edge_cases"] > 0 else 1.0

        # Calculate category coverage
        category_coverage = {}
        for category, data in metrics["test_categories"].items():
            if data["total"] > 0:
                category_coverage[category] = data["covered"] / data["total"]
            else:
                category_coverage[category] = 1.0

        # Overall test alignment score (weighted average)
        weights = {
            "element_coverage": 0.3,
            "assertion_coverage": 0.4,
            "edge_case_coverage": 0.3
        }

        overall_score = (
            element_coverage * weights["element_coverage"] +
            assertion_coverage * weights["assertion_coverage"] +
            edge_case_coverage * weights["edge_case_coverage"]
        )

        # Report if the overall alignment is poor
        if overall_score < 0.7:
            issues.append({
                "issue_type": "poor_test_alignment",
                "severity": "high" if overall_score < 0.5 else "medium",
                "description": f"Overall test alignment is poor: {overall_score:.2f}",
                "metrics": {
                    "overall_score": overall_score,
                    "element_coverage": element_coverage,
                    "assertion_coverage": assertion_coverage,
                    "edge_case_coverage": edge_case_coverage,
                    "category_coverage": category_coverage
                }
            })

        # Report specific category alignment issues
        for category, coverage in category_coverage.items():
            if coverage < 0.7 and metrics["test_categories"][category]["total"] > 0:
                issues.append({
                    "issue_type": f"poor_{category}_test_alignment",
                    "severity": "medium",
                    "description": f"{category.capitalize()} tests have poor implementation alignment: {coverage:.2f}",
                    "category": category,
                    "coverage": coverage,
                    "total_tests": metrics["test_categories"][category]["total"],
                    "covered_tests": metrics["test_categories"][category]["covered"]
                })

    return issues


def _extract_expected_behaviors(tests: List[Dict[str, Any]]) -> List[str]:
    """
    Extract expected behaviors from tests to help with semantic matching.

    Args:
        tests: List of test requirements for an element

    Returns:
        List of expected behaviors extracted from tests
    """
    behaviors = []

    for test in tests:
        # Extract from test name
        test_name = test.get("test_name", "")
        if test_name:
            behaviors.append(test_name)

        # Extract from test description
        description = test.get("description", "")
        if description:
            behaviors.append(description)

        # Extract from BDD-style given/when/then
        for field in ["given", "when", "then"]:
            if field in test and test[field]:
                behaviors.append(test[field])

        # Extract from assertion messages
        for assertion in test.get("assertions", []):
            message_match = re.search(r',[^,]*[\'"]([^\'"]*)[\'"]', assertion)
            if message_match:
                behaviors.append(message_match.group(1).strip())

        # Extract from test code comments
        code = test.get("code", "")
        code_lines = code.split("\n")
        for line in code_lines:
            # Look for comment lines and docstrings
            if re.match(r'\s*#\s*(.+)$', line):
                comment = re.match(r'\s*#\s*(.+)$', line).group(1)
                behaviors.append(comment)
            elif re.search(r'[\'"](?:[\'"][\'"]\s*)?([^\'"]*)(?:[\'"][\'"])?\s*[\'"]', line):
                # This is a rough pattern for docstrings or string literals that might describe behavior
                string_match = re.search(r'[\'"](?:[\'"][\'"]\s*)?([^\'"]*)(?:[\'"][\'"])?\s*[\'"]', line)
                behaviors.append(string_match.group(1).strip())

    return behaviors


def _element_needs_implementation(element_id: str, system_design: Dict[str, Any]) -> bool:
    """
    Determine if an element needs implementation based on its type.
    Some elements like interfaces or abstract classes may not need direct implementation.

    Args:
        element_id: The element ID to check
        system_design: The system design data

    Returns:
        True if the element needs implementation, False otherwise
    """
    # Find the element in system design
    element = None
    for e in system_design.get("code_elements", []):
        if isinstance(e, dict) and e.get("element_id") == element_id:
            element = e
            break

    if not element:
        return True  # Default to requiring implementation if element not found

    # Check if it's an interface or abstract class
    element_type = element.get("element_type", "").lower()
    element_name = element.get("name", "").lower()
    description = element.get("description", "").lower()

    # Skip interfaces, abstract classes, and certain utility types
    if "interface" in element_type or "abstract" in element_type:
        return False

    if "interface" in element_name or "abstract" in element_name:
        return False

    if "interface" in description and "implement" not in description:
        return False

    return True


def _extract_edge_cases_from_tests(test_requirements: List[Dict[str, Any]]) -> List[str]:
    """
    Extract edge cases from test requirements.

    Args:
        test_requirements: List of test requirements for an element

    Returns:
        List of extracted edge cases
    """
    edge_cases = []

    for test_req in test_requirements:
        # Extract from test name
        test_name = test_req.get("test_name", "").lower()
        if any(term in test_name for term in ["edge", "boundary", "invalid", "null", "empty", "error"]):
            edge_cases.append(test_name)

        # Extract from assertions
        for assertion in test_req.get("assertions", []):
            assertion_lower = assertion.lower()
            if any(term in assertion_lower for term in ["edge", "boundary", "invalid", "null", "empty", "error"]):
                edge_cases.append(assertion)

        # Extract from test code
        code = test_req.get("code", "")
        code_lines = code.split("\n")
        for i, line in enumerate(code_lines):
            line_lower = line.lower()
            if any(term in line_lower for term in ["edge case", "boundary", "invalid input", "null value", "empty"]):
                # Get a few lines of context
                start = max(0, i - 1)
                end = min(len(code_lines), i + 2)
                edge_case_context = " ".join(code_lines[start:end])
                edge_cases.append(edge_case_context)

    # Remove duplicates and return
    return list(set(edge_cases))


def _repair_structure(plan: Dict[str, Any], system_design: Dict[str, Any]) -> Dict[str, Any]:
    """
    Repair basic structure issues in the implementation plan.

    Args:
        plan: The implementation plan to repair
        system_design: The system design data for reference

    Returns:
        Repaired plan with correct structure
    """
    # If plan is not a dictionary, create a new one
    if not isinstance(plan, dict):
        plan = {}

    # If plan is empty, fill with placeholder implementations based on system design
    if not plan:
        code_elements = system_design.get("code_elements", [])
        files_by_type = {}

        # Group elements by type for better file organization
        for element in code_elements:
            if isinstance(element, dict) and "element_id" in element:
                element_type = element.get("element_type", "unknown")
                if element_type not in files_by_type:
                    files_by_type[element_type] = []
                files_by_type[element_type].append(element)

        # Create file structure based on element types
        for element_type, elements in files_by_type.items():
            # Create file path based on element type
            if element_type == "class":
                file_path = "models.py"
            elif element_type == "function":
                file_path = "functions.py"
            elif "service" in element_type or "controller" in element_type:
                file_path = "services.py"
            else:
                file_path = f"{element_type.replace(' ', '_')}.py"

            # Add placeholder implementations for each element
            plan[file_path] = []

            for element in elements:
                element_id = element.get("element_id", "")
                name = element.get("name", "Unknown")
                signature = element.get("signature", f"def {name.lower()}():")

                # Create placeholder implementation
                plan[file_path].append({
                    "function": signature,
                    "description": f"Implementation of {name}",
                    "element_id": element_id,
                    "steps": [
                        {
                            "step_description": "Implement core functionality",
                            "pseudo_code": "# TODO: Implement core functionality",
                            "relevant_data_structures": [],
                            "api_calls_made": [],
                            "error_handling_notes": "Handle potential errors"
                        }
                    ],
                    "edge_cases": ["Error handling needed"],
                    "architecture_issues_addressed": []
                })

    return plan


def _repair_file_paths(plan: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Repair invalid file paths in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of file path issues to address

    Returns:
        Repaired plan with valid file paths
    """
    repaired_plan = {}

    for file_path, functions in plan.items():
        # Check if this file path is valid
        is_valid = True
        for issue in issues:
            if issue.get("file_path") == file_path:
                is_valid = False
                break

        if is_valid:
            # Keep valid file paths as is
            repaired_plan[file_path] = functions
        else:
            # For invalid file paths, create a normalized version
            if isinstance(file_path, (int, float, bool)):
                # Convert non-string paths to strings
                new_file_path = f"file_{file_path}.py"
                repaired_plan[new_file_path] = functions
            elif not isinstance(file_path, str):
                # For other types, use a generic file name
                new_file_path = "unnamed_file.py"
                repaired_plan[new_file_path] = functions
            else:
                # Already a string but perhaps invalid format
                if not file_path.endswith(('.py', '.js', '.ts', '.java', '.rb', '.go', '.c', '.cpp', '.h', '.hpp')):
                    new_file_path = f"{file_path}.py"
                    repaired_plan[new_file_path] = functions
                else:
                    # This shouldn't happen given the validation issues, but just in case
                    repaired_plan[file_path] = functions

    return repaired_plan


def _repair_functions_format(plan: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Repair invalid functions format in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of function format issues to address

    Returns:
        Repaired plan with valid functions format
    """
    repaired_plan = {}

    for file_path, functions in plan.items():
        # Check if this file's functions need repair
        needs_repair = False
        for issue in issues:
            if issue.get("file_path") == file_path:
                needs_repair = True
                break

        if not needs_repair or isinstance(functions, list):
            # Keep valid functions as is
            repaired_plan[file_path] = functions
        else:
            # Convert non-list functions to a list
            if isinstance(functions, dict):
                # Single function as a dictionary, wrap in list
                repaired_plan[file_path] = [functions]
            elif isinstance(functions, str):
                # String describing a function, convert to proper format
                repaired_plan[file_path] = [{
                    "function": functions,
                    "description": "Auto-generated function description",
                    "element_id": f"auto_generated_{file_path.replace('.', '_').replace('/', '_')}",
                    "steps": [
                        {
                            "step_description": "Implement function logic",
                            "pseudo_code": functions,
                            "relevant_data_structures": [],
                            "api_calls_made": [],
                            "error_handling_notes": ""
                        }
                    ],
                    "edge_cases": [],
                    "architecture_issues_addressed": []
                }]
            else:
                # For other types, create an empty list
                repaired_plan[file_path] = []

    return repaired_plan


def _repair_missing_elements(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]],
    system_design: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Repair missing element implementations in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of missing element issues to address
        system_design: The system design data

    Returns:
        Repaired plan with added element implementations
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Group elements by type for better file placement
    elements_by_type = {}

    for issue in issues:
        element_id = issue.get("element_id")
        if not element_id:
            continue

        # Find the element in system design
        element = None
        for e in system_design.get("code_elements", []):
            if isinstance(e, dict) and e.get("element_id") == element_id:
                element = e
                break

        if not element:
            continue

        # Group by element type
        element_type = element.get("element_type", "unknown")
        if element_type not in elements_by_type:
            elements_by_type[element_type] = []
        elements_by_type[element_type].append(element)

    # Add missing elements to appropriate files
    for element_type, elements in elements_by_type.items():
        # Find or create an appropriate file for this element type
        file_path = None

        # First try to find an existing file with similar elements
        for fp, functions in repaired_plan.items():
            if not isinstance(functions, list):
                continue

            for function in functions:
                if not isinstance(function, dict):
                    continue

                # Check function's element_id to find matching element types
                function_element_id = function.get("element_id")
                if not function_element_id:
                    continue

                # Find this function's element
                function_element = None
                for e in system_design.get("code_elements", []):
                    if isinstance(e, dict) and e.get("element_id") == function_element_id:
                        function_element = e
                        break

                if not function_element:
                    continue

                # If this function's element has the same type, use this file
                if function_element.get("element_type") == element_type:
                    file_path = fp
                    break

            if file_path:
                break

        # If no existing file found, create a new one
        if not file_path:
            if element_type == "class":
                file_path = "models.py"
            elif element_type == "function":
                file_path = "functions.py"
            elif "service" in element_type or "controller" in element_type:
                file_path = "services.py"
            else:
                file_path = f"{element_type.replace(' ', '_')}.py"

            # Ensure the file path doesn't conflict with existing ones
            base_path = file_path
            counter = 1
            while file_path in repaired_plan:
                file_path = f"{base_path[:-3]}_{counter}.py"
                counter += 1

            # Create the new file
            repaired_plan[file_path] = []

        # Add element implementations to the file
        for element in elements:
            element_id = element.get("element_id")
            name = element.get("name", "Unknown")
            signature = element.get("signature", f"def {name.lower()}():")

            repaired_plan[file_path].append({
                "function": signature,
                "description": f"Implementation of {name}",
                "element_id": element_id,
                "steps": [
                    {
                        "step_description": "Implement core functionality",
                        "pseudo_code": "# TODO: Implement core functionality",
                        "relevant_data_structures": [],
                        "api_calls_made": [],
                        "error_handling_notes": "Handle potential errors"
                    }
                ],
                "edge_cases": ["Error handling needed"],
                "architecture_issues_addressed": []
            })

    return repaired_plan


def _repair_element_id_references(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]],
    system_design: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Repair invalid element ID references in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of invalid element ID issues to address
        system_design: The system design data

    Returns:
        Repaired plan with fixed element ID references
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Extract all valid element IDs
    valid_element_ids = set()
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "element_id" in element:
            valid_element_ids.add(element["element_id"])

    # Process each issue
    for issue in issues:
        file_path = issue.get("file_path")
        function_index = issue.get("function_index")
        invalid_id = issue.get("invalid_id")

        if not file_path or function_index is None or not invalid_id:
            continue

        if file_path in repaired_plan and isinstance(repaired_plan[file_path], list):
            functions = repaired_plan[file_path]
            if 0 <= function_index < len(functions):
                function = functions[function_index]

                # Try to find a similar valid element ID
                best_match = None
                highest_similarity = 0

                for valid_id in valid_element_ids:
                    similarity = difflib.SequenceMatcher(None, invalid_id, valid_id).ratio()
                    if similarity > highest_similarity and similarity > 0.7:  # Threshold for similarity
                        highest_similarity = similarity
                        best_match = valid_id

                if best_match:
                    # Replace the invalid ID with the best match
                    function["element_id"] = best_match
                else:
                    # No good match found, use the first valid ID as a fallback
                    if valid_element_ids:
                        function["element_id"] = next(iter(valid_element_ids))

    return repaired_plan


def _repair_incomplete_implementations(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]],
    system_design: Dict[str, Any],
    test_implementations: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Repair incomplete function implementations in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of incomplete implementation issues to address
        system_design: The system design data
        test_implementations: The test implementations data

    Returns:
        Repaired plan with completed implementations
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Process each issue
    for issue in issues:
        file_path = issue.get("file_path")
        function_index = issue.get("function_index")
        issue_type = issue.get("issue_type")

        if not file_path or function_index is None:
            continue

        if file_path in repaired_plan and isinstance(repaired_plan[file_path], list):
            functions = repaired_plan[file_path]
            if 0 <= function_index < len(functions):
                function = functions[function_index]

                # Repair missing steps
                if issue_type == "missing_steps" and ("steps" not in function or not function["steps"]):
                    element_id = function.get("element_id")

                    # Find element in system design
                    element = None
                    for e in system_design.get("code_elements", []):
                        if isinstance(e, dict) and e.get("element_id") == element_id:
                            element = e
                            break

                    if element:
                        # Create steps based on element type and description
                        element_type = element.get("element_type", "")

                        # Generate basic steps based on element type
                        if "class" in element_type.lower():
                            function["steps"] = [
                                {
                                    "step_description": "Initialize class attributes",
                                    "pseudo_code": "def __init__(self, ...)
                                        :\n    # Initialize attributes",                                    "relevant_data_structures": [],
                                    "api_calls_made": [],
                                    "error_handling_notes": ""
                                },
                                {
                                    "step_description": "Implement core methods",
                                    "pseudo_code": "# Core methods implementation",
                                    "relevant_data_structures": [],
                                    "api_calls_made": [],
                                    "error_handling_notes": ""
                                }
                            ]
                        else:
                            function["steps"] = [
                                {
                                    "step_description": "Validate input parameters",
                                    "pseudo_code": "# Input validation",
                                    "relevant_data_structures": [],
                                    "api_calls_made": [],
                                    "error_handling_notes": "Raise appropriate exception for invalid inputs"
                                },
                                {
                                    "step_description": "Implement core functionality",
                                    "pseudo_code": "# Core implementation",
                                    "relevant_data_structures": [],
                                    "api_calls_made": [],
                                    "error_handling_notes": "Handle potential errors"
                                },
                                {
                                    "step_description": "Return results",
                                    "pseudo_code": "return result",
                                    "relevant_data_structures": [],
                                    "api_calls_made": [],
                                    "error_handling_notes": ""
                                }
                            ]

                # Ensure edge cases field exists
                if "edge_cases" not in function or not isinstance(function["edge_cases"], list):
                    function["edge_cases"] = []

                # Ensure architecture_issues_addressed field exists
                if "architecture_issues_addressed" not in function or not isinstance(function["architecture_issues_addressed"], list):
                    function["architecture_issues_addressed"] = []

    return repaired_plan


def _repair_architecture_issue_coverage(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]],
    architecture_review: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Repair architecture issue coverage in the implementation plan.

    Args:
        plan: The implementation plan to repair
        issues: List of architecture issue coverage issues to address
        architecture_review: The architecture review data

    Returns:
        Repaired plan with addressed architecture issues
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Map element IDs to file paths and function indices
    element_map = {}
    for file_path, functions in repaired_plan.items():
        if not isinstance(functions, list):
            continue

        for idx, function in enumerate(functions):
            if isinstance(function, dict) and "element_id" in function:
                element_id = function["element_id"]
                if element_id not in element_map:
                    element_map[element_id] = []
                element_map[element_id].append((file_path, idx))

    # Process each issue
    for issue in issues:
        issue_type = issue.get("issue_type")
        arch_issue_id = issue.get("arch_issue_id")

        if issue_type == "unaddressed_critical_issue" and arch_issue_id:
            # Find the architecture issue
            arch_issue = None
            for section in ["logical_gaps", "security_concerns", "optimization_opportunities"]:
                for ai in architecture_review.get(section, []):
                    if isinstance(ai, dict) and ai.get("id") == arch_issue_id:
                        arch_issue = ai
                        break
                if arch_issue:
                    break

            if not arch_issue:
                continue

            # Find the target elements for this issue
            target_elements = arch_issue.get("target_element_ids", [])

            # If no target elements specified, try to infer from description
            if not target_elements:
                description = arch_issue.get("description", "")
                # Try to match with element IDs
                for element_id in element_map.keys():
                    if element_id.lower() in description.lower():
                        target_elements.append(element_id)

            # Assign the issue to appropriate functions
            assigned = False
            for element_id in target_elements:
                if element_id in element_map:
                    for file_path, function_idx in element_map[element_id]:
                        function = repaired_plan[file_path][function_idx]

                        # Add the issue to architecture_issues_addressed if not already there
                        if "architecture_issues_addressed" not in function:
                            function["architecture_issues_addressed"] = []

                        if arch_issue_id not in function["architecture_issues_addressed"]:
                            function["architecture_issues_addressed"].append(arch_issue_id)
                            assigned = True

            # If we couldn't assign to a specific function, add it to the first function
            if not assigned and repaired_plan:
                first_file = next(iter(repaired_plan.keys()))
                functions = repaired_plan[first_file]
                if isinstance(functions, list) and functions:
                    first_function = functions[0]
                    if isinstance(first_function, dict):
                        if "architecture_issues_addressed" not in first_function:
                            first_function["architecture_issues_addressed"] = []
                        if arch_issue_id not in first_function["architecture_issues_addressed"]:
                            first_function["architecture_issues_addressed"].append(arch_issue_id)

    return repaired_plan



