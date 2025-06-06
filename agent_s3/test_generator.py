"""Test Generator for decoupled test implementation.

This module provides utilities to generate comprehensive test implementations
based on test requirements and system design, separate from the consolidated planning phase.
This separation allows for more focused generation and review of test code before
proceeding to implementation planning.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
import traceback

from .pre_planner_json_enforced import get_openrouter_json_params

logger = logging.getLogger(__name__)

class TestGenerationError(Exception):
    """Exception raised when test generation encounters errors."""
    pass


def get_test_implementation_system_prompt() -> str:
    """
    Get the enhanced system prompt for test code generation with stricter JSON enforcement.

    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior test engineer specializing in writing high-quality, comprehensive test code.
Your task is to implement complete, runnable test code based on refined test specifications.

**CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:**

{
  "tests": {
    "unit_tests": [
      {
        "file": "string (path to test file, e.g., 'tests/test_user_service.py')",
        "test_name": "string (descriptive test function name, e.g., 'test_get_user_by_id_returns_correct_user')",
        "tested_functions": ["string (format: file_path::function_name)"],
        "target_element_ids": ["string (element_ids from system_design.code_elements this test validates)"],
        "description": "string (description of what this test verifies)",
        "code": "string (complete, runnable test code with proper fixtures, assertions, etc.)",
        "setup_requirements": "string (any setup needed for this test)",
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "file": "tests/services/test_auth_service.py",
      //   "test_name": "test_authenticate_fails_with_invalid_credentials",
      //   "tested_functions": ["src/services/auth_service.py::AuthService.authenticate"],
      //   "target_element_ids": ["auth_service_authenticate_function"],
      //   "description": "Verify authentication fails and returns appropriate error when invalid credentials are provided",
      //   "code": "def test_authenticate_fails_with_invalid_credentials()
          :\n    # Arrange\n    auth_service = AuthService()
          \n    username = 'nonexistent_user'\n    password = 'any_password'\n\n    # Act\n    result = auth_service.authenticate
          (username, password)
          \n\n    # Assert\n    assert result.success is False\n    assert result.error_code == 'AUTH_INVALID_CREDENTIALS'"
          ,      //   "setup_requirements": "Mock UserRepository to return None for the nonexistent user",
      //   "architecture_issue_addressed": "Security concern regarding authentication validation"
      // }
    ],
    "property_based_tests": [
      {
        "file": "string (path to property test file)",
        "test_name": "string (descriptive property test name)",
        "description": "string (description of the property being tested)",
        "target_element_ids": ["string (element_ids from system_design.code_elements this test validates)"],
        "code": "string (complete, runnable property-based test code)",
        "setup_requirements": "string (libraries and setup needed for this test)",
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "file": "tests/property/test_pricing_properties.py",
      //   "test_name": "test_final_price_always_non_negative",
      //   "description": "Test that calculated final price is always non-negative regardless of inputs",
      //   "target_element_ids": ["pricing_service_calculate_function"],
      //   "code": "from hypothesis import given, strategies as st\n\n@given(base_price=st.floats(min_value=-100, max_value=1000), discount=st.floats(min_value=0, max_value=100))\ndef test_final_price_always_non_negative(base_price, discount):\n    pricing_service = PricingService()\n    final_price = pricing_service.calculate_final_price(base_price, discount)\n    assert final_price >= 0",
      //   "setup_requirements": "Hypothesis library for property-based testing",
      //   "architecture_issue_addressed": "Optimization suggestion regarding input validation in pricing calculations"
      // }
    ],
    "acceptance_tests": [
      {
        "file": "string (path to acceptance test file)",
        "test_name": "string (descriptive acceptance test name)",
        "description": "string (description of the acceptance criterion being tested)",
        "target_element_ids": ["string (element_ids from system_design.code_elements this test validates)"],
        "code": "string (complete runnable acceptance test code)",
        "setup_requirements": "string (environment setup needed for this test)",
        "given": "string (for BDD-style tests)",
        "when": "string (for BDD-style tests)",
        "then": "string (for BDD-style tests)",
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "file": "tests/acceptance/test_user_registration.py",
      //   "test_name": "test_new_user_registration",
      //   "description": "Verify that new users can successfully register for an account",
      //   "target_element_ids": ["user_registration_controller", "user_service_create", "auth_service_login"],
      //   "code": "def test_new_user_registration():\n    # Given\n    app = create_test_app()
          \n    client = app.test_client()\n    username = f'testuser_{int(time.time())
          }'\n    \n    # When\n    response = client.post('/register',
           json={\n        'username': username,\n        'email': f'{username}@example.com',
          \n        'password': 'SecurePass123!'\n    })
          \n    \n    # Then\n    assert response.status_code == 200\n    data = response.get_json()
          \n    assert data['success'] is True\n    assert 'user_id' in data\n    \n    # Verify user is in database\n    user_service = get_user_service
          ()\n    user = user_service.get_by_username(username)
          \n    assert user is not None\n    assert user.email == f'{username}@example.com'",      //   "setup_requirements": "Flask test client, clean test database",
      //   "given": "A user is on the registration page and has not previously created an account",
      //   "when": "The user fills in valid registration information and submits the form",
      //   "then": "A new account should be created, the user should be logged in, and redirected to the dashboard",
      //   "architecture_issue_addressed": "Additional consideration for user onboarding flow"
      // }
    ]
  },
  "test_strategy_implementation": {
    "coverage_goal": "string (how the implemented tests achieve the coverage goal)",
    "ui_test_approach_implementation": "string (how UI tests are implemented if applicable)",
    "test_data_strategy": "string (approach to test data generation/management)",
    "mocking_strategy": "string (approach to mocking external dependencies)",
    "test_execution_plan": "string (description of how tests should be run, including order and environment setup)"
  },
  "discussion": "string (explanation of test implementation decisions and approach)"
}

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce valid test implementations:

1️⃣ **ANALYZE INPUTS**
   - Carefully review the refined test specifications
   - Understand the architecture review findings referenced in the test specs
   - Study the system design components being tested
   - Note all target_element_ids needing test coverage
   - Identify testing framework and patterns appropriate for the codebase

2️⃣ **PLAN TEST STRUCTURE**
   - Determine appropriate test file organization
   - Plan for test dependencies, fixtures, and utility functions
   - Consider how to implement mocking requirements
   - Decide on test data strategy (generated vs. fixed)
   - Plan for environment setup needs

3️⃣ **IMPLEMENT UNIT TESTS**
   - For each unit test in the specifications:
     * Create a descriptive test name that reflects the test's purpose
     * Write complete test function implementation including:
       - Setup (Arrange)
       - Execution (Act)
       - Verification (Assert)
     * Include necessary imports, fixtures, and mocks
     * Ensure proper error handling within tests
     * Verify all edge cases are covered
     * **IMPORTANT:** Ensure test directly validates target_element_ids

4️⃣ **IMPLEMENT ACCEPTANCE TESTS**
   - For each acceptance test in the specifications:
    * Create a descriptive test name reflecting the integration scenario
     * Write complete test implementation including:
       - Component setup and configuration
       - Interaction execution
       - Multi-component verification
     * Include necessary inter-component communication
     * Handle asynchronous behavior if needed
     * **IMPORTANT:** Ensure test validates interactions between all components_involved

5️⃣ **IMPLEMENT PROPERTY-BASED TESTS**
   - For each property-based test in the specifications:
     * Create appropriate generators for input data
     * Define property assertions clearly
     * Implement comprehensive property validation
     * Set appropriate test parameters (iterations, etc.)
     * **IMPORTANT:** Ensure properties validate fundamental invariants

6️⃣ **IMPLEMENT ACCEPTANCE TESTS**
   - For each acceptance test in the specifications:
     * Implement in given-when-then structure if appropriate
     * Include end-to-end interaction flows
     * Validate user-visible outcomes
     * Handle UI interactions if required
     * **IMPORTANT:** Ensure test validates the complete feature

7️⃣ **FINALIZE TEST STRATEGY IMPLEMENTATION**
   - Document how the implemented tests achieve coverage goals
   - Explain the approach to UI testing if applicable
   - Detail the test data strategy used
   - Describe the mocking approach for external dependencies
   - Provide a test execution plan

8️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Explain key implementation decisions
   - Discuss any challenges and how they were addressed
   - Note any assumptions made during implementation
   - **IMPORTANT:** Be concise yet comprehensive

**CRITICAL CONSTRAINTS:**

1. ⚠️ You MUST produce runnable test code:
   - **WRITE** syntactically correct code for the appropriate testing framework
   - **INCLUDE** all necessary imports, fixtures, and setup
   - **VALIDATE** all assertions check the correct behaviors
   - **AVOID** pseudo-code or incomplete implementations

2. ⚠️ You MUST maintain traceability:
   - **EVERY** test must validate the correct target_element_ids
   - **EVERY** test must include tested_functions with correct file paths and signatures
   - **EVERY** test addressing an architecture issue must reference that issue
   - **ALWAYS** use consistent naming between test code and element references

3. ⚠️ You MUST implement complete test coverage:
   - **ENSURE** all edge cases from specifications are covered
   - **INCLUDE** appropriate error handling in tests
   - **IMPLEMENT** all specified assertions
   - **INCLUDE** tests for all specified target elements

4. ⚠️ You MUST follow testing best practices:
   - **USE** arrange-act-assert pattern for clarity
   - **IMPLEMENT** proper mocking of external dependencies
   - **CREATE** isolated tests that don't depend on each other
   - **WRITE** descriptive, clear test names
   - **INCLUDE** meaningful assertion messages

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Every test implementation:
   - Has complete, runnable code (no pseudocode or stubs)
   - Correctly tests the specified behavior
   - Has proper assertions that validate expected outcomes
   - Properly references target_element_ids and tested_functions
   - Includes necessary setup and configuration
3. Your test strategy implementation details how the tests achieve coverage goals
4. You've maintained strict traceability between tests and system components
5. The discussion section explains your implementation approach clearly

Your test implementations will be used to validate the actual code implementation, so they must be accurate, complete, and ready to run with minimal adjustments.
"""


def generate_test_implementations(
    router_agent,
    refined_test_specs: Dict[str, Any],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any],
    task_description: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate concrete test implementations based on refined test specifications.

    Args:
        router_agent: The LLM router agent for making LLM calls
        refined_test_specs: The refined test specifications
        system_design: The system design data
        architecture_review: The architecture review data including security concerns
        task_description: Original task description
        context: Optional additional context

    Returns:
        Dictionary containing test implementations
    """
    logger.info("Generating test implementations from refined specifications")

    # Create the enhanced user prompt
    user_prompt = f"""Please implement complete, runnable test code based on the refined test specifications.

# Task Description
{task_description}

# Refined Test Specifications
{json.dumps(refined_test_specs, indent=2)}

# System Design
{json.dumps(system_design, indent=2)}

# Architecture Review
{json.dumps(architecture_review, indent=2)}

# Additional instructions may be provided via the context dictionary.

Your task is to implement complete, runnable test code for each test specification with special attention to:

1. Creating syntactically correct, logically sound test code that can be executed with minimal modifications
2. Including proper imports, fixtures, assertions, mocks, and error handling for each test
3. Following best practices for the appropriate testing framework (pytest, unittest, etc.)
4. Maintaining explicit traceability to target_element_ids throughout all tests
5. Ensuring comprehensive coverage of all security concerns identified in the architecture review
6. Implementing proper test isolation through effective mocking and test boundaries
7. Adding descriptive names and documentation to make test intent clear
8. Including edge case testing as specified in the refined test requirements

For security concerns in the architecture review:
- Ensure each security concern has dedicated test coverage
- Implement both positive and negative test cases for security features
- Verify input validation, authentication, and authorization work as expected
- Test for proper error handling without information leakage

Each test must include complete runnable code - not stubs or pseudocode.
"""

    # Get LLM parameters
    llm_params = get_openrouter_json_params()
    llm_params["temperature"] = 0.2  # Lower temperature for more reliable code generation

    # Call the LLM
    try:
        system_prompt = get_test_implementation_system_prompt()
        response_text = router_agent.call_llm_by_role(
            role="test_engineer",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=llm_params,
            tech_stack=context.get("tech_stack") if context else None,
            code_context=context.get("code_context") if context else None,
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
            if "tests" not in response_data:
                raise ValueError("Missing 'tests' in response")

            # Perform validation and repair
            logger.info("Validating test implementations")
            from .tools.test_implementation_validator import (
                validate_test_implementations,
                repair_test_implementations
            )

            validated_data, validation_issues, needs_repair = validate_test_implementations(
                response_data,
                refined_test_specs,
                system_design,
                architecture_review
            )

            # Log validation results
            issue_count = len(validation_issues)
            if issue_count > 0:
                logger.warning(
                    "%s",
                    "Found %d issues in test implementations",
                    issue_count,
                )
                critical_issues = sum(1 for issue in validation_issues if issue.get('severity') == 'critical')
                high_issues = sum(1 for issue in validation_issues if issue.get('severity') == 'high')
                other_issues = issue_count - critical_issues - high_issues

                logger.warning(
                    "Issues breakdown: %s critical, %s high, %s medium/low",
                    critical_issues,
                    high_issues,
                    other_issues,
                )
            else:
                logger.info("No issues found in test implementations")

            # Attempt repair if needed
            if needs_repair:
                logger.info("Attempting to repair test implementation issues")
                repaired_data = repair_test_implementations(
                    validated_data,
                    validation_issues,
                    refined_test_specs,
                    system_design,
                    architecture_review
                )
                logger.info("Test implementations repaired")
                return repaired_data

            return validated_data

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", e)
            raise TestGenerationError(f"Invalid JSON response: {e}")
        except ValueError as e:
            logger.error("Invalid response structure: %s", e)
            raise TestGenerationError(f"Invalid response structure: {e}")

    except Exception as e:
        logger.error("Error generating test implementations: %s", e)
        logger.error(traceback.format_exc())
        raise TestGenerationError(f"Error generating test implementations: {e}")
