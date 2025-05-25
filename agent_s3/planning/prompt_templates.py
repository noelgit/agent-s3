"""System prompt templates for the planning module.

This module contains all the carefully crafted AI system prompts used throughout
the planning process. These prompts are critical for proper AI behavior and must
be preserved exactly as written.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_personas_content() -> str:
    """Load the personas content from personas.md file. Returns str: Content of the personas.md file"""
    try:
        personas_path = Path("personas.md")
        if personas_path.exists():
            return personas_path.read_text(encoding='utf-8')
        else:
            logger.warning("personas.md file not found, using default personas")
            # --- Using default personas from original code ---
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
        logger.error("Error loading personas content: %s", str(e))
        return "Error loading personas content. Using default expert personas."


def get_coding_guidelines() -> str:
    """Load the coding guidelines from .github/copilot-instructions.md file. Returns str: Content of the coding guidelines file"""
    try:
        guidelines_path = Path(".github/copilot-instructions.md")
        if guidelines_path.exists():
            return guidelines_path.read_text(encoding='utf-8')
        else:
            logger.warning("copilot-instructions.md file not found, using default guidelines")
            # --- Using default guidelines from original code ---
            return """
            # Coding Guidelines

            - Follow best practices for security, performance, and code quality
            - Write clean, modular code with proper error handling
            - Include comprehensive tests for all functionality
            - Follow project-specific conventions and patterns
            """
    except Exception as e:
        logger.error("Error loading coding guidelines: %s", str(e))
        return "Error loading coding guidelines. Using default standards."


def get_consolidated_plan_system_prompt() -> str:
    """
    Get the system prompt for consolidated architecture review, test implementation, and implementation plan generation with enforced JSON output.
    This prompt guides the LLM through a two-step internal process.

    Returns:
        str: Properly formatted system prompt string
    """
    # --- MODIFICATION: Added emphasis on test passing ---
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
   - DO NOT restart the review process from Step 1. Your goal here is to detail the 'how-to' based on the code elements provided in the system_design, with adjustments only as recommended in your architecture review.
   - For each function in the `implementation_plan`:
       - The `function` field should be the full, typed signature (e.g., `def get_user_profile(
           user_id: int) -> Optional[UserProfile]:`).       - The `description` should explain its purpose.
       - The `element_id` field should be the `element_id` from `system_design.code_elements` (e.g. "login_button_impl").
       - The `steps` array should contain structured step objects:
           - `step_description`: A single, clear, actionable implementation step.
           - `pseudo_code`: Optional. A brief pseudo-code snippet if the step is complex.
           - `relevant_data_structures`: List data structures manipulated or accessed.
           - `api_calls_made`: List external or internal API calls.
           - `error_handling_notes`: Note specific error handling for each step where applicable.
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
*   **The implementation plan is a direct, detailed elaboration of the input system_design.code_elements, and the tests must accurately verify these elements.**
*   **Maintain consistent element_id references throughout architecture review, implementation plan, and tests to ensure complete traceability.**
*   **The final generated implementation code derived from this plan MUST pass the tests generated within this same plan.**
"""