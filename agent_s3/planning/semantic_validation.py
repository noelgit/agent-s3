"""Semantic validation utilities for planning module.

This module contains functions for validating semantic coherence between
different planning phase outputs.
"""

import logging
from typing import Dict, Any, List

from .llm_integration import call_llm_with_retry, parse_and_validate_json
# Removed import that's not available

logger = logging.getLogger(__name__)


def validate_planning_semantic_coherence(
    router_agent,
    architecture_review,
    refined_test_specs,
    test_implementations,
    implementation_plan,
    task_description,
    context=None,
    system_design=None
):
    """
    Validates the semantic coherence between different planning phase outputs.

    This function ensures that there is consistency and logical coherence between the architecture review,
    test specifications, test implementations, and implementation plan. It helps identify any disconnects
    that might lead to issues in later phases.

    Args:
        router_agent: The LLM router agent
        architecture_review: The architecture review data
        refined_test_specs: The refined test specifications data
        test_implementations: The test implementation data
        implementation_plan: The implementation plan data
        task_description: Original task description
        context: Optional additional context
        system_design: Optional system design data for element ID validation

    Returns:
        Dictionary containing validation results with coherence scores and issue details
    """
    logger.info("Validating semantic coherence between planning phase outputs")

    try:
        # Perform individual validations
        validation_results = _perform_individual_validations(
            architecture_review, refined_test_specs, test_implementations, implementation_plan
        )

        # Perform cross-validation between components
        cross_validation_results = _perform_cross_validation(
            architecture_review, refined_test_specs, test_implementations, implementation_plan
        )

        # Calculate coherence metrics
        coherence_metrics = _calculate_coherence_metrics(
            validation_results, cross_validation_results
        )

        # Generate LLM-based semantic validation
        llm_validation = _perform_llm_semantic_validation(
            router_agent, architecture_review, refined_test_specs, 
            test_implementations, implementation_plan, task_description, context
        )

        # Combine all validation results
        final_results = _combine_validation_results(
            validation_results, cross_validation_results, 
            coherence_metrics, llm_validation
        )

        logger.info("Semantic coherence validation completed successfully")
        return final_results

    except Exception as e:
        logger.error("Error during semantic coherence validation: %s", e)
        return _create_error_validation_result(str(e))


def _perform_individual_validations(
    architecture_review, refined_test_specs, test_implementations, implementation_plan
) -> Dict[str, Any]:
    """Perform individual validation checks on each component."""
    validation_results = {}

    # Validate architecture review
    validation_results["architecture_review"] = _validate_architecture_review_structure(architecture_review)

    # Validate test specifications
    validation_results["test_specifications"] = _validate_test_specs_structure(refined_test_specs)

    # Validate test implementations
    validation_results["test_implementations"] = _validate_test_implementations_structure(test_implementations)

    # Validate implementation plan
    validation_results["implementation_plan"] = _validate_implementation_plan_structure(implementation_plan)

    return validation_results


def _perform_cross_validation(
    architecture_review, refined_test_specs, test_implementations, implementation_plan
) -> Dict[str, Any]:
    """Perform cross-validation between different components."""
    cross_validation = {}

    # Check alignment between architecture review and implementation plan
    cross_validation["arch_to_impl"] = _validate_architecture_implementation_alignment(
        architecture_review, implementation_plan
    )

    # Check alignment between test specs and test implementations
    cross_validation["specs_to_impl"] = _validate_specs_implementation_alignment(
        refined_test_specs, test_implementations
    )

    # Check alignment between implementation plan and test implementations
    cross_validation["impl_to_tests"] = _validate_implementation_test_alignment(
        implementation_plan, test_implementations
    )

    return cross_validation


def _calculate_coherence_metrics(
    validation_results: Dict[str, Any], 
    cross_validation_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate overall coherence metrics."""
    metrics = {}

    # Calculate individual component scores
    component_scores = []
    for component, result in validation_results.items():
        score = result.get("score", 0.0)
        component_scores.append(score)
        metrics[f"{component}_score"] = score

    # Calculate cross-validation scores
    cross_scores = []
    for validation_type, result in cross_validation_results.items():
        score = result.get("score", 0.0)
        cross_scores.append(score)
        metrics[f"{validation_type}_score"] = score

    # Calculate overall coherence score
    all_scores = component_scores + cross_scores
    if all_scores:
        metrics["overall_coherence_score"] = sum(all_scores) / len(all_scores)
    else:
        metrics["overall_coherence_score"] = 0.0

    # Determine coherence level
    overall_score = metrics["overall_coherence_score"]
    if overall_score >= 0.9:
        metrics["coherence_level"] = "high"
    elif overall_score >= 0.7:
        metrics["coherence_level"] = "medium"
    else:
        metrics["coherence_level"] = "low"

    return metrics


def _perform_llm_semantic_validation(
    router_agent, architecture_review, refined_test_specs, 
    test_implementations, implementation_plan, task_description, context
) -> Dict[str, Any]:
    """Perform LLM-based semantic validation."""
    try:
        # Create user prompt for semantic validation
        user_prompt = _create_semantic_validation_prompt(
            architecture_review, refined_test_specs, test_implementations, 
            implementation_plan, task_description, context
        )

        # Get system prompt (using fallback)
        system_prompt = "You are an expert validator. Analyze the semantic coherence between planning components."

        # Get configuration
        config = _get_semantic_validation_config()

        # Call LLM
        response = call_llm_with_retry(
            router_agent,
            system_prompt,
            user_prompt,
            config
        )

        # Parse response
        llm_validation = parse_and_validate_json(
            response,
            enforce_schema=False,  # Flexible schema for validation results
            repair_mode=True
        )

        return llm_validation

    except Exception as e:
        logger.error("LLM semantic validation failed: %s", e)
        return {"error": str(e), "score": 0.0}


def _validate_architecture_review_structure(architecture_review) -> Dict[str, Any]:
    """Validate the structure of architecture review data."""
    if not isinstance(architecture_review, dict):
        return {"valid": False, "score": 0.0, "issues": ["Architecture review is not a dictionary"]}

    issues = []
    score = 1.0

    # Check for required fields
    required_fields = ["logical_gaps", "optimization_suggestions", "security_review"]
    for field in required_fields:
        if field not in architecture_review:
            issues.append(f"Missing {field} in architecture review")
            score -= 0.2

    return {"valid": len(issues) == 0, "score": max(0.0, score), "issues": issues}


def _validate_test_specs_structure(test_specs) -> Dict[str, Any]:
    """Validate the structure of test specifications."""
    if not isinstance(test_specs, dict):
        return {"valid": False, "score": 0.0, "issues": ["Test specs is not a dictionary"]}

    issues = []
    score = 1.0

    # Check for test types
    if "refined_test_specifications" not in test_specs:
        issues.append("Missing refined_test_specifications")
        score -= 0.3

    return {"valid": len(issues) == 0, "score": max(0.0, score), "issues": issues}


def _validate_test_implementations_structure(test_implementations) -> Dict[str, Any]:
    """Validate the structure of test implementations."""
    if not isinstance(test_implementations, dict):
        return {"valid": False, "score": 0.0, "issues": ["Test implementations is not a dictionary"]}

    issues = []
    score = 1.0

    # Check for implementations
    if "test_implementations" not in test_implementations:
        issues.append("Missing test_implementations key")
        score -= 0.3

    return {"valid": len(issues) == 0, "score": max(0.0, score), "issues": issues}


def _validate_implementation_plan_structure(implementation_plan) -> Dict[str, Any]:
    """Validate the structure of implementation plan."""
    if not isinstance(implementation_plan, dict):
        return {"valid": False, "score": 0.0, "issues": ["Implementation plan is not a dictionary"]}

    issues = []
    score = 1.0

    # Check for implementation plan
    if "implementation_plan" not in implementation_plan:
        issues.append("Missing implementation_plan key")
        score -= 0.3

    return {"valid": len(issues) == 0, "score": max(0.0, score), "issues": issues}


def _validate_architecture_implementation_alignment(architecture_review, implementation_plan) -> Dict[str, Any]:
    """Validate alignment between architecture review and implementation plan."""
    issues = []
    score = 1.0

    # Check if implementation addresses architecture gaps
    logical_gaps = architecture_review.get("logical_gaps", [])
    impl_plan = implementation_plan.get("implementation_plan", {})

    if logical_gaps and not impl_plan:
        issues.append("Architecture has logical gaps but implementation plan is empty")
        score -= 0.5

    return {"score": max(0.0, score), "issues": issues}


def _validate_specs_implementation_alignment(test_specs, test_implementations) -> Dict[str, Any]:
    """Validate alignment between test specs and implementations."""
    issues = []
    score = 1.0

    # Basic alignment check
    specs = test_specs.get("refined_test_specifications", {})
    implementations = test_implementations.get("test_implementations", {})

    if specs and not implementations:
        issues.append("Test specifications exist but no implementations found")
        score -= 0.5

    return {"score": max(0.0, score), "issues": issues}


def _validate_implementation_test_alignment(implementation_plan, test_implementations) -> Dict[str, Any]:
    """Validate alignment between implementation plan and test implementations."""
    issues = []
    score = 1.0

    # Basic alignment check
    impl_plan = implementation_plan.get("implementation_plan", {})
    test_impl = test_implementations.get("test_implementations", {})

    if impl_plan and not test_impl:
        issues.append("Implementation plan exists but no test implementations found")
        score -= 0.3

    return {"score": max(0.0, score), "issues": issues}


def _create_semantic_validation_prompt(
    architecture_review, refined_test_specs, test_implementations, 
    implementation_plan, task_description, context
) -> str:
    """Create prompt for LLM-based semantic validation."""
    context_info = ""
    if context:
        context_info = f"\\n\\nAdditional Context:\\n{context}"

    return f"""
Task Description: {task_description}

Please validate the semantic coherence between the following planning outputs:

Architecture Review:
{architecture_review}

Test Specifications:
{refined_test_specs}

Test Implementations:
{test_implementations}

Implementation Plan:
{implementation_plan}

Analyze the coherence, consistency, and alignment between these components.
{context_info}
"""


def _combine_validation_results(
    validation_results, cross_validation_results, coherence_metrics, llm_validation
) -> Dict[str, Any]:
    """Combine all validation results into a comprehensive report."""
    return {
        "individual_validations": validation_results,
        "cross_validations": cross_validation_results,
        "coherence_metrics": coherence_metrics,
        "llm_validation": llm_validation,
        "overall_status": "valid" if coherence_metrics.get("overall_coherence_score", 0) >= 0.7 else "invalid",
        "timestamp": logger.info("Validation completed")
    }


def _get_semantic_validation_config() -> Dict[str, Any]:
    """Get configuration for semantic validation."""
    return {
        "max_tokens": 3000,
        "temperature": 0.1,
        "top_p": 0.7
    }


def _create_error_validation_result(error_message: str) -> Dict[str, Any]:
    """Create error validation result when validation fails."""
    return {
        "error": error_message,
        "overall_status": "error",
        "coherence_metrics": {"overall_coherence_score": 0.0, "coherence_level": "error"},
        "individual_validations": {},
        "cross_validations": {},
        "llm_validation": {}
    }


def _calculate_syntax_validation_percentage(validation_issues: List[Dict[str, Any]]) -> float:
    """Calculate the percentage of syntax validation issues."""
    if not validation_issues:
        return 100.0
    
    syntax_issues = [issue for issue in validation_issues if issue.get("category") == "syntax"]
    return max(0.0, 100.0 - (len(syntax_issues) / len(validation_issues) * 100))


def _calculate_traceability_coverage(validation_issues: List[Dict[str, Any]]) -> float:
    """Calculate traceability coverage percentage."""
    if not validation_issues:
        return 100.0
    
    traceability_issues = [issue for issue in validation_issues if "traceability" in issue.get("type", "")]
    return max(0.0, 100.0 - (len(traceability_issues) / len(validation_issues) * 100))