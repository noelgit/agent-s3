"""
Base pre-planner module for organizing complex tasks into manageable units.

This module provides the foundation for pre-planning functionality used to:
1. Decompose user requests into feature groups
2. Generate structured planning outputs that can be processed by downstream components
3. Provide base validation and utility methods for pre-planning

This base module can be extended or wrapped by specialized implementations
like pre_planner_json_enforced.py which adds JSON schema enforcement and repair.
"""

import json
import logging
import re
import time
from typing import Dict, Any, Optional, Tuple, List, Union

logger = logging.getLogger(__name__)

class PrePlanningError(Exception):
    """Exception raised when pre-planning encounters errors."""
    pass

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

6. Address cross-cutting concerns:
   - Mitigate OWASP Top 10 vulnerabilities
   - Consider performance impacts and optimizations
   - Uphold code quality standards
   - Incorporate accessibility requirements
"""

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

def get_llm_params() -> Dict[str, Any]:
    """
    Get default parameters for LLM call during pre-planning.
    
    Returns:
        Dictionary of parameters for the LLM call
    """
    return {
        "temperature": 0.2,  # Lower temperature for more consistent planning
        "max_tokens": 2048,  # Ensure enough space for comprehensive planning
        "top_p": 0.3         # Narrow token selection for more focused content
    }

def _extract_text_from_response(response: str) -> str:
    """
    Extract clean text from LLM response, removing any special formatting.
    
    Args:
        response: Raw LLM response
        
    Returns:
        Cleaned text string
    """
    # Remove markdown code block syntax if present
    code_block_pattern = r"```(?:\w+)?\s*([\s\S]*?)\s*```"
    matches = re.findall(code_block_pattern, response)
    if matches:
        return matches[0]
    
    return response

def validate_pre_planning_output(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Basic validation of pre-planning output for minimal correctness.
    
    Specialized implementations may provide more rigorous schema validation.
    
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
    
    # Check for feature groups array
    if "feature_groups" not in data or not isinstance(data["feature_groups"], list):
        return False, "Missing or invalid 'feature_groups' in output"
    
    if not data["feature_groups"]:
        return False, "Feature groups array is empty"
    
    # Basic group structure validation
    for i, group in enumerate(data["feature_groups"]):
        if not isinstance(group, dict):
            return False, f"Feature group at index {i} is not a dictionary"
        
        if "group_name" not in group:
            return False, f"Feature group at index {i} is missing 'group_name'"
        
        if "features" not in group or not isinstance(group["features"], list):
            return False, f"Feature group at index {i} is missing or has invalid 'features' array"
        
        if not group["features"]:
            return False, f"Feature group at index {i} has empty 'features' array"
    
    return True, "Pre-planning output is valid"

def call_pre_planner(llm_client, task_description: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Base implementation for calling a pre-planner.
    
    Args:
        llm_client: The LLM client to use for pre-planning
        task_description: The original task description
        context: Optional context information
        
    Returns:
        Tuple of (success, result_data, error_message)
    """
    system_prompt = get_base_system_prompt()
    user_prompt = get_base_user_prompt(task_description)
    llm_params = get_llm_params()
    
    try:
        logger.info("Calling pre-planner with task description")
        
        # Call LLM
        response = llm_client.call_llm_by_role(
            role='pre_planner',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=llm_params
        )
        
        if not response:
            return False, {}, "Empty response from LLM"
        
        # Extract and process the text
        extracted_text = _extract_text_from_response(response)
        
        # Parse as JSON if possible, otherwise treat as text
        try:
            result_data = json.loads(extracted_text)
        except json.JSONDecodeError:
            # For non-JSON responses, create a basic structure
            result_data = {
                "original_request": task_description,
                "feature_groups": [
                    {
                        "group_name": "Main Feature Group",
                        "group_description": "Features extracted from text response",
                        "features": [
                            {
                                "name": "Main Feature",
                                "description": extracted_text,
                                "files_affected": []
                            }
                        ]
                    }
                ]
            }
        
        # Basic validation
        is_valid, error_message = validate_pre_planning_output(result_data)
        
        if is_valid:
            return True, result_data, None
        else:
            return False, result_data, error_message
        
    except Exception as e:
        logger.error(f"Error in pre-planning: {e}")
        return False, {}, f"Pre-planning error: {str(e)}"

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
        "feature_groups": [
            {
                "group_name": "Fallback Feature Group",
                "group_description": "Automatically created due to pre-planning failure",
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
                ]
            }
        ]
    }

# Canonical JSON-enforced pre-planning entry point is in pre_planner_json_enforced.py
# Use pre_planning_workflow from that module for all JSON-enforced workflows.
# This module provides only the base/compatibility interface.
