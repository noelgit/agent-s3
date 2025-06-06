"""
Enhanced pre-planner with enforced JSON output for OpenRouter API integration.

This module is the canonical implementation for pre-planning with enhanced
JSON schema enforcement, validation, repair, and fallbacks for more robust
pre-planning outputs.

Key responsibilities:
1. Define and enforce strict JSON schemas for pre-planning outputs
2. Validate and repair malformed JSON responses from LLMs
3. Provide fallback mechanisms when validation fails
4. Integrate directly with the coordinator
"""

import json
import logging
import os
from typing import Dict, Any, Optional, Tuple, List, Union, Callable

from agent_s3.errors import PrePlanningError
from agent_s3.json_utils import (
    extract_json_from_text,
    get_openrouter_json_params,
    validate_json_schema,
)
from agent_s3.planning import repair_json_structure
from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator
from agent_s3.pre_planner_repair import ensure_element_id_consistency
from agent_s3.common_utils import (
    retry_with_backoff,
    handle_error_with_context,
    create_error_response,
    log_function_entry_exit,
    ProcessingError
)

logger = logging.getLogger(__name__)

# Base system prompt for pre-planning
def get_base_system_prompt() -> str:
    """
    Get the base system prompt for pre-planning.

    This provides the foundational instructions that all pre-planners should follow.
    Specialized implementations may extend this with additional format requirements.

    Returns:
        String containing the base system prompt
    """
    return """You are a skilled software architect and requirements analyst. Your task is to analyze software development requests, decompose them into features, and organize those features into logical groups.

Follow these general guidelines:
1. Analyze the underlying user intent:
   - What is the primary business or technical goal of this request?
   - What problem is the user ultimately trying to solve?
   - Are there unstated requirements or assumptions in this request?
   - What constraints (performance, security, etc.) are important?

2. Consider both the explicit request and the implicit needs:
   - Feature decomposition should align with the true underlying intent
   - Identify any constraints or non-functional requirements

3. Decompose the task into coherent feature groups:
   - Features with strong relationships should be kept in the same group
   - Balance between too many small features and too few large features

4. For each feature group, provide:
   - A clear descriptive name and description
   - A list of features belonging to this group
   - Dependencies between features within and across groups

5. For each feature, provide:
   - A detailed description
   - Files that will be affected
   - Test requirements
   - Risk assessment
   - System design components
"""

# Base user prompt for pre-planning
def get_base_user_prompt(task_description: str) -> str:
    """
    Get the base user prompt for pre-planning.

    This provides the foundation for what to ask the LLM during pre-planning.
    Specialized implementations may extend this with format requirements.

    Args:
        task_description: The original task description

    Returns:
        String containing the base user prompt
    """
    return f"""Analyze this software development request and decompose it into distinct features and feature groups:

{task_description}

Before decomposing into distinct features and feature groups, analyze the underlying user intent:
- What is the primary business or technical goal of this request?
- What problem is the user ultimately trying to solve?
- Are there unstated requirements or assumptions in this request?
- What constraints (performance, security, etc.) are important?

Consider both the explicit request and the implicit needs. Your feature and feature group decomposition should align with the true underlying intent rather than just the surface request.

The decomposition should reflect not just what to build, but also consider:
1. How features interact with and depend on each other
2. Potential risks and mitigation strategies for each feature
3. Impact on existing code and backward compatibility
4. Order of implementation to maximize progress while minimizing integration issues

    Provide comprehensive test requirements, dependencies, risk assessments and acceptance tests for each feature.
"""

def get_json_user_prompt(task_description: str) -> str:
    """Return the user prompt specifically for JSON-enforced planning."""
    base_prompt = get_base_user_prompt(task_description)
    return f"{base_prompt}\n\nRespond in structured JSON only."

# Create fallback pre-planning output
def create_fallback_pre_planning_output(task_description: str) -> Dict[str, Any]:
    """
    Create a minimal fallback pre-planning output when regular pre-planning fails.

    Args:
        task_description: The original task description

    Returns:
        Dictionary with basic pre-planning structure
    """
    feature = {
        "name": "Main Task Implementation",
        "description": task_description,
        "files_affected": ["main.py"],
        "test_requirements": {
            "unit_tests": [
                {
                    "description": "Test main functionality",
                    "target_element": "main_function",
                    "target_element_ids": ["main_function_id"],
                    "inputs": ["basic input"],
                    "expected_outcome": "expected output"
                }
            ],
            "property_based_tests": [],
            "acceptance_tests": [
                {
                    "given": "basic setup",
                    "when": "main function is called",
                    "then": "expected result is returned",
                    "target_element_ids": ["main_function_id"]
                }
            ],
            "test_strategy": {
                "coverage_goal": "80%",
                "ui_test_approach": "manual",
            },
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
            "overview": f"Implementation of {task_description}",
            "code_elements": [
                {
                    "element_type": "function",
                    "name": "main_function",
                    "element_id": "main_function_id",
                    "signature": "def main_function():",
                    "description": "Main function implementation",
                    "key_attributes_or_methods": [],
                    "target_file": "main.py"
                }
            ],
            "data_flow": "Standard data flow",
            "key_algorithms": ["basic implementation"]
        }
    }

    return {
        "original_request": task_description,
        "feature_groups": [
            {
                "group_name": "Default Group",
                "group_description": "Automatically generated fallback group",
                "features": [feature],
            }
        ]
    }

# Alias used by tests
def create_fallback_json(task_description: str) -> Dict[str, Any]:
    """Backward-compatible wrapper for fallback generation."""
    return create_fallback_pre_planning_output(task_description)

# Validate pre-planning output
def validate_pre_planning_output(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Basic validation of pre-planning output for minimal correctness.

    Args:
        data: Pre-planning output to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Pre-planning output is not a dictionary"

    # Check for request info
    if "original_request" not in data:
        return False, "Missing 'original_request' in output"

    # Check for features array
    if "features" not in data or not isinstance(data["features"], list):
        return False, "Missing or invalid 'features' in output"

    if not data["features"]:
        return False, "Features array is empty"

    # Basic feature structure validation
    for i, feature in enumerate(data["features"]):
        if not isinstance(feature, dict):
            return False, f"Feature at index {i} is not a dictionary"

        if "name" not in feature:
            return False, f"Feature at index {i} is missing 'name'"

        if "description" not in feature:
            return False, f"Feature at index {i} is missing 'description'"

    return True, "Pre-planning output is valid"

# JSON schema for validation

# Use the base PrePlanningError as JSONValidationError for backward compatibility
JSONValidationError = PrePlanningError

def get_openrouter_params() -> Dict[str, Any]:
    """Return OpenRouter parameters enforcing JSON output."""
    return get_openrouter_json_params()


def validate_preplan_all(data) -> Tuple[bool, str, Dict[str, Any]]:
    """Run all pre-planning validations and attempt repairs.

    This function validates the plan using multiple validators and, when
    necessary, leverages :class:`PrePlannerJsonValidator` to repair the plan.

    Returns a tuple ``(is_valid, message, plan)`` where ``plan`` is the validated
    (and possibly repaired) plan.
    """

    errors: List[str] = []
    validated_data = data

    # 1. JSON schema validation
    is_valid, validation_msg, _ = validate_json_schema(validated_data)
    if not is_valid:
        errors.append(f"JSON schema validation error: {validation_msg}")

    # 2. Enhanced validation with PrePlannerJsonValidator
    try:
        from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator

        validator = PrePlannerJsonValidator()
        enhanced_valid, enhanced_errors, validated_data = validator.validate_all(
            validated_data
        )
        if not enhanced_valid:
            errors.extend(f"Enhanced validation error: {e}" for e in enhanced_errors)

            # Attempt automatic repair when validation fails
            validated_data, repaired = validator.repair_plan(validated_data, enhanced_errors)
            if repaired:
                # Re-validate after repair
                enhanced_valid, enhanced_errors, validated_data = validator.validate_all(
                    validated_data
                )
                if enhanced_valid:
                    errors.clear()
                else:
                    errors.extend(f"Enhanced validation error: {e}" for e in enhanced_errors)
    except Exception as e:  # pragma: no cover - defensive
        errors.append(f"Enhanced validator exception: {str(e)}")

    # 3. Static plan checker
    try:
        from agent_s3.tools.plan_validator import validate_pre_plan

        static_valid, static_msg = validate_pre_plan(validated_data)
        if not static_valid:
            if isinstance(static_msg, dict) and "critical" in static_msg:
                for err in static_msg["critical"]:
                    errors.append(
                        f"Static plan checker critical error: {err.get('message', '')}"
                    )
            else:
                errors.append(f"Static plan checker error: {static_msg}")
    except Exception as e:  # pragma: no cover - defensive
        errors.append(f"Static plan checker exception: {e}")

    # 4. Planner compatibility
    try:
        from agent_s3.planner_json_enforced import validate_pre_planning_for_planner

        planner_compatible, planner_msg = validate_pre_planning_for_planner(validated_data)
        if not planner_compatible:
            errors.append(f"Planner compatibility error: {planner_msg}")
    except Exception as e:  # pragma: no cover - defensive
        errors.append(f"Planner compatibility check exception: {e}")

    return (len(errors) == 0), "\n".join(errors), validated_data

def integrate_with_coordinator(
    coordinator,
    task_description: str,
    context: Dict[str, Any] = None,
    max_preplanning_attempts: int = 2,
) -> Dict[str, Any]:
    """
    Integrate pre-planning with the coordinator.

    This function is the main entry point for the coordinator to use pre-planning.
    It handles the entire pre-planning workflow and returns the results in a format
    that the coordinator can use.

    Args:
        coordinator: The coordinator instance
        task_description: The task description
        context: Optional context dictionary
        max_preplanning_attempts: Maximum number of attempts for the pre-planning step

    Returns:
        Dictionary containing pre-planning results
    """
    # Get the router agent from the coordinator
    router_agent = coordinator.router_agent

    config = getattr(coordinator, "config", None)
    allow_interactive_clarification = True
    if config and isinstance(getattr(config, "config", None), dict):
        allow_interactive_clarification = config.config.get(
            "allow_interactive_clarification", True
        )

    # Always use enforced JSON mode
    success, pre_planning_data = call_pre_planner_with_enforced_json(
        router_agent,
        task_description,
        context,
        allow_interactive_clarification=allow_interactive_clarification,
    )

    if success:
        # Extract key information for the coordinator
        test_requirements = []
        dependencies = []
        edge_cases = []

        # Process feature groups
        for group in pre_planning_data.get("feature_groups", []):
            for feature in group.get("features", []):
                # Extract test requirements
                if "test_requirements" in feature:
                    test_reqs = feature["test_requirements"]

                    # Unit tests
                    for test in test_reqs.get("unit_tests", []):
                        test_requirements.append({
                            "type": "unit",
                            "description": test.get("description", ""),
                            "target": test.get("target_element", ""),
                            "expected": test.get("expected_outcome", "")
                        })

                    # Acceptance tests
                    for test in test_reqs.get("acceptance_tests", []):
                        test_requirements.append({
                            "type": "acceptance",
                            "given": test.get("given", ""),
                            "when": test.get("when", ""),
                            "then": test.get("then", "")
                        })

                # Extract dependencies
                if "dependencies" in feature:
                    deps = feature["dependencies"]

                    # Internal dependencies
                    for dep in deps.get("internal", []):
                        dependencies.append({
                            "type": "internal",
                            "name": dep,
                            "feature": feature.get("name", "")
                        })

                    # External dependencies
                    for dep in deps.get("external", []):
                        dependencies.append({
                            "type": "external",
                            "name": dep,
                            "feature": feature.get("name", "")
                        })

                    # Feature dependencies
                    for dep in deps.get("feature_dependencies", []):
                        dependencies.append({
                            "type": "feature",
                            "name": dep.get("feature_name", ""),
                            "dependency_type": dep.get("dependency_type", ""),
                            "reason": dep.get("reason", ""),
                            "feature": feature.get("name", "")
                        })

                # Extract edge cases from risk assessment
                if "risk_assessment" in feature:
                    risk = feature["risk_assessment"]

                    # Potential regressions
                    for reg in risk.get("potential_regressions", []):
                        edge_cases.append({
                            "type": "regression",
                            "description": reg,
                            "feature": feature.get("name", "")
                        })

                    # Backward compatibility concerns
                    for concern in risk.get("backward_compatibility_concerns", []):
                        edge_cases.append({
                            "type": "compatibility",
                            "description": concern,
                            "feature": feature.get("name", "")
                        })

        # Assess complexity
        from agent_s3.complexity_analyzer import ComplexityAnalyzer
        complexity_analyzer = ComplexityAnalyzer()
        complexity_result = complexity_analyzer.assess_complexity(
            pre_planning_data,
            task_description=task_description
        )

        # Return results
        return {
            "success": True,
            "uses_enforced_json": True,
            "status": "completed",
            "timestamp": coordinator.get_current_timestamp(),
            "pre_planning_data": pre_planning_data,
            "test_requirements": test_requirements,
            "dependencies": dependencies,
            "edge_cases": edge_cases,
            "is_complex": complexity_result.get("is_complex", False),
            "complexity_score": complexity_result.get("complexity_score", 0),
            "complexity_factors": complexity_result.get("complexity_factors", [])
        }
    else:
        # Return failure
        return {
            "success": False,
            "uses_enforced_json": True,
            "status": "failed",
            "timestamp": coordinator.get_current_timestamp(),
            "error": "Failed to generate pre-planning data"
        }


def _parse_structured_modifications(text: str) -> List[Dict[str, str]]:
    """Parse structured modification requests from text."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    modifications: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    for line in lines:
        if line.startswith("STRUCTURED_MODIFICATIONS"):
            continue
        if line.startswith("Modification") or line == "RAW_INPUT:" or line == "---":
            if current:
                modifications.append(current)
                current = {}
            continue
        if ":" in line:
            key, value = [part.strip() for part in line.split(":", 1)]
            current[key] = value
    if current:
        modifications.append(current)
    required = {"COMPONENT", "LOCATION", "CHANGE_TYPE", "DESCRIPTION"}
    return [m for m in modifications if required.issubset(m)]


def regenerate_pre_planning_with_modifications(
    router_agent, original_results: Dict[str, Any], modification_text: str
) -> Dict[str, Any]:
    """Regenerate pre-planning results based on user modifications."""
    system_prompt = get_json_system_prompt()
    user_prompt = (
        "Modification Request:\n" + modification_text.strip()
    )
    openrouter_params = get_openrouter_params()
    response = router_agent.call_llm_by_role(
        role="pre_planner",
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=openrouter_params,
    )
    status, data = process_response(response, original_results.get("original_request", ""))
    if status is True:
        return data
    raise JSONValidationError("Failed to regenerate pre-planning JSON")


def pre_planning_workflow(
    router_agent,
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
    max_preplanning_attempts: int = 2,
    allow_interactive_clarification: bool = True,
    clarification_callback: Optional[Callable[[str], str]] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Run the JSON-enforced pre-planning workflow.

    Args:
        router_agent: Agent used to call the LLM.
        task_description: The user's task description.
        context: Optional context dictionary passed to the LLM.
        max_preplanning_attempts: Maximum number of attempts to get valid
            pre-planning data.
        allow_interactive_clarification: When ``True`` (default) questions are
            presented via ``input`` for manual clarification. When ``False`` the
            provided ``clarification_callback`` is used instead.
        clarification_callback: Optional callable that returns an answer to a
            clarification question when interactive clarification is disabled.

    The workflow may prompt the user for additional clarification when the
    initial request lacks sufficient detail. Clarification exchanges are
    limited by the ``MAX_CLARIFICATION_ROUNDS`` environment variable
    (default: ``3``). Set this variable to control how many clarification
    prompts are allowed.
    """
    env_attempts = os.getenv("MAX_PREPLANNING_ATTEMPTS")
    if env_attempts is not None:
        try:
            max_preplanning_attempts = int(env_attempts)
        except ValueError:
            max_preplanning_attempts = 2

    system_prompt = get_json_system_prompt()
    user_prompt = get_json_user_prompt(task_description)
    openrouter_params = get_openrouter_params()

    current_prompt = user_prompt
    attempts = 0
    clarification_attempts = 0
    try:
        max_clarifications = int(os.getenv("MAX_CLARIFICATION_ROUNDS", "3"))
    except ValueError:
        max_clarifications = 3

    while attempts < max_preplanning_attempts:
        response = router_agent.call_llm_by_role(
            role="pre_planner",
            system_prompt=system_prompt,
            user_prompt=current_prompt,
            config=openrouter_params,
            tech_stack=context.get("tech_stack") if context else None,
            code_context=context.get("code_context") if context else None,
        )
        status, data = process_response(response, task_description)
        if status is True:
            return True, data

        if status == "question" and clarification_attempts < max_clarifications:
            question = data.get("question", "") if isinstance(data, dict) else ""
            if allow_interactive_clarification:
                answer = input(question + " ")
            elif clarification_callback is not None:
                answer = clarification_callback(question)
            else:
                return False, {}
            try:
                # progress_tracker.logger.info(
                #     json.dumps(
                #         {
                #             "phase": "pre-planning clarification",
                #             "question": question,
                #             "answer": sanitize_text(answer),
                #         }
                #     )
                # )
                pass  # Commented out logging
            except Exception:  # pragma: no cover - logging failure should not crash
                logger.error("Failed to log clarification", exc_info=True)
            current_prompt = answer
            clarification_attempts += 1
            continue

        attempts += 1

    raise JSONValidationError("Failed to generate valid pre-planning data")

def process_response(
    response: str, original_request: str
) -> Tuple[Union[bool, str], Dict[str, Any]]:
    """Validate and interpret an LLM response.

    Args:
        response: The raw response from the LLM.
        original_request: The user's initial request used for context.

    Returns:
        Tuple of ``(status, data)`` where ``status`` is ``True`` when the
        response is valid JSON, ``False`` when validation fails, or the string
        ``"question"``/``"error"`` for special cases. ``data`` contains the
        parsed JSON or an empty dictionary on failure.
    """
    data = None
    error_message = None

    # Try to parse the response as JSON directly
    try:
        if isinstance(response, str):
            data = json.loads(response)
        elif isinstance(response, dict):
            # Response might already be parsed JSON
            data = response
        else:
            error_message = "LLM response is not a string or dictionary."
            logger.warning(error_message + f" Type: {type(response)}")

    except json.JSONDecodeError as e:
        error_message = f"Response is not valid JSON: {e}. Attempting extraction."
        logger.warning(error_message)

    # If direct parsing failed or wasn't possible, try extraction
    if data is None and isinstance(response, str):
        json_text = extract_json_from_text(response)
        if json_text:
            try:
                data = json.loads(json_text)
                error_message = None # Reset error if extraction and parsing succeeded
            except json.JSONDecodeError as e:
                error_message = f"Extracted text is not valid JSON: {e}"
                logger.warning(error_message)
                data = None # Ensure data is None if parsing extracted text fails
        else:
            error_message = "Could not extract JSON object from LLM response text."
            logger.warning(error_message)

    # If we don't have data at this point, return failure
    if data is None:
        return "error", {}

    # Check for the mutually exclusive question form
    if (
        isinstance(data, dict)
        and set(data.keys()) == {"question"}
        and isinstance(data["question"], str)
    ):
        # This is the question form, return special status
        return "question", data

    # Otherwise, validate schema - now with partial validation support
    is_valid, validation_msg, _ = validate_json_schema(data)

    if is_valid:
        return True, data # Fully valid
    else:
        # Try to repair structure only if validation failed completely
        logger.warning(
            "%s",
            "JSON schema validation failed: %s. Attempting repair.",
            validation_msg,
        )
        try:
            repaired = repair_json_structure(data)
            is_valid2, validation_msg2, _ = validate_json_schema(repaired)
            if is_valid2:
                return True, repaired
            else:
                return False, repaired
        except Exception:
            return False, data


def get_json_system_prompt() -> str:
    """
    Get the system prompt that enforces JSON output format.

    This extends the base pre-planner system prompt with specific JSON formatting
    requirements and schema details.

    Returns:
        Properly formatted system prompt string
    """
    # Start with the base pre-planner prompt for consistent foundational instructions
    base_prompt = get_base_system_prompt()

    # Extend with JSON-specific requirements
    json_specific = """You are given this JSON skeleton for feature groups with detailed feature definitions, test requirements, dependencies, risk assessments, and system design. Fill in the arrays with concise and accurate information based on the development request.

**IMPORTANT SIZE CONTROL INSTRUCTIONS:**
For complex requests, prioritize conciseness and focus on the most important features. If the request seems large or complex:
1. Group related functionality into fewer, more cohesive feature groups (aim for 2-4 groups maximum)
2. Focus on core features rather than exhaustive coverage of edge cases
3. Keep descriptions brief but precise
4. Prioritize architectural clarity over implementation details

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce a valid pre-planning JSON:

⚠️ **SAFETY AND SECURITY CONSTRAINTS:**
- NEVER include destructive file operations (rm, deltree, DROP TABLE, etc.)
- NEVER include code that enables command injection
- NEVER include credentials, API keys, or sensitive data
- NEVER suggest operations that could compromise system security
- ALL file operations MUST include proper validation and error handling

1️⃣ **ANALYZE THE REQUEST**
   - Carefully examine the development request to understand its scope and requirements
   - Identify the core functionality being requested
   - Determine the technical domains involved (frontend, backend, database, etc.)
   - Consider the implicit requirements not explicitly stated

2️⃣ **DESIGN FEATURE GROUPS**
   - Organize related functionality into logical feature groups
   - Ensure each group has a clear purpose and boundaries
   - Balance group size (3-7 features per group is ideal)
   - Establish clear relationships between groups

3️⃣ **DEFINE DETAILED FEATURES**
   - Break down each feature group into specific implementable features
   - Provide clear, concise descriptions for each feature
   - Identify all files that will be affected by each feature
   - Rate each feature's complexity from 0 (trivial) to 3 (highly complex)
   - For complex requests, prioritize core features and limit total features to keep plan manageable

4️⃣ **CREATE SYSTEM DESIGN**
   - Define the architectural overview for each feature
   - Specify all code elements (classes, functions, interfaces) with proper signatures
   - Describe data flow patterns clearly
   - Document key algorithms and design patterns to be used
   - Assign unique element_ids to maintain traceability

5️⃣ **PLAN COMPREHENSIVE TESTS**
   - Define unit tests that target specific code elements
   - Create acceptance tests for component interactions
   - Specify property-based tests for invariant properties
   - Design acceptance tests using given-when-then format
   - Ensure every test references specific element_ids for traceability

6️⃣ **ASSESS DEPENDENCIES AND RISKS**
   - Identify internal and external dependencies
   - Document feature-to-feature dependencies with clear relationship types
   - Evaluate potential risks and backward compatibility concerns
   - Provide specific mitigation strategies for identified risks

7️⃣ **FORMAT AS VALID JSON**
   - Structure all information according to the required JSON schema
   - Ensure all required fields are populated
   - Validate that element_ids are consistent across the document
   - Verify that all references between elements are valid

⚠️ **CRITICAL RESPONSE CONSTRAINTS:**

1. You MUST respond in valid JSON format ONLY, with exactly two options:
   - The complete JSON schema (detailed below) for feature groups and features, OR
   - A question JSON: {"question": string}

2. You MUST maintain strict traceability:
   - EVERY test must reference specific code elements via element_ids
   - EVERY feature dependency must be explicitly declared
   - ALL file modifications must be traceable to specific features
   - EVERY section (Architecture, Implementation, Tests) must be complete

3. You MUST prioritize security and safety:
   - NEVER include destructive file operations
   - ALL file operations MUST include proper validation
   - NEVER include code enabling command injection
   - ALWAYS include explicit security review for security-critical features
   - NEVER include blacklisted terms: "rm -rf", "deltree", "format", "DROP TABLE", "DROP DATABASE",
     "DELETE FROM", "TRUNCATE TABLE", "sudo", "chmod 777", "eval(", "exec(", "system(", "shell_exec"

4. You MUST balance detail and conciseness:
   - Focus on significant features rather than exhaustive lists
   - Provide enough detail for implementation without overspecification
   - For complex requests, prioritize high-level structure
   - If the plan is becoming too large, split into smaller feature groups

**JSON SCHEMA DEFINITION:**

```json
{
  "original_request": string,
  "feature_groups": [
    {
      "group_name": string,
      "group_description": string,
      "features": [
        {
          "name": string,
          "description": string,
          "files_affected": [string],
          "test_requirements": {
            "unit_tests": [
              {
                "description": "string (What this unit test should verify)",
                "target_element": "string (e.g., MyClass.my_method, my_function from system_design.code_elements)",
                "target_element_id": "string (The element_id from system_design.code_elements that this test targets)",
                "inputs": ["string (Description of inputs/conditions, e.g., 'user_id=1', 'order_total=0')"],
                "expected_outcome": "string (Description of the expected behavior or result, e.g., 'should return user object', 'throws InvalidOrderTotalError')"
              }
            ],
            "property_based_tests": [
              {
                "description": "string (The property to test, e.g., 'idempotency of create_user function')",
                "target_element": "string (e.g., create_user_function from system_design.code_elements)",
                "target_element_id": "string (The element_id from system_design.code_elements that this test targets)",
                "input_generators": ["string (Description of data generators, e.g., 'random valid email strings', 'integers between 1 and 100')"]
              }
            ],
            "acceptance_tests": [
              {
                "given": "string",
                "when": "string",
                "then": "string"
              }
            ],
            "test_strategy": {
              "coverage_goal": "string (e.g., '85% line coverage for new modules')",
              "ui_test_approach": "string (e.g., 'End-to-end tests using Playwright for critical user flows', 'Snapshot tests for UI components')"
            }
          },
          "dependencies": {
            "internal": [string],
            "external": [string],
            "feature_dependencies": [
              {
                "feature_name": string,
                "dependency_type": string,
                "reason": string
              }
            ]
          },
          "risk_assessment": {
            "critical_files": [string],
            "potential_regressions": [string],
            "backward_compatibility_concerns": [string],
            "mitigation_strategies": [string],
            "required_test_characteristics": {
              "required_types": [string],
              "required_keywords": [string],
              "suggested_libraries": [string]
            }
          },
          "system_design": {
            "overview": "string (High-level architectural overview for this feature)",
            "code_elements": [
              {
                "element_type": "enum (class | function | interface | enum_type | struct)",
                "name": "string (e.g., MyClass, my_function)",
                "element_id": "string (Unique identifier for this element, e.g., auth_service_login_function)",
                "signature": "string (e.g., def my_function(param1: int, param2: str) -> bool:,
                     class MyClass(BaseClass):)",                "description": "string (Purpose and brief description of the element)",
                "key_attributes_or_methods": ["string (For classes: list of important method names or attributes, empty list if not applicable)"],
                "target_file": "string (The planned file path for this element, e.g., src/module/file.py)"
              }
            ],
            "data_flow": "string (Description of data flow related to this feature, including how data is ingested, processed, stored, and outputted)",
            "key_algorithms": ["string (List of key algorithms or logic patterns employed, e.g., 'Depth-First Search for tree traversal', 'SHA-256 for hashing passwords')"]
          }
        }
      ]
    }
  ]
}
```

**IMPLEMENTATION GUIDELINES:**

1️⃣ **SYSTEM DESIGN BEST PRACTICES:**
   - Ensure all function signatures include proper type hints
   - Design clear interfaces between components
   - Follow the principle of least privilege for security-sensitive operations
   - Use appropriate design patterns for the problem domain
   - Maintain consistency with existing architecture patterns

2️⃣ **TEST PLANNING EXCELLENCE:**
   - Ensure tests verify both happy paths and edge cases
   - Link each test to specific code elements via element_ids
   - Include tests for security-critical functionality
   - Design tests that validate performance characteristics where relevant
   - Follow test naming and organization conventions of the target framework

3️⃣ **DEPENDENCY MANAGEMENT:**
   - For "dependency_type" field, use only these values:
     - "blocks" (this feature blocks another)
     - "blocked_by" (this feature is blocked by another)
     - "enhances" (this feature enhances another)
     - "enhanced_by" (this feature is enhanced by another)
   - Clearly document reasons for dependencies
   - Minimize unnecessary dependencies between features

4️⃣ **CODE QUALITY FOCUS:**
    - Identify potential areas of high complexity
    - Flag files with poor test coverage that should be improved
    - Consider maintainability impact of feature design
    - Highlight opportunities to harmonize divergent standards
"""
    return f"{base_prompt}\n\n{json_specific}"


def _prepare_pre_planning_prompt(
    task_description: str, 
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Prepare the prompt for pre-planning LLM call.
    
    Args:
        task_description: The user-provided task description
        context: Optional context dictionary
    
    Returns:
        Prepared prompt dictionary
    """
    system_prompt = get_json_system_prompt()
    user_prompt = get_base_user_prompt(task_description)
    
    prompt = {
        "system": system_prompt,
        "user": user_prompt,
    }
    
    # Attach context under dedicated key
    if context and isinstance(context, dict):
        prompt["context"] = context
    
    return prompt

def _process_pre_planning_response(
    response: str, 
    task_description: str
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """Process LLM response for pre-planning.
    
    Args:
        response: Raw LLM response
        task_description: Original task description
    
    Returns:
        Tuple of (success, processed_data, error_message)
    """
    try:
        status, data = process_response(response, task_description)
        
        if status is True:
            # Ensure element_id consistency and traceability
            data = ensure_element_id_consistency(data)
            # Validate all requirements
            valid, validation_msg, validated_plan = validate_preplan_all(data)
            if valid:
                return True, validated_plan, None
            else:
                return False, data, f"Validation failed: {validation_msg}"
        elif status == "question":
            # LLM is asking for clarification
            return False, data, "question"
        else:
            return False, data, f"Response processing failed: {data}"
    except Exception as e:
        error_msg = handle_error_with_context(e, "processing pre-planning response", logger)
        return False, {}, error_msg

@retry_with_backoff(max_retries=3, base_delay=0.5, logger_instance=logger)
def _attempt_pre_planning_call(
    router_agent,
    prompt: Dict[str, Any],
    openrouter_params: Dict[str, Any]
) -> str:
    """Attempt a single pre-planning LLM call with retry logic.
    
    Args:
        router_agent: The agent responsible for LLM calls
        prompt: Prepared prompt dictionary
        openrouter_params: OpenRouter parameters
    
    Returns:
        LLM response
    
    Raises:
        ProcessingError: If LLM call fails
    """
    try:
        response = router_agent.run(prompt, **openrouter_params)
        if not response:
            raise ProcessingError("Empty response from LLM")
        return response
    except Exception as e:
        raise ProcessingError(f"LLM call failed: {e}")

def _handle_fallback_pre_planning(task_description: str) -> Tuple[bool, Dict[str, Any]]:
    """Handle fallback pre-planning when all attempts fail.
    
    Args:
        task_description: Original task description
    
    Returns:
        Tuple of (success, fallback_data)
    """
    logger.warning("Creating fallback pre-planning output")
    fallback_data = create_fallback_pre_planning_output(task_description)
    
    # Validate fallback data to ensure it meets minimum requirements
    valid, validation_msg, validated_fallback = validate_preplan_all(fallback_data)
    if not valid:
        logger.error("Fallback validation failed: %s", validation_msg)
        return False, create_error_response(
            success=False,
            error_message="Fallback validation failed",
            error_context=validation_msg,
            data=validated_fallback
        )
    
    return False, validated_fallback

@log_function_entry_exit(logger)
def call_pre_planner_with_enforced_json(
    router_agent,
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
    allow_interactive_clarification: bool = True,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Run the JSON-enforced pre-planning workflow using the router_agent.
    This function generates a pre-planning JSON plan, validates and repairs it as needed,
    and ensures strict schema and traceability requirements are met.

    Args:
        router_agent: The agent responsible for LLM calls (must have a .run() method)
        task_description: The user-provided task description
        context: Optional context dictionary
        allow_interactive_clarification: Enable interactive clarification when
            ``True``. Unused currently but accepted for API parity.

    Returns:
        Tuple of (success: bool, pre_planning_data: dict)
    """
    # Prepare the prompt
    prompt = _prepare_pre_planning_prompt(task_description, context)
    openrouter_params = get_openrouter_params()
    
    max_attempts = 3
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Pre-planning attempt {attempt}/{max_attempts}")
            
            # Make LLM call with retry logic
            response = _attempt_pre_planning_call(router_agent, prompt, openrouter_params)
            
            # Process the response
            success, data, error_msg = _process_pre_planning_response(response, task_description)
            
            if success:
                logger.info("Pre-planning completed successfully")
                return True, data
            elif error_msg == "question":
                # LLM is asking for clarification, return as-is
                logger.info("LLM requested clarification")
                return False, data
            else:
                last_error = error_msg
                logger.warning(f"Pre-planning attempt {attempt} failed: {error_msg}")
                
        except ProcessingError as e:
            last_error = str(e)
            logger.warning(f"Pre-planning attempt {attempt} failed: {e}")
        except Exception as e:
            last_error = handle_error_with_context(e, f"pre-planning attempt {attempt}", logger)
    
    # If all attempts failed, use fallback
    logger.error(f"All pre-planning attempts failed. Last error: {last_error}")
    return _handle_fallback_pre_planning(task_description)


class PrePlanner:
    """Wrapper class around pre-planning utilities."""

    def __init__(self, router_agent, config: Optional[Dict[str, Any]] = None):
        self.router_agent = router_agent
        self.config = config or {}
        self.config.setdefault("use_json_enforcement", True)
        self.validator = PrePlannerJsonValidator()

    def generate_pre_planning_data(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        max_preplanning_attempts: int = 2,
    ) -> Dict[str, Any]:
        """Generate initial pre-planning data.

        Args:
            task_description: Description of the requested task.
            context: Optional context dictionary.
            max_preplanning_attempts: Maximum number of attempts for the
                pre-planning step.
        """
        if self.config.get("use_json_enforcement", True):
            success, data = pre_planning_workflow(
                self.router_agent,
                task_description,
                context,
                max_preplanning_attempts=max_preplanning_attempts,
            )
        else:
            system_prompt = get_base_system_prompt()
            user_prompt = get_base_user_prompt(task_description)
            response = self._call_llm_with_retry(system_prompt, user_prompt)
            if not response.get("success"):
                return {
                    "success": False,
                    "pre_planning_data": {},
                    "complexity_assessment": {},
                    "error": response.get("error"),
                }
            status, data = process_response(response.get("response"), task_description)
            success = status is True
        return {
            "success": success,
            "pre_planning_data": data,
            "complexity_assessment": {},
        }

    def regenerate_pre_planning_with_modifications(
        self,
        task_description: str,
        original_results: Dict[str, Any],
        modification_text: str,
    ) -> Dict[str, Any]:
        """Public wrapper to regenerate pre-planning results."""
        return self._regenerate_pre_planning_with_modifications(
            task_description, original_results, modification_text
        )

    def _regenerate_pre_planning_with_modifications(
        self,
        task_description: str,
        original_results: Dict[str, Any],
        modification_text: str,
    ) -> Dict[str, Any]:
        """Regenerate plan incorporating user modifications."""
        if self.config.get("use_json_enforcement", True):
            data = regenerate_pre_planning_with_modifications(
                self.router_agent, original_results, modification_text
            )
        else:
            system_prompt = get_base_system_prompt()
            user_prompt = "Modification Request:\n" + modification_text.strip()
            response = self._call_llm_with_retry(system_prompt, user_prompt)
            if not response.get("success"):
                return {
                    "success": False,
                    "pre_planning_data": {},
                    "complexity_assessment": {},
                    "error": response.get("error"),
                }
            status, data = process_response(
                response.get("response"), original_results.get("original_request", "")
            )
            if status is not True:
                data, _ = self._attempt_repair(data, [])
        return {
            "success": True,
            "pre_planning_data": data,
            "complexity_assessment": {},
        }

    def _attempt_repair(self, data: Dict[str, Any], errors: List[str]) -> Tuple[Dict[str, Any], bool]:
        """Attempt to repair invalid pre-planning data."""
        if self.config.get("use_json_enforcement", True):
            from agent_s3.pre_planner_repair import repair_preplanning_data

            return repair_preplanning_data(data, errors)
        return data, False

    def _call_llm_with_retry(
        self, system_prompt: str, user_prompt: str, max_retries: int = 2
    ) -> Dict[str, Any]:
        """Call the router agent with retry logic."""
        last_error: Optional[str] = None
        for _ in range(max_retries + 1):
            try:
                response = self.router_agent.call_llm_by_role(
                    role="pre_planner",
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    config=self.config.get("llm_params", {}),
                )
                return {"success": True, "response": response}
            except Exception as e:  # pragma: no cover - error path
                import time
                last_error = str(e)
                time.sleep(0.5)
        return {"success": False, "error": last_error or "LLM call failed"}
