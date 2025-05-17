"""
Enhanced pre-planner with enforced JSON output for OpenRouter API integration.

This module extends the base pre_planner module to provide specialized
JSON schema enforcement, validation, repair, and fallbacks for more robust
pre-planning outputs.

Key responsibilities:
1. Define and enforce strict JSON schemas for pre-planning outputs
2. Validate and repair malformed JSON responses from LLMs
3. Provide fallback mechanisms when validation fails
4. Integrate directly with the coordinator as an alternative to PrePlanningManager
"""

import json
import logging
import re
import time # Added for potential delays in retry
import sys
from typing import Dict, Any, Optional, Tuple, List

# Import base pre-planner functionality
from agent_s3.pre_planner import (
    PrePlanningError,
    get_base_system_prompt,
    get_base_user_prompt,
    create_fallback_pre_planning_output
)

from agent_s3.json_utils import (
    extract_json_from_text,
    get_openrouter_json_params,
    validate_json_schema,
    repair_json_structure,
)

logger = logging.getLogger(__name__)

# JSON schema for validation
REQUIRED_SCHEMA = {
    "original_request": str,
    "feature_groups": list,  # Will validate each feature group separately
}

FEATURE_GROUP_SCHEMA = {
    "group_name": str,
    "group_description": str,
    "features": list  # Will validate each feature separately
}

FEATURE_SCHEMA = {
    "name": str,
    "description": str,
    "files_affected": list,
    "test_requirements": dict,
    "dependencies": dict,
    "risk_assessment": dict,
    "system_design": dict
}

# Use the base PrePlanningError as JSONValidationError for backward compatibility
JSONValidationError = PrePlanningError

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

CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, and you have exactly two options for your response:
1. The original JSON schema below (for feature groups and features), OR
2. A question JSON: {"question": string}

IMPORTANT: You must return ONLY ONE of these JSON objects. Never include both keys or structures in the same response. If you cannot produce the original JSON because the request is unclear or you need more information, respond with the question JSON and ask your clarifying question. Do not attempt to partially fill both or combine them.

Original JSON schema:
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
            "integration_tests": [
              {
                "description": "string (What this integration test should verify)",
                "components_involved": ["string (List of components/modules interacting, e.g., 'AuthService', 'DatabaseModule')"],
                "scenario": "string (Description of the integration scenario, e.g., 'User login with valid credentials and token generation')"
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
            "acceptance_tests": [ // Keep existing structure
              {
                "given": "string",
                "when": "string",
                "then": "string"
              }
            ],
            "test_strategy": { // Keep existing structure
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
                "signature": "string (e.g., def my_function(param1: int, param2: str) -> bool:, class MyClass(BaseClass):)",
                "description": "string (Purpose and brief description of the element)",
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

OR, if you cannot proceed due to lack of clarity or missing information, respond with:
{
  "question": "string (Ask your clarifying question about the request here)"
}

Analyze the code structure and semantics deeply:
- Identify key abstractions and design patterns in the codebase
- Understand the architectural boundaries between components
- Map out data flow patterns and state management approaches
- Recognize existing coding conventions and patterns

Group related features together based on:
- Shared functionality or domain concepts
- Technical dependency relationships
- Similar implementation patterns
- Common testing requirements
- Related user workflows or use cases

System Design:
- For each feature, populate the `system_design` object:
  - `overview`: Provide a high-level architectural overview for this feature.
  - `code_elements`: This is an array. For each new or significantly modified class, function, interface, enum, or struct:
    - `element_type`: Specify the type (class, function, interface, enum_type, struct).
    - `name`: The name of the element (e.g., `MyClass`, `calculate_total_price`).
    - `signature`: Provide the full, correctly typed signature. Examples:
      - Python function: `def calculate_total_price(items: List[Item], discount_percentage: float = 0.0) -> float:`
      - Python class: `class UserSession(BaseModel):`
      - TypeScript function: `function getUser(id: string): Promise<User | null>;`
      - TypeScript interface: `interface ProductOptions { color?: string; size?: 'S' | 'M' | 'L'; }`
    - `description`: Briefly explain the purpose and responsibility of this code element.
    - `key_attributes_or_methods`: For classes, list important method names or attributes. For functions or other types, this can be an empty list `[]`.
    - `target_file`: Specify the intended file path for this element (e.g., `src/services/payment_service.py`, `components/UserProfile.tsx`).
  - `data_flow`: Describe how data is ingested, processed, stored, and outputted in relation to this feature.
  - `key_algorithms`: List any key algorithms or distinct logic patterns used (e.g., "Binary search for product lookup", "Observer pattern for UI updates").
- Ensure all function and method signatures are complete, with explicit type hints for all parameters and return values, adhering to the project's language and conventions.
- The design should be a clear blueprint, consistent with the overall system architecture and industry best practices.

Comprehensive Test Planning:
- For each feature, populate the `test_requirements` object:
  - `unit_tests`: For each unit test:
    - `description`: Clearly state what the test verifies.
    - `target_element`: Specify the function or method name from `system_design.code_elements.name` that this test targets (e.g., "MyClass.my_method", "calculate_total").
    - `inputs`: Describe the inputs or conditions for the test case.
    - `expected_outcome`: Describe the expected result or behavior.
  - `integration_tests`: For each integration test:
    - `description`: State what the test verifies.
    - `components_involved`: List the components/modules interacting.
    - `scenario`: Describe the integration scenario being tested.
  - `property_based_tests`: For each property-based test:
    - `description`: Define the property being tested.
    - `target_element`: Specify the function or method name from `system_design.code_elements.name`.
    - `input_generators`: Describe the data generators used.
  - `acceptance_tests`: Follow the "given, when, then" structure.
  - `test_strategy`: Define the overall `coverage_goal` and `ui_test_approach` if applicable.
- Ensure `target_element_id` in tests accurately refers to `element_id` fields within the `system_design.code_elements` array for the same feature. This linkage is crucial for test generation.
- Explicitly include all relevant test types. If a test type (e.g., unit_tests) is applicable, provide a list of structured test case objects. If not applicable, provide an empty list `[]`.
- Ensure test coverage for public and authenticated functionality.
- The test plan must be organized, modular, and directly compatible with the project's testing framework and conventions.

Consider technical debt implications:
- Identify areas with high complexity or coupling that need refactoring
- Note files with poor test coverage that should be improved
- Consider maintainability impact of your feature decomposition
- Flag areas where standards diverge that could be harmonized

For the "dependency_type" field, use one of these values:
- "blocks" (this feature blocks another)
- "blocked_by" (this feature is blocked by another)
- "enhances" (this feature enhances another)
- "enhanced_by" (this feature is enhanced by another)

IMPORTANT: When generating your response, you must follow these coding instructions unless they directly contradict a system message or schema requirement. Do not invent requirements, features, or constraints not present in the user request, schema, or instructions.
"""

    # Combine base prompt with JSON-specific requirements
    return f"{base_prompt}\n\n{json_specific}"

def get_json_user_prompt(task_description: str) -> str:
    """
    Get the user prompt that requests JSON output.

    This extends the base pre-planner user prompt with JSON-specific formatting
    instructions.

    Args:
        task_description: The original request text

    Returns:
        Properly formatted user prompt string
    """
    # Get the base user prompt for consistent core requirements
    base_prompt = get_base_user_prompt(task_description)

    # Add JSON-specific formatting instructions
    json_specific = """Return a valid JSON object following the exact schema specified in the system prompt. Include comprehensive test requirements, dependencies, risk assessments and acceptance tests for each feature. Ensure your response contains ONLY the JSON object.
"""

    # Combine them while avoiding duplicate content
    return f"{base_prompt}\n\n{json_specific}"
    return None

def process_response(response: str, original_request: str) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """
    Process and validate the LLM response.

    Args:
        response: The LLM response text
        original_request: The original request text

    Returns:
        Tuple of (status, data, message):
            - status: 'success', 'question', or 'error'
            - data: parsed JSON data (if any)
            - message: error message or question string
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
        return "error", {}, error_message or "Failed to obtain JSON data from LLM response."

    # Check for the mutually exclusive question form
    if (
        isinstance(data, dict)
        and set(data.keys()) == {"question"}
        and isinstance(data["question"], str)
    ):
        # This is the question form, return special status
        return "question", data, data["question"]

    # Otherwise, validate schema - now with partial validation support
    is_valid, validation_msg, valid_indices = validate_json_schema(data)

    if is_valid:
        return "success", data, None # Fully valid
    else:
        # Try to repair structure only if validation failed completely
        if not valid_indices:
            logger.warning(f"JSON schema validation failed: {validation_msg}. Attempting repair.")
            try:
                repaired = repair_json_structure(data)
                is_valid2, validation_msg2, valid_indices2 = validate_json_schema(repaired)
                if is_valid2:
                    return "success", repaired, None
                else:
                    return "error", repaired, f"Repair failed: {validation_msg2}"
            except Exception as repair_e:
                return "error", data, f"Repair exception: {repair_e}"
        else: # Partial validation was initially successful
            logger.warning(f"Partial JSON validation: {validation_msg}")
            # Filter to only valid groups
            # (You may want to implement partial group filtering here if needed)
            return "error", data, validation_msg

def ensure_element_id_consistency(pre_planning_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure that all element_ids in the pre-planning data are consistent and valid.

    This function validates and repairs element_ids in system_design.code_elements and
    ensures test_requirements properly reference these element_ids for traceability.

    Args:
        pre_planning_data: The pre-planning data to validate

    Returns:
        Updated pre-planning data with consistent element_ids
    """
    if not isinstance(pre_planning_data, dict) or "feature_groups" not in pre_planning_data:
        logger.warning("Invalid pre-planning data structure for element_id validation")
        return pre_planning_data

    # Track assigned element_ids to ensure uniqueness
    assigned_ids = set()

    for group_idx, group in enumerate(pre_planning_data["feature_groups"]):
        if not isinstance(group, dict) or "features" not in group:
            continue

        for feature_idx, feature in enumerate(group["features"]):
            if not isinstance(feature, dict):
                continue

            # Check system_design.code_elements for element_ids
            if "system_design" in feature and isinstance(feature["system_design"], dict) and "code_elements" in feature["system_design"]:
                code_elements = feature["system_design"]["code_elements"]
                if isinstance(code_elements, list):
                    # First pass: ensure all code_elements have valid element_ids
                    for elem_idx, element in enumerate(code_elements):
                        if not isinstance(element, dict):
                            continue

                        # Ensure element has a valid element_id
                        if "element_id" not in element or not element["element_id"] or not isinstance(element["element_id"], str):
                            # Generate a standard element_id based on name or position
                            element_name = element.get("name", f"element_{elem_idx}")
                            base_id = f"{element_name.lower().replace(' ', '_')}_{group_idx}_{feature_idx}_{elem_idx}"

                            # Ensure uniqueness
                            element_id = base_id
                            counter = 1
                            while element_id in assigned_ids:
                                element_id = f"{base_id}_{counter}"
                                counter += 1

                            element["element_id"] = element_id
                            assigned_ids.add(element_id)
                            logger.info(f"Generated element_id {element_id} for element {element_name}")
                        else:
                            # Normalize existing element_id
                            element_id = element["element_id"]
                            if element_id in assigned_ids:
                                # Duplicate element_id, need to create a unique one
                                base_id = element_id
                                counter = 1
                                while element_id in assigned_ids:
                                    element_id = f"{base_id}_{counter}"
                                    counter += 1
                                element["element_id"] = element_id
                                logger.info(f"Renamed duplicate element_id from {base_id} to {element_id}")
                            assigned_ids.add(element_id)

                    # Second pass: ensure test_requirements reference valid element_ids
                    if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                        # Process unit tests
                        if "unit_tests" in feature["test_requirements"] and isinstance(feature["test_requirements"]["unit_tests"], list):
                            for test_idx, test in enumerate(feature["test_requirements"]["unit_tests"]):
                                if not isinstance(test, dict):
                                    continue

                                # If target_element exists but target_element_id doesn't or is invalid
                                if "target_element" in test and isinstance(test["target_element"], str):
                                    target_element = test["target_element"]

                                    # Find matching code element by name
                                    matched_element = None
                                    for element in code_elements:
                                        if isinstance(element, dict) and element.get("name") == target_element:
                                            matched_element = element
                                            break

                                    if matched_element and "element_id" in matched_element:
                                        # Set or fix target_element_id
                                        test["target_element_id"] = matched_element["element_id"]
                                        logger.info(f"Linked test to element_id {matched_element['element_id']} based on target_element {target_element}")

                        # Process property-based tests
                        if "property_based_tests" in feature["test_requirements"] and isinstance(feature["test_requirements"]["property_based_tests"], list):
                            for test_idx, test in enumerate(feature["test_requirements"]["property_based_tests"]):
                                if not isinstance(test, dict):
                                    continue

                                # If target_element exists but target_element_id doesn't or is invalid
                                if "target_element" in test and isinstance(test["target_element"], str):
                                    target_element = test["target_element"]

                                    # Find matching code element by name
                                    matched_element = None
                                    for element in code_elements:
                                        if isinstance(element, dict) and element.get("name") == target_element:
                                            matched_element = element
                                            break

                                    if matched_element and "element_id" in matched_element:
                                        # Set or fix target_element_id
                                        test["target_element_id"] = matched_element["element_id"]
                                        logger.info(f"Linked property test to element_id {matched_element['element_id']} based on target_element {target_element}")

    return pre_planning_data

def validate_preplan_all(data) -> Tuple[bool, str]:
    """
    Run all pre-planning validations and accumulate errors.
    Returns (True, "") if all pass, else (False, error_message).
    """
    errors = []
    # 1. JSON schema validation
    is_valid, validation_msg, _ = validate_json_schema(data)
    if not is_valid:
        errors.append(f"JSON schema validation error: {validation_msg}")
    # 2. Static plan checker
    try:
        from agent_s3.tools.plan_validator import validate_pre_plan
        static_valid, static_msg = validate_pre_plan(data)
        if not static_valid:
            errors.append(f"Static plan checker error: {static_msg}")
    except Exception as e:
        errors.append(f"Static plan checker exception: {e}")
    # 3. Planner compatibility
    try:
        from agent_s3.planner_json_enforced import validate_pre_planning_for_planner
        planner_compatible, planner_msg = validate_pre_planning_for_planner(data)
        if not planner_compatible:
            errors.append(f"Planner compatibility error: {planner_msg}")
    except Exception as e:
        errors.append(f"Planner compatibility check exception: {e}")
    return (len(errors) == 0), "\n".join(errors)

def pre_planning_workflow(router_agent, initial_request: str, context: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Canonical pre-planning workflow: user request, LLM (question or preplan JSON), user clarification loop, then extensive JSON validation.
    Now includes retry on JSON validation failure, appending error feedback to the prompt and always requesting the full JSON schema.
    Args:
        router_agent: The router agent with call_llm_by_role capability
        initial_request: The original user request
        context: Optional context dictionary
    Returns:
        Tuple of (success, result_data)
    """
    request_text = initial_request
    conversation_history = []
    max_rounds = 5
    last_error_msg = None

    for round_num in range(max_rounds):
        system_prompt = get_json_system_prompt()
        openrouter_params = get_openrouter_json_params()
        router_agent.reload_config()

        # If there was a JSON error, append it to the user prompt for feedback
        user_prompt = get_json_user_prompt(request_text)
        if last_error_msg:
            user_prompt += f"\n\nPREVIOUS ERROR: {last_error_msg}\nPlease correct your response to address this error. Return the full JSON object as specified in the schema."

        response = router_agent.call_llm_by_role(
            role='pre_planner',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=openrouter_params,
            scratchpad=None,
            context=context
        )
        status, data, msg = process_response(response, request_text)
        if status == "success":
            logger.info("Ensuring element_id consistency and test-code traceability...")
            data = ensure_element_id_consistency(data)
            valid, all_errors = validate_preplan_all(data)
            if not valid:
                logger.warning(f"Validation failed: {all_errors}")
                last_error_msg = all_errors
                continue  # Retry LLM with combined error feedback
            # --- Write preplan.json for human review ---
            preplan_path = "preplan.json"
            try:
                with open(preplan_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info(f"Wrote preplan.json for human review at {preplan_path}")
            except Exception as e:
                logger.error(f"Failed to write preplan.json: {e}")
                print(f"\n\033[91mError: Could not write preplan.json: {e}\033[0m")
                return False, {}
            # --- Read preplan.json and re-validate before handoff ---
            try:
                with open(preplan_path, "r", encoding="utf-8") as f:
                    preplan_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read preplan.json: {e}")
                print(f"\n\033[91mError: Could not read preplan.json: {e}\033[0m")
                return False, {}
            valid, all_errors = validate_preplan_all(preplan_data)
            if not valid:
                logger.warning(f"Human-edited preplan.json is invalid: {all_errors}")
                print(f"\n\033[91mError: preplan.json is invalid after human edit. Please fix the file and rerun.\033[0m")
                return False, {}
            # Only return the data loaded from preplan.json, not the in-memory data
            return True, preplan_data
        elif status == "question":
            print(f"\nThe pre-planner needs clarification before proceeding:")
            print(f"\033[93m{msg}\033[0m")
            user_answer = input("Your answer: ").strip()
            conversation_history.append({"request": request_text, "question": msg, "answer": user_answer})
            request_text = f"{request_text}\n\nClarification: {msg}\nUser answer: {user_answer}"
            last_error_msg = None  # Reset error on clarification
            continue
        else:
            print(f"\n\033[91mError: {msg}\033[0m")
            last_error_msg = msg
            # Retry with error feedback in prompt
            continue

    print("\n\033[91mError: Too many clarification or correction rounds. Aborting.\033[0m")
    return False, {}

# Canonical pre-planning entry point: use only pre_planning_workflow
# All other entry points are removed for consistency.
