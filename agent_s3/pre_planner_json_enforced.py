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
import re
import time # Added for potential delays in retry
import sys
import functools
from typing import Dict, Any, Optional, Tuple, List, Union

from agent_s3.pre_planning_errors import (
    AgentS3BaseError, PrePlanningError, ValidationError, SchemaError,
    ComplexityError, RepairError, handle_pre_planning_errors
)

from agent_s3.planner_json_enforced import get_openrouter_params

# Override the repair_json_structure function to work with the expected schema
def repair_json_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Repair JSON structure to match the expected schema.
    
    This function overrides the one from planner_json_enforced to work with the expected schema.
    
    Args:
        data: The JSON data to repair
        
    Returns:
        Repaired JSON data
    """
    # Create a new dictionary with the required structure
    repaired = {
        "original_request": data.get("original_request", "Unknown request"),
        "features": []
    }
    
    # If the data has feature_groups, convert them to features
    if "feature_groups" in data and isinstance(data["feature_groups"], list):
        for group in data["feature_groups"]:
            if isinstance(group, dict) and "features" in group and isinstance(group["features"], list):
                for feature in group["features"]:
                    if isinstance(feature, dict):
                        # Add the feature to the features list
                        repaired["features"].append(feature)
    
    # If the data already has features, use them
    elif "features" in data and isinstance(data["features"], list):
        repaired["features"] = data["features"]
    
    # Ensure each feature has the required fields
    for feature in repaired["features"]:
        if "name" not in feature:
            feature["name"] = "Unnamed Feature"
        if "description" not in feature:
            feature["description"] = "No description provided"
        if "files_affected" not in feature:
            feature["files_affected"] = []
        if "test_requirements" not in feature:
            feature["test_requirements"] = {
                "unit_tests": [],
                "integration_tests": [],
                "property_based_tests": [],
                "acceptance_tests": [],
                "test_strategy": {
                    "coverage_goal": "80% line coverage",
                    "ui_test_approach": "manual testing"
                }
            }
        if "dependencies" not in feature:
            feature["dependencies"] = {
                "internal": [],
                "external": [],
                "feature_dependencies": []
            }
    
    # Add complexity score and breakdown if not present
    if "complexity_score" not in repaired:
        repaired["complexity_score"] = 50
    if "complexity_breakdown" not in repaired:
        repaired["complexity_breakdown"] = {}
    
    return repaired

# Override the validate_json_schema function to work with the "features" schema
def validate_json_schema(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate JSON against the pre-planning schema.
    
    This function validates the JSON data against the expected schema with "features" instead of "feature_groups".
    
    Args:
        data: The JSON data to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic structure validation
    if not isinstance(data, dict):
        return False, "Data is not a dictionary"
    
    # Check for required fields
    if "original_request" not in data:
        return False, "Missing required field: 'original_request'"
    
    if not isinstance(data.get("original_request"), str):
        return False, "Field 'original_request' should be a string"
    
    # Check for features array
    if "features" not in data:
        return False, "Missing required field: 'features'"
    
    if not isinstance(data.get("features"), list):
        return False, "Field 'features' should be a list"
    
    # Validate each feature
    for i, feature in enumerate(data.get("features", [])):
        if not isinstance(feature, dict):
            return False, f"Feature at index {i} should be a dictionary"
        
        # Check for required feature fields
        if "name" not in feature:
            return False, f"Missing required field: 'name' in feature at index {i}"
        
        if not isinstance(feature.get("name"), str):
            return False, f"Field 'name' in feature at index {i} should be a string"
        
        if "description" not in feature:
            return False, f"Missing required field: 'description' in feature at index {i}"
        
        if not isinstance(feature.get("description"), str):
            return False, f"Field 'description' in feature at index {i} should be a string"
    
    # All validations passed
    return True, ""
from agent_s3.complexity_analyzer import ComplexityAnalyzer

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

# Create fallback pre-planning output
def create_fallback_json(task_description: str) -> Dict[str, Any]:
    """
    Create a minimal fallback JSON when regular pre-planning fails.
    
    Args:
        task_description: The original task description
        
    Returns:
        Dictionary with basic pre-planning structure
    """
    return create_fallback_pre_planning_output(task_description)

def create_fallback_pre_planning_output(task_description: str) -> Dict[str, Any]:
    """
    Create a minimal fallback pre-planning output when regular pre-planning fails.
    
    Args:
        task_description: The original task description
        
    Returns:
        Dictionary with basic pre-planning structure
    """
    return {
        "original_request": task_description,
        "features": [
            {
                "name": "Main Task Implementation",
                "description": task_description,
                "files_affected": [],
                "test_requirements": {
                    "unit_tests": [],
                    "integration_tests": [],
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
                    "overview": "Basic implementation of the requested functionality",
                    "code_elements": [
                        {
                            "element_type": "function",
                            "name": "main_implementation",
                            "element_id": "main_implementation_function",
                            "signature": "def main_implementation():",
                            "description": f"Main implementation of: {task_description}",
                            "key_attributes_or_methods": [],
                            "target_file": "main_implementation.py"
                        }
                    ],
                    "data_flow": "Standard data flow for this implementation",
                    "key_algorithms": ["Main implementation algorithm"]
                }
            }
        ],
        "complexity_score": 50,
        "complexity_breakdown": {}
    }

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
   - Create integration tests for component interactions
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

CRITICAL INSTRUCTION: When generating your response, you must follow these instructions unless they directly contradict a system message or schema requirement. Do not invent requirements, features, or constraints not present in the user request, schema, or instructions.
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
    json_specific = """Return a valid JSON object with structured data following the exact schema specified in the system prompt. Include comprehensive test requirements, dependencies, risk assessments and acceptance tests for each feature. Ensure your response contains ONLY the JSON object.
"""

    # Combine them while avoiding duplicate content
    return f"{base_prompt}\n\n{json_specific}"

def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from text that might contain markdown or other formatting.

    Args:
        text: Text that might contain JSON

    Returns:
        Extracted JSON string or None if no valid JSON found
    """
    # Try to extract JSON from code blocks first
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    matches = re.findall(code_block_pattern, text)

    for potential_json in matches:
        try:
            # Test if it's valid JSON
            json.loads(potential_json)
            return potential_json
        except json.JSONDecodeError:
            continue

    # If no code blocks found or none contained valid JSON,
    # try to extract JSON directly (looking for outer braces)
    direct_json_pattern = r"(\{[\s\S]*\})"
    matches = re.findall(direct_json_pattern, text)

    if matches:
        # Try to find the most likely JSON object (often the last one or largest one)
        potential_jsons = []
        for potential_json in matches:
            try:
                json.loads(potential_json) # Test if valid
                potential_jsons.append(potential_json)
            except json.JSONDecodeError:
                continue
        if potential_jsons:
            return max(potential_jsons, key=len) # Return largest valid JSON found

    # Last resort: try parsing the whole text if it looks like JSON
    if text.strip().startswith('{') and text.strip().endswith('}'):
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass # Fall through if parsing whole text fails

    return None

def process_response(response: str, original_request: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Process and validate the LLM response.

    Args:
        response: The LLM response text
        original_request: The original request text

    Returns:
        Tuple of (success, data):
            - success: True if processing was successful, False otherwise
            - data: parsed JSON data (if any)
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
    is_valid, validation_msg = validate_json_schema(data)

    if is_valid:
        return True, data # Fully valid
    else:
        # Try to repair structure only if validation failed completely
        logger.warning(f"JSON schema validation failed: {validation_msg}. Attempting repair.")
        try:
            repaired = repair_json_structure(data)
            is_valid2, validation_msg2 = validate_json_schema(repaired)
            if is_valid2:
                return True, repaired
            else:
                return False, repaired
        except Exception as repair_e:
            return False, data

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
    is_valid, validation_msg = validate_json_schema(data)
    if not is_valid:
        errors.append(f"JSON schema validation error: {validation_msg}")
    
    # 2. Enhanced validation with PrePlannerJsonValidator
    try:
        from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator
        validator = PrePlannerJsonValidator()
        enhanced_valid, enhanced_errors, validated_data = validator.validate_all(data)
        if not enhanced_valid:
            for error in enhanced_errors:
                errors.append(f"Enhanced validation error: {error}")
    except Exception as e:
        errors.append(f"Enhanced validator exception: {str(e)}")
    
    # 3. Static plan checker
    try:
        from agent_s3.tools.plan_validator import validate_pre_plan
        static_valid, static_msg = validate_pre_plan(data)
        if not static_valid:
            if isinstance(static_msg, dict) and "critical" in static_msg:
                for err in static_msg["critical"]:
                    errors.append(f"Static plan checker critical error: {err.get('message', '')}")
            else:
                errors.append(f"Static plan checker error: {static_msg}")
    except Exception as e:
        errors.append(f"Static plan checker exception: {e}")
    
    # 4. Planner compatibility
    try:
        from agent_s3.planner_json_enforced import validate_pre_planning_for_planner
        planner_compatible, planner_msg = validate_pre_planning_for_planner(data)
        if not planner_compatible:
            errors.append(f"Planner compatibility error: {planner_msg}")
    except Exception as e:
        errors.append(f"Planner compatibility check exception: {e}")
    
    return (len(errors) == 0), "\n".join(errors)

def _parse_structured_modifications(modification_text: str) -> List[Dict[str, str]]:
    """
    Parse structured modifications from the modification text.
    
    This function extracts structured modification instructions from the text,
    which can be in either the STRUCTURED_MODIFICATIONS format or the raw format.
    
    Args:
        modification_text: The modification text to parse
        
    Returns:
        List of dictionaries containing structured modifications
    """
    structured_mods = []
    
    # Check if using the STRUCTURED_MODIFICATIONS format
    if "STRUCTURED_MODIFICATIONS:" in modification_text:
        # Extract the RAW_INPUT section if it exists
        raw_input_match = re.search(r"RAW_INPUT:(.*?)(?=$)", modification_text, re.DOTALL)
        if raw_input_match:
            raw_input = raw_input_match.group(1).strip()
            # Split by separator lines
            components = re.split(r"---+", raw_input)
            for component in components:
                mod = {}
                # Extract key-value pairs
                for line in component.strip().split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        mod[key.strip()] = value.strip()
                
                # Check if it has the required fields
                if all(k in mod for k in ["COMPONENT", "LOCATION", "CHANGE_TYPE", "DESCRIPTION"]):
                    structured_mods.append(mod)
    else:
        # Try to parse as raw format
        components = re.split(r"---+", modification_text)
        for component in components:
            mod = {}
            # Extract key-value pairs
            for line in component.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    mod[key.strip()] = value.strip()
            
            # Check if it has the required fields
            if all(k in mod for k in ["COMPONENT", "LOCATION", "CHANGE_TYPE", "DESCRIPTION"]):
                structured_mods.append(mod)
    
    return structured_mods

def integrate_with_coordinator(coordinator, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Integrate pre-planning with the coordinator.
    
    This function is the main entry point for the coordinator to use pre-planning.
    It handles the entire pre-planning workflow and returns the results in a format
    that the coordinator can use.
    
    Args:
        coordinator: The coordinator instance
        task_description: The task description
        context: Optional context dictionary
        
    Returns:
        Dictionary containing pre-planning results
    """
    # Get the router agent from the coordinator
    router_agent = coordinator.router_agent
    
    # Call the pre-planning workflow
    success, pre_planning_data = pre_planning_workflow(router_agent, task_description, context)
    
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
                    
                    # Integration tests
                    for test in test_reqs.get("integration_tests", []):
                        if isinstance(test, dict):
                            test_requirements.append({
                                "type": "integration",
                                "description": test.get("description", ""),
                                "components": test.get("components_involved", []),
                                "scenario": test.get("scenario", "")
                            })
                        elif isinstance(test, str):
                            test_requirements.append({
                                "type": "integration",
                                "description": test
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

def regenerate_pre_planning_with_modifications(
    router_agent, 
    original_data: Dict[str, Any], 
    modification_text: str
) -> Dict[str, Any]:
    """
    Regenerate pre-planning data with user-requested modifications.
    
    Args:
        router_agent: The router agent with call_llm_by_role capability
        original_data: Original pre-planning data
        modification_text: User's modification request
        
    Returns:
        Modified pre-planning data
    """
    logger.info(f"Regenerating pre-planning data with modifications: {modification_text[:50]}...")
    
    # Create a prompt that includes the original data and the modification request
    system_prompt = get_json_system_prompt()
    
    user_prompt = f"""Original Pre-Planning Data:
{json.dumps(original_data, indent=2)}

Modification Request:
{modification_text}

Please generate an updated version of the pre-planning data that incorporates the requested modifications. 
Maintain the same JSON format and structure, but adjust the content according to the modification request.
Return ONLY the modified JSON object.
"""
    
    # Call the LLM
    openrouter_params = get_openrouter_params()
    router_agent.reload_config()
    
    response = router_agent.call_llm_by_role(
        role='pre_planner',
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=openrouter_params,
        scratchpad=None
    )
    
    # Process the response
    success, data = process_response(response, modification_text)
    
    if success:
        # Ensure element_id consistency
        data = ensure_element_id_consistency(data)
        return data
    else:
        # If there was an error, return the original data
        logger.warning(f"Failed to regenerate pre-planning data")
        return original_data

def pre_planning_workflow(router_agent, initial_request: str, context: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Canonical pre-planning workflow: user request, LLM (question or preplan JSON), user clarification loop, then extensive JSON validation.
    Now includes retry on JSON validation failure, appending error feedback to the prompt and always requesting the full JSON schema.
    Also includes automatic repair loop using PrePlannerJsonValidator for certain types of errors.
    
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
    repair_attempts = 0
    max_repair_attempts = 3

    # Initialize the enhanced validator
    try:
        from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator
        validator = PrePlannerJsonValidator()
    except ImportError:
        logger.warning("Enhanced JSON validator not available. Using standard validation only.")
        validator = None

    for round_num in range(max_rounds):
        system_prompt = get_json_system_prompt()
        openrouter_params = get_openrouter_params()
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
        success, data = process_response(response, request_text)
        msg = None
        if isinstance(data, dict) and "question" in data:
            msg = data["question"]
            success = False
            
        if success:
            logger.info("Ensuring element_id consistency and test-code traceability...")
            data = ensure_element_id_consistency(data)
            
            # First, try automatic repair if we have a validator
            original_data = data.copy() if isinstance(data, dict) else {}
            valid, all_errors = validate_preplan_all(data)
            
            # If not valid but we have a validator, try to repair
            if not valid and validator and repair_attempts < max_repair_attempts:
                logger.info(f"Validation failed - attempting automatic repair (attempt {repair_attempts+1}/{max_repair_attempts})...")
                try:
                    errors_list = all_errors.split('\n') if isinstance(all_errors, str) else [all_errors]
                    repaired_data, was_repaired = validator.repair_plan(original_data, errors_list)
                    
                    if was_repaired:
                        # Revalidate after repair
                        repair_valid, repair_errors = validate_preplan_all(repaired_data)
                        if repair_valid:
                            logger.info("Automatic repair successful!")
                            data = repaired_data
                            valid = True
                            
                            # Report successful repair to the user
                            print("\n\033[92mAutomatic plan repair successful!\033[0m")
                            print("The following issues were fixed automatically:")
                            for err in errors_list[:5]:  # Show at most 5 fixed issues
                                print(f"- \033[92m✓\033[0m {err[:100]}{'...' if len(err) > 100 else ''}")
                            if len(errors_list) > 5:
                                print(f"- \033[92m✓\033[0m ...and {len(errors_list) - 5} more issues")
                        else:
                            logger.warning(f"Automatic repair unsuccessful: {repair_errors}")
                            repair_attempts += 1
                            if repair_attempts < max_repair_attempts:
                                # Get repair suggestions and include in error feedback
                                suggestions = validator.generate_repair_suggestions(original_data, errors_list)
                                suggestion_text = "\n".join([f"{cat.upper()}:\n" + "\n".join([f"- {s['suggestion']}" for s in items]) 
                                                         for cat, items in suggestions.items()])
                                
                                # Generate user feedback for display
                                user_feedback = validator.generate_user_feedback(errors_list)
                                
                                # Display user-friendly feedback
                                print("\n\033[93mPlan validation issues found:\033[0m")
                                for category, issues in user_feedback.get("issues_by_category", {}).items():
                                    if issues:
                                        print(f"\n\033[1m{category.replace('_', ' ').title()}:\033[0m")
                                        for issue in issues[:3]:  # Show at most 3 issues per category
                                            severity_color = "\033[91m" if issue["severity"] == "critical" else "\033[93m"
                                            print(f"- {severity_color}●\033[0m {issue['message'][:100]}{'...' if len(issue['message']) > 100 else ''}")
                                        if len(issues) > 3:
                                            print(f"  ...and {len(issues) - 3} more issues in this category")
                                
                                # Still include the full error message for the LLM
                                last_error_msg = f"{all_errors}\n\nSUGGESTED FIXES:\n{suggestion_text}"
                                continue  # Try again with better error feedback
                    else:
                        logger.warning("No automatic repairs were possible")
                        repair_attempts += 1
                except Exception as e:
                    logger.error(f"Error during plan repair: {e}")
                    repair_attempts += 1
            
            # If still not valid after repair attempts, continue with standard error feedback
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
        elif isinstance(data, dict) and "question" in data:
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

class PrePlanner:
    """
    Enhanced pre-planning system with improved validation, complexity assessment,
    and error handling. This consolidates functionality from multiple files and
    incorporates JSON enforcement capabilities.
    """
    def __init__(self, router_agent=None, scratchpad=None, config=None):
        self.router_agent = router_agent
        self.scratchpad = scratchpad
        self.config = {} if config is None else config
        from agent_s3.pre_planning_validator import PrePlanningValidator
        from agent_s3.complexity_analyzer import ComplexityAnalyzer
        self.validator = PrePlanningValidator()
        self.complexity_analyzer = ComplexityAnalyzer()
        # Flag to determine whether to use JSON enforcement
        self.use_json_enforcement = self.config.get("use_json_enforcement", True)
    
    def generate_pre_planning_data(self, task_description: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate pre-planning data for a given task description.
        
        Args:
            task_description: Task description provided by the user
            context: Optional context dictionary with additional information
            
        Returns:
            Dictionary containing pre-planning results or error information
        """
        logger.info(f"Generating pre-planning data for task: {task_description[:50]}...")
        
        # If JSON enforcement is enabled, use the pre_planner_json_enforced workflow
        if self.use_json_enforcement:
            success, pre_planning_data = pre_planning_workflow(self.router_agent, task_description, context)
            
            if success:
                # Assess complexity
                complexity_result = self.complexity_analyzer.assess_complexity(
                    pre_planning_data, 
                    task_description=task_description
                )
                
                return {
                    "success": True,
                    "pre_planning_data": pre_planning_data,
                    "complexity_assessment": complexity_result,
                    "requires_confirmation": complexity_result["is_complex"]
                }
            else:
                return {
                    "success": False,
                    "error_type": "json_enforcement",
                    "message": "Failed to generate pre-planning data with JSON enforcement"
                }
        
        # Otherwise, use the original implementation
        start_time = time.time()
        
        # 1. Generate pre-planning data using LLM
        system_prompt = get_base_system_prompt()
        user_prompt = get_base_user_prompt(task_description)
        
        response = self._call_llm_with_retry(system_prompt, user_prompt)
        
        if not response.get("success", False):
            return response
        
        # 2. Parse and validate JSON response
        try:
            pre_planning_data = json.loads(response["response"])
        except json.JSONDecodeError as e:
            from agent_s3.pre_planning_errors import SchemaError
            raise SchemaError(f"Invalid JSON response: {str(e)}", ["JSON parsing failed"])
        
        # 3. Validate structure and semantics
        is_valid, validation_result = self.validator.validate_all(pre_planning_data)
        
        if not is_valid:
            all_errors = []
            for category, errors in validation_result["errors"].items():
                all_errors.extend(errors)
            
            # If validation failed, try to repair before giving up
            if self.config.get("enable_auto_repair", True):
                repaired_data, repair_successful = self._attempt_repair(pre_planning_data, all_errors)
                if repair_successful:
                    pre_planning_data = repaired_data
                    logger.info("Successfully repaired pre-planning data")
                else:
                    from agent_s3.pre_planning_errors import ValidationError
                    raise ValidationError("Pre-planning validation failed after repair attempt", 
                                         all_errors, validation_result)
            else:
                from agent_s3.pre_planning_errors import ValidationError
                raise ValidationError("Pre-planning validation failed", all_errors, validation_result)
        
        # 4. Assess complexity
        complexity_result = self.complexity_analyzer.assess_complexity(
            pre_planning_data, 
            task_description=task_description
        )
        
        # 5. Add metadata
        pre_planning_data["metadata"] = {
            "generation_time": time.time() - start_time,
            "complexity_assessment": complexity_result
        }
        
        return {
            "success": True,
            "pre_planning_data": pre_planning_data,
            "complexity_assessment": complexity_result,
            "requires_confirmation": complexity_result["is_complex"]
        }
    
    def regenerate_pre_planning_with_modifications(
        self, 
        task_description: str, 
        original_data: Dict[str, Any],
        modification_text: str
    ) -> Dict[str, Any]:
        """
        Regenerate pre-planning data with user-requested modifications.
        
        Args:
            task_description: Original task description
            original_data: Original pre-planning data
            modification_text: User's modification request
            
        Returns:
            Dictionary containing modified pre-planning results or error information
        """
        logger.info(f"Regenerating pre-planning data with modifications: {modification_text[:50]}...")
        
        # If JSON enforcement is enabled, use the pre_planner_json_enforced workflow
        if self.use_json_enforcement:
            modified_data = regenerate_pre_planning_with_modifications(
                self.router_agent, 
                original_data, 
                modification_text
            )
            
            # Assess complexity
            complexity_result = self.complexity_analyzer.assess_complexity(
                modified_data, 
                task_description=task_description
            )
            
            return {
                "success": True,
                "pre_planning_data": modified_data,
                "complexity_assessment": complexity_result,
                "requires_confirmation": complexity_result["is_complex"]
            }
        
        # Otherwise, use the original implementation
        # 1. Generate modified pre-planning data using LLM
        system_prompt = get_base_system_prompt()
        user_prompt = self._get_modification_prompt(task_description, original_data, modification_text)
        
        response = self._call_llm_with_retry(system_prompt, user_prompt)
        
        if not response.get("success", False):
            return response
        
        # 2. Parse and validate JSON response
        try:
            modified_data = json.loads(response["response"])
        except json.JSONDecodeError as e:
            from agent_s3.pre_planning_errors import SchemaError
            raise SchemaError(f"Invalid JSON in modified response: {str(e)}", ["JSON parsing failed"])
        
        # 3. Validate structure and semantics
        is_valid, validation_result = self.validator.validate_all(modified_data)
        
        if not is_valid:
            all_errors = []
            for category, errors in validation_result["errors"].items():
                all_errors.extend(errors)
            
            # If validation failed, try to repair before giving up
            if self.config.get("enable_auto_repair", True):
                repaired_data, repair_successful = self._attempt_repair(modified_data, all_errors)
                if repair_successful:
                    modified_data = repaired_data
                    logger.info("Successfully repaired modified pre-planning data")
                else:
                    from agent_s3.pre_planning_errors import ValidationError
                    raise ValidationError("Modified pre-planning validation failed after repair attempt", 
                                         all_errors, validation_result)
            else:
                from agent_s3.pre_planning_errors import ValidationError
                raise ValidationError("Modified pre-planning validation failed", all_errors, validation_result)
        
        # 4. Assess complexity
        complexity_result = self.complexity_analyzer.assess_complexity(
            modified_data, 
            task_description=task_description
        )
        
        # 5. Add metadata
        modified_data["metadata"] = {
            "modified_from_original": True,
            "modification_text": modification_text,
            "complexity_assessment": complexity_result
        }
        
        return {
            "success": True,
            "pre_planning_data": modified_data,
            "complexity_assessment": complexity_result,
            "requires_confirmation": complexity_result["is_complex"]
        }
    
    def _attempt_repair(self, data: Dict[str, Any], errors: List[str]) -> Tuple[Dict[str, Any], bool]:
        """
        Attempt to repair invalid pre-planning data.
        
        Args:
            data: The pre-planning data to repair
            errors: List of validation errors
            
        Returns:
            Tuple of (repaired_data, was_successful)
        """
        # If JSON enforcement is enabled, try to use the JSON validator's repair functionality
        if self.use_json_enforcement:
            try:
                from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator
                validator = PrePlannerJsonValidator()
                repaired_data, was_repaired = validator.repair_plan(data, errors)
                if was_repaired:
                    return repaired_data, True
            except (ImportError, Exception) as e:
                logger.warning(f"Failed to use JSON validator for repair: {e}")
        
        # Implement basic repair strategies for common issues
        repaired = data.copy()
        
        # Fix missing fields
        for error in errors:
            if "missing fields" in error.lower():
                parts = error.split("missing fields: ")
                if len(parts) > 1:
                    missing_fields = parts[1].strip()
                    field_names = [f.strip() for f in missing_fields.split(",")]
                    
                    # Locate the object with missing fields
                    if "feature group" in error.lower():
                        match = re.search(r"feature group (\d+)", error.lower())
                        if match:
                            group_idx = int(match.group(1))
                            if 0 <= group_idx < len(repaired.get("feature_groups", [])):
                                group = repaired["feature_groups"][group_idx]
                                for field in field_names:
                                    if field == "group_name":
                                        group["group_name"] = f"Group {group_idx + 1}"
                                    elif field == "group_description":
                                        group["group_description"] = "Automatically generated group description"
                                    elif field == "features":
                                        group["features"] = []
            
            elif "feature group" in error.lower() and "feature" in error.lower() and "missing fields" in error.lower():
                match = re.search(r"feature group (\d+), feature (\d+)", error.lower())
                if match:
                    group_idx = int(match.group(1))
                    feature_idx = int(match.group(2))
                    
                    parts = error.split("missing fields: ")
                    if len(parts) > 1:
                        missing_fields = parts[1].strip()
                        field_names = [f.strip() for f in missing_fields.split(",")]
                        
                        # Fix missing feature fields
                        if 0 <= group_idx < len(repaired.get("feature_groups", [])):
                            group = repaired["feature_groups"][group_idx]
                            if "features" in group and 0 <= feature_idx < len(group["features"]):
                                feature = group["features"][feature_idx]
                                for field in field_names:
                                    if field == "name":
                                        feature["name"] = f"Feature {feature_idx + 1}"
                                    elif field == "description":
                                        feature["description"] = "Automatically generated feature description"
                                    elif field == "complexity":
                                        feature["complexity"] = 1
                                    else:
                                        # Add any other missing fields with default values
                                        feature[field] = f"Automatically generated {field}"
        
        # Validate the repaired data
        is_valid, _ = self.validator.validate_all(repaired)
        return repaired, is_valid
    
    def _get_modification_prompt(self, task_description: str, original_data: Dict[str, Any], 
                               modification_text: str) -> str:
        """Generate user prompt for modifying pre-planning data."""
        return f"""Task: {task_description}

Original Pre-Planning Data:
{json.dumps(original_data, indent=2)}

Modification Request:
{modification_text}

Please generate an updated version of the pre-planning data that incorporates the requested modifications. Maintain the same JSON format and structure, but adjust the content according to the modification request."""
    
    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, 
                           max_retries: int = 2) -> Dict[str, Any]:
        """Call LLM with retry logic for reliability."""
        for attempt in range(max_retries + 1):
            try:
                response_text = self.router_agent.call_llm_by_role(
                    role='pre_planner',
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    config=self.config.get("llm_config", {}),
                    scratchpad=self.scratchpad
                )
                # Wrap the string response in a dictionary for compatibility
                return {
                    "success": True,
                    "response": response_text
                }
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"LLM call failed (attempt {attempt+1}/{max_retries+1}): {str(e)}. Retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"LLM call failed after {max_retries+1} attempts: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Failed to generate pre-planning data after {max_retries+1} attempts: {str(e)}"
                    }
