"""Planner module for agent-s3.

Responsible for creating implementation plans for tasks with enforced JSON output.
This module is part of the planning architecture consisting of:
- pre_planner_json_enforced.py: Enhanced JSON schema enforcement for pre-planning
- planner.py: Base planning functionality (this module)
- planner_json_enforced.py: Enhanced JSON schema enforcement for planning
"""

# Standard library imports
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Third-party imports
# None required

# Local imports
from agent_s3.errors import PlanningError
from agent_s3.json_utils import (
    extract_json_from_text,
    get_openrouter_json_params
)
from agent_s3.llm_utils import cached_call_llm

logger = logging.getLogger(__name__)

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
    """The Planner class is responsible for creating plans for tasks using an LLM."""
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
        "function": "def function_name(param1: type, param2: type) -> return_type:",
             // Full signature        "description": "Purpose of the function and how it contributes to the feature",
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
   - For each function in the `implementation_plan`:
       - The `function` field should be the full, typed signature (e.g., \`def get_user_profile(
           user_id: int) -> Optional[UserProfile]:\`).
       - The \`description\` should explain its purpose.
       - The \`element_id\` field should be the \`element_id\` from \`system_design.code_elements\` (e.g. "login_button_impl").
       - The \`steps\` array should contain structured step objects:
           - \`step_description\`: A single, clear, actionable implementation step.
           - \`pseudo_code\`: Optional. A brief pseudo-code snippet if the step is complex.
           - \`relevant_data_structures\`: List data structures manipulated or accessed.
           - \`api_calls_made\`: List external or internal API calls.
           - \`error_handling_notes\`: Note specific error handling for this step.
       - The \`edge_cases\` array should list specific edge cases to handle in this function's implementation.
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

    def get_consolidated_plan_user_prompt(self, feature_group: Dict[str, Any], task_description: str, 
                                        context: Optional[Dict[str, Any]] = None) -> str:
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
        except (IOError, OSError) as e:
            logger.error("Error loading personas content: %s", str(e))
            return "Error loading personas content. Using default expert personas."
        except UnicodeError as e:
            logger.error("Error decoding personas content: %s", str(e))
            return "Error decoding personas content. Using default expert personas."

    def get_coding_guidelines(self) -> str:
        """Load the coding guidelines from .github/copilot-instructions.md file."""
        try:
            guidelines_path = Path(".github/copilot-instructions.md")
            if guidelines_path.exists():
                return guidelines_path.read_text(encoding='utf-8')

            logger.warning("copilot-instructions.md file not found, using default guidelines")
            # Default guidelines
            return """
            # Coding Guidelines

            - Follow best practices for security, performance, and code quality
            - Write clean, modular code with proper error handling
            - Include comprehensive tests for all functionality
            - Follow project-specific conventions and patterns
            """
        except (IOError, OSError) as e:
            logger.error("Error loading coding guidelines: %s", str(e))
            return "Error loading coding guidelines. Using default standards."
        except UnicodeError as e:
            logger.error("Error decoding coding guidelines: %s", str(e))
            return "Error loading coding guidelines. Using default standards."



    def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        llm_params: Dict[str, Any],
        retries: int = 2
    ) -> str:
        """Call LLM with retry logic.

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

            except (ValueError, IOError, ConnectionError) as e:
                last_error = str(e)
                logger.warning(
                    "LLM call attempt %d/%d failed: %s",
                    attempt + 1,
                    retries + 1,
                    str(e)
                )

                if attempt < retries:
                    # Wait before retry with exponential backoff
                    import time
                    time.sleep(2 ** attempt)
                else:
                    logger.error("All LLM call attempts failed: %s", str(e))

        msg = f"LLM call failed after {retries + 1} attempts: {last_error}"
        raise PlanningError(msg) from last_error

    def generate_architecture_review(
        self,
        feature_group: Dict[str, Any],
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate architecture review for a feature group's system design.

        Args:
            feature_group: The feature group data
            task_description: The original task description
            context: Optional context information

        Returns:
            Dictionary with architecture_review and discussion fields
        """
        logger.info(
            "Generating architecture review for feature group: %s",
            feature_group.get('group_name', 'Unknown')
        )

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
                    elif (
                        isinstance(value, list) and
                        isinstance(system_design[key], list)
                    ):
                        system_design[key].extend(value)

        # Create system prompt for architecture review
        system_prompt = (
            "You are a senior software architect specializing in architecture "
            "review. Your task is to analyze a feature group's system design "
            "and identify logical gaps, optimization opportunities, and "
            "architectural considerations.\n\n"
            "CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, "
            "conforming EXACTLY to this schema:\n"
            "{\n"
            '  "architecture_review": {\n'
            '    "logical_gaps": [\n'
            "      {\n"
            '        "description": "Description of the logical gap (e.g., '
            'Authentication system lacks CSRF protection)",\n'
            '        "impact": "Potential impact of the gap (e.g., Vulnerable '
            'to cross-site request forgery attacks)",\n'
            '        "recommendation": "Recommendation to address the gap '
            '(e.g., Implement CSRF tokens in all forms)"\n'
            "      }\n"
            "    ],\n"
            '    "optimization_suggestions": [\n'
            "      {\n"
            '        "description": "Description of the optimization (e.g., '
            'Database queries not optimized for pagination)",\n'
            '        "benefit": "Potential benefit of the optimization (e.g., '
            'Reduced memory usage and query time for large datasets)",\n'
            '        "implementation_approach": "Suggested approach for '
            'implementation (e.g., Add LIMIT/OFFSET or cursor-based '
            'pagination)"\n'
            "      }\n"
            "    ],\n"
            '    "additional_considerations": [\n'
            '      "Any other relevant considerations (e.g., Consider '
            'implementing rate limiting to prevent abuse)"\n'
            "    ]\n"
            "  },\n"
            '  "discussion": "Overall assessment of the architecture, '
            'explaining key findings and recommendations"\n'
            "}\n\n"
            "Your task is to:\n"
            "1. Analyze the system design with a focus on its architecture, "
            "interfaces, and overall coherence\n"
            "2. Identify logical gaps in the design that could lead to issues "
            "or failures\n"
            "3. Suggest optimizations that could improve performance, security, "
            "or maintainability\n"
            "4. Provide additional considerations that might not be covered in "
            "the logical gaps or optimizations\n\n"
            "Be concise and direct in your analysis. Focus on substantive "
            "issues rather than style or naming conventions.\n"
            "Each identified issue should be clear, specific, and actionable, "
            "with a clear description, impact/benefit, and recommendation."
        )

        # Create the user prompt
        user_prompt = (
            "Please analyze the system design for the following feature group "
            "and provide an architecture review.\n\n"
            "# Task Description\n"
            f"{task_description}\n\n"
            "# Feature Group\n"
            f"{json.dumps(feature_group, indent=2)}\n\n"
            "# System Design\n"
            f"{json.dumps(system_design, indent=2)}\n\n"
            "# Additional Context\n"
            f"{json.dumps(context or {}, indent=2)}\n\n"
            "Focus on:\n"
            "1. Identifying logical gaps in the design\n"
            "2. Suggesting optimizations for performance, security, and "
            "maintainability\n"
            "3. Providing additional architectural considerations"
        )

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
                raise PlanningError(
                    "Failed to extract JSON from architecture review response"
                )

            try:
                review_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                raise PlanningError("Invalid JSON in architecture review") from e

            # Validate required sections
            if "architecture_review" not in review_data:
                raise PlanningError("Missing 'architecture_review' in response")

            return review_data

        except (IOError, ConnectionError) as e:
            logger.error("Error generating architecture review: %s", str(e))
            raise PlanningError("Failed to generate architecture review") from e

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

                            if ("target_element" in test and "target_element_id" not in test) or not test.get("target_element_id"):
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


