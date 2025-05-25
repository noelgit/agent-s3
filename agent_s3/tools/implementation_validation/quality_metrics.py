"""Quality metrics helpers for implementation validation.

This module contains functions for analyzing code quality aspects like
naming consistency, complexity, dependencies, and design patterns.
"""

import re
import logging
from typing import Dict, Any, List, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


def check_function_naming_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
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
            name_match = re.search(r'(?:def|class)\\s+(\\w+)', function_signature)
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

    inconsistent_names = []

    for name in function_names:
        if re.match(snake_case_pattern, name):
            naming_styles["snake_case"] += 1
        elif re.match(camel_case_pattern, name):
            naming_styles["camel_case"] += 1
        elif re.match(pascal_case_pattern, name):
            naming_styles["pascal_case"] += 1
        else:
            naming_styles["other"] += 1
            inconsistent_names.append(name)

    # Determine the predominant style
    predominant_style = max(naming_styles, key=naming_styles.get)

    # Check for inconsistencies
    total_functions = sum(naming_styles.values())
    if total_functions > 0:
        consistency_ratio = naming_styles[predominant_style] / total_functions

        if consistency_ratio < 0.8:  # Less than 80% consistency
            issues.append({
                "type": "naming_consistency",
                "severity": "medium",
                "message": f"Inconsistent naming convention. Predominant style: {predominant_style} ({consistency_ratio:.0%})",
                "details": {
                    "naming_styles": naming_styles,
                    "inconsistent_names": inconsistent_names[:5],  # Show first 5
                    "recommendation": f"Consider standardizing on {predominant_style} convention"
                }
            })

    # Check for duplicate function names
    name_counts = {}
    for name in function_names:
        name_counts[name] = name_counts.get(name, 0) + 1

    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    if duplicates:
        issues.append({
            "type": "duplicate_names",
            "severity": "high",
            "message": f"Found {len(duplicates)} duplicate function names",
            "details": {
                "duplicates": duplicates,
                "recommendation": "Ensure all function names are unique or appropriately scoped"
            }
        })

    return issues


def check_implementation_complexity(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check implementation complexity metrics.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to complexity
    """
    issues = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        file_complexity_issues = []

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check function description length (proxy for complexity)
            description = function.get("description", "")
            if len(description) > 500:
                file_complexity_issues.append({
                    "function": function.get("function", "unknown"),
                    "issue": "overly_complex_description",
                    "description_length": len(description)
                })

            # Check for nested implementation steps
            implementation_steps = function.get("implementation_steps", [])
            if len(implementation_steps) > 15:
                file_complexity_issues.append({
                    "function": function.get("function", "unknown"),
                    "issue": "too_many_steps",
                    "step_count": len(implementation_steps)
                })

            # Check for complex error handling
            error_handling = function.get("error_handling", [])
            if len(error_handling) > 8:
                file_complexity_issues.append({
                    "function": function.get("function", "unknown"),
                    "issue": "complex_error_handling",
                    "error_cases": len(error_handling)
                })

        # If file has many complex functions, flag it
        if len(file_complexity_issues) > 3:
            issues.append({
                "type": "high_complexity",
                "severity": "medium",
                "message": f"File {file_path} has high complexity indicators",
                "details": {
                    "file_path": file_path,
                    "complexity_issues": file_complexity_issues,
                    "recommendation": "Consider breaking down complex functions into smaller helpers"
                }
            })

    return issues


def check_dependency_management(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check dependency management across files and functions.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to dependencies
    """
    issues = []

    # Track dependencies between files
    file_dependencies = defaultdict(set)
    function_dependencies = defaultdict(set)

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check for explicit dependencies
            dependencies = function.get("dependencies", [])
            for dep in dependencies:
                if isinstance(dep, str):
                    # Check if it's a file dependency
                    if dep.endswith(('.py', '.js', '.ts')):
                        file_dependencies[file_path].add(dep)
                    else:
                        function_dependencies[function.get("function", "unknown")].add(dep)

            # Extract implicit dependencies from implementation steps
            impl_steps = function.get("implementation_steps", [])
            for step in impl_steps:
                if isinstance(step, str):
                    # Look for import statements or function calls
                    _extract_implicit_dependencies(step, file_path, function, 
                                                file_dependencies, function_dependencies)

    # Check for circular dependencies
    circular_deps = find_circular_dependencies(file_dependencies)
    if circular_deps:
        issues.append({
            "type": "circular_dependencies",
            "severity": "high",
            "message": f"Found {len(circular_deps)} circular dependency chains",
            "details": {
                "circular_chains": circular_deps,
                "recommendation": "Refactor to eliminate circular dependencies"
            }
        })

    # Check for excessive dependencies
    for file_path, deps in file_dependencies.items():
        if len(deps) > 10:
            issues.append({
                "type": "excessive_dependencies",
                "severity": "medium",
                "message": f"File {file_path} has many dependencies ({len(deps)})",
                "details": {
                    "file_path": file_path,
                    "dependency_count": len(deps),
                    "dependencies": list(deps)[:5],  # Show first 5
                    "recommendation": "Consider reducing dependencies or splitting into smaller modules"
                }
            })

    return issues


def find_circular_dependencies(dependencies: Dict[str, Set[str]]) -> List[List[str]]:
    """
    Find circular dependencies in a dependency graph.

    Args:
        dependencies: Dictionary mapping items to their dependencies

    Returns:
        List of circular dependency chains
    """
    def dfs(node, visited, rec_stack, path):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in dependencies.get(node, set()):
            if neighbor not in visited:
                cycle = dfs(neighbor, visited, rec_stack, path)
                if cycle:
                    return cycle
            elif neighbor in rec_stack:
                # Found a cycle
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]

        rec_stack.remove(node)
        path.pop()
        return None

    circular_dependencies = []
    visited = set()

    for node in dependencies:
        if node not in visited:
            cycle = dfs(node, visited, set(), [])
            if cycle:
                circular_dependencies.append(cycle)

    return circular_dependencies


def check_error_handling_patterns(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check error handling patterns consistency.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to error handling
    """
    issues = []

    error_patterns = defaultdict(int)
    missing_error_handling = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            function_name = function.get("function", "unknown")
            error_handling = function.get("error_handling", [])

            if not error_handling:
                missing_error_handling.append(f"{file_path}::{function_name}")
                continue

            # Analyze error handling patterns
            for error_case in error_handling:
                if isinstance(error_case, dict):
                    error_type = error_case.get("type", "unknown")
                    handling_strategy = error_case.get("handling", "unknown")
                    pattern = f"{error_type}:{handling_strategy}"
                    error_patterns[pattern] += 1

    # Check for missing error handling
    if len(missing_error_handling) > len(implementation_plan) * 0.3:  # 30% threshold
        issues.append({
            "type": "missing_error_handling",
            "severity": "medium",
            "message": f"{len(missing_error_handling)} functions lack error handling",
            "details": {
                "functions_without_error_handling": missing_error_handling[:10],
                "recommendation": "Add appropriate error handling to all functions"
            }
        })

    # Check for inconsistent error handling patterns
    if len(error_patterns) > 10:  # Too many different patterns
        issues.append({
            "type": "inconsistent_error_patterns",
            "severity": "low",
            "message": "Many different error handling patterns detected",
            "details": {
                "pattern_count": len(error_patterns),
                "common_patterns": dict(sorted(error_patterns.items(), 
                                             key=lambda x: x[1], reverse=True)[:5]),
                "recommendation": "Standardize on common error handling patterns"
            }
        })

    return issues


def check_solid_principles(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check adherence to SOLID principles.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to SOLID principles
    """
    issues = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        # Single Responsibility Principle
        if len(functions) > 20:  # Too many functions in one file
            issues.append({
                "type": "srp_violation",
                "severity": "medium", 
                "message": f"File {file_path} may violate Single Responsibility Principle",
                "details": {
                    "function_count": len(functions),
                    "recommendation": "Consider splitting into multiple focused modules"
                }
            })

        # Check for functions with multiple responsibilities
        for function in functions:
            if not isinstance(function, dict):
                continue

            description = function.get("description", "")
            # Look for "and" statements indicating multiple responsibilities
            and_count = description.lower().count(" and ")
            if and_count > 3:
                issues.append({
                    "type": "function_srp_violation",
                    "severity": "low",
                    "message": "Function may have multiple responsibilities",
                    "details": {
                        "function": function.get("function", "unknown"),
                        "file": file_path,
                        "and_statements": and_count,
                        "recommendation": "Consider breaking into smaller, focused functions"
                    }
                })

    return issues


def _extract_implicit_dependencies(
    step: str, 
    file_path: str, 
    function: Dict[str, Any],
    file_dependencies: Dict[str, Set[str]], 
    function_dependencies: Dict[str, Set[str]]
) -> None:
    """Extract implicit dependencies from implementation step text."""
    # Look for import statements
    import_matches = re.findall(r'import\\s+([\\w.]+)', step)
    for match in import_matches:
        if '.' in match:
            # Module import
            module_file = match.replace('.', '/') + '.py'
            file_dependencies[file_path].add(module_file)

    # Look for function calls to external functions
    call_matches = re.findall(r'([\\w_]+)\\s*\\(', step)
    for match in call_matches:
        if not match.startswith('_'):  # Not a private function
            function_dependencies[function.get("function", "unknown")].add(match)