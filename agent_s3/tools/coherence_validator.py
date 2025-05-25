"""
Implementation Coherence Validator Module

This module provides validation and repair functions for ensuring coherence across
implementation aspects including naming conventions, error handling approaches,
API design patterns, and data flow patterns. It helps maintain consistent implementation
patterns across the entire codebase.
"""

import json
import logging
import re
from typing import Dict, Any, List

from .validation_result import ValidationResult

logger = logging.getLogger(__name__)


def validate_implementation_coherence(
    implementation_plan: Dict[str, Any]
) -> ValidationResult:
    """
    Validate coherence across implementations, checking for consistency in naming,
    error handling, API design patterns, and data flow.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        ValidationResult with issues and coherence metrics
    """
    issues: List[Dict[str, Any]] = []

    # Extract implementation_plan dict if it's nested in a larger structure
    if "implementation_plan" in implementation_plan:
        impl_plan = implementation_plan["implementation_plan"]
    else:
        impl_plan = implementation_plan

    # Validate naming consistency
    naming_issues, _ = check_naming_consistency(impl_plan)
    issues.extend(naming_issues)

    # Validate error handling approaches
    error_handling_issues, _ = check_error_handling_consistency(impl_plan)
    issues.extend(error_handling_issues)

    # Validate API design patterns
    api_design_issues, _ = check_api_design_consistency(impl_plan)
    issues.extend(api_design_issues)

    # Validate data flow patterns
    data_flow_issues, _ = check_data_flow_consistency(impl_plan)
    issues.extend(data_flow_issues)

    metrics = calculate_coherence_metrics(impl_plan)
    needs_repair = any(i.get("severity") in ["critical", "high"] for i in issues)

    return ValidationResult(issues=issues, needs_repair=needs_repair, metrics=metrics)


def check_naming_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check naming convention consistency across the implementation plan.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to naming consistency
    """
    issues = []

    # Extract all function names and their signatures
    function_names = []
    function_signatures = {}  # Map names to signatures for detailed analysis
    function_locations = {}  # Track file paths for reporting

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function_idx, function in enumerate(functions):
            if not isinstance(function, dict) or "function" not in function:
                continue

            function_signature = function["function"]

            # Extract just the name part from the signature
            name_match = re.search(r'(?:def|class)\s+(\w+)', function_signature)
            if name_match:
                name = name_match.group(1)
                function_names.append(name)
                function_signatures[name] = function_signature
                function_locations[name] = (file_path, function_idx)

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

    name_to_style = {}

    for name in function_names:
        if re.match(snake_case_pattern, name):
            naming_styles["snake_case"] += 1
            name_to_style[name] = "snake_case"
        elif re.match(camel_case_pattern, name):
            naming_styles["camel_case"] += 1
            name_to_style[name] = "camel_case"
        elif re.match(pascal_case_pattern, name):
            naming_styles["pascal_case"] += 1
            name_to_style[name] = "pascal_case"
        else:
            naming_styles["other"] += 1
            name_to_style[name] = "other"

    # Calculate naming consistency score
    total_names = len(function_names)
    if total_names == 0:
        naming_consistency_score = 1.0
    else:
        # Find the dominant style
        dominant_style = max(naming_styles, key=naming_styles.get)
        dominant_count = naming_styles[dominant_style]
        naming_consistency_score = dominant_count / total_names

    # Detect inconsistencies if we have a significant number of functions
    if total_names >= 3 and naming_consistency_score < 0.8:
        # Find names that don't match the dominant style
        inconsistent_names = []

        for name, style in name_to_style.items():
            if style != dominant_style:
                file_path, function_idx = function_locations.get(name, ("unknown", 0))
                inconsistent_names.append({
                    "name": name,
                    "current_style": style,
                    "file_path": file_path,
                    "function_idx": function_idx,
                    "signature": function_signatures.get(name, "")
                })

        # Report the issue
        if inconsistent_names:
            issues.append({
                "issue_type": "inconsistent_naming_convention",
                "severity": "medium",
                "description": f"Inconsistent naming conventions detected. Dominant style is {dominant_style} " +
                                                                                          f"({dominant_count}/{total_names} functions), but found {len(inconsistent_names)} exceptions.",
                "inconsistent_names": [item["name"] for item in inconsistent_names],
                "dominant_style": dominant_style,
                "naming_consistency_score": naming_consistency_score,
                "detailed_inconsistencies": inconsistent_names
            })

    return issues, naming_consistency_score


def check_error_handling_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check error handling approach consistency across functions.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to error handling consistency
    """
    issues = []

    # Track different error handling approaches
    error_handling_approaches = {
        "exception_based": 0,
        "return_code_based": 0,
        "optional_return_based": 0,
        "callback_based": 0,
        "no_error_handling": 0
    }

    functions_with_error_handling = []
    functions_without_error_handling = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function_idx, function in enumerate(functions):
            if not isinstance(function, dict):
                continue

            # Look for error handling in steps
            error_approach = "no_error_handling"
            has_error_handling = False

            steps = function.get("steps", [])
            function_signature = function.get("function", "")

            # Check if function signature indicates error handling approach
            if "raise " in function_signature or "Exception" in function_signature:
                error_approach = "exception_based"
                has_error_handling = True
            elif "Optional[" in function_signature or "Union[" in function_signature and "None" in function_signature:
                error_approach = "optional_return_based"
                has_error_handling = True

            # Check individual steps for error handling
            for step in steps:
                if not isinstance(step, dict):
                    continue

                step_desc = step.get("step_description", "").lower()
                error_notes = step.get("error_handling_notes", "").lower()
                pseudo_code = step.get("pseudo_code", "").lower()

                # Look for error handling indicators
                if error_notes:
                    has_error_handling = True

                    if "raise" in error_notes or "exception" in error_notes or "try" in error_notes:
                        error_approach = "exception_based"
                    elif "return none" in error_notes or "return null" in error_notes or "optional" in error_notes:
                        error_approach = "optional_return_based"
                    elif "return error" in error_notes or "return code" in error_notes or "status code" in error_notes:
                        error_approach = "return_code_based"
                    elif "callback" in error_notes:
                        error_approach = "callback_based"

                # Also check step description and pseudo code
                if "exception" in step_desc or "try" in step_desc or "catch" in step_desc or "except" in step_desc:
                    has_error_handling = True
                    error_approach = "exception_based"

                if pseudo_code and ("try" in pseudo_code or "except" in pseudo_code or "raise" in pseudo_code):
                    has_error_handling = True
                    error_approach = "exception_based"

            # Record the approach used
            if has_error_handling:
                error_handling_approaches[error_approach] += 1
                functions_with_error_handling.append({
                    "file_path": file_path,
                    "function_idx": function_idx,
                    "signature": function_signature,
                    "approach": error_approach
                })
            else:
                error_handling_approaches["no_error_handling"] += 1
                functions_without_error_handling.append({
                    "file_path": file_path,
                    "function_idx": function_idx,
                    "signature": function_signature
                })

    # Calculate error handling consistency score
    total_with_handling = sum(count for approach, count in error_handling_approaches.items()
                            if approach != "no_error_handling")

    if total_with_handling == 0:
        error_consistency_score = 0.0
    else:
        # Find the dominant approach
        approaches_with_handling = {k: v for k, v in error_handling_approaches.items()
                                  if k != "no_error_handling"}
        dominant_approach = max(approaches_with_handling, key=approaches_with_handling.get) if approaches_with_handling else "no_error_handling"
        dominant_count = approaches_with_handling.get(dominant_approach, 0)
        error_consistency_score = dominant_count / total_with_handling if total_with_handling > 0 else 1.0

    # Report inconsistency if score is low and we have multiple functions with error handling
    if total_with_handling >= 3 and error_consistency_score < 0.7:
        # Find inconsistent functions
        inconsistent_functions = []
        dominant_approach = max(error_handling_approaches, key=error_handling_approaches.get)

        for func in functions_with_error_handling:
            if func["approach"] != dominant_approach and func["approach"] != "no_error_handling":
                inconsistent_functions.append(func)

        if inconsistent_functions:
            issues.append({
                "issue_type": "inconsistent_error_handling",
                "severity": "medium",
                "description": "Inconsistent error handling approaches detected. " +
                              f"Dominant approach is {dominant_approach}, but found {len(inconsistent_functions)} exceptions.",
                "dominant_approach": dominant_approach,
                "error_consistency_score": error_consistency_score,
                "inconsistent_functions": inconsistent_functions
            })

    # Also flag if many functions lack error handling
    total_functions = total_with_handling + error_handling_approaches["no_error_handling"]
    if total_functions > 5 and error_handling_approaches["no_error_handling"] / total_functions > 0.3:
        issues.append({
            "issue_type": "insufficient_error_handling",
            "severity": "high",
            "description": f"Many functions ({error_handling_approaches['no_error_handling']}/{total_functions}) " +
                                                                          "lack explicit error handling.",
            "functions_without_error_handling": functions_without_error_handling
        })

    return issues, error_consistency_score


def check_api_design_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check API design pattern consistency across the implementation.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to API design consistency
    """
    issues = []

    # Analyze public API functions for parameter and return patterns
    api_patterns = {
        "rest_style": 0,
        "rpc_style": 0,
        "query_style": 0,
        "fluent_style": 0,
        "other": 0
    }

    api_functions = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function_idx, function in enumerate(functions):
            if not isinstance(function, dict) or "function" not in function:
                continue

            function_signature = function["function"]

            # Skip private functions (starting with _)
            name_match = re.search(r'def\s+(_*\w+)', function_signature)
            if not name_match or name_match.group(1).startswith("_"):
                continue

            # Analyze parameter patterns and return types
            rest_indicators = ["get", "post", "put", "delete", "patch"]
            rpc_indicators = ["execute", "invoke", "call", "run", "perform"]
            query_indicators = ["query", "find", "search", "filter", "list", "get_all"]
            fluent_indicators = ["with_", "build", "create", "configure"]

            # Determine pattern based on function name
            name = name_match.group(1).lower() if name_match else ""
            pattern = "other"

            if any(name.startswith(indicator) for indicator in rest_indicators):
                pattern = "rest_style"
            elif any(name.startswith(indicator) for indicator in rpc_indicators):
                pattern = "rpc_style"
            elif any(name.startswith(indicator) for indicator in query_indicators):
                pattern = "query_style"
            elif any(name.startswith(indicator) for indicator in fluent_indicators) or name.startswith("set_"):
                pattern = "fluent_style"

            api_patterns[pattern] += 1

            api_functions.append({
                "file_path": file_path,
                "function_idx": function_idx,
                "signature": function_signature,
                "name": name,
                "pattern": pattern
            })

    # Calculate API pattern consistency score
    total_api_functions = len(api_functions)
    if total_api_functions == 0:
        api_consistency_score = 1.0
    else:
        dominant_pattern = max(api_patterns, key=api_patterns.get)
        dominant_count = api_patterns[dominant_pattern]
        api_consistency_score = dominant_count / total_api_functions

    # Report inconsistency if we have enough API functions and consistency is low
    if total_api_functions >= 5 and api_consistency_score < 0.6:
        # Find inconsistent functions
        inconsistent_functions = []
        dominant_pattern = max(api_patterns, key=api_patterns.get)

        for func in api_functions:
            if func["pattern"] != dominant_pattern:
                inconsistent_functions.append(func)

        if inconsistent_functions:
            issues.append({
                "issue_type": "inconsistent_api_design",
                "severity": "medium",
                "description": "Inconsistent API design patterns detected. " +
                              f"Dominant pattern is {dominant_pattern}, but found {len(inconsistent_functions)} exceptions.",
                "dominant_pattern": dominant_pattern,
                "api_consistency_score": api_consistency_score,
                "inconsistent_functions": inconsistent_functions
            })

    return issues, api_consistency_score


def check_data_flow_consistency(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check data flow pattern consistency across the implementation.

    Args:
        implementation_plan: The implementation plan to validate

    Returns:
        List of validation issues related to data flow consistency
    """
    issues = []

    # Analyze data flow patterns
    data_flow_patterns = {
        "transform_pipeline": 0,
        "repository_pattern": 0,
        "pubsub_pattern": 0,
        "callback_pattern": 0,
        "direct_manipulation": 0,
        "other": 0
    }

    functions_with_data_flow = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function_idx, function in enumerate(functions):
            if not isinstance(function, dict):
                continue

            function_signature = function.get("function", "")
            steps = function.get("steps", [])

            # Skip functions without steps
            if not steps:
                continue

            data_structures = []
            api_calls = []
            flow_indicators = set()

            # Collect data structures and API calls from all steps
            for step in steps:
                if not isinstance(step, dict):
                    continue

                step_desc = step.get("step_description", "").lower()
                structures = step.get("relevant_data_structures", [])
                calls = step.get("api_calls_made", [])

                if isinstance(structures, list):
                    data_structures.extend(structures)
                if isinstance(calls, list):
                    api_calls.extend(calls)

                # Look for flow pattern indicators in step descriptions
                if any(word in step_desc for word in ["transform", "convert", "map", "reduce", "filter", "pipeline"]):
                    flow_indicators.add("transform_pipeline")
                if any(word in step_desc for word in ["repository", "store", "retrieve", "persistence", "dao"]):
                    flow_indicators.add("repository_pattern")
                if any(word in step_desc for word in ["publish", "subscribe", "event", "message", "notification"]):
                    flow_indicators.add("pubsub_pattern")
                if any(word in step_desc for word in ["callback", "async", "promise", "future", "completion"]):
                    flow_indicators.add("callback_pattern")
                if any(word in step_desc for word in ["modify", "update", "direct", "in-place", "manipulate"]):
                    flow_indicators.add("direct_manipulation")

            # Determine dominant pattern for this function
            if flow_indicators:
                # Use the most specific pattern if multiple are detected
                if "transform_pipeline" in flow_indicators:
                    pattern = "transform_pipeline"
                elif "repository_pattern" in flow_indicators:
                    pattern = "repository_pattern"
                elif "pubsub_pattern" in flow_indicators:
                    pattern = "pubsub_pattern"
                elif "callback_pattern" in flow_indicators:
                    pattern = "callback_pattern"
                elif "direct_manipulation" in flow_indicators:
                    pattern = "direct_manipulation"
                else:
                    pattern = "other"

                data_flow_patterns[pattern] += 1

                functions_with_data_flow.append({
                    "file_path": file_path,
                    "function_idx": function_idx,
                    "signature": function_signature,
                    "pattern": pattern,
                    "data_structures": data_structures,
                    "api_calls": api_calls
                })

    # Calculate data flow consistency score
    total_flow_functions = len(functions_with_data_flow)
    if total_flow_functions == 0:
        flow_consistency_score = 1.0
    else:
        dominant_flow = max(data_flow_patterns, key=data_flow_patterns.get)
        dominant_count = data_flow_patterns[dominant_flow]
        flow_consistency_score = dominant_count / total_flow_functions

    # Report inconsistency if we have enough functions and consistency is low
    if total_flow_functions >= 5 and flow_consistency_score < 0.6:
        # Find inconsistent functions
        inconsistent_functions = []
        dominant_flow = max(data_flow_patterns, key=data_flow_patterns.get)

        for func in functions_with_data_flow:
            if func["pattern"] != dominant_flow:
                inconsistent_functions.append(func)

        if inconsistent_functions:
            issues.append({
                "issue_type": "inconsistent_data_flow",
                "severity": "medium",
                "description": "Inconsistent data flow patterns detected. " +
                              f"Dominant pattern is {dominant_flow}, but found {len(inconsistent_functions)} exceptions.",
                "dominant_flow": dominant_flow,
                "flow_consistency_score": flow_consistency_score,
                "inconsistent_functions": inconsistent_functions
            })

    return issues, flow_consistency_score


def calculate_coherence_metrics(implementation_plan: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate coherence metrics for the implementation plan.

    Args:
        implementation_plan: The implementation plan to analyze

    Returns:
        Dictionary of coherence metric scores (0.0 to 1.0)
    """
    metrics = {}

    # Calculate naming consistency score
    naming_issues, naming_score = check_naming_consistency(implementation_plan)
    metrics["naming_consistency_score"] = naming_score

    # Calculate error handling consistency score
    error_issues, error_score = check_error_handling_consistency(implementation_plan)
    metrics["error_handling_consistency_score"] = error_score

    # Calculate API design pattern consistency score
    api_issues, api_score = check_api_design_consistency(implementation_plan)
    metrics["api_design_consistency_score"] = api_score

    # Calculate data flow pattern consistency score
    flow_issues, flow_score = check_data_flow_consistency(implementation_plan)
    metrics["data_flow_consistency_score"] = flow_score

    # Calculate overall pattern consistency score (weighted average)
    weights = {
        "naming_consistency_score": 0.25,
        "error_handling_consistency_score": 0.30,
        "api_design_consistency_score": 0.25,
        "data_flow_consistency_score": 0.20
    }

    weighted_sum = sum(metrics[metric] * weight for metric, weight in weights.items())
    metrics["pattern_consistency_score"] = weighted_sum

    return metrics


def repair_inconsistent_patterns(
    implementation_plan: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Repair inconsistent implementation patterns by updating documentation.

    Args:
        implementation_plan: The implementation plan to repair
        issues: List of issues related to pattern inconsistencies

    Returns:
        Repaired plan with improved pattern consistency documentation
    """
    repaired_plan = json.loads(json.dumps(implementation_plan))

    # Extract implementation_plan dict if it's nested in a larger structure
    if "implementation_plan" in repaired_plan:
        impl_plan = repaired_plan["implementation_plan"]
    else:
        impl_plan = repaired_plan
        # Create a properly structured plan
        repaired_plan = {"implementation_plan": impl_plan}

    # Ensure implementation_strategy exists
    if "implementation_strategy" not in repaired_plan:
        repaired_plan["implementation_strategy"] = {}

    # Add a new section for pattern guidelines
    strategy = repaired_plan["implementation_strategy"]
    if "pattern_guidelines" not in strategy:
        strategy["pattern_guidelines"] = {}

    guidelines = strategy["pattern_guidelines"]

    # Process each issue and add guidelines
    for issue in issues:
        if issue.get("issue_type") == "inconsistent_naming_convention":
            guidelines["naming_convention"] = {
                "dominant_style": issue.get("dominant_style", "snake_case"),
                "description": f"Use {issue.get('dominant_style', 'snake_case')} for all function and variable names",
                "examples": {
                    "snake_case": "process_data, get_user_by_id",
                    "camelCase": "processData, getUserById",
                    "PascalCase": "ProcessData, GetUserById"
                },
                "exceptions": "Class names should use PascalCase regardless of the dominant style"
            }

        elif issue.get("issue_type") == "inconsistent_error_handling":
            guidelines["error_handling"] = {
                "dominant_approach": issue.get("dominant_approach", "exception_based"),
                "description": f"Use {issue.get('dominant_approach', 'exception_based')} error handling consistently",
                "examples": {
                    "exception_based": "raise ValueError('Invalid input')",
                    "return_code_based": "return ErrorResult(code=404, message='Not found')",
                    "optional_return_based": "return None if not found"
                },
                "exceptions": "External API interfaces may need to maintain their own conventions"
            }

        elif issue.get("issue_type") == "inconsistent_api_design":
            guidelines["api_design"] = {
                "dominant_pattern": issue.get("dominant_pattern", "rest_style"),
                "description": f"Use {issue.get('dominant_pattern', 'rest_style')} API design consistently",
                "examples": {
                    "rest_style": "get_user(id), create_user(data), update_user(id, data)",
                    "rpc_style": "execute_user_query(params), perform_user_creation(data)",
                    "query_style": "find_users_by_role(role), search_orders(criteria)"
                },
                "exceptions": "Internal utility functions may follow different patterns"
            }

        elif issue.get("issue_type") == "inconsistent_data_flow":
            guidelines["data_flow"] = {
                "dominant_flow": issue.get("dominant_flow", "transform_pipeline"),
                "description": f"Use {issue.get('dominant_flow', 'transform_pipeline')} data flow pattern consistently",
                "examples": {
                    "transform_pipeline": "data -> validate -> transform -> store",
                    "repository_pattern": "repository.save(entity), repository.find_by_id(id)",
                    "pubsub_pattern": "event_bus.publish(event), subscriber.on_event(handler)"
                },
                "exceptions": "Low-level utility functions may use direct manipulation"
            }

    # Add pattern guidelines to discussion for visibility
    if issues and "discussion" in repaired_plan:
        repaired_plan["discussion"] += "\n\nIMPORTANT PATTERN GUIDELINES:\n"
        for pattern_type, guide in guidelines.items():
            repaired_plan["discussion"] += f"\n{pattern_type.upper()}: {guide['description']}\n"
            repaired_plan[
                "discussion"
            ] += (
                "Dominant pattern: "
                f"{guide.get('dominant_style') or guide.get('dominant_approach') or guide.get('dominant_pattern') or guide.get('dominant_flow')}\n"
            )
    return repaired_plan
