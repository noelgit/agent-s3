"""Planner module for agent-s3.

Responsible for creating implementation plans for tasks with enforced JSON output.
This module is part of the planning architecture consisting of:
- pre_planner.py: Base pre-planning functionality
- pre_planner_json_enforced.py: Enhanced JSON schema enforcement for pre-planning
- planner.py: Base planning functionality (this module)
- planner_json_enforced.py: Enhanced JSON schema enforcement for planning
"""

import json
import logging
import re
import os
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime

# Import pre-planning compatibility functionality
from agent_s3.pre_planner import PrePlanningError

from agent_s3.json_utils import (
    validate_and_repair_json,
    extract_json_from_text,
    get_openrouter_json_params
)
from agent_s3.llm_utils import cached_call_llm
from agent_s3.errors import PlanningError

# Re-export PrePlanningError for backward compatibility
# This helps maintain symmetry with planner_json_enforced importing from pre_planner_json_enforced
from agent_s3.pre_planner import validate_pre_planning_output

# To maintain architectural consistency, include a method for validating pre-planning output
# from the planner's perspective for symmetry with planner_json_enforced
def validate_pre_planning_from_planner(pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate that pre-planning output is compatible with the planner.

    This is a wrapper around the base validate_pre_planning_output function
    and is included here for architectural consistency.

    Args:
        pre_plan_data: Pre-planning data to validate

    Returns:
        Tuple of (is_valid, message)
    """
    return validate_pre_planning_output(pre_plan_data)

logger = logging.getLogger(__name__)

class Planner:
    """
    The Planner class is responsible for creating plans for tasks using an LLM.
    Focused specifically on feature-level planning with integrated function-level details.
    """
    def __init__(self, coordinator=None, config=None, scratchpad=None, progress_tracker=None, 
                 task_state_manager=None, code_analysis_tool=None, tech_stack_detector=None, 
                 memory_manager=None, database_tool=None, test_frameworks=None, test_critic=None, **kwargs):
        """Initialize the planner with a coordinator for access to tools.
        
        Args:
            coordinator: The coordinator instance (optional)
            config: Configuration object (optional, taken from coordinator if available)
            scratchpad: Scratchpad for logging (optional, taken from coordinator if available)
            progress_tracker: Progress tracker (optional)
            task_state_manager: Task state manager (optional)
            code_analysis_tool: Code analysis tool (optional)
            tech_stack_detector: Tech stack detector (optional)
            memory_manager: Memory manager (optional)
            database_tool: Database tool (optional)
            test_frameworks: Test frameworks (optional)
            test_critic: Test critic (optional)
            **kwargs: Additional keyword arguments (for backward compatibility)
        """
        self.coordinator = coordinator
        self.context_registry = coordinator.context_registry if coordinator else None
        self.llm = coordinator.llm if coordinator else None
        self.scratchpad = scratchpad or (coordinator.scratchpad if coordinator else None)
        
        # Store tools and components
        self.tech_stack_detector = tech_stack_detector
        self.memory_manager = memory_manager
        self.database_tool = database_tool
        self.test_frameworks = test_frameworks or (coordinator.test_frameworks if coordinator else None)
        self.test_critic = test_critic or (coordinator.test_critic if coordinator else None)
        
        # Get workspace path
        self.workspace_path = Path(coordinator.config.config.get("workspace_path", ".")) if coordinator and coordinator.config else Path(".")
        
        # Get config from coordinator or use provided config
        self.config = config or (coordinator.config if coordinator else None)
        
        # Error tracking
        self.last_error = None

    def stop_observer(self):
        """Stops the filesystem observer and event handler timers."""
        if hasattr(self, 'file_system_watcher'):
            self.file_system_watcher.stop()
            if self.scratchpad:
                self.scratchpad.log("Planner", "Stopped filesystem watcher.")

    def get_consolidated_plan_system_prompt(self) -> str:
        """
        Get the system prompt for consolidated planning with enforced JSON output.
        
        Returns:
            Properly formatted system prompt string
        """
        return """You are a senior software architect and test implementation expert. Your task is to analyze a feature group, perform an architecture review, and then, based on that review and the original input, create comprehensive tests and a detailed implementation plan.

CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:
{
  "architecture_review": {
    "logical_gaps": [
      {
        "description": "Description of the logical gap (e.g., Authentication system lacks CSRF protection)",
        "impact": "Potential impact of the gap (e.g., Vulnerable to cross-site request forgery attacks)",
        "recommendation": "Recommendation to address the gap (e.g., Implement CSRF tokens in all forms)"
      }
      // ... more gaps
    ],
    "optimization_suggestions": [
      {
        "description": "Description of the optimization (e.g., Database queries not optimized for pagination)",
        "benefit": "Potential benefit of the optimization (e.g., Reduced memory usage and query time for large datasets)",
        "implementation_approach": "Suggested approach for implementation (e.g., Add LIMIT/OFFSET or cursor-based pagination)"
      }
      // ... more suggestions
    ],
    "additional_considerations": [
      "Any other relevant considerations (e.g., Consider implementing rate limiting to prevent abuse)"
      // ... more considerations
    ]
  },
  "tests": { // Comprehensive, runnable test implementations based on input 'test_requirements' and 'risk_assessment'
    "unit_tests": [
      {
        "file": "path/to/test_file.py", // Planned path for the test file
        "test_name": "test_function_name_descriptive",
        "tested_functions": ["<file_path_of_function_under_test>::<full_function_signature>"], // Array of strings identifying functions covered
        "target_element_ids": ["string"], // Array of element_ids this test covers, linking to implementation_plan and system_design elements
        "description": "Clear description of what this unit test verifies",
        "code": "Complete, runnable Python code for the unit test function, using appropriate testing frameworks and assertions. THIS CODE MUST BE SYNTACTICALLY VALID AND LOGICALLY CORRECT.",
        "setup_requirements": "Any setup needed (e.g., fixtures, mocks, specific data states)"
      }
      // ... more unit tests
    ],
    "integration_tests": [
      {
        "file": "path/to/integration_test_file.py", // Planned path
        "test_name": "test_integration_scenario_descriptive",
        "description": "Clear description of the integrated components and interaction being tested",
        "code": "Complete, runnable Python code for the integration test. THIS CODE MUST BE SYNTACTICALLY VALID AND LOGICALLY CORRECT.",
        "setup_requirements": "Setup for integrated components (e.g., mock services, database state)"
      }
      // ... more integration tests
    ],
    "property_based_tests": [
      {
        "file": "path/to/property_test_file.py", // Planned path
        "test_name": "test_property_of_function_descriptive",
        "description": "Description of the property being tested and the range of inputs",
        "code": "Complete, runnable Python code for the property-based test (e.g., using Hypothesis). THIS CODE MUST BE SYNTACTICALLY VALID AND LOGICALLY CORRECT.",
        "setup_requirements": "Libraries like Hypothesis, data generation strategies"
      }
      // ... more property-based tests
    ],
    "acceptance_tests": [
      {
        "file": "path/to/acceptance_test_file.py", // Planned path
        "test_name": "test_user_journey_or_acceptance_criterion",
        "description": "Description of the user story or acceptance criterion being verified",
        "code": "Complete, runnable code for the acceptance test (can be Gherkin-style if applicable, or actual test code). THIS CODE MUST BE SYNTACTICALLY VALID AND LOGICALLY CORRECT.",
        "setup_requirements": "End-to-end environment setup, specific user roles or data",
        "given": "string (Optional: For BDD-style tests)",
        "when": "string (Optional: For BDD-style tests)",
        "then": "string (Optional: For BDD-style tests)"
      }
      // ... more acceptance tests
    ]
    // ... include other test types if specified in input 'test_requirements.required_types'
  },
  "implementation_plan": { // Detailed file/function level plan, refining input 'system_design' based on architecture_review
    "file_path_1.py": [ // Key is the full path to the file to be modified or created
      {
        "function": "def function_name(param1: type, param2: type) -> return_type:", // Full signature
        "description": "Purpose of the function and how it contributes to the feature",
        "element_id": "string (Should match an element_id from system_design.code_elements)", // Link to code element for test alignment
        "steps": [
          {
            "step_description": "string (A single, clear, actionable implementation step, e.g., 'Initialize database connection', 'Fetch user data by ID', 'Validate input parameters')",
            "pseudo_code": "string (Optional: A brief pseudo-code snippet for this step if complex, e.g., 'if user_id is None: raise ValueError')",
            "relevant_data_structures": ["string (Data structures manipulated or accessed in this step, e.g., 'User_Pydantic_Model', 'Order_Cache_Dictionary')"],
            "api_calls_made": ["string (External or internal API calls made in this step, e.g., 'auth_service.verify_token(token)', 'database.user.get(user_id)')"],
            "error_handling_notes": "string (Specific error handling considerations for this step, e.g., 'Catch UserNotFoundException and return 404', 'Retry API call up to 3 times on timeout')"
          }
          // ... more steps for this function
        ],
        "edge_cases": [
            "Specific edge case 1 to handle in this function",
            "Specific edge case 2...",
            // ... more edge cases
        ]
      }
      // ... more functions in this file
    ],
    "file_path_2.py": [ /* ... more files ... */ ]
  },
  "discussion": "Overall approach, key decisions made, rationale for the plan, and how the architecture review influenced the tests and implementation."
}

IMPORTANT: You MUST perform the following two steps sequentially to generate the above JSON structure:

**Step 1: Architecture Review**
   Based on the provided input feature group data (which includes `system_design.code_elements` with element signatures and target files):
   - Critically review the provided `system_design` object, focusing on its overview, code_elements (their signatures, descriptions, and interactions), data_flow, and key_algorithms.
   - Be concise and direct - use bullet points where appropriate.
   - Focus on interactions between the proposed code_elements and their adherence to architectural principles (SOLID, etc.).
   - Identify security/performance implications of the proposed interfaces and high-level logic.
   - Look for missing elements within the context of the proposed design, NOT a wholesale redesign.
   - DO NOT redesign the entire architecture from scratch. Your job is to critique and improve what's provided.
   - Each identified issue (logical_gap, optimization_suggestion) must be clear, specific, and actionable, with a description, impact/benefit, and recommendation/implementation_approach.
   - List any 'additional_considerations' that are relevant.
   The output of this step will populate the `architecture_review` field in the final JSON.

**Step 2: Refined Implementation Plan and Test Implementation**
   Using the original input feature group data (specifically its `system_design` as the initial plan for each feature, `test_requirements`, and `risk_assessment`) AND the findings from your Architecture Review (Step 1):

   **TEST IMPLEMENTATION (to populate the `tests` field):**
   - Create comprehensive test implementations. These tests are based on the `test_requirements` (including `unit_tests`, `integration_tests`, `acceptance_tests`, `test_strategy` fields) and `risk_assessment` (including `critical_files`, `potential_regressions`, `required_test_characteristics` fields) from the input feature group.
   - For each unit test:
     - Populate the `tested_functions` array with strings identifying the exact function(s) covered by that test, using the format "<file_path>::<function_signature>". The file_path should match the target_file of the code_element, and the function_signature should match the signature in the code_element.
     - Populate the `target_element_ids` array with the element_ids from system_design.code_elements that this test targets. This creates a direct linkage between tests and the original blueprint.
     - Tests should reflect any signature changes recommended in your architecture review, maintaining consistency with your implementation plan.
   - Include ALL test types specified in the input `test_requirements.required_types` or implied by the `test_requirements` structure.
   - Tests MUST be complete, runnable implementations (actual code), not stubs or descriptions of tests. Ensure the generated test code is syntactically correct and logically sound.
   - Ensure all edge cases and potential regressions identified in the input `risk_assessment` are covered by specific tests.
   - Adhere to the `test_strategy` (e.g., `coverage_goal`, `ui_test_approach`) from the input.

   **IMPLEMENTATION PLAN (to populate the `implementation_plan` field):**
   - For each code_element provided in the input `system_design.code_elements`, create a corresponding entry in the implementation_plan.
   - The function signature in your output should match the input signature unless your architecture_review explicitly recommended a change to it.
   - Your main task here is to generate the detailed structured steps for implementation, not to redesign the interfaces unless your review identified specific issues with them.
   - DO NOT restart the review process from Step 1. Your goal here is to detail the 'how-to' based on the code elements provided in the system_design, with adjustments only as recommended in your architecture review.
   - For each function in the `implementation_plan`:
       - The `function` field should be the full, typed signature (e.g., `def get_user_profile(user_id: int) -> Optional[UserProfile]:`).
       - The `description` should explain its purpose.
       - The `steps` array should contain structured step objects:
           - `step_description`: A single, clear, actionable implementation step.
           - `pseudo_code`: Optional. A brief pseudo-code snippet if the step is complex.
           - `relevant_data_structures`: List data structures manipulated or accessed.
           - `api_calls_made`: List external or internal API calls.
           - `error_handling_notes`: Note specific error handling for this step.
       - The `edge_cases` array should list specific edge cases to handle in this function's implementation.
   - **CRITICAL:** The implementation resulting from these structured steps MUST satisfy the corresponding planned tests in the `tests` section. The use of element_id fields creates an explicit link between the test requirements, system design elements, and implementation plan steps, ensuring test congruence.

   **DISCUSSION (to populate the `discussion` field):**
   - Provide an overall summary of your approach, key decisions, and the rationale behind the plan, explaining how the architecture review influenced the final test and implementation plans.

**General Adherence to Guidelines (Apply to both steps and final output):**
*   Apply OWASP Top 10 security practices, input validation, secure credential storage, and proper session handling (for requirements and risk assessment).
*   Consider performance: time complexity, resource usage, database query efficiency, and memory management (for architectural and design decisions).
*   Follow code quality standards: SOLID principles, modularity, clear naming, error handling, and DRY (for feature decomposition and design).
*   Ensure accessibility: WCAG 2.1 AA, semantic HTML, ARIA, keyboard navigation, and screen reader support (for requirements and acceptance criteria).
*   Adhere to project-specific guidelines for architecture, tech stack, error handling, UI/UX, testing, and development workflow if provided in context.
*   Only use information from the provided pre-planning data (feature group), context, and these instructions. Do not add, assume, or hallucinate features, requirements, or behaviors not explicitly specified.
*   **The implementation plan is a direct, detailed elaboration of the input system_design.code_elements, and the tests must accurately verify these elements.**
*   **Maintain consistent element_id references throughout architecture review, implementation plan, and tests to ensure complete traceability.**
*   **The final generated implementation code derived from this plan MUST pass the tests generated within this same plan.**
"""

    def get_consolidated_plan_user_prompt(self, feature_group: Dict[str, Any], task_description: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get the user prompt for the consolidated planning LLM call.
        
        Args:
            feature_group: The feature group data
            task_description: The original task description
            context: Optional context information
            
        Returns:
            Properly formatted user prompt string
        """
        feature_json = json.dumps(feature_group, indent=2)
        context_str = json.dumps(context, indent=2) if context else "No additional context provided."

        return f"""Please generate a consolidated plan (architecture review, tests, implementation details) for the following feature group, based on the original task description and provided context.

# Original Task Description
{task_description}

# Feature Group Data
{feature_json}

# Context Information
{context_str}

Your task is to:
1.  Critically review the provided system_design (focusing on code_elements, their signatures, interfaces, and interactions) to identify logical gaps, optimizations, and considerations.
2.  Implement comprehensive, runnable tests based on test_requirements that explicitly link to the code_elements through element_ids. Ensure tests are logically sound and syntactically correct.
3.  Create a detailed, step-by-step implementation plan that directly elaborates on the system_design.code_elements. The implementation must maintain consistent references to element_ids and ensure the code will pass the generated tests.
4.  Provide a brief discussion explaining the rationale behind your refinements to the system design.

Ensure your response strictly adheres to the JSON schema provided in the system prompt. Focus on creating a practical, actionable plan based *only* on the provided information.
"""

    def get_personas_content(self) -> str:
        """Load the personas content from personas.md file."""
        try:
            personas_path = Path("personas.md")
            if personas_path.exists():
                return personas_path.read_text(encoding='utf-8')
            else:
                logger.warning("personas.md file not found, using default personas")
                # Default personas
                return """
                ## Business Development Manager
                Clarify why we're building this feature, whom it serves, and what real-world scenarios it must cover.

                ## Expert Coder
                Define how the feature will be built—step by step, with tech choices, data models, and file breakdown.

                ## Reviewer
                Ensure the proposed solution is logically consistent and covers all functional scenarios.

                ## Validator
                Confirm the solution adheres to best practices and organizational guidelines.
                """
        except Exception as e:
            logger.error(f"Error loading personas content: {str(e)}")
            return "Error loading personas content. Using default expert personas."

    def get_coding_guidelines(self) -> str:
        """Load the coding guidelines from .github/copilot-instructions.md file."""
        try:
            guidelines_path = Path(".github/copilot-instructions.md")
            if guidelines_path.exists():
                return guidelines_path.read_text(encoding='utf-8')
            else:
                logger.warning("copilot-instructions.md file not found, using default guidelines")
                # Default guidelines
                return """
                # Coding Guidelines

                - Follow best practices for security, performance, and code quality
                - Write clean, modular code with proper error handling
                - Include comprehensive tests for all functionality
                - Follow project-specific conventions and patterns
                """
        except Exception as e:
            logger.error(f"Error loading coding guidelines: {str(e)}")
            return "Error loading coding guidelines. Using default standards."

    def generate_consolidated_plan(self, feature_group: Dict[str, Any], task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generates a consolidated plan including architecture review, tests, and implementation details.
        
        Args:
            feature_group: The feature group data from pre-planning
            task_description: The original task description
            context: Optional context information (e.g., tech stack, file contents)
            
        Returns:
            A dictionary containing the consolidated plan
            
        Raises:
            PlanningError: If the process fails or validation fails
        """
        logger.info(f"Generating consolidated plan for feature group: {feature_group.get('group_name', 'Unnamed')}")
        
        if not self.llm:
            raise PlanningError("No LLM client available for planning")
        
        system_prompt = self.get_consolidated_plan_system_prompt()
        user_prompt = self.get_consolidated_plan_user_prompt(feature_group, task_description, context)
        
        llm_params = get_openrouter_json_params()
        
        try:
            # Log to scratchpad if available
            if self.scratchpad:
                self.scratchpad.log("Planner", "Generating consolidated plan...")
                
            # Call LLM with retry logic
            response = self._call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                llm_params=llm_params
            )
            
            # Extract and validate JSON
            success, plan_data, error_msg = validate_and_repair_json(
                response_text=response,
                schema={
                    "architecture_review": dict,
                    "tests": dict,
                    "implementation_plan": dict,
                    "discussion": str
                }
            )
            
            if not success:
                if self.scratchpad:
                    self.scratchpad.log("Planner", f"Failed to generate valid plan: {error_msg}", level="ERROR")
                raise PlanningError(f"Failed to generate consolidated plan: {error_msg}")
            
            # Log success
            logger.info(f"Successfully generated consolidated plan for: {feature_group.get('group_name', 'Unnamed')}")
            
            if self.scratchpad:
                self.scratchpad.log("Planner", "Successfully generated consolidated plan")
                
            return plan_data
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Error generating consolidated plan: {e}", exc_info=True)
            
            if self.scratchpad:
                self.scratchpad.log("Planner", f"Error generating plan: {e}", level="ERROR")
                
            raise PlanningError(f"Failed to generate consolidated plan: {str(e)}")

    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, llm_params: Dict[str, Any], retries: int = 2) -> str:
        """
        Call LLM with retry logic.
        
        Args:
            system_prompt: System prompt for LLM
            user_prompt: User prompt for LLM
            llm_params: Parameters for LLM call
            retries: Number of retries (default: 2)
            
        Returns:
            LLM response text
            
        Raises:
            PlanningError: If all retries fail
        """
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                if isinstance(self.llm, dict):
                    # If llm is a dictionary of parameters
                    response = cached_call_llm(
                        prompt=user_prompt, 
                        system=system_prompt,
                        **llm_params
                    )
                    return response.get('response', '')
                else:
                    # Assume it's router_agent or similar
                    role = 'planner'
                    response = self.llm.call_llm_by_role(
                        role=role,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        config=llm_params,
                        scratchpad=self.scratchpad
                    )
                    
                    if not response:
                        raise ValueError("LLM returned an empty response")
                        
                    return response
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM call attempt {attempt + 1}/{retries + 1} failed: {e}")
                
                if attempt < retries:
                    # Wait before retry with exponential backoff
                    import time
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"All LLM call attempts failed: {e}")
        
        raise PlanningError(f"LLM call failed after {retries + 1} attempts: {last_error}")


    def generate_architecture_review(self, feature_group: Dict[str, Any], task_description: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate architecture review for a feature group's system design.

        Args:
            feature_group: The feature group data
            task_description: The original task description
            context: Optional context information

        Returns:
            Dictionary with architecture_review and discussion fields
        """
        logger.info(f"Generating architecture review for feature group: {feature_group.get('group_name', 'Unknown')}")
        
        if not self.llm:
            raise PlanningError("No LLM client available")
            
        # Extract system design from feature group
        system_design = {}
        for feature in feature_group.get("features", []):
            if isinstance(feature, dict) and "system_design" in feature:
                feature_system_design = feature.get("system_design", {})
                # Merge system design from all features
                for key, value in feature_system_design.items():
                    if key not in system_design:
                        system_design[key] = value
                    elif isinstance(value, list) and isinstance(system_design[key], list):
                        system_design[key].extend(value)
        
        # Create system prompt for architecture review
        system_prompt = """You are a senior software architect specializing in architecture review.
Your task is to analyze a feature group's system design and identify logical gaps, optimization opportunities, and architectural considerations.

CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:
{
  "architecture_review": {
    "logical_gaps": [
      {
        "description": "Description of the logical gap (e.g., Authentication system lacks CSRF protection)",
        "impact": "Potential impact of the gap (e.g., Vulnerable to cross-site request forgery attacks)",
        "recommendation": "Recommendation to address the gap (e.g., Implement CSRF tokens in all forms)"
      }
    ],
    "optimization_suggestions": [
      {
        "description": "Description of the optimization (e.g., Database queries not optimized for pagination)",
        "benefit": "Potential benefit of the optimization (e.g., Reduced memory usage and query time for large datasets)",
        "implementation_approach": "Suggested approach for implementation (e.g., Add LIMIT/OFFSET or cursor-based pagination)"
      }
    ],
    "additional_considerations": [
      "Any other relevant considerations (e.g., Consider implementing rate limiting to prevent abuse)"
    ]
  },
  "discussion": "Overall assessment of the architecture, explaining key findings and recommendations"
}

Your task is to:
1. Analyze the system design with a focus on its architecture, interfaces, and overall coherence
2. Identify logical gaps in the design that could lead to issues or failures
3. Suggest optimizations that could improve performance, security, or maintainability
4. Provide additional considerations that might not be covered in the logical gaps or optimizations

Be concise and direct in your analysis. Focus on substantive issues rather than style or naming conventions.
Each identified issue should be clear, specific, and actionable, with a clear description, impact/benefit, and recommendation.
"""

        # Create the user prompt
        user_prompt = f"""Please analyze the system design for the following feature group and provide an architecture review.

# Task Description
{task_description}

# Feature Group
{json.dumps(feature_group, indent=2)}

# System Design
{json.dumps(system_design, indent=2)}

# Additional Context
{json.dumps(context or {}, indent=2)}

Focus on:
1. Identifying logical gaps in the design
2. Suggesting optimizations for performance, security, and maintainability
3. Providing additional architectural considerations
"""

        # Get OpenRouter params
        llm_params = get_openrouter_json_params()

        try:
            # Call the LLM
            response = self._call_llm_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                llm_params=llm_params
            )
            
            # Extract and validate JSON
            json_text = extract_json_from_text(response)
            if not json_text:
                raise PlanningError("Failed to extract JSON from architecture review response")
                
            try:
                review_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                raise PlanningError(f"Invalid JSON in architecture review: {e}")
                
            # Validate required sections
            if "architecture_review" not in review_data:
                raise PlanningError("Missing 'architecture_review' in response")
                
            return review_data
            
        except Exception as e:
            logger.error(f"Error generating architecture review: {e}", exc_info=True)
            raise PlanningError(f"Failed to generate architecture review: {str(e)}")

    def validate_pre_planning_for_planner(self, pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate that pre-planning output is compatible with the planning phase.
        
        Args:
            pre_plan_data: Pre-planning data to validate
            
        Returns:
            Tuple of (is_compatible, message):
            - is_compatible: True if the data is compatible, False otherwise
            - message: Description of compatibility issues or confirmation of compatibility
        """
        compatibility_issues = []

        # Check basic structure first
        if not isinstance(pre_plan_data, dict):
            return False, "Pre-planning data is not a dictionary"

        if "feature_groups" not in pre_plan_data or not isinstance(pre_plan_data["feature_groups"], list):
            return False, "Pre-planning data missing feature_groups or it's not a list"

        if not pre_plan_data["feature_groups"]:
            return False, "No feature groups in pre-planning data"

        # Validate each feature group for planner compatibility
        for group_idx, group in enumerate(pre_plan_data["feature_groups"]):
            if not isinstance(group, dict):
                compatibility_issues.append(f"Feature group {group_idx} is not a dictionary")
                continue

            if "features" not in group or not isinstance(group["features"], list) or not group["features"]:
                compatibility_issues.append(f"Feature group {group_idx} has no valid features")
                continue

            for feature_idx, feature in enumerate(group["features"]):
                if not isinstance(feature, dict):
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} is not a dictionary")
                    continue

                # Check system_design with code_elements (crucial for planning)
                if "system_design" not in feature or not isinstance(feature["system_design"], dict):
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} missing system_design object")
                    continue

                if "code_elements" not in feature["system_design"] or not isinstance(feature["system_design"]["code_elements"], list):
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} missing code_elements array")
                    continue

                if not feature["system_design"]["code_elements"]:
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} has empty code_elements array")
                    continue

                # Check code elements for required fields
                elements_with_missing_ids = 0
                for elem_idx, element in enumerate(feature["system_design"]["code_elements"]):
                    if not isinstance(element, dict):
                        compatibility_issues.append(f"Code element {elem_idx} in feature {feature_idx}, group {group_idx} is not a dictionary")
                        continue

                    if "element_id" not in element or not element["element_id"]:
                        elements_with_missing_ids += 1

                    required_fields = ["element_type", "name", "signature", "description", "target_file"]
                    missing_fields = [field for field in required_fields if field not in element]
                    if missing_fields:
                        compatibility_issues.append(f"Code element {elem_idx} in feature {feature_idx}, group {group_idx} missing fields: {', '.join(missing_fields)}")

                if elements_with_missing_ids > 0:
                    compatibility_issues.append(f"Feature {feature_idx} in group {group_idx} has {elements_with_missing_ids} code elements missing element_ids")

                # Check test_requirements have properly linked element_ids
                if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                    if "unit_tests" in feature["test_requirements"] and isinstance(feature["test_requirements"]["unit_tests"], list):
                        tests_missing_element_ids = 0
                        for test_idx, test in enumerate(feature["test_requirements"]["unit_tests"]):
                            if not isinstance(test, dict):
                                continue

                            if ("target_element" in test and not "target_element_id" in test) or not test.get("target_element_id"):
                                tests_missing_element_ids += 1

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

    def generate_plan(self, task_description: str, error_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Public method to generate a plan for a task based on description.
        
        Args:
            task_description: The task description
            error_context: Optional error context for plan generation
            
        Returns:
            Dictionary with plan data and status
        """
        if not self.llm:
            return {
                "success": False,
                "error": "No LLM client available for planning"
            }
            
        try:
            # This is a simplified implementation - in a real system, this would:
            # 1. Analyze the task to extract key requirements
            # 2. Generate a feature group structure
            # 3. Call generate_consolidated_plan with the feature group
            
            # For illustration, we'll create a minimal feature group
            feature_group = {
                "group_name": "Main Feature Group",
                "group_description": f"Implementation plan for: {task_description}",
                "features": [
                    {
                        "name": "Main Feature",
                        "description": task_description,
                        "files_affected": [],
                        "system_design": {
                            "overview": "Implementation of the requested functionality",
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
                        },
                        "test_requirements": {
                            "unit_tests": [
                                {
                                    "description": "Test the main implementation",
                                    "target_element": "main_implementation",
                                    "target_element_id": "main_implementation_function",
                                    "inputs": ["test inputs"],
                                    "expected_outcome": "Expected output"
                                }
                            ],
                            "integration_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": [],
                            "test_strategy": {
                                "coverage_goal": "90%",
                                "ui_test_approach": "None"
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
                        }
                    }
                ]
            }
            
            # Add error context if provided
            context = {}
            if error_context:
                context["previous_error"] = error_context
                
            # Generate consolidated plan
            plan_data = self.generate_consolidated_plan(feature_group, task_description, context)
            
            return {
                "success": True,
                "plan": plan_data,
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "task_description": task_description
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating plan: {e}", exc_info=True)
            self.last_error = str(e)
            
            return {
                "success": False,
                "error": f"Failed to generate plan: {str(e)}",
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "task_description": task_description
                }
            }
