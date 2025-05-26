"""
Canonical Implementation Validator Module

This module provides validation and repair functions for ensuring each element
has exactly one canonical implementation in the implementation plan. It helps
prevent duplication of functionality and promotes consistent implementation patterns.
"""
from collections import defaultdict
import json
import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Set

from .validation_result import ValidationResult

logger = logging.getLogger(__name__)


def validate_canonical_implementations(
    implementation_plan: Dict[str, Any],
    element_ids: Set[str]
) -> ValidationResult:
    """
    Validate that each element has exactly one canonical implementation.

    Args:
        implementation_plan: The implementation plan to validate
        element_ids: Set of element IDs from system design

    Returns:
        ValidationResult with any issues found
    """
    issues = []

    # Track implementations by element ID
    implementations_by_element_id = defaultdict(list)

    # Find all implementations for each element ID
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function_idx, function in enumerate(functions):
            if not isinstance(function, dict):
                continue

            element_id = function.get("element_id")
            if element_id:
                implementations_by_element_id[element_id].append({
                    "file_path": file_path,
                    "function_idx": function_idx,
                    "function": function
                })

    # Check for duplicate implementations
    for element_id, implementations in implementations_by_element_id.items():
        if len(implementations) > 1:
            # Found duplicate implementations for an element
            duplicate_files = [impl["file_path"] for impl in implementations]

            issues.append({
                "issue_type": "duplicate_implementation",
                "severity": "critical",
                "description": f"Element {element_id} has multiple implementations in: {', '.join(duplicate_files)}",
                "element_id": element_id,
                "implementations": implementations,
                "recommendation": "Consolidate into a single canonical implementation"
            })

    # Check for missing canonical implementation paths in the implementation strategy
    if "implementation_strategy" in implementation_plan and "canonical_implementation_paths" in implementation_plan["implementation_strategy"]:
        canonical_paths = implementation_plan["implementation_strategy"]["canonical_implementation_paths"]

        # Check that all elements with implementations have a canonical path
        for element_id, implementations in implementations_by_element_id.items():
            if element_id not in canonical_paths and len(implementations) > 0:
                issues.append({
                    "issue_type": "missing_canonical_path",
                    "severity": "medium",
                    "description": f"Element {element_id} is implemented but missing a canonical path declaration",
                    "element_id": element_id,
                    "implementation_files": [impl["file_path"] for impl in implementations]
                })

        # Check that all canonical paths have a corresponding implementation
        for element_id, path in canonical_paths.items():
            if element_id not in implementations_by_element_id:
                issues.append({
                    "issue_type": "unused_canonical_path",
                    "severity": "medium",
                    "description": f"Canonical path defined for element {element_id}, but no implementation exists",
                    "element_id": element_id,
                    "canonical_path": path
                })
            elif not any(impl["file_path"] == path for impl in implementations_by_element_id[element_id]):
                # The canonical path doesn't match any implementation locations
                existing_paths = [impl["file_path"] for impl in implementations_by_element_id[element_id]]
                issues.append({
                    "issue_type": "mismatched_canonical_path",
                    "severity": "medium",
                    "description": f"Canonical path for element {element_id} is {path}, but implementations are in {', '.join(existing_paths)}",
                    "element_id": element_id,
                    "canonical_path": path,
                    "actual_paths": existing_paths
                })
    else:
        # No canonical implementation paths section
        if implementations_by_element_id:  # Only report if there are implementations
            issues.append({
                "issue_type": "missing_canonical_paths_section",
                "severity": "high",
                "description": "Implementation strategy is missing canonical_implementation_paths section",
                "recommendation": "Add canonical_implementation_paths section to implementation_strategy"
            })

    needs_repair = any(issue.get("severity") in ["critical", "high"] for issue in issues)

    return ValidationResult(issues=issues, needs_repair=needs_repair)


def repair_duplicate_implementations(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Repair duplicate implementations by consolidating them into a single canonical implementation.

    Args:
        plan: The implementation plan to repair
        issues: List of duplicate implementation issues to address

    Returns:
        Repaired plan with consolidated implementations
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Process each duplicate implementation issue
    for issue in issues:
        if issue.get("issue_type") != "duplicate_implementation":
            continue

        element_id = issue.get("element_id")
        if not element_id:
            continue

        implementations = issue.get("implementations", [])
        if not implementations:
            continue

        # Choose the canonical implementation (based on various heuristics)
        canonical_impl = find_optimal_implementation(implementations)
        canonical_file = canonical_impl["file_path"]

        # Remove duplicates from other files
        for impl in implementations:
            file_path = impl["file_path"]
            function_idx = impl["function_idx"]

            if file_path != canonical_file:
                # This is a duplicate to remove
                if file_path in repaired_plan:
                    # Filter out the duplicate implementation
                    repaired_plan[file_path] = [
                        func for i, func in enumerate(repaired_plan[file_path])
                        if i != function_idx
                    ]

                    # Remove the file if it's now empty
                    if not repaired_plan[file_path]:
                        del repaired_plan[file_path]

        # If strategy section exists, update canonical implementation paths
        if "implementation_strategy" in repaired_plan:
            if "canonical_implementation_paths" not in repaired_plan["implementation_strategy"]:
                repaired_plan["implementation_strategy"]["canonical_implementation_paths"] = {}

            repaired_plan["implementation_strategy"]["canonical_implementation_paths"][element_id] = canonical_file

    return repaired_plan


def repair_missing_canonical_paths(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Repair missing canonical path declarations in the implementation strategy.

    Args:
        plan: The implementation plan to repair
        issues: List of issues related to canonical paths

    Returns:
        Repaired plan with added canonical paths
    """
    repaired_plan = json.loads(json.dumps(plan))

    # Ensure the canonical paths section exists
    if "implementation_strategy" not in repaired_plan:
        repaired_plan["implementation_strategy"] = {}

    if "canonical_implementation_paths" not in repaired_plan["implementation_strategy"]:
        repaired_plan["implementation_strategy"]["canonical_implementation_paths"] = {}

    # Process each missing canonical path issue
    for issue in issues:
        if issue.get("issue_type") in ["missing_canonical_path", "mismatched_canonical_path"]:
            element_id = issue.get("element_id")
            implementation_files = issue.get("implementation_files") or []

            if element_id and implementation_files:
                # Choose the best file as the canonical path
                canonical_file = implementation_files[0]  # Default to first one
                repaired_plan["implementation_strategy"]["canonical_implementation_paths"][element_id] = canonical_file

        elif issue.get("issue_type") == "unused_canonical_path":
            # Remove unused canonical path
            element_id = issue.get("element_id")
            if element_id and element_id in repaired_plan["implementation_strategy"]["canonical_implementation_paths"]:
                del repaired_plan["implementation_strategy"]["canonical_implementation_paths"][element_id]

    return repaired_plan


def find_optimal_implementation(implementations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Find the best implementation to use as the canonical one based on various heuristics.

    Current heuristics:
    1. Prefer implementations with more detailed steps
    2. Prefer implementations with more edge cases handled
    3. Prefer implementations that address more architecture issues

    Args:
        implementations: List of implementations to choose from

    Returns:
        The selected canonical implementation
    """
    if not implementations:
        raise ValueError("No implementations provided")

    if len(implementations) == 1:
        return implementations[0]

    # Score each implementation
    scored_impls = []
    for impl in implementations:
        function = impl["function"]

        # Calculate a score based on completeness and detail
        score = 0

        # Score based on number of steps
        steps = function.get("steps", [])
        score += len(steps) * 10

        # Score based on edge cases
        edge_cases = function.get("edge_cases", [])
        score += len(edge_cases) * 15

        # Score based on architecture issues addressed
        arch_issues = function.get("architecture_issues_addressed", [])
        score += len(arch_issues) * 20

        # Add detailed step information score
        for step in steps:
            if isinstance(step, dict):
                if step.get("pseudo_code"):
                    score += 5
                if step.get("relevant_data_structures"):
                    score += len(step.get("relevant_data_structures", [])) * 3
                if step.get("api_calls_made"):
                    score += len(step.get("api_calls_made", [])) * 3
                if step.get("error_handling_notes"):
                    score += 8

        scored_impls.append((score, impl))

    # Return the highest-scoring implementation
    best_impl = max(scored_impls, key=lambda x: x[0])[1]
    return best_impl


def validate_and_repair_canonical_implementations(
    implementation_plan: Dict[str, Any],
    element_ids: Set[str]
) -> ValidationResult:
    """
    Validate canonical implementations and repair any issues found.

    Args:
        implementation_plan: The implementation plan to validate and repair
        element_ids: Set of element IDs from system design

    Returns:
        ValidationResult containing the repaired plan and issues
    """
    # Validate canonical implementations
    canonical_result = validate_canonical_implementations(implementation_plan, element_ids)

    if not canonical_result.needs_repair:
        return ValidationResult(
            data=implementation_plan,
            issues=canonical_result.issues,
            needs_repair=False,
        )

    # Repair the plan
    repaired_plan = json.loads(json.dumps(implementation_plan))

    # Group issues by type
    duplicate_issues = [i for i in canonical_result.issues if i["issue_type"] == "duplicate_implementation"]
    path_issues = [i for i in canonical_result.issues if i["issue_type"] in [
        "missing_canonical_path", "mismatched_canonical_path", "unused_canonical_path"
    ]]

    # Apply repairs in sequence
    if duplicate_issues:
        repaired_plan = repair_duplicate_implementations(repaired_plan, duplicate_issues)

    if path_issues:
        repaired_plan = repair_missing_canonical_paths(repaired_plan, path_issues)

    return ValidationResult(
        data=repaired_plan,
        issues=canonical_result.issues,
        needs_repair=True,
    )
