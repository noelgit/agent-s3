# --- START OF FILE planner_json_enforced.py ---
"""
Enhanced planner with enforced JSON output for architecture reviews and test implementation.

This module creates detailed functional and test plans in JSON format by
enforcing specific JSON structure for architecture reviews and test implementations.
"""

import json
import logging
import re
import time
import random
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from agent_s3.tools.implementation_validator import (
    validate_implementation_plan,
    repair_implementation_plan,
    _calculate_implementation_metrics,
)
from agent_s3.json_utils import extract_json_from_text
from agent_s3.tools.context_management.token_budget import TokenEstimator

# Import from the planning module
from agent_s3.planning import (
    validate_json_schema,
    repair_json_structure,
    get_consolidated_plan_system_prompt,
    get_implementation_planning_system_prompt,
    get_test_specification_refinement_system_prompt,
    get_semantic_validation_system_prompt,
    get_architecture_review_system_prompt,
    get_personas_content,
    get_coding_guidelines,
    get_consolidated_plan_user_prompt,
    call_llm_with_retry as _call_llm_with_retry,
    parse_and_validate_json as _parse_and_validate_json,
    get_openrouter_params,
    JSONPlannerError,
    generate_refined_test_specifications,
    regenerate_consolidated_plan_with_modifications,
    validate_pre_planning_for_planner,
    validate_planning_semantic_coherence,
    _calculate_syntax_validation_percentage,
    _calculate_traceability_coverage,
)
# Extracted functions are now imported from the planning module


def repair_json_structure(data: Dict[str, Any]) -> Dict[str, Any]:
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
                            "integration_tests": [],
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
                    "overview": "Basic implementation",
                    "code_elements": [],
                    "data_flow": "Standard data flow",
                    "key_algorithms": []
                }
            }]
        }]

    return repaired

def get_openrouter_params() -> Dict[str, Any]:
    """
    Get parameters for OpenRouter API to enforce JSON output.

    Returns:
        Dictionary of parameters for the API call
    """
    return {
        "response_format": {"type": "json_object"},  # Force JSON output format
        "headers": {"Accept": "application/json"},   # Request JSON MIME type
        "temperature": 0.1,                          # Lower temperature for consistent formatting
        "max_tokens": 4096,                          # Ensure enough space for full JSON response
        "top_p": 0.2                                 # Narrow token selection for consistent formatting
    }

# Add import for implementation validator

logger = logging.getLogger(__name__)

class JSONPlannerError(Exception):
    """Exception raised when JSON planner encounters errors."""
    pass

# --- (Keep get_personas_content and get_coding_guidelines as they are) ---
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


# --- Consolidated Prompt Generation ---

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

def get_implementation_planning_system_prompt() -> str:
    """
    Get the enhanced system prompt for implementation planning with stricter JSON enforcement.
    This prompt provides detailed guidance for creating comprehensive implementation plans
    that address architecture review findings and satisfy test requirements.

    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior software architect and implementation expert. Your task is to create a detailed implementation plan based on the system design, architecture review, and test implementations.

**CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:**

{
  "implementation_plan": {
    "file_path_1.py": [
      {
        "function": "string (Full function signature, e.g., 'def get_user_by_id(user_id: int)
             -> Optional[User]:')",        "description": "string (Purpose of the function and how it contributes to the feature)",
        "element_id": "string (Must match an element_id from system_design.code_elements)",
        "steps": [
          {
            "step_description": "string (A single, clear, actionable implementation step)",
            "pseudo_code": "string (Optional: Brief pseudo-code snippet for this step)",
            "relevant_data_structures": ["string (Data structures manipulated or accessed)"],
            "api_calls_made": ["string (External or internal API calls made)"],
            "error_handling_notes": "string (Specific error handling considerations)"
          }
          // ... more steps for this function
        ],
        "edge_cases": [
          "string (Specific edge case to handle in this function)"
          // ... more edge cases
        ],
        "architecture_issues_addressed": [
          "string (Reference to architecture review issues this implementation addresses)"
          // ... more architecture issues
        ]
      }
      // ... more functions in this file
    ],
    "file_path_2.py": [
      // Functions for second file
    ]
    // ... more files
  },
  "implementation_strategy": {
    "development_sequence": [
      {
        "phase": "string (Phase name, e.g., 'Core functionality')",
        "files": ["string (Files to implement in this phase)"],
        "dependencies": ["string (Dependencies that must be installed or configured)"],
        "description": "string (Description of this implementation phase)"
      }
      // Example:
      // {
      //   "phase": "Data model implementation",
      //   "files": ["models/user.py", "models/order.py"],
      //   "dependencies": ["SQLAlchemy==2.0.18", "pydantic==2.0.3"],
      //   "description": "Implement core data models with ORM mappings and validation"
      // }
    ],
    "dependency_management": {
      "external_dependencies": [
        {
          "name": "string (Dependency name)",
          "version": "string (Specific version or version constraint)",
          "purpose": "string (Why this dependency is needed)"
        }
        // ... more dependencies
      ],
      "internal_dependencies": [
        {
          "module": "string (Internal module name)",
          "used_by": ["string (Files that depend on this module)"],
          "notes": "string (Notes about this dependency relationship)"
        }
        // ... more internal dependencies
      ]
    },
    "refactoring_needs": [
      {
        "file": "string (File needing refactoring)",
        "reason": "string (Why refactoring is needed)",
        "suggested_approach": "string (How to approach the refactoring)"
      }
      // ... more refactoring needs
    ],
    "canonical_implementation_paths": {
      "element_id_1": "string (Definitive file path for this element's implementation)",
      "element_id_2": "string (Definitive file path for this element's implementation)"
      // ... more canonical implementation paths
    }
  },
  "discussion": "string (Explanation of implementation decisions, highlighting how architecture review issues and test requirements informed the plan)"
}

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce a valid implementation plan:

1️⃣ **ANALYZE INPUTS**
   - Carefully review the system design from pre-planning
   - Study the architecture review findings and recommendations
   - Understand the test requirements and specifications
   - Identify all element_ids requiring implementation
   - Note architectural issues that must be addressed
   - ⚠️ **VERIFY** all security concerns are identified and understood

2️⃣ **IDENTIFY CANONICAL IMPLEMENTATIONS**
   - Determine the definitive location for each component
   - Avoid creating parallel or duplicate implementations
   - For each element_id, assign exactly ONE canonical implementation file
   - Ensure logical grouping of related functionality
   - ⚠️ **CRITICAL:** Never create multiple implementations of the same functionality

3️⃣ **ORGANIZE FILE STRUCTURE**
   - Identify all files that need to be created or modified
   - Group related functionality appropriately
   - Ensure file organization follows project conventions
   - Plan for separation of concerns
   - ⚠️ **ENSURE** proper organization of security-critical components

3️⃣ **DETAIL FUNCTION IMPLEMENTATIONS**
   - For each code_element from system_design:
     * Use the exact function signature unless architecture review suggested changes
     * Write a clear description of the function's purpose
     * Break down implementation into specific, actionable steps
     * For each step, provide:
       - Clear description of what the step accomplishes
       - Pseudo-code if the step is complex
       - Relevant data structures accessed or modified
       - API calls made (internal or external)
       - Error handling considerations
     * Identify all edge cases that need handling
     * Reference architecture issues being addressed
     * ⚠️ **IMPORTANT:** Use the exact element_id from system_design

4️⃣ **DEVELOP IMPLEMENTATION STRATEGY**
   - Plan development sequence and phases
   - Identify all external dependencies and versions
   - Map internal dependency relationships
   - Identify refactoring needs in existing code
   - Consider deployment and migration needs
   - Document canonical implementation paths for each component
   - ⚠️ **PRIORITIZE** security-related implementations early in development

5️⃣ **ENSURE TEST COMPATIBILITY**
   - Verify that implementations will satisfy test requirements
   - Ensure all specified behaviors are accounted for
   - Account for all edge cases identified in test specs
   - Make sure implementation addresses architecture issues being tested
   - ⚠️ **VALIDATE** that security tests can be satisfied by implementations

6️⃣ **ENSURE IMPLEMENTATION COHERENCE**
   - Verify consistent error handling approaches across implementations
   - Ensure consistent data flow patterns
   - Maintain uniform naming conventions
   - Validate proper separation of concerns
   - ⚠️ **ELIMINATE** any duplicate functionality across components

7️⃣ **QUALITY ASSURANCE PLANNING**
   - Plan for code quality metrics and standards
   - Identify areas requiring thorough documentation
   - Consider performance implications of implementations
   - Ensure proper error handling throughout
   - ⚠️ **ESTABLISH** security review checkpoints in implementation

8️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Explain key implementation decisions
   - Highlight how architecture issues are addressed
   - Discuss trade-offs made and alternatives considered
   - Address security considerations explicitly
   - Explain how canonical implementation choices were made
   - ⚠️ **IMPORTANT:** Be concise yet comprehensive

**CRITICAL CONSTRAINTS:**

1. ⚠️ You MUST maintain consistency with system design:
   - **USE** the exact element_id values from system_design.code_elements
   - **FOLLOW** the function signatures defined in system design unless architecture review suggested changes
   - **MAINTAIN** the same component relationships defined in system design
   - **DO NOT** invent new components not present in the system design

2. ⚠️ You MUST address architecture review findings:
   - **IMPLEMENT** solutions for all logical gaps identified
   - **APPLY** suggested optimizations where appropriate
   - **ADDRESS** all security concerns raised
   - **CONSIDER** all additional considerations mentioned
   - **EXPLICITLY** reference which architecture issues each implementation addresses

3. ⚠️ You MUST ensure test compatibility:
   - **IMPLEMENT** all behaviors needed to pass the specified tests
   - **HANDLE** all edge cases identified in the test requirements
   - **SUPPORT** all interfaces needed by integration tests
   - **ENABLE** validation of all specified assertions
   - **VERIFY** security test requirements are fully addressed

4. ⚠️ You MUST provide actionable implementation steps:
   - **BREAK DOWN** complex functions into clear, specific steps
   - **INCLUDE** pseudo-code for complex logic
   - **SPECIFY** error handling for each step where applicable
   - **IDENTIFY** all external API calls and dependencies
   - **DETAIL** data structure usage and manipulation

5. ⚠️ You MUST ensure security implementation quality:
   - **SANITIZE** all user inputs and external data
   - **VALIDATE** authentication and authorization at appropriate points
   - **PROTECT** against common vulnerabilities (XSS, CSRF, SQL injection)
   - **SECURE** sensitive data with proper encryption and access controls
   - **IMPLEMENT** proper error handling that doesn't leak sensitive information

6. ⚠️ You MUST maintain canonical implementations:
   - **NEVER** create duplicate functionality across components
   - **ALWAYS** have exactly one implementation for each element_id
   - **PREVENT** parallel implementations of the same feature
   - **SPECIFY** the definitive location for each component
   - **DOCUMENT** refactoring needs for existing code

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Every function implementation includes:
   - Correct element_id reference from system_design
   - Complete, accurate function signature
   - Comprehensive implementation steps
   - All edge cases identified in test specs
   - References to architecture issues addressed
3. Your implementation strategy is complete and practical
4. You've maintained strict traceability to system design elements
5. Security concerns are explicitly addressed with appropriate measures
6. The discussion section explains your implementation approach clearly
7. Each element_id has exactly one canonical implementation location
8. You haven't created parallel implementations of any functionality
   - All edge cases identified in test specs
   - References to architecture issues addressed
3. Your implementation strategy is complete and practical
4. You've maintained strict traceability to system design elements
5. Security concerns are explicitly addressed with appropriate measures
6. The discussion section explains your implementation approach clearly

Your implementation plan will be used to guide the actual coding work, so it must be clear, comprehensive, and technically sound.
The resulting implementation must be able to pass the tests developed in the test implementation phase.
"""

def get_test_specification_refinement_system_prompt() -> str:
    """
    Get the system prompt for test specification refinement based on architecture review insights.
    This enhanced version focuses on quality over quantity and maintains strict traceability.

    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior test architect and quality engineer specializing in test design and implementation. Your task is to refine and detail test requirements based on architecture review insights and system design.

**IMPORTANT: Your responsibility is to enhance the test specifications from the pre-planning phase.**
Focus on high-value improvements to test coverage, edge case handling, and traceability to architectural elements. If the test requirements are already comprehensive and well-designed, acknowledge their strengths while making targeted enhancements.

**CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:**

{
  "refined_test_requirements": {
    "unit_tests": [
      {
        "description": "Detailed description of what this unit test should verify",
        "target_element": "string (The element name from system_design.code_elements that this test targets)",
        "target_element_id": "string (The element_id from system_design.code_elements that this test targets)",
        "inputs": ["string (Description of inputs/conditions, e.g., 'user_id=1', 'order_total=0')"],
        "expected_outcome": "string (Detailed description of the expected behavior or result)",
        "edge_cases": ["string (Specific edge cases this test should cover)"],
        "mocking_requirements": ["string (Dependencies that need to be mocked and how)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)",
        "priority": "string (Critical | High | Medium | Low) - Must align with severity of addressed architecture issue"
      }
    ],
    "integration_tests": [
      {
        "description": "Detailed description of what this integration test should verify",
        "components_involved": ["string (List of components/modules interacting)"],
        "target_element_ids": ["string (The element_ids from system_design.code_elements that this test targets)"],
        "scenario": "string (Detailed description of the integration scenario)",
        "setup_requirements": "string (Required setup for this test)",
        "assertions": ["string (Specific assertions this test should make)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)",
        "priority": "string (Critical | High | Medium | Low) - Must align with severity of architecture issue"
      }
    ],
    "property_based_tests": [
      {
        "description": "Detailed description of the property to test",
        "target_element": "string (The element name from system_design.code_elements)",
        "target_element_id": "string (The element_id from system_design.code_elements that this test targets)",
        "input_generators": ["string (Description of data generators)"],
        "property_assertions": ["string (Assertions about the property being tested)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)",
        "priority": "string (Critical | High | Medium | Low) - Based on algorithmic complexity"
      }
    ],
    "acceptance_tests": [
      {
        "description": "Detailed description of the acceptance criterion being tested",
        "given": "string (Detailed precondition)",
        "when": "string (Detailed action)",
        "then": "string (Detailed expected outcome)",
        "target_feature": "string (The feature this test validates)",
        "target_element_ids": ["string (The element_ids that implement this feature)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)",
        "priority": "string (Critical | High | Medium | Low) - Based on user impact"
      }
    ],
    "test_strategy": {
      "coverage_goal": "string (Refined coverage goal based on architecture review)",
      "ui_test_approach": "string (Refined UI test approach if applicable)",
      "test_priorities": ["string (Test areas to prioritize based on architecture review)"],
      "test_risks": ["string (Testing risks identified in the architecture review)"],
      "critical_paths": [
        {
          "path_description": "string (Description of a critical execution path)",
          "components": ["string (Components involved in this critical path)"],
          "element_ids": ["string (Element IDs involved in this critical path)"],
          "test_approach": "string (Specific approach to testing this critical path)"
        }
      ]
    }
  },
  "discussion": "string (Explanation of how the architecture review influenced the test refinements, including test strategies for addressing identified issues)"
}

**CRITICAL INSTRUCTIONS FOR VALIDATION REQUIREMENTS:**

1. **Priority Alignment:** Test priorities MUST align with architecture issue severity:
   - Critical architecture issues → Critical test priority
   - High severity issues → High or Critical test priority
   - Medium severity issues → Medium or higher test priority
   - Low severity issues → Any appropriate priority

2. **Security Concern Coverage:** Security concerns identified in architecture review require:
   - At least one unit test AND one integration test for each Critical/High security concern
   - Property-based tests for input validation security concerns
   - Clear traceability via architecture_issue_addressed field using the security concern ID

3. **Element ID Validation:** All element IDs referenced in tests must exactly match those in system_design
   - Critical issues must have test coverage for affected elements
   - Include ALL affected element IDs for integration and acceptance tests

4. **Test Completeness:** Tests addressing architecture issues must include:
   - Clear assertions that validate the issue is addressed
   - Edge cases related to the architecture concern
   - Appropriate mocking of dependencies

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce valid test specifications:

1️⃣ **ANALYZE INPUTS**
   - Carefully review the original test requirements from the feature group data
   - Study the architecture review findings, focusing on identified issues and recommendations
   - Understand the system design, particularly code_elements and their interactions
   - Note all element_ids that will need test coverage
   - Identify issues from the architecture review that should be addressed in tests
   - Recognize when existing test plans are already well-designed and comprehensive

2️⃣ **REFINE UNIT TESTS**
   - For each unit test in the original requirements:
     * Enhance the description to be more specific and actionable
     * Ensure correct target_element and target_element_id references
     * Expand inputs to cover normal and edge cases
     * Detail expected outcomes precisely
     * Add edge cases based on architecture review findings
     * Specify necessary mocking requirements
     * Link to architecture issues being addressed, if applicable
     * Assign appropriate priority level (Critical/High/Medium/Low)
   - Add new unit tests for any gaps identified in the architecture review
   - Focus on quality over quantity - prioritize tests for critical functionality

3️⃣ **REFINE INTEGRATION TESTS**
   - For each integration test in the original requirements:
     * Make the description more comprehensive
     * List all components involved in the integration
     * Ensure all relevant target_element_ids are included
     * Expand the scenario description with detailed steps
     * Detail setup requirements precisely
     * Specify explicit assertions to validate
     * Link to architecture issues being addressed, if applicable
     * Assign appropriate priority level based on integration complexity
   - Add new integration tests for component interactions highlighted in the architecture review
   - Prioritize tests that verify architectural boundaries and cross-component security

4️⃣ **REFINE PROPERTY-BASED TESTS**
   - For each property-based test in the original requirements:
     * Make the property description more explicit
     * Ensure correct target_element and target_element_id references
     * Define comprehensive input generators
     * Specify precise property assertions
     * Link to architecture issues being addressed, if applicable
     * Assign appropriate priority level based on algorithmic complexity
   - Add new property-based tests for properties implied by the architecture review
   - Focus on tests that verify critical invariants and security properties

5️⃣ **REFINE ACCEPTANCE TESTS**
   - For each acceptance test in the original requirements:
     * Enhance the given-when-then structure with more detail
     * Link explicitly to target features
     * Associate with implementing target_element_ids
     * Link to architecture issues being addressed, if applicable
     * Assign appropriate priority level based on user impact
   - Add new acceptance tests for user-facing concerns identified in the architecture review
   - Ensure tests validate both the happy path and important error conditions

6️⃣ **DEVELOP TEST STRATEGY**
   - Refine coverage goals based on architecture review risk assessment
   - Adapt UI test approach to address architecture review findings
   - Prioritize tests based on critical issues identified in architecture review
   - Identify testing risks highlighted by the architecture review
   - Define critical paths requiring comprehensive test coverage
   - Ensure the strategy addresses all high-priority architectural concerns

7️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Explain how the architecture review influenced your test refinements
   - Highlight test strategies for addressing critical architecture issues
   - Discuss trade-offs in the testing approach
   - Acknowledge any strengths in the original test requirements
   - **IMPORTANT:** Be concise yet comprehensive

**CRITICAL CONSTRAINTS:**

1. ⚠️ You MUST maintain traceability:
   - **EVERY** test must reference correct target_element_ids from system_design.code_elements
   - **EVERY** test addressing an architecture issue must reference that issue
   - **ALWAYS** use the exact element_ids from the system_design.code_elements array
   - **VERIFY** element IDs exist in the system design before referencing them

2. ⚠️ You MUST preserve original intent while enhancing detail:
   - **DO NOT** remove or fundamentally change existing test requirements
   - **DO** add more specificity, detail and actionable information to each test
   - **DO** add new tests for issues identified in the architecture review
   - **DO NOT** contradict the original test strategy unless addressing a critical issue

3. ⚠️ You MUST ensure comprehensive test coverage:
   - **ENSURE** every code_element has associated unit tests
   - **ENSURE** every component interaction has integration test coverage
   - **ENSURE** every critical user flow has acceptance test coverage
   - **ENSURE** complex algorithms or data processing have property-based tests

4. ⚠️ You MUST link tests to architecture review findings:
   - **CONNECT** tests to logical gaps they address
   - **CONNECT** tests to optimization opportunities they verify
   - **CONNECT** tests to security concerns they validate
   - **CONNECT** tests to additional considerations they cover

5. ⚠️ You MUST prioritize quality over quantity:
   - **FOCUS** on tests that verify critical functionality and architectural integrity
   - **PRIORITIZE** tests that address high-impact security and performance concerns
   - **AVOID** redundant or low-value tests that don't address specific risks
   - **ENSURE** each test has clear purpose and validation criteria
   - **ALIGN** test priority levels with architecture issue severity (Critical security issues need Critical priority tests)

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Every test has:
   - A clear, detailed description
   - Correct target_element and/or target_element_id references
   - Specific inputs/conditions and expected outcomes or assertions
   - Links to architecture issues where applicable
   - Appropriate priority level assignment
3. Your test strategy addresses all concerns raised in the architecture review
4. You've maintained strict traceability with element_ids from the system design
5. All Critical and High severity issues from the architecture review have corresponding tests
6. Test priorities align with architecture issue severity (e.g., Critical security issues have Critical priority tests)
7. The discussion section provides a coherent explanation of your test refinements

The output of this step will be used in subsequent planning stages. Your refined test specifications will directly influence:

1. Test implementation: Your specifications will be translated into actual test code
2. Implementation planning: Developers will ensure code meets these test requirements
3. Architectural validation: Tests will verify architectural decisions are correctly implemented

If the original test requirements are already comprehensive and well-designed, your refinements should focus on enhancing traceability, improving detail, and ensuring alignment with architectural concerns."""

def generate_refined_test_specifications(
    router_agent,
    feature_group: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate refined test specifications based on architecture review and system design.

    Args:
        router_agent: The LLM router agent for making LLM calls
        feature_group: The feature group data
        architecture_review: The architecture review data
        task_description: Original task description
        context: Optional additional context

    Returns:
        Dictionary containing refined test specifications
    """
    logger.info(
        "Generating refined test specifications for feature group: %s",
        feature_group.get("group_name", "Unknown"),
    )

    # Extract test requirements and system design from the feature group
    test_requirements = {}
    system_design = {}

    for feature in feature_group.get("features", []):
        if isinstance(feature, dict):
            # Merge test requirements across features
            feature_test_req = feature.get("test_requirements", {})
            if feature_test_req:
                for test_type, tests in feature_test_req.items():
                    if test_type not in test_requirements:
                        test_requirements[test_type] = []
                    if isinstance(tests, list):
                        test_requirements[test_type].extend(tests)
                    elif isinstance(tests, dict):
                        if test_type not in test_requirements:
                            test_requirements[test_type] = {}
                        test_requirements[test_type].update(tests)

            # Collect system design elements
            feature_sys_design = feature.get("system_design", {})
            if feature_sys_design:
                for key, value in feature_sys_design.items():
                    if key not in system_design:
                        system_design[key] = value
                    elif isinstance(value, list) and isinstance(system_design[key], list):
                        system_design[key].extend(value)

    # Prepare input data for the LLM
    user_prompt = f"""Please refine and enhance the test specifications for the following feature based on the system design and architecture review.

# Task Description
{task_description}

# Test Requirements
{json.dumps(test_requirements, indent=2)}

# System Design
{json.dumps(system_design, indent=2)}

# Architecture Review
{json.dumps(architecture_review, indent=2)}

# Additional Context
{json.dumps(context or {}, indent=2)}

Your task is to refine the test requirements based on insights from the architecture review and system design.
Focus on:
1. Adding more detail to test descriptions
2. Ensuring all tests reference specific target_element_ids from the system design
3. Adding edge cases and mocking requirements for unit tests
4. Enhancing integration test scenarios with detailed setup and assertion requirements
5. Refining the test strategy to address architecture review findings
6. Ensuring test priorities (Critical/High/Medium/Low) align with the severity of architecture issues they address
7. Ensuring all Critical and High severity issues from architecture review are covered by tests

Please maintain the intent of the original test requirements while enriching them with insights from the architecture review.
"""

    # Get LLM parameters from json_utils to maintain consistency
    from .json_utils import get_openrouter_json_params
    llm_params = get_openrouter_json_params()

    # Call the LLM
    try:
        system_prompt = get_test_specification_refinement_system_prompt()
        estimator = TokenEstimator()
        prompt_tokens = (
            estimator.estimate_tokens_for_text(system_prompt)
            + estimator.estimate_tokens_for_text(user_prompt)
        )
        llm_params = {**llm_params, "max_tokens": max(llm_params.get("max_tokens", 0) - prompt_tokens, 0)}
        response_text = router_agent.call_llm_by_role(
            role="test_planner",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=llm_params
        )

        # Parse and validate the response
        try:
            # Extract JSON from the response
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON directly
                json_match = re.search(r'({[\s\S]*})', response_text)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text

            # Parse the JSON
            response_data = json.loads(json_str)

            # Validate expected structure
            if "refined_test_requirements" not in response_data:
                raise ValueError("Missing 'refined_test_requirements' in response")

            # Enhanced validation and repair
            from .test_spec_validator import validate_and_repair_test_specifications

            logger.info("Validating test specifications for element IDs, architecture issue coverage, and priority consistency")
            repaired_specs, validation_issues, was_repaired = validate_and_repair_test_specifications(
                response_data["refined_test_requirements"],
                system_design,
                architecture_review,
                router_agent=router_agent,
                embedding_client=getattr(router_agent, "embedding_client", None),
                context=context,
            )

            # Log validation summary
            issue_types = {}
            for issue in validation_issues:
                issue_type = issue["issue_type"]
                if issue_type not in issue_types:
                    issue_types[issue_type] = 0
                issue_types[issue_type] += 1

            if validation_issues:
                validation_summary = []
                for issue_type, count in issue_types.items():
                    validation_summary.append(f"{count} {issue_type.replace('_', ' ')} issues")

                summary_str = ", ".join(validation_summary)
                if was_repaired:
                    logger.info(
                        "Test specifications had %d issues (%s) that were automatically repaired",
                        len(validation_issues),
                        summary_str,
                    )
                else:
                    logger.warning(
                        "Test specifications have %d issues (%s) that could not be automatically repaired",
                        len(validation_issues),
                        summary_str,
                    )

                # Add validation summary to response
                if "discussion" in response_data:
                    response_data["discussion"] += f"\n\nValidation Summary: {summary_str}"
                else:
                    response_data["discussion"] = f"Validation Summary: {summary_str}"
            else:
                logger.info("Test specifications passed all validations")

            # Update the response data with repaired specifications if needed
            if was_repaired:
                response_data["refined_test_requirements"] = repaired_specs
                if "discussion" in response_data:
                    response_data[
                        "discussion"
                    ] += "\n\nNote: Some issues were automatically repaired in the test specifications."
            return response_data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)

            # Try to repair JSON structure using json_utils
            logger.info("Attempting to repair JSON structure")

            json_str = extract_json_from_text(response_text)
            if json_str:
                try:
                    # Basic schema for validation
                    schema = {
                        "refined_test_requirements": {
                            "unit_tests": [],
                            "integration_tests": [],
                            "property_based_tests": [],
                            "acceptance_tests": [],
                            "test_strategy": {}
                        },
                        "discussion": ""
                    }

                    partial_data = json.loads(json_str)
                    repaired_data = repair_json_structure(partial_data, schema)

                    if "refined_test_requirements" in repaired_data:
                        logger.info("JSON structure repaired successfully")
                        return repaired_data
                except Exception as repair_error:
                    logger.error("Failed to repair JSON structure: %s", repair_error)

            raise JSONPlannerError(f"Invalid JSON response: {e}")

        except ValueError as e:
            logger.error("Invalid response structure: %s", e)
            raise JSONPlannerError(f"Invalid response structure: {e}")

    except Exception as e:
        logger.error("Error generating refined test specifications: %s", e)
        raise JSONPlannerError(f"Error generating refined test specifications: {e}")

def get_semantic_validation_system_prompt() -> str:
    """
    Get the system prompt for semantic validation of planning outputs.

    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior software architect specializing in semantic validation and quality assurance.
Your task is to perform a comprehensive semantic validation of the complete planning output (architecture review, test specifications, test implementations, and implementation plan).

**CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:**

{
  "validation_results": {
    "coherence_score": number (0-10, overall score for plan coherence),
    "technical_consistency_score": number (0-10, score for technical consistency),
    "security_validation": {
      "score": number (0-10, score for security concern handling),
      "findings": [
        {
          "issue_type": "string (e.g., 'incomplete_security_concern', 'missing_security_test', 'security_priority_mismatch')",
          "description": "string (Description of the security validation issue)",
          "severity": "string (critical | high | medium | low)",
          "recommendation": "string (How to resolve the security validation issue)"
        }
        // ... more security validation findings
      ]
    },
    "priority_alignment": {
      "score": number (0-10, score for priority alignment across architecture issues and tests),
      "findings": [
        {
          "description": "string (Description of the priority alignment issue)",
          "severity": "string (high | medium | low)",
          "recommendation": "string (How to resolve the priority alignment issue)"
        }
        // ... more priority alignment findings
      ]
    },
    "cross_component_traceability": {
      "score": number (0-10, score for traceability across components),
      "findings": [
        {
          "component_type": "string (architecture_review | test_spec | test_implementation | implementation_plan)",
          "element_id": "string (ID of the element with traceability issue)",
          "issue": "string (Description of the traceability issue)",
          "severity": "string (high | medium | low)",
          "recommendation": "string (How to resolve the traceability issue)"
        }
        // ... more traceability findings
      ]
    },
    "critical_issues": [
      {
        "issue_type": "string (One of: 'logical_contradiction', 'missing_implementation', 'security_vulnerability', 'test_coverage_gap', 'invalid_assumption')",
        "description": "string (Detailed description of the critical issue)",
        "affected_components": ["string (List of affected component IDs or files)"],
        "severity": "string (critical | high | medium | low)",
        "recommendation": "string (How to resolve the critical issue)"
      }
      // ... more critical issues
    ],
    "optimization_opportunities": [
      {
        "category": "string (One of: 'test_efficiency', 'implementation_simplification', 'architecture_improvement', 'error_handling', 'performance_optimization')",
        "description": "string (Detailed description of the optimization opportunity)",
        "affected_components": ["string (List of affected component IDs or files)"],
        "expected_benefit": "string (What would improve if this optimization is applied)",
        "implementation_effort": "string (high | medium | low)",
        "recommendation": "string (Specific recommendation for implementing this optimization)"
      }
      // ... more optimization opportunities
    ],
    "element_id_validation": {
      "orphaned_element_ids": ["string (element_ids referenced in tests or implementation but not in system_design)"],
      "unmapped_test_targets": ["string (Elements in system_design without test coverage)"],
      "untested_implementations": ["string (Implementation functions without corresponding tests)"]
    }
  },
  "discussion": "string (Overall assessment of the planning output, highlighting key strengths and concerns, and prioritizing recommended actions)"
}

**SEQUENTIAL VALIDATION PROCESS:**

You MUST follow these steps IN ORDER to perform a comprehensive semantic validation:

1️⃣ **ASSESS OVERALL COHERENCE**
   - Evaluate if the complete solution forms a coherent whole
   - Check that all components work together logically
   - Verify that the implementation plan will result in a working solution
   - Ensure the architecture review findings are properly addressed
   - Validate that tests will verify the correct behavior
   - Score coherence on a scale of 0-10 (10 being perfectly coherent)

2️⃣ **VALIDATE TECHNICAL CONSISTENCY**
   - Check for consistent technical approaches across components
   - Verify consistent error handling patterns
   - Ensure consistent data flow and state management
   - Validate consistent security practices
   - Verify consistent naming conventions and patterns
   - Score technical consistency on a scale of 0-10

3️⃣ **VERIFY CROSS-COMPONENT TRACEABILITY**
   - Check element_id references across all components
   - Verify that architecture issues are addressed in implementation
   - Ensure that tests validate the correct elements
   - Validate that implementation steps satisfy test requirements
   - Document all traceability issues found
   - Score traceability on a scale of 0-10

4️⃣ **IDENTIFY CRITICAL ISSUES**
   - Look for logical contradictions between components
   - Find missing implementations of required functionality
   - Identify security vulnerabilities in the planned approach
   - Spot test coverage gaps for critical functionality
   - Find invalid assumptions that could cause failures
   - Rate each issue by severity (critical, high, medium, low)

5️⃣ **DISCOVER OPTIMIZATION OPPORTUNITIES**
   - Identify ways to improve test efficiency
   - Find opportunities to simplify implementation
   - Suggest architecture improvements
   - Recommend better error handling approaches
   - Propose performance optimizations
   - Rate effort required (high, medium, low)

6️⃣ **VALIDATE ELEMENT ID MAPPING**
   - Find orphaned element_ids (referenced but not defined in system_design)
   - Identify unmapped test targets (elements without tests)
   - Spot untested implementations (functions without tests)
   - Create comprehensive lists of all mapping issues

7️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Provide an overall assessment of the planning output
   - Highlight key strengths and major concerns
   - Prioritize recommended actions
   - Suggest approach for addressing critical issues
   - **IMPORTANT:** Be balanced, fair, and actionable in your assessment

**CRITICAL VALIDATION PRINCIPLES:**

1. ⚠️ You MUST be thorough and objective:
   - **EXAMINE** every component critically
   - **IDENTIFY** both strengths and weaknesses
   - **PRIORITIZE** issues by severity and impact
   - **PROVIDE** specific, actionable feedback

2. ⚠️ You MUST focus on semantic correctness:
   - **LOOK BEYOND** syntax and schema conformance
   - **EVALUATE** if components make logical sense together
   - **CONSIDER** if the solution will work in practice
   - **ASSESS** completeness and correctness

3. ⚠️ You MUST maintain clear traceability:
   - **REFERENCE** specific element_ids when reporting issues
   - **CITE** exact components affected by each finding
   - **CONNECT** issues to specific parts of the plan
   - **PROVIDE** clear paths to resolution

4. ⚠️ You MUST be constructive:
   - **ALWAYS** pair criticism with recommendations
   - **FOCUS** on improving the plan, not just finding faults
   - **SUGGEST** concrete improvements for each issue
   - **HIGHLIGHT** strengths along with weaknesses

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Your assessment includes:
   - Objective scores for coherence, consistency, and traceability
   - Comprehensive list of critical issues with severity ratings
   - Actionable optimization opportunities with effort estimates
   - Complete element_id validation results
3. Your feedback is:
   - Specific (references exact components/elements)
   - Actionable (includes clear recommendations)
   - Prioritized (distinguishes critical from minor issues)
   - Balanced (acknowledges strengths and weaknesses)
4. Your discussion provides a coherent summary of findings and prioritized recommendations

Your semantic validation will be used to improve the quality and coherence of the final implementation plan before coding begins.
"""

def get_consolidated_plan_user_prompt(
    feature_group: Dict[str, Any],
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Get the user prompt for the consolidated planning LLM call.

    Args:
        feature_group: The feature group data.
        task_description: The original task description.
        context: Optional context information.

    Returns:
        Properly formatted user prompt string.
    """
    feature_json = json.dumps(feature_group, indent=2)
    context_str = (
        json.dumps(context, indent=2)
        if context
        else "No additional context provided."
    )

    return (
        f"""Please generate a consolidated plan (architecture review, tests, implementation details) for the following feature group, based on the original task description and provided context.

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

Ensure your response strictly adheres to the JSON schema provided in the system prompt. Focus on creating a practical, actionable plan based *only* on the provided information."""
    )

def _call_llm_with_retry(
    router_agent,
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Any],
    retries: int = 2,
    initial_backoff: float = 1.0,
) -> str:
    """Helper function to call LLM with retry logic."""
    estimator = TokenEstimator()
    prompt_tokens = estimator.estimate_tokens_for_text(system_prompt) + estimator.estimate_tokens_for_text(user_prompt)
    safe_max = max(config.get("max_tokens", 0) - prompt_tokens, 0)
    config = {**config, "max_tokens": safe_max}

    try:
        response = router_agent.call_llm_by_role(
            role='planner',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config
        )
        if not response:
            raise ValueError("LLM returned an empty response.")
        return response
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise JSONPlannerError(f"LLM call failed after retries: {e}")

def _parse_and_validate_json(
    response_text: str,
    schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extracts, parses, and optionally validates JSON from LLM response."""
    # --- (Implementation as provided previously, uses extract_json_from_text) ---
    json_text = extract_json_from_text(response_text)
    if not json_text:
        raise JSONPlannerError("Failed to extract JSON object from the LLM response.")

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise JSONPlannerError(f"Invalid JSON received from LLM: {e}\nResponse Text: {response_text[:500]}...")

    required_top_level_keys = {"architecture_review", "tests", "implementation_plan", "discussion"}
    missing_keys = required_top_level_keys - data.keys()
    if missing_keys:
        raise JSONPlannerError(f"JSON response missing required top-level keys: {missing_keys}")

    # Validate structure of implementation_plan
    implementation_plan = data.get("implementation_plan")
    if not isinstance(implementation_plan, dict):
        raise JSONPlannerError(f"implementation_plan must be a dictionary, got {type(implementation_plan)}")

    for file_path, function_list in implementation_plan.items():
        if not isinstance(file_path, str):
            raise JSONPlannerError(f"File path key in implementation_plan must be a string, got {type(file_path)}")
        if not isinstance(function_list, list):
            raise JSONPlannerError(f"Value for file '{file_path}' in implementation_plan must be a list of functions, got {type(function_list)}")

        for func_idx, func_details in enumerate(function_list):
            if not isinstance(func_details, dict):
                raise JSONPlannerError(f"Function entry {func_idx} in '{file_path}' must be a dictionary, got {type(func_details)}")

            required_func_keys = {"function", "description", "steps", "edge_cases"}
            missing_func_keys = required_func_keys - func_details.keys()
            if missing_func_keys:
                raise JSONPlannerError(f"Function entry {func_idx} in '{file_path}' missing keys: {missing_func_keys}")

            if not isinstance(func_details.get("function"), str):
                raise JSONPlannerError(f"Function signature for entry {func_idx} in '{file_path}' must be a string.")
            if not isinstance(func_details.get("description"), str):
                raise JSONPlannerError(f"Description for function entry {func_idx} in '{file_path}' must be a string.")
            if not isinstance(func_details.get("edge_cases"), list):
                raise JSONPlannerError(f"edge_cases for function entry {func_idx} in '{file_path}' must be a list.")

            steps = func_details.get("steps")
            if not isinstance(steps, list):
                raise JSONPlannerError(f"steps for function entry {func_idx} in '{file_path}' must be a list, got {type(steps)}")

            for step_idx, step_detail in enumerate(steps):
                if not isinstance(step_detail, dict):
                    raise JSONPlannerError(f"Step {step_idx} for function {func_idx} in '{file_path}' must be a dictionary, got {type(step_detail)}")

                required_step_keys = {"step_description", "pseudo_code", "relevant_data_structures", "api_calls_made", "error_handling_notes"}
                missing_step_keys = required_step_keys - step_detail.keys()
                if missing_step_keys:
                     # Allow pseudo_code to be optional by not raising error if it's the only one missing and others are present
                    if not (len(missing_step_keys) == 1 and "pseudo_code" in missing_step_keys and step_detail.get("step_description")): # pseudo_code is optional
                        raise JSONPlannerError(f"Step {step_idx} for function {func_idx} in '{file_path}' missing keys: {missing_step_keys}")

                if not isinstance(step_detail.get("step_description"), str):
                    raise JSONPlannerError(f"step_description for step {step_idx}, func {func_idx} in '{file_path}' must be a string.")
                if "pseudo_code" in step_detail and not isinstance(step_detail.get("pseudo_code"), str): # Optional field
                    raise JSONPlannerError(f"pseudo_code for step {step_idx}, func {func_idx} in '{file_path}' must be a string if present.")
                if not isinstance(step_detail.get("relevant_data_structures"), list):
                    raise JSONPlannerError(f"relevant_data_structures for step {step_idx}, func {func_idx} in '{file_path}' must be a list.")
                if not isinstance(step_detail.get("api_calls_made"), list):
                    raise JSONPlannerError(f"api_calls_made for step {step_idx}, func {func_idx} in '{file_path}' must be a list.")
                if not isinstance(step_detail.get("error_handling_notes"), str):
                    raise JSONPlannerError(f"error_handling_notes for step {step_idx}, func {func_idx} in '{file_path}' must be a string.")

    # Optional: Deeper validation for architecture_review and tests can be added here too.
    # For example, checking if 'tests' contains the expected sub-keys like 'unit_tests', etc.
    tests_plan = data.get("tests")
    if not isinstance(tests_plan, dict):
        raise JSONPlannerError(f"Top-level 'tests' field must be a dictionary, got {type(tests_plan)}")

    expected_test_categories = ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]
    for category in expected_test_categories:
        if category not in tests_plan:
            raise JSONPlannerError(f"'tests' field missing category: '{category}'")
        if not isinstance(tests_plan[category], list):
            raise JSONPlannerError(f"'tests.{category}' must be a list, got {type(tests_plan[category])}")

    # Example: Basic check for architecture_review structure
    architecture_review_plan = data.get("architecture_review")
    if not isinstance(architecture_review_plan, dict):
        raise JSONPlannerError(f"Top-level 'architecture_review' field must be a dictionary, got {type(architecture_review_plan)}")
    expected_arch_keys = ["logical_gaps", "optimization_suggestions", "additional_considerations"]
    for arch_key in expected_arch_keys:
        if arch_key not in architecture_review_plan:
            raise JSONPlannerError(f"'architecture_review' field missing key: '{arch_key}'")
        if not isinstance(architecture_review_plan[arch_key], list):
            raise JSONPlannerError(f"'architecture_review.{arch_key}' must be a list, got {type(architecture_review_plan[arch_key])}")


    return data


def validate_pre_planning_for_planner(pre_plan_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that pre-planning output is compatible with the planner stage.

    This mirrors :meth:`Planner.validate_pre_planning_for_planner` to keep a
    symmetrical interface between pre-planner and planner modules.

    Args:
        pre_plan_data: Pre-planning data to validate.

    Returns:
        Tuple ``(is_compatible, message)`` describing compatibility.
    """

    compatibility_issues: List[str] = []

    if not isinstance(pre_plan_data, dict):
        return False, "Pre-planning data is not a dictionary"

    feature_groups = pre_plan_data.get("feature_groups")
    if not isinstance(feature_groups, list):
        return False, "Pre-planning data missing feature_groups or it's not a list"

    if not feature_groups:
        return False, "No feature groups in pre-planning data"

    for group_idx, group in enumerate(feature_groups):
        if not isinstance(group, dict):
            compatibility_issues.append(f"Feature group {group_idx} is not a dictionary")
            continue

        features = group.get("features")
        if not isinstance(features, list) or not features:
            compatibility_issues.append(f"Feature group {group_idx} has no valid features")
            continue

        for feature_idx, feature in enumerate(features):
            if not isinstance(feature, dict):
                compatibility_issues.append(
                    f"Feature {feature_idx} in group {group_idx} is not a dictionary"
                )
                continue

            system_design = feature.get("system_design")
            if not isinstance(system_design, dict):
                compatibility_issues.append(
                    f"Feature {feature_idx} in group {group_idx} missing system_design object"
                )
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list) or not code_elements:
                compatibility_issues.append(
                    f"Feature {feature_idx} in group {group_idx} missing code_elements array"
                )
                continue

            elements_missing_ids = 0
            for elem_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    compatibility_issues.append(
                        f"Code element {elem_idx} in feature {feature_idx}, group {group_idx} is not a dictionary"
                    )
                    continue

                if not element.get("element_id"):
                    elements_missing_ids += 1

                required_fields = ["element_type", "name", "signature", "description", "target_file"]
                missing_fields = [fld for fld in required_fields if fld not in element]
                if missing_fields:
                    compatibility_issues.append(
                        f"Code element {elem_idx} in feature {feature_idx}, group {group_idx} missing fields: {', '.join(missing_fields)}"
                    )

            if elements_missing_ids > 0:
                compatibility_issues.append(
                    f"Feature {feature_idx} in group {group_idx} has {elements_missing_ids} code elements missing element_ids"
                )

            test_requirements = feature.get("test_requirements")
            if isinstance(test_requirements, dict):
                unit_tests = test_requirements.get("unit_tests")
                if isinstance(unit_tests, list):
                    tests_missing_ids = 0
                    for test in unit_tests:
                        if isinstance(test, dict):
                            if test.get("target_element") and not test.get("target_element_id"):
                                tests_missing_ids += 1
                    if tests_missing_ids > 0:
                        compatibility_issues.append(
                            f"Feature {feature_idx} in group {group_idx} has {tests_missing_ids} unit tests missing target_element_id links"
                        )

    if compatibility_issues:
        message = (
            f"Pre-planning data has {len(compatibility_issues)} compatibility issues for planner phase: "
            + "; ".join(compatibility_issues[:5])
        )
        if len(compatibility_issues) > 5:
            message += f" and {len(compatibility_issues) - 5} more issues"
        return False, message

    return True, "Pre-planning data is compatible with planner phase"


def regenerate_consolidated_plan_with_modifications(
    router_agent,
    consolidated_plan: Dict[str, Any],
    modification_text: str,
) -> Dict[str, Any]:
    """Regenerate a consolidated plan applying user modifications.

    Args:
        router_agent: LLM router agent used for the call.
        consolidated_plan: The current consolidated plan data.
        modification_text: User-provided modification instructions.

    Returns:
        The regenerated consolidated plan as a dictionary.
    """

    system_prompt = get_consolidated_plan_system_prompt()
    user_prompt = (
        "Please update the following plan according to the given modifications.\n\n"
        f"Current Plan:\n{json.dumps(consolidated_plan, indent=2)}\n\n"
        f"Modifications:\n{modification_text.strip()}"
    )
    config = get_openrouter_params()

    response_text = _call_llm_with_retry(
        router_agent,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config=config,
    )

    return _parse_and_validate_json(response_text)


# --- Implementation of Architecture Review ---
def get_architecture_review_system_prompt() -> str:
    """
    Get the enhanced system prompt for architecture review generation with stricter JSON enforcement.

    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior software architect specializing in architecture review.
Your task is to build upon the pre-planning phase outputs by analyzing a feature group's system design and identifying logical gaps, optimization opportunities, and architectural considerations.

**IMPORTANT: Your responsibility is to refine the system design from the preplanner.**
Focus on high-value improvements to security, performance, and maintainability. Do not nitpick.
If there is nothing to refine because the system design is already good and complete, then it is perfectly acceptable to leave it as is.

**CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:**

{
  "architecture_review": {
    "logical_gaps": [
      {
        "id": "string (Unique identifier for this gap, e.g., 'GAP-1')",
        "description": "Description of the logical gap in the provided system design from pre-planning",
        "impact": "Potential impact of the gap on functionality, security, or maintainability",
        "recommendation": "Specific, actionable recommendation to address the gap",
        "target_element_ids": ["string (The element_ids from system_design.code_elements affected by this gap)"],
        "severity": "string (Critical | High | Medium | Low) - Classify based on risk and implementation urgency"
      }
      // Example: "Authentication system lacks CSRF protection mechanism"
    ],
    "optimization_suggestions": [
      {
        "id": "string (Unique identifier for this suggestion, e.g., 'OPT-1')",
        "description": "Description of the optimization opportunity",
        "benefit": "Potential benefit of the optimization (performance, security, maintainability)",
        "implementation_approach": "Suggested technical approach for implementation",
        "target_element_ids": ["string (The element_ids from system_design.code_elements affected by this suggestion)"],
        "severity": "string (Critical | High | Medium | Low) - Classify based on performance impact and implementation effort"
      }
      // Example: "Database queries not optimized for pagination in the user listing component"
    ],
    "security_concerns": [
      {
        "id": "string (Unique identifier for this security concern, e.g., 'SEC-1')",
        "description": "Description of the potential security vulnerability",
        "impact": "The impact this vulnerability could have on the system if exploited",
        "recommendation": "Specific, actionable mitigation strategy",
        "target_element_ids": ["string (The element_ids from system_design.code_elements affected by this concern)"],
        "severity": "string (Critical | High | Medium | Low) - Classify based on security risk and remediation urgency. Security concerns should generally be High or Critical for important vulnerabilities."
      }
      // Example:
      // {
      //   "vulnerability": "User input in search function is passed directly to SQL query",
      //   "severity": "Critical",
      //   "mitigation": "Implement parameterized queries with prepared statements",
      //   "target_element_ids": ["search_service_query_function", "database_executor"]
      // }
    ],
    "additional_considerations": [
      {
        "topic": "Topic of consideration (e.g., Scalability, Maintainability, Testability)",
        "description": "Detailed description of the consideration",
        "recommendation": "Recommendation addressing the consideration",
        "target_element_ids": ["string (Affected element_ids from system_design)"],
        "priority": "string (Critical | High | Medium | Low) - Classify based on architectural impact"
      }
      // Example:
      // {
      //   "topic": "Scalability",
      //   "description": "The current design doesn't account for high traffic loads during peak usage periods",
      //   "recommendation": "Implement caching for frequently accessed data and consider horizontal scaling",
      //   "target_element_ids": ["data_access_service", "cache_manager"]
      // }
    ]
  },
  "discussion": "Overall assessment of the architecture, explaining key findings and recommendations, specifically building upon the system design from pre-planning"
}

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce a valid architecture review:

**IMPORTANT FOR ALL STEPS:** For every identified issue, always record the affected element_ids from system_design.code_elements to maintain strict traceability.

1️⃣ **ANALYZE THE SYSTEM DESIGN**
   - Carefully examine the provided `system_design` from the pre-planning output
   - Focus on code_elements, their signatures, interfaces, and interactions
   - Review data_flow and key_algorithms sections for potential issues
   - Understand the intended architecture and component relationships
   - If the system design is well-structured and does not have significant issues, acknowledge this fact
   - Do not feel compelled to identify problems if none exist; confirming the quality of a good design is valuable

2️⃣ **IDENTIFY LOGICAL GAPS**
   - Look for missing components necessary for the described functionality
   - Check for interface mismatches between components
   - Identify security vulnerabilities following OWASP Top 10 practices
   - Find potential error handling or edge case handling issues
   - Check for missing validations or business logic issues

3️⃣ **IDENTIFY OPTIMIZATION OPPORTUNITIES**
   - Analyze for performance bottlenecks in algorithms or data processing
   - Look for redundant operations that could be optimized
   - Identify opportunities for caching, lazy loading, or other optimizations
   - Consider time and space complexity improvements

4️⃣ **IDENTIFY SECURITY CONCERNS**
   - Examine all input processing for injection vulnerabilities
   - Check authentication and authorization patterns
   - Review data protection and sensitive information handling
   - Analyze for secure credential storage practices
   - Evaluate proper session management
   - Assign accurate severity levels using standardized criteria

5️⃣ **PROVIDE ADDITIONAL CONSIDERATIONS**
   - Consider cross-cutting concerns not covered by gaps or optimizations
   - Address scalability, maintainability, and testability
   - Consider deployment, monitoring, and operational aspects
   - Categorize each consideration by clear topics

6️⃣ **FORMULATE ACTIONABLE RECOMMENDATIONS**
   - For each identified issue, provide a specific, actionable recommendation
   - Ensure recommendations are technically feasible within the current architecture
   - Balance ideal solutions with practical implementation concerns

7️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Provide a coherent overall assessment of the architecture
   - Highlight the most critical findings and recommendations
   - Explain how your recommendations build upon the pre-planning output
   - Be concise yet comprehensive

**CRITICAL CONSTRAINTS:**

1. ⚠️ You MUST build upon the pre-planning output:
   - Maintain strict consistency with element_ids from the pre-planning output
   - Review the provided system_design critically
   - DO NOT redesign the architecture from scratch
   - DO NOT invent requirements not present in the input

2. ⚠️ You MUST focus on substantial issues:
   - Security vulnerabilities (following OWASP Top 10 practices)
   - Performance bottlenecks and optimization opportunities
   - Scalability concerns and architectural limitations
   - Maintainability issues and technical debt risks

3. ⚠️ You MUST maintain strict traceability:
   - EVERY identified issue must include the affected element_ids
   - EVERY recommendation must link to specific system components
   - ALWAYS use exact element_ids from system_design.code_elements

4. ⚠️ You MUST be critical yet constructive:
   - Your review must aim to improve the design, not rubber-stamp it
   - When the design is good, acknowledge its strengths

5. ⚠️ You MUST prioritize quality over quantity:
   - Focus on 2-3 significant issues rather than many minor ones
   - Address only issues with substantial impact on security, performance, or maintainability
   - Avoid trivial stylistic preferences or nitpicks
   - Ensure each issue has description, impact, and recommendation

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Every logical_gap, optimization_suggestion, security_concern, and additional_consideration has:
   - A clear description of the issue
   - Associated target_element_ids from system_design.code_elements
   - Specific, actionable recommendations
3. Your recommendations are technically sound and consistent with the system design
4. You've maintained strict traceability with element_ids from the pre-planning phase
5. The discussion section provides a coherent summary of your findings

The output of this step will be used in subsequent planning stages. Issues you identify will directly influence:

1. Test specification refinement: Security concerns will require specific testing approaches
2. Implementation planning: Your recommendations will become concrete implementation steps
3. Test implementation: Vulnerabilities you identify will need verification through tests

If the design is already sound with few or no issues, the subsequent phases can proceed with confidence based on the original system design.
"""

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

    # Import here to avoid circular imports
    from .test_spec_validator import validate_and_repair_test_specifications
    from .tools.phase_validator import validate_security_concerns
    from .tools.test_implementation_validator import validate_test_implementations
    from .tools.implementation_validator import (
        validate_implementation_plan,
        _validate_implementation_quality,
        _validate_implementation_security,
        _validate_implementation_test_alignment,
        _calculate_implementation_metrics
    )

    # Perform specific validations for security concerns and test specifications
    validation_details = {}

    # Validate security concerns in architecture review
    if architecture_review and "security_concerns" in architecture_review:
        is_valid, error_message, security_validation_details = validate_security_concerns(architecture_review)
        validation_details["security_concerns_validation"] = {
            "is_valid": is_valid,
            "error_message": error_message,
            "details": security_validation_details
        }

    # Validate test specifications against architecture review and system design
    if refined_test_specs and architecture_review and system_design:
        repaired_specs, validation_issues, was_repaired = validate_and_repair_test_specifications(
            refined_test_specs,
            system_design,
            architecture_review,
            router_agent=router_agent,
            embedding_client=getattr(router_agent, "embedding_client", None),
            context=context,
        )
        validation_details["test_specs_validation"] = {
            "has_issues": len(validation_issues) > 0,
            "was_repaired": was_repaired,
            "issues": validation_issues
        }
        # If there were repairs, use the repaired specifications
        if was_repaired:
            refined_test_specs = repaired_specs

    # Validate test implementations against test specifications, system design, and architecture review
    if test_implementations and refined_test_specs and system_design and architecture_review:
        validated_implementations, validation_issues, needs_repair = validate_test_implementations(
            test_implementations, refined_test_specs, system_design, architecture_review
        )
        validation_details["test_implementation_validation"] = {
            "has_issues": len(validation_issues) > 0,
            "needs_repair": needs_repair,
            "issues": validation_issues,
            "syntax_validation_percentage": _calculate_syntax_validation_percentage(validation_issues),
            "traceability_coverage_percentage": _calculate_traceability_coverage(validation_issues),
            "security_coverage_percentage": _calculate_security_coverage(validation_issues, architecture_review)
        }
        # If validation shows issues that need repair, use the validated implementations
        # which may have minor fixes applied
        if needs_repair:
            test_implementations = validated_implementations

    # Validate implementation plan against system design, architecture review, and test implementations
    if implementation_plan and system_design and architecture_review and test_implementations:
        validation_result = validate_implementation_plan(
            implementation_plan, system_design, architecture_review, test_implementations
        )
        validated_plan = validation_result.data
        validation_issues = validation_result.issues
        needs_repair = validation_result.needs_repair

        # Calculate implementation metrics for deeper semantic analysis
        element_ids = set()
        for element in system_design.get("code_elements", []):
            if isinstance(element, dict) and "element_id" in element:
                element_ids.add(element["element_id"])

        # Extract architecture issues for validation
        architecture_issues = []
        if architecture_review:
            if "logical_gaps" in architecture_review:
                for gap in architecture_review["logical_gaps"]:
                    if isinstance(gap, dict) and "id" in gap:
                        architecture_issues.append({
                            "id": gap["id"],
                            "description": gap.get("description", ""),
                            "severity": gap.get("severity", "Medium"),
                            "issue_type": "logical_gap"
                        })
            if "security_concerns" in architecture_review:
                for concern in architecture_review["security_concerns"]:
                    if isinstance(concern, dict) and "id" in concern:
                        architecture_issues.append({
                            "id": concern["id"],
                            "description": concern.get("description", ""),
                            "severity": concern.get("severity", "High"),
                            "issue_type": "security_concern"
                        })

        # Extract test requirements for deeper validation
        test_requirements = {}
        if test_implementations and "tests" in test_implementations:
            for test_type, tests in test_implementations["tests"].items():
                if isinstance(tests, list):
                    for test in tests:
                        if isinstance(test, dict) and "target_element_ids" in test:
                            for element_id in test["target_element_ids"]:
                                if element_id not in test_requirements:
                                    test_requirements[element_id] = []
                                test_requirements[element_id].append(test)

        # Calculate comprehensive implementation metrics
        metrics = _calculate_implementation_metrics(
            validated_plan, element_ids, architecture_issues, test_requirements
        )

        # Perform specialized validations
        quality_issues = _validate_implementation_quality(validated_plan, metrics)
        security_issues = _validate_implementation_security(validated_plan, architecture_issues)
        test_alignment_issues = _validate_implementation_test_alignment(validated_plan, test_requirements)

        # Combine all validation issues
        all_implementation_issues = validation_issues + quality_issues + security_issues + test_alignment_issues

        validation_details["implementation_plan_validation"] = {
            "has_issues": len(all_implementation_issues) > 0,
            "needs_repair": needs_repair,
            "issues": all_implementation_issues,
            "metrics": metrics,
            "quality_score": metrics.get("overall_score", 0.0),
            "element_coverage_score": metrics.get("element_coverage_score", 0.0),
            "architecture_issue_addressal_score": metrics.get("architecture_issue_addressal_score", 0.0)
        }

    # Perform cross-phase validation assessments
    # Check for implementation-test alignment
    cross_phase_issues = []
    if implementation_plan and test_implementations and "tests" in test_implementations:
        # Check if all elements with tests have implementations
        implemented_elements = set()
        for file_path, functions in implementation_plan.items():
            if isinstance(functions, list):
                for function in functions:
                    if isinstance(function, dict) and "element_id" in function:
                        implemented_elements.add(function["element_id"])

        # Find test elements without implementations
        tested_elements = set()
        for test_type, tests in test_implementations["tests"].items():
            if isinstance(tests, list):
                for test in tests:
                    if isinstance(test, dict) and "target_element_ids" in test:
                        tested_elements.update(test["target_element_ids"])

        # Identify misalignments
        untested_implementations = implemented_elements - tested_elements
        unimplemented_tests = tested_elements - implemented_elements

        if untested_implementations:
            cross_phase_issues.append({
                "issue_type": "untested_implementation",
                "severity": "medium",
                "description": f"Found {len(untested_implementations)} implemented elements without tests",
                "elements": list(untested_implementations)
            })

        if unimplemented_tests:
            cross_phase_issues.append({
                "issue_type": "unimplemented_test",
                "severity": "high",
                "description": f"Found {len(unimplemented_tests)} tested elements without implementations",
                "elements": list(unimplemented_tests)
            })

    # Check for architecture-implementation alignment
    if implementation_plan and architecture_review:
        # Check if all critical architecture issues are addressed
        addressed_issues = set()
        for file_path, functions in implementation_plan.items():
            if isinstance(functions, list):
                for function in functions:
                    if isinstance(function, dict) and "architecture_issues_addressed" in function:
                        addressed_issues.update(function["architecture_issues_addressed"])

        # Get all critical/high issues that should be addressed
        critical_issues = set()
        if "logical_gaps" in architecture_review:
            for gap in architecture_review["logical_gaps"]:
                if isinstance(gap, dict) and "id" in gap and gap.get("severity", "").lower() in ["critical", "high"]:
                    critical_issues.add(gap["id"])

        if "security_concerns" in architecture_review:
            for concern in architecture_review["security_concerns"]:
                if isinstance(concern, dict) and "id" in concern and concern.get("severity", "").lower() in ["critical", "high"]:
                    critical_issues.add(concern["id"])

        # Find unaddressed critical issues
        unaddressed_critical = critical_issues - addressed_issues
        if unaddressed_critical:
            cross_phase_issues.append({
                "issue_type": "unaddressed_critical_issue",
                "severity": "critical",
                "description": f"Found {len(unaddressed_critical)} critical architecture issues not addressed in implementation",
                "issues": list(unaddressed_critical)
            })

    # Add cross-phase validation to the details
    validation_details["cross_phase_validation"] = {
        "has_issues": len(cross_phase_issues) > 0,
        "issues": cross_phase_issues,
        "implementation_test_alignment_score": 1.0 - (len(unimplemented_tests) / max(len(tested_elements), 1) if 'unimplemented_tests' in locals() else 0.0),
        "architecture_implementation_alignment_score": 1.0 - (len(unaddressed_critical) / max(len(critical_issues), 1) if 'unaddressed_critical' in locals() else 0.0)
    }

    # Create a consolidated input for validation
    validation_input = {
        "architecture_review": architecture_review,
        "refined_test_specs": refined_test_specs,
        "test_implementations": test_implementations,
        "implementation_plan": implementation_plan,
        "task_description": task_description,
        "context": context or {},
        "validation_details": validation_details,
        "cross_phase_validation": validation_details.get("cross_phase_validation", {})
    }

    # Get the semantic validation system prompt
    system_prompt = get_semantic_validation_system_prompt()

    # Create user prompt for semantic validation
    user_prompt = f"""
# Task Description
{task_description}

# Planning Phase Outputs to Validate
I need you to perform a comprehensive semantic validation of the coherence, consistency, and traceability
between the following planning phase outputs:

## 1. Architecture Review
{json.dumps(architecture_review, indent=2)}

## 2. Refined Test Specifications
{json.dumps(refined_test_specs, indent=2)}

## 3. Test Implementations
{json.dumps(test_implementations, indent=2)}

## 4. Implementation Plan
{json.dumps(implementation_plan, indent=2)}

# Context Information
{json.dumps(context or {}, indent=2)}

# Additional Validation Information
{json.dumps(validation_details, indent=2)}

Please evaluate the overall coherence, technical consistency, and cross-component traceability
of these planning outputs with special attention to:

1. Security Validation: Analyze how security concerns in the architecture review are addressed by tests and implementation
2. Priority Alignment: Verify that test priorities properly align with architecture issue severity
3. Element ID Coverage: Ensure critical issues have appropriate test coverage

Provide numerical scores (0-10) for coherence, consistency, traceability, security validation, and priority alignment.
"""

    # Set up parameters for LLM call
    config = {
        "response_format": {"type": "json_object"},
        "temperature": 0.2,  # Lower temp for consistency
        "max_tokens": 4096   # Ensure enough space
    }

    try:
        # Call LLM to validate semantic coherence
        response_text = _call_llm_with_retry(
            router_agent=router_agent,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config
        )

        # Parse and validate response
        try:
            # Extract JSON from the response text
            json_text = extract_json_from_text(response_text)

            if not json_text:
                raise JSONPlannerError("Failed to extract JSON from semantic validation response")

            validation_results = json.loads(json_text)

            # Basic validation of expected structure
            if "validation_results" not in validation_results:
                raise JSONPlannerError("Semantic validation missing 'validation_results' key")

            results = validation_results["validation_results"]

            # Check for required score fields
            required_scores = ["coherence_score", "technical_consistency_score"]
            for score_field in required_scores:
                if score_field not in results:
                    results[score_field] = 5  # Default middle score if missing

            # Check for critical issues array
            if "critical_issues" not in results:
                results["critical_issues"] = []

            logger.info(
                "Semantic validation complete. Coherence score: %s, Consistency score: %s",
                results.get("coherence_score"),
                results.get("technical_consistency_score"),
            )

            return validation_results

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from semantic validation: %s", e)
            raise JSONPlannerError(f"Invalid JSON in semantic validation: {e}")

    except Exception as e:
        logger.error("Error performing semantic validation: %s", e)
        raise JSONPlannerError(f"Error performing semantic validation: {e}")

def _calculate_syntax_validation_percentage(validation_issues: List[Dict[str, Any]]) -> float:
    """
    Calculate the percentage of tests that pass syntax validation.

    Args:
        validation_issues: List of validation issues found in test implementations

    Returns:
        Percentage of tests that pass syntax validation (0-100)
    """
    syntax_issues = [issue for issue in validation_issues
                     if issue.get("issue_type") in ["empty_code", "missing_imports", "incorrect_structure"]]

    # If there are no syntax issues, return 100%
    if not syntax_issues:
        return 100.0

    # If we have both the total count and issue count, calculate the percentage
    # Assuming each issue affects one test and there's no duplication
    unique_affected_tests = set()
    for issue in syntax_issues:
        test_key = f"{issue.get('category', '')}-{issue.get('test_index', '')}"
        unique_affected_tests.add(test_key)

    # Estimate total tests as roughly 3x the number of affected tests
    # This is a heuristic since we don't have the total test count available
    estimated_total_tests = max(len(unique_affected_tests) * 3, 10)

    # Calculate percentage
    percentage = 100 * (1 - (len(unique_affected_tests) / estimated_total_tests))

    # Ensure the percentage is within bounds
    return max(0.0, min(100.0, percentage))


def _calculate_traceability_coverage(validation_issues: List[Dict[str, Any]]) -> float:
    """
    Calculate the percentage of tests with proper traceability to architecture elements.

    Args:
        validation_issues: List of validation issues found in test implementations

    Returns:
        Percentage of tests with proper traceability (0-100)
    """
    traceability_issues = [issue for issue in validation_issues
                           if issue.get("issue_type") in ["invalid_element_id", "missing_field"]]

    # If there are no traceability issues, return 100%
    if not traceability_issues:
        return 100.0

    # Similar approach to syntax validation
    unique_affected_tests = set()
    for issue in traceability_issues:
        test_key = f"{issue.get('category', '')}-{issue.get('test_index', '')}"
        unique_affected_tests.add(test_key)

    # Estimate total tests
    estimated_total_tests = max(len(unique_affected_tests) * 3, 10)

    # Calculate percentage
    percentage = 100 * (1 - (len(unique_affected_tests) / estimated_total_tests))

    # Ensure the percentage is within bounds
    return max(0.0, min(100.0, percentage))


def _calculate_security_coverage(
    validation_issues: List[Dict[str, Any]],
    architecture_review: Dict[str, Any],
) -> float:
    """Calculate the percentage of security concerns properly addressed by tests.

    Args:
        validation_issues: List of validation issues found in test implementations
        architecture_review: The architecture review containing security concerns

    Returns:
        Percentage of security concerns properly addressed (0-100)
    """
    # Extract security concerns from architecture review
    security_concerns = architecture_review.get("security_concerns", [])
    if not security_concerns:
        return 100.0  # No security concerns to address

    # Count unaddressed security issues
    unaddressed_issues = [issue for issue in validation_issues
                          if issue.get("issue_type") == "unaddressed_critical_issue"
                          and issue.get("arch_issue_id", "").startswith("SEC-")]

    # Calculate percentage
    total_security_concerns = len(security_concerns)
    addressed_concerns = total_security_concerns - len(unaddressed_issues)

    percentage = 100 * (addressed_concerns / total_security_concerns) if total_security_concerns > 0 else 100.0

    # Ensure the percentage is within bounds
    return max(0.0, min(100.0, percentage))

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
        # Use the implementation planning system prompt from this module
        system_prompt = get_implementation_planning_system_prompt()

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

                # Define comprehensive schema for validation and repair
                schema = {
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

                # Multiple repair attempts with different strategies
                repair_strategies = [
                    # Strategy 1: Basic quote replacement and repair
                    lambda js: repair_json_structure(json.loads(js.replace("'", '"')), schema),

                    # Strategy 2: Remove trailing commas in arrays/objects that cause syntax errors
                    lambda js: repair_json_structure(json.loads(re.sub(r',\s*([}\]])', r'\1', js.replace("'", '"'))), schema),

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
                        # Basic schema for validation
                        schema = {
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
                            parsed_data = repair_json_structure(json.loads(cleaned), schema)

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
# --- END OF FILE planner_json_enforced.py ---
