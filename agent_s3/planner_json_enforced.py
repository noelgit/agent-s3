# --- START OF FILE planner_json_enforced.py ---
"""
Enhanced planner with enforced JSON output for architecture reviews and test implementation.

This module creates detailed functional and test plans in JSON format by
enforcing specific JSON structure for architecture reviews and test implementations.
"""

import json
import logging
import random
import re
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from agent_s3.tools.implementation_validator import (
    validate_implementation_plan,
    repair_implementation_plan,
    _calculate_implementation_metrics,
)
from agent_s3.json_utils import extract_json_from_text
from agent_s3.tools.context_management.token_budget import TokenEstimator

# Import from the planning module
from agent_s3.planning import (
    repair_json_structure,
    get_stage_system_prompt,
    JSONPlannerError,
    validate_planning_semantic_coherence,
)

# Extracted functions are now imported from the planning module


def repair_json_structure_basic(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Attempt to repair a JSON structure to match the expected schema.

    Args:
        data: The JSON data to repair

    Returns:
        Repaired JSON data
    """
    repaired = {}

    # Ensure original_request exists
    if "original_request" not in data:
        repaired["original_request"] = "Unknown request"
    else:
        repaired["original_request"] = data["original_request"]

    # Ensure feature_groups exists and is a list
    if "feature_groups" not in data or not isinstance(data["feature_groups"], list):
        repaired["feature_groups"] = []
    else:
        repaired["feature_groups"] = []

        # Process each feature group
        for group in data["feature_groups"]:
            if not isinstance(group, dict):
                continue

            repaired_group = {}

            # Ensure group_name exists
            if "group_name" not in group:
                continue  # Skip groups without names
            repaired_group["group_name"] = group["group_name"]

            # Ensure group_description exists
            if "group_description" not in group:
                repaired_group["group_description"] = f"Description for {group['group_name']}"
            else:
                repaired_group["group_description"] = group["group_description"]

            # Ensure features exists and is a list
            if "features" not in group or not isinstance(group["features"], list):
                repaired_group["features"] = []
            else:
                repaired_group["features"] = []

                # Process each feature
                for feature in group["features"]:
                    if not isinstance(feature, dict):
                        continue

                    repaired_feature = {}

                    # Ensure name exists
                    if "name" not in feature:
                        continue  # Skip features without names
                    repaired_feature["name"] = feature["name"]

                    # Ensure description exists
                    if "description" not in feature:
                        repaired_feature["description"] = f"Description for {feature['name']}"
                    else:
                        repaired_feature["description"] = feature["description"]

                    # Ensure files_affected exists
                    if "files_affected" not in feature or not isinstance(feature["files_affected"], list):
                        repaired_feature["files_affected"] = []
                    else:
                        repaired_feature["files_affected"] = feature["files_affected"]

                    # Ensure test_requirements exists
                    if "test_requirements" not in feature or not isinstance(feature["test_requirements"], dict):
                        repaired_feature["test_requirements"] = {
                            "unit_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": [],
                            "test_strategy": {
                                "coverage_goal": "80%",
                                "ui_test_approach": "manual"
                            }
                        }
                    else:
                        repaired_feature["test_requirements"] = feature["test_requirements"]

                        # Ensure test_strategy exists
                        if "test_strategy" not in repaired_feature["test_requirements"]:
                            repaired_feature["test_requirements"]["test_strategy"] = {
                                "coverage_goal": "80%",
                                "ui_test_approach": "manual"
                            }

                    # Ensure dependencies exists
                    if "dependencies" not in feature or not isinstance(feature["dependencies"], dict):
                        repaired_feature["dependencies"] = {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        }
                    else:
                        repaired_feature["dependencies"] = feature["dependencies"]

                    # Ensure risk_assessment exists
                    if "risk_assessment" not in feature or not isinstance(feature["risk_assessment"], dict):
                        repaired_feature["risk_assessment"] = {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": ["unit"],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        }
                    else:
                        repaired_feature["risk_assessment"] = feature["risk_assessment"]

                    # Ensure system_design exists
                    if "system_design" not in feature or not isinstance(feature["system_design"], dict):
                        repaired_feature["system_design"] = {
                            "overview": f"Implementation of {feature['name']}",
                            "code_elements": [],
                            "data_flow": "Standard data flow",
                            "key_algorithms": []
                        }
                    else:
                        repaired_feature["system_design"] = feature["system_design"]

                        # Ensure code_elements exists
                        if "code_elements" not in repaired_feature["system_design"]:
                            repaired_feature["system_design"]["code_elements"] = []

                    repaired_group["features"].append(repaired_feature)

            # Only add the group if it has features
            if repaired_group["features"]:
                repaired["feature_groups"].append(repaired_group)

    # If no valid feature groups were found, create a minimal valid structure
    if not repaired["feature_groups"]:
        repaired["feature_groups"] = [{
            "group_name": "Repaired Feature Group",
            "group_description": "Automatically created during repair",
            "features": [{
                "name": "Main Feature",
                "description": "Automatically created feature",
                "files_affected": [],
                "test_requirements": {
                    "unit_tests": [],
                    "property_based_tests": [],
                    "acceptance_tests": [],
                    "test_strategy": {
                        "coverage_goal": "80%",
                        "ui_test_approach": "manual"
                    }
                },
                "dependencies": {
                    "internal": [],
                    "external": [],
                    "feature_dependencies": []
                },
                "risk_assessment": {
                    "critical_files": [],
                    "potential_regressions": [],
                    "backward_compatibility_concerns": [],
                    "mitigation_strategies": [],
                    "required_test_characteristics": {
                        "required_types": ["unit"],
                        "required_keywords": [],
                        "suggested_libraries": []
                    }
                },
                "system_design": {
                    "overview": "Basic implementation",
                    "code_elements": [],
                    "data_flow": "Standard data flow",
                    "key_algorithms": []
                }
            }]
        }]

    return repaired


logger = logging.getLogger(__name__)

def generate_implementation_plan(
    router_agent,
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any],
    tests: Dict[str, Any],
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate implementation plan based on architecture review and tests.
    Includes comprehensive validation and repair of the implementation plan
    for quality assurance and semantic coherence across planning phases.

    Args:
        router_agent: The LLM router agent for making LLM calls
        system_design: The system design data
        architecture_review: The architecture review data
        tests: The test implementations
        task_description: Original task description
        context: Optional additional context

    Returns:
        Dictionary containing implementation plan with validation metrics and semantic coherence assessment
    """
    logger.info("Generating implementation plan")
    start_time = time.time()

    # Create an enhanced user prompt with explicit guidance on addressing architecture review findings
    # and ensuring test compatibility
    user_prompt = f"""Please create a detailed implementation plan based on the system design, architecture review, and test implementations.

# Task Description
{task_description}

# System Design
{json.dumps(system_design, indent=2)}

# Architecture Review
{json.dumps(architecture_review, indent=2)}

# Tests
{json.dumps(tests, indent=2)}

# Additional Context
{json.dumps(context or {}, indent=2)}

Your task is to create a detailed implementation plan that:
1. Addresses ALL elements in the system design, maintaining correct element_id references
2. Explicitly addresses all logical gaps, security concerns, and optimization suggestions from the architecture review
3. Ensures the implementation will pass ALL the provided tests with specific attention to edge cases
4. Provides step-by-step guidance for implementing each function with detailed error handling
5. Identifies and addresses all edge cases mentioned in tests and additional ones that might arise
6. Implements proper security measures for any security-sensitive operations
7. Maintains canonical implementations to avoid duplication of functionality
8. Provides a clear implementation strategy with phased development sequence
9. Specifies appropriate error handling patterns consistently across all components

For EACH architecture issue from the review:
- Link it explicitly to the functions addressing it using the architecture_issues_addressed field
- Include specific implementation steps that directly resolve the issue
- Ensure all CRITICAL and HIGH severity issues receive thorough implementation details
- Implement proper security measures for security concerns with defensive programming techniques

For EACH test:
- Ensure your implementation steps will satisfy all test assertions
- Include edge cases covered by the tests in your implementation strategy
- Match your function signatures and behavior exactly to what tests expect
- Implement all required functionality to ensure tests pass without modification

Focus on creating a comprehensive and detailed plan that a developer can follow to implement the feature while ensuring that all tests will pass and all architecture issues are properly addressed.
"""

    # Get LLM parameters from json_utils to maintain consistency
    from .json_utils import get_openrouter_json_params
    llm_params = get_openrouter_json_params()

    # Call the LLM with enhanced retry logic
    try:
        # Use a stage-specific planning system prompt for implementation planning
        system_prompt = get_stage_system_prompt("implementation_plan")

        # Use improved retry logic for LLM calls with exponential backoff
        max_retries = 3  # Increased from 2 to 3 for better reliability
        retry_count = 0

        response_text = None
        last_error = None

        while retry_count <= max_retries:
            try:
                logger.info(
                    "Making LLM call attempt %d/%d",
                    retry_count + 1,
                    max_retries + 1,
                )
                estimator = TokenEstimator()
                tokens = estimator.estimate_tokens_for_text(system_prompt) + estimator.estimate_tokens_for_text(user_prompt)
                params = {**llm_params, "max_tokens": max(llm_params.get("max_tokens", 0) - tokens, 0)}
                response_text = router_agent.call_llm_by_role(
                    role="planner",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    config=params
                )

                if not response_text:
                    raise ValueError("Received empty response from LLM")

                logger.info(
                    "Successfully received response from LLM (length: %d chars)",
                    len(response_text),
                )
                break  # Break out of the retry loop if successful

            except Exception as e:
                retry_count += 1
                last_error = e
                logger.warning(
                    "LLM call attempt %d failed: %s",
                    retry_count,
                    str(e),
                )

                if retry_count > max_retries:
                    logger.error(
                        "Failed to get LLM response after %d attempts",
                        max_retries + 1,
                    )
                    raise JSONPlannerError(
                        f"LLM call failed after {max_retries + 1} attempts: {str(last_error)}"
                    )
                # Exponential backoff with jitter
                backoff_time = (2 ** retry_count) + (random.random() * 0.5)
                logger.info("Retrying in %.2f seconds...", backoff_time)
                time.sleep(backoff_time)

        # Enhanced JSON extraction and parsing with robust recovery mechanisms
        try:
            # Initialize response data with default structure
            response_data = {
                "implementation_plan": {},
                "implementation_strategy": {
                    "development_sequence": [],
                    "dependency_management": {
                        "external_dependencies": [],
                        "internal_dependencies": []
                    },
                    "refactoring_needs": [],
                    "canonical_implementation_paths": {}
                },
                "discussion": ""
            }

            # Extract JSON from the response with multiple fallback mechanisms
            json_extraction_start = time.time()
            json_str = extract_json_from_text(response_text)

            if not json_str:
                logger.warning("Failed to extract JSON using primary method. Attempting multiple fallback extraction patterns.")

                # Try different extraction patterns in sequence
                extraction_patterns = [
                    # Code block pattern (most common)
                    (r'```json\n(.*?)\n```', "code block"),

                    # Markdown code block without language specifier
                    (r'```\n(.*?)\n```', "generic code block"),

                    # Direct JSON pattern with optional whitespace
                    (r'(\{\s*"implementation_plan"\s*:.*\})', "direct JSON pattern"),

                    # Broader JSON pattern fallback
                    (r'({[\s\S]*})', "general JSON pattern"),

                    # XML-like pattern (sometimes LLMs wrap JSON in XML-like tags)
                    (r'<json>([\s\S]*?)<\/json>', "XML-like wrapper")
                ]

                for pattern, pattern_name in extraction_patterns:
                    json_match = re.search(pattern, response_text, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        logger.info(
                            "Extracted JSON using %s pattern",
                            pattern_name,
                        )
                        break

                # If all patterns fail, use the full response as a last resort
                if not json_str:
                    json_str = response_text
                    logger.warning("All extraction patterns failed. Using full response as JSON (may cause parsing errors)")

            json_extraction_time = time.time() - json_extraction_start
            logger.info(
                "JSON extraction completed in %.2fs",
                json_extraction_time,
            )

            # Enhanced JSON parsing with advanced repair capabilities
            parse_start = time.time()

            # Try to parse the JSON directly first
            try:
                logger.info("Attempting direct JSON parsing")
                parsed_data = json.loads(json_str)
                logger.info("JSON parsed successfully")

                # Update our response data with parsed data
                for key in parsed_data:
                    response_data[key] = parsed_data[key]

            except json.JSONDecodeError as json_error:
                logger.warning("Direct JSON parsing failed: %s", json_error)
                logger.info("Attempting JSON repair sequence")

                # Multiple repair attempts with different strategies
                repair_strategies = [
                    # Strategy 1: Basic quote replacement and repair
                    lambda js: repair_json_structure(json.loads(js.replace("'", '"'))),

                    # Strategy 2: Remove trailing commas in arrays/objects that cause syntax errors
                    lambda js: repair_json_structure(json.loads(re.sub(r',\s*([}\]])', r'\1', js.replace("'", '"')))),

                    # Strategy 3: Extract just the implementation_plan object if it's identifiable
                    lambda js: {"implementation_plan": json.loads(re.search(r'"implementation_plan"\s*:\s*(\{.*?\})', js, re.DOTALL).group(1))}
                ]

                repaired = False
                for strategy_idx, repair_strategy in enumerate(repair_strategies):
                    try:
                        logger.info(
                            "Attempting repair strategy %d",
                            strategy_idx + 1,
                        )
                        repaired_data = repair_strategy(json_str)

                        # Update our response data with repaired data
                        for key in repaired_data:
                            if key in response_data and repaired_data[key]:
                                response_data[key] = repaired_data[key]

                        logger.info(
                            "Repair strategy %d succeeded",
                            strategy_idx + 1,
                        )
                        repaired = True
                        break
                    except Exception as repair_error:
                        logger.warning(
                            "Repair strategy %d failed: %s",
                            strategy_idx + 1,
                            repair_error,
                        )
                        continue

                if not repaired:
                    logger.error("All repair strategies failed")
                    # We'll continue with our default structured response_data
                    logger.warning("Using minimal default structure for implementation plan")

            parse_time = time.time() - parse_start
            logger.info("JSON parsing/repair completed in %.2fs", parse_time)

            # Comprehensive structure validation
            validate_start = time.time()

            # Check if all required sections exist and create them if missing
            required_sections = {
                "implementation_plan": {},
                "implementation_strategy": {
                    "development_sequence": [],
                    "dependency_management": {
                        "external_dependencies": [],
                        "internal_dependencies": []
                    },
                    "refactoring_needs": [],
                    "canonical_implementation_paths": {}
                },
                "discussion": ""
            }

            is_valid = True
            for section, default_value in required_sections.items():
                if section not in response_data:
                    logger.warning(
                        "Missing required section '%s' in response",
                        section,
                    )
                    response_data[section] = default_value
                    is_valid = False
                elif not response_data[section] and default_value:
                    # Section exists but is empty when it shouldn't be
                    logger.warning(
                        "Section '%s' is empty, initializing with default structure",
                        section,
                    )
                    response_data[section] = default_value
                    is_valid = False

            # Additional validation for nested structures
            if "implementation_strategy" in response_data:
                strategy = response_data["implementation_strategy"]
                if not isinstance(strategy, dict):
                    logger.warning("implementation_strategy is not a dictionary, reinitializing")
                    response_data["implementation_strategy"] = required_sections["implementation_strategy"]
                    is_valid = False
                else:
                    for key, default in required_sections["implementation_strategy"].items():
                        if key not in strategy:
                            logger.warning(
                                "Missing required strategy component '%s', adding default",
                                key,
                            )
                            strategy[key] = default
                            is_valid = False

            if not is_valid:
                logger.warning("Response structure validation failed, proceeding with repaired structure")

            validate_time = time.time() - validate_start
            logger.info("Structure validation completed in %.2fs", validate_time)


            # Comprehensive implementation plan validation
            validation_start = time.time()
            logger.info("Beginning implementation plan validation")

            implementation_plan = response_data["implementation_plan"]

            # Prepare data for validation
            # Extract element IDs for validation and metric calculation
            element_ids = set()
            for element in system_design.get("code_elements", []):
                if isinstance(element, dict) and "element_id" in element:
                    element_ids.add(element["element_id"])

            # Extract architecture issues for validation
            architecture_issues = []
            if "logical_gaps" in architecture_review:
                for gap in architecture_review["logical_gaps"]:
                    if isinstance(gap, dict):
                        severity = gap.get("severity", "Medium")
                        architecture_issues.append({
                            "id": gap.get("id", ""),
                            "description": gap.get("description", ""),
                            "severity": severity,
                            "issue_type": "logical_gap"
                        })

            if "security_concerns" in architecture_review:
                for concern in architecture_review["security_concerns"]:
                    if isinstance(concern, dict):
                        severity = concern.get("severity", "High") # Default security concerns to high severity
                        architecture_issues.append({
                            "id": concern.get("id", ""),
                            "description": concern.get("description", ""),
                            "severity": severity,
                            "issue_type": "security_concern"
                        })

            # Extract test requirements for validation with more detailed organization
            test_requirements = {}
            for test_type, test_list in tests.get("tests", {}).items():
                if isinstance(test_list, list):
                    for test in test_list:
                        if isinstance(test, dict) and "target_element_ids" in test:
                            for element_id in test["target_element_ids"]:
                                if element_id not in test_requirements:
                                    test_requirements[element_id] = []
                                # Store test type along with test for better categorization
                                test_with_type = dict(test)
                                test_with_type["test_type"] = test_type
                                test_requirements[element_id].append(test_with_type)

            # Perform validation with detailed logging
            validation_result = validate_implementation_plan(
                implementation_plan,
                system_design,
                architecture_review,
                tests,
            )
            validated_plan = validation_result.data
            validation_issues = validation_result.issues
            needs_repair = validation_result.needs_repair

            # Log validation issues with structured categorization
            issue_types = defaultdict(lambda: defaultdict(int))
            if validation_issues:
                logger.info(
                    "Found %d validation issues in implementation plan",
                    len(validation_issues),
                )
                for issue in validation_issues:
                    severity = issue.get("severity", "unknown")
                    issue_type = issue.get("issue_type", "unknown")
                    issue_types[issue_type][severity] += 1

                    if severity in ["critical", "high"]:
                        logger.warning(
                            "[%s] %s",
                            severity.upper(),
                            issue.get("description", "Unknown issue"),
                        )
                    else:
                        logger.info(
                            "[%s] %s",
                            severity.upper(),
                            issue.get("description", "Unknown issue"),
                        )

                # Log summary of issue types with severity breakdown
                logger.info("Validation issue summary:")
                for issue_type, severities in issue_types.items():
                    severity_counts = ", ".join([f"{severity}: {count}" for severity, count in severities.items()])
                    logger.info(
                        "%s: %d issues (%s)",
                        issue_type,
                        sum(severities.values()),
                        severity_counts,
                    )

            validation_time = time.time() - validation_start
            logger.info(
                "Implementation validation completed in %.2fs",
                validation_time,
            )

            # Calculate comprehensive implementation metrics
            metrics_start = time.time()

            # Calculate base metrics
            metrics = _calculate_implementation_metrics(
                validated_plan,
                element_ids,
                architecture_issues,
                test_requirements
            )

            # Add additional metrics for better assessment
            metrics["validation_time_seconds"] = validation_time
            metrics["issue_count_by_type"] = {k: sum(v.values()) for k, v in issue_types.items()}
            metrics["issue_count_by_severity"] = {
                severity: sum(counts.get(severity, 0) for counts in issue_types.values())
                for severity in ["critical", "high", "medium", "low"]
            }

            logger.info(f"Implementation metrics: Overall score: {metrics['overall_score']:.2f}, " +
                       f"Element coverage: {metrics['element_coverage_score']:.2f}, " +
                       f"Architecture issue addressal: {metrics['architecture_issue_addressal_score']:.2f}, " +
                                                                                                        f"Test coverage: {metrics['test_coverage_score']:.2f}")

            metrics_time = time.time() - metrics_start
            logger.info("Metrics calculation completed in %.2fs", metrics_time)

            # Enhanced repair mechanism with quality improvements
            repair_start = time.time()
            repaired_plan = validated_plan  # Default to the validated plan

            if needs_repair:
                logger.info("Repairing implementation plan to fix validation issues")
                try:
                    repaired_plan = repair_implementation_plan(
                        validated_plan,
                        validation_issues,
                        system_design,
                        architecture_review,
                        tests
                    )
                    response_data["implementation_plan"] = repaired_plan

                    # Calculate new metrics after repair
                    new_metrics = _calculate_implementation_metrics(
                        repaired_plan,
                        element_ids,
                        architecture_issues,
                        test_requirements
                    )

                    # Add repair metrics
                    new_metrics["validation_time_seconds"] = validation_time
                    new_metrics["repair_time_seconds"] = time.time() - repair_start
                    new_metrics["pre_repair_score"] = metrics["overall_score"]
                    new_metrics["improvement_percentage"] = ((new_metrics["overall_score"] - metrics["overall_score"]) /
                                                           max(0.001, metrics["overall_score"])) * 100

                    logger.info(f"Post-repair metrics: Overall score: {new_metrics['overall_score']:.2f}, " +
                                                                                                       f"Element coverage: {new_metrics['element_coverage_score']:.2f}, " +
                                                                                                                                                                             f"Architecture issue addressal: {new_metrics['architecture_issue_addressal_score']:.2f}, " +
                                                                                                                                                                                                   f"Test coverage: {new_metrics['test_coverage_score']:.2f}")

                    # Add validation and repair information to the discussion
                    if "discussion" not in response_data:
                        response_data["discussion"] = ""

                    repair_note = "\n\n## Implementation Plan Validation and Repair\n\n"
                    repair_note += (
                        "The implementation plan was automatically validated and "
                        "the following issues were addressed:\n\n"
                    )
                    # Group issues by type and severity for clearer reporting
                    issues_by_category = defaultdict(list)
                    for issue in validation_issues:
                        severity = issue.get("severity", "unknown")
                        issue_type = issue.get("issue_type", "unknown")
                        category = f"{severity.upper()} {issue_type}"
                        issues_by_category[category].append(issue.get("description", "Unknown issue"))

                    for category, descriptions in issues_by_category.items():
                        repair_note += f"### {category} ({len(descriptions)} issues)\n\n"
                        for i, description in enumerate(descriptions[:5]):  # Show at most 5 issues per category
                            repair_note += f"- {description}\n"
                        if len(descriptions) > 5:
                            repair_note += f"- ... and {len(descriptions) - 5} more similar issues\n"
                        repair_note += "\n"
                    # Add metrics improvement summary
                    if new_metrics["overall_score"] > metrics["overall_score"]:
                        improvement = (
                            new_metrics["overall_score"] - metrics["overall_score"]
                        ) * 100
                        repair_note += "\n### Quality Improvement\n\n"
                        repair_note += (
                            f"Overall quality score improved by {improvement:.1f}%.\n"
                            f"- Element coverage: {metrics['element_coverage_score']:.2f} → {new_metrics['element_coverage_score']:.2f}\n"
                            f"- Architecture issue addressal: {metrics['architecture_issue_addressal_score']:.2f} → {new_metrics['architecture_issue_addressal_score']:.2f}\n"
                            f"- Test coverage: {metrics['test_coverage_score']:.2f} → {new_metrics['test_coverage_score']:.2f}\n"
                        )
                    response_data["discussion"] += repair_note

                    # Store validation metrics in response
                    response_data["implementation_metrics"] = new_metrics
                except Exception as repair_error:
                    logger.error("Error during implementation plan repair: %s", repair_error)
                    # Continue with validated plan if repair fails
                    response_data["implementation_plan"] = validated_plan
                    response_data["implementation_metrics"] = metrics
                    response_data["repair_error"] = str(repair_error)
            else:
                logger.info("Implementation plan validation successful")
                response_data["implementation_plan"] = validated_plan
                response_data["implementation_metrics"] = metrics

            repair_time = time.time() - repair_start
            logger.info("Implementation repair completed in %.2fs", repair_time)

            # Run enhanced semantic coherence validation
            coherence_start = time.time()
            try:
                logger.info("Running semantic coherence validation")
                coherence_results = validate_planning_semantic_coherence(
                    router_agent,
                    architecture_review,
                    tests.get("refined_test_requirements", {}),
                    tests,
                    repaired_plan,  # Use the final plan (either validated or repaired)
                    task_description,
                    context,
                    system_design
                )

                # Add semantic coherence results to the response
                if coherence_results:
                    # Add semantic validation to the response
                    response_data["semantic_validation"] = coherence_results

                    # Calculate additional cross-phase metrics
                    if "validation_results" in coherence_results:
                        results = coherence_results["validation_results"]

                        # Add summary of semantic validation to the discussion
                        if "discussion" not in response_data:
                            response_data["discussion"] = ""
                        coherence_note = "\n\n## Semantic Coherence Validation Results\n\n"
                        coherence_note += (
                            "The implementation plan was validated for semantic coherence "
                            "across architecture review, test implementation, and system design.\n\n"
                        )
                        # Add scores
                        coherence_note += "### Validation Scores\n\n"
                        coherence_note += (
                            f"- **Coherence Score**: {results.get('coherence_score', 0.0):.1f}/10\n"
                            f"- **Technical Consistency**: {results.get('technical_consistency_score', 0.0):.1f}/10\n"
                            f"- **Implementation-Test Alignment**: {results.get('implementation_test_alignment_score', 0.0):.2f}/1.0\n"
                        )
                        # Add cross-validation findings
                        if "cross_component_traceability" in results:
                            traceability = results["cross_component_traceability"]
                            coherence_note += (
                                f"- **Traceability Score**: {traceability.get('score', 0.0):.1f}/10\n\n"
                            )
                        # Add security validation results if available
                        if "security_validation" in results:
                            security = results["security_validation"]
                            coherence_note += (
                                f"- **Security Validation**: {security.get('score', 0.0):.1f}/10\n\n"
                            )
                        # Add critical issues if present
                        if "critical_issues" in results and results["critical_issues"]:
                            coherence_note += "### Critical Issues\n\n"
                            for issue in results["critical_issues"][:5]:  # Show at most 5 critical issues
                                issue_desc = issue.get("description", "Unknown issue")
                                issue_severity = issue.get("severity", "critical")
                                coherence_note += f"- **[{issue_severity.upper()}]** {issue_desc}\n"
                            if len(results["critical_issues"]) > 5:
                                coherence_note += f"- ... and {len(results['critical_issues']) - 5} more critical issues\n"
                            coherence_note += "\n"
                        # Add optimization opportunities
                        if "optimization_opportunities" in results and results["optimization_opportunities"]:
                            coherence_note += "### Optimization Opportunities\n\n"
                            for opt in results["optimization_opportunities"][:3]:  # Show top 3 opportunities
                                opt_desc = opt.get("description", "Unknown opportunity")
                                opt_effort = opt.get("implementation_effort", "unknown")
                                opt_benefit = opt.get("expected_benefit", "")
                                coherence_note += f"- **[{opt_effort} effort]** {opt_desc}\n"
                                if opt_benefit:
                                    coherence_note += f"  - Benefit: {opt_benefit}\n"
                            if len(results["optimization_opportunities"]) > 3:
                                coherence_note += f"- ... and {len(results['optimization_opportunities']) - 3} more opportunities\n"
                        response_data["discussion"] += coherence_note
            except Exception as coherence_error:
                logger.error("Semantic coherence validation failed: %s", coherence_error)
                # Add error information without failing the process
                response_data.setdefault("semantic_validation", {})["error"] = str(coherence_error)

            coherence_time = time.time() - coherence_start
            logger.info(
                "Semantic coherence validation completed in %.2fs",
                coherence_time,
            )

            # Add timing information to metrics
            total_time = time.time() - start_time
            response_data.setdefault("implementation_metrics", {}).update({
                "total_processing_time_seconds": total_time,
                "json_extraction_time_seconds": json_extraction_time,
                "parsing_time_seconds": parse_time,
                "validation_time_seconds": validation_time,
                "repair_time_seconds": repair_time,
                "coherence_validation_time_seconds": coherence_time
            })

            logger.info(
                "Implementation plan generation completed in %.2fs",
                total_time,
            )
            return response_data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)

            # Enhanced JSON repair with more aggressive fallback mechanisms
            try:
                logger.info("Attempting aggressive JSON structure repair")

                # Define a more tolerant JSON extraction regex pattern
                json_pattern = r'({[\s\S]*?})'
                matches = re.finditer(json_pattern, response_text, re.DOTALL)

                # Try different potential JSON chunks in the response
                json_candidates = []

                for match in matches:
                    candidate = match.group(1)
                    if len(candidate) > 100:  # Ignore tiny matches
                        json_candidates.append(candidate)

                # Sort candidates by length (longest first - likely to be the full response)
                json_candidates.sort(key=len, reverse=True)

                # Try each candidate with all repair techniques
                for i, candidate in enumerate(json_candidates[:3]):  # Try top 3 candidates
                    logger.info(
                        "Trying JSON candidate %d (length: %d)",
                        i + 1,
                        len(candidate),
                    )

                    try:
                        # Basic text cleaning - replace single quotes, fix trailing commas
                        cleaned = re.sub(r',\s*([}\]])', r'\1', candidate.replace("'", '"'))

                        # Try parsing directly first
                        try:
                            parsed_data = json.loads(cleaned)
                            logger.info("Successfully parsed candidate %d", i + 1)

                            # Validate that it contains implementation_plan
                            if "implementation_plan" in parsed_data:
                                logger.info("Found implementation_plan in parsed data")
                                return parsed_data
                            else:
                                logger.warning("Parsed data missing implementation_plan")
                        except json.JSONDecodeError:
                            # Try repair
                            parsed_data = repair_json_structure(json.loads(cleaned))

                            if "implementation_plan" in parsed_data:
                                logger.info("Successfully repaired candidate %d", i + 1)
                                return parsed_data
                    except Exception as repair_error:
                        logger.warning(
                            "Failed to repair candidate %d: %s",
                            i + 1,
                            repair_error,
                        )
                        continue

                # If all candidates fail, create a minimal valid response
                logger.warning("All JSON extraction and repair attempts failed, creating minimal valid response")

                minimal_response = {
                    "implementation_plan": {},
                    "implementation_strategy": {
                        "development_sequence": [],
                        "dependency_management": {
                            "external_dependencies": [],
                            "internal_dependencies": []
                        },
                        "refactoring_needs": [],
                        "canonical_implementation_paths": {}
                    },
                    "discussion": "Implementation plan generation failed. Please check the logs for details."
                }

                # Extract any potential functions from the text
                function_matches = re.finditer(r'def\s+([a-zA-Z0-9_]+)\s*\((.*?)\)', response_text)
                for match in function_matches:
                    func_name = match.group(1)
                    func_params = match.group(2)
                    # Add as a skeleton entry to implementation plan
                    file_path = f"extracted_function_{func_name}.py"  # Placeholder file
                    if file_path not in minimal_response["implementation_plan"]:
                        minimal_response["implementation_plan"][file_path] = []

                    minimal_response["implementation_plan"][file_path].append({
                        "function": f"def {func_name}({func_params}):",
                        "description": "Function extracted from response text",
                        "steps": [{"step_description": "Implement function logic"}],
                        "edge_cases": ["Extracted from failed parsing, requires manual review"]
                    })

                # Add error information
                minimal_response["error"] = {
                    "message": f"JSON parsing failed: {e}",
                    "recovery": "Minimal implementation plan structure created",
                    "timestamp": datetime.now().isoformat()
                }

                return minimal_response
            except Exception as extract_error:
                logger.error(
                    "All JSON extraction and repair attempts failed: %s",
                    extract_error,
                )
                raise JSONPlannerError(f"Failed to extract or repair JSON: {e} → {extract_error}")

        except ValueError as e:
            logger.error("Invalid response structure: %s", e)
            raise JSONPlannerError(f"Invalid response structure: {e}")

    except Exception as e:
        logger.error("Error generating implementation plan: %s", e)
        raise JSONPlannerError(f"Error generating implementation plan: {e}")

# Configuration object pattern to reduce number of arguments
class PlannerConfig:
    """Configuration class for Planner to reduce instance attributes."""
    def __init__(
        self,
        coordinator=None,
        scratchpad=None,
        tech_stack_detector=None,
        memory_manager=None,
        database_tool=None,
        test_frameworks=None,
        test_critic=None
    ):
        self.coordinator = coordinator
        self.scratchpad = scratchpad or (
            coordinator.scratchpad if coordinator else None
        )
        self.tech_stack_detector = tech_stack_detector
        self.memory_manager = memory_manager
        self.database_tool = database_tool
        self.test_frameworks = test_frameworks or (
            coordinator.test_frameworks if coordinator else None
        )
        self.test_critic = test_critic or (
            coordinator.test_critic if coordinator else None
        )
        # Derived attributes
        self.llm = coordinator.llm if coordinator else None
        self.context_registry = (
            coordinator.context_registry if coordinator else None
        )
        self.config = coordinator.config if coordinator else None
        self.workspace_path = (
            Path(coordinator.config.config.get("workspace_path", "."))
            if coordinator and coordinator.config
            else Path(".")
        )


class Planner:
    """The Planner class is responsible for creating plans for tasks using an LLM with enforced JSON output."""
    def __init__(self, config: PlannerConfig):
        """Initialize the planner with configuration.

        Args:
            config: PlannerConfig instance containing all necessary components
        """
        # Store config instance
        self._config = config

        # Error tracking
        self.last_error = None

    @property
    def coordinator(self):
        """Get the coordinator instance."""
        return self._config.coordinator

    @property
    def scratchpad(self):
        """Get the scratchpad instance."""
        return self._config.scratchpad

    @property
    def tech_stack_detector(self):
        """Get the tech stack detector instance."""
        return self._config.tech_stack_detector

    @property
    def memory_manager(self):
        """Get the memory manager instance."""
        return self._config.memory_manager

    @property
    def database_tool(self):
        """Get the database tool instance."""
        return self._config.database_tool

    @property
    def test_frameworks(self):
        """Get the test frameworks instance."""
        return self._config.test_frameworks

    @property
    def test_critic(self):
        """Get the test critic instance."""
        return self._config.test_critic

    @property
    def llm(self):
        """Get the LLM instance."""
        return self._config.llm

    @property
    def context_registry(self):
        """Get the context registry instance."""
        return self._config.context_registry

    @property
    def config(self):
        """Get the config instance."""
        return self._config.config

    @property
    def workspace_path(self):
        """Get the workspace path."""
        return self._config.workspace_path

    def stop_observer(self):
        """Stops the filesystem observer and event handler timers."""
        if hasattr(self, 'file_system_watcher'):
            self.file_system_watcher.stop()
            if self.scratchpad:
                self.scratchpad.log("Planner", "Stopped filesystem watcher.")

    def validate_pre_planning_for_planner(self, pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that pre-planning output is compatible with the planning phase.

        Args:
            pre_plan_data: Pre-planning data to validate

        Returns:
            Tuple of (is_valid, message)
        """
        compatibility_issues = []

        # Check for feature groups structure
        if not isinstance(pre_plan_data, dict):
            return False, "Pre-planning data must be a dictionary"

        feature_groups = pre_plan_data.get("feature_groups", [])
        if not isinstance(feature_groups, list):
            return False, "Pre-planning data must contain 'feature_groups' list"

        if not feature_groups:
            return False, "Pre-planning data must contain at least one feature group"

        # Validate each feature group
        for group_idx, group in enumerate(feature_groups):
            if not isinstance(group, dict):
                compatibility_issues.append(f"Feature group {group_idx} is not a dictionary")
                continue

            # Check for required fields
            required_group_fields = ["group_name", "features"]
            for field in required_group_fields:
                if field not in group:
                    compatibility_issues.append(f"Feature group {group_idx} missing required field: {field}")

            # Validate features within the group
            features = group.get("features", [])
            if not isinstance(features, list):
                compatibility_issues.append(f"Feature group {group_idx} 'features' must be a list")
                continue

            for feature_idx, feature in enumerate(features):
                if not isinstance(feature, dict):
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} is not a dictionary")
                    continue

                # Check for required feature fields
                required_feature_fields = ["name", "system_design", "test_requirements"]
                for field in required_feature_fields:
                    if field not in feature:
                        compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} missing required field: {field}")

                # Validate system_design structure
                system_design = feature.get("system_design", {})
                if isinstance(system_design, dict):
                    code_elements = system_design.get("code_elements", [])
                    if isinstance(code_elements, list):
                        for elem_idx, element in enumerate(code_elements):
                            if isinstance(element, dict) and "element_id" not in element:
                                compatibility_issues.append(f"Code element {elem_idx} in feature {feature_idx}, group {group_idx} missing element_id")

                # Validate test_requirements structure
                test_requirements = feature.get("test_requirements", {})
                if isinstance(test_requirements, dict):
                    unit_tests = test_requirements.get("unit_tests", [])
                    if isinstance(unit_tests, list):
                        tests_missing_element_ids = sum(1 for test in unit_tests if isinstance(test, dict) and not test.get("target_element_ids"))
                        if tests_missing_element_ids > 0:
                            compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} has {tests_missing_element_ids} unit tests missing target_element_id links")

        # Return compatibility result
        if compatibility_issues:
            message = f"Pre-planning data has {len(compatibility_issues)} compatibility issues for planner phase: {'; '.join(compatibility_issues[:5])}"
            if len(compatibility_issues) > 5:
                message += f" and {len(compatibility_issues) - 5} more issues"
            return False, message
        else:
            return True, "Pre-planning data is compatible with planner phase"


def validate_pre_planning_for_planner(pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Standalone function to validate pre-planning output compatibility with planner.
    
    Args:
        pre_plan_data: Pre-planning data to validate
    
    Returns:
        Tuple of (is_valid, message)
    """
    # Create a temporary planner config for validation
    config = PlannerConfig()
    planner = Planner(config)
    return planner.validate_pre_planning_for_planner(pre_plan_data)


# --- END OF FILE planner_json_enforced.py ---
