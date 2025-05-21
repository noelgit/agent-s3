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

def get_test_specification_system_prompt() -> str:
    """
    DEPRECATED: This function is maintained for backward compatibility only.
    Use get_test_specification_refinement_system_prompt() from planner_json_enforced.py instead.
    
    This older version lacks priority ratings and structured guidance compared to the new version.
    
    Returns:
        Properly formatted system prompt string
    """
    return """You are a senior test architect and quality engineer specializing in test design and implementation. 
Your task is to refine and detail test requirements based on architecture review insights and system design.

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
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "description": "Test that user authentication fails with invalid credentials",
      //   "target_element": "AuthService.authenticate",
      //   "target_element_id": "auth_service_authenticate_function",
      //   "inputs": ["Invalid username 'nonexistent'", "Any password value"],
      //   "expected_outcome": "Should return AuthResult with success=false and error code AUTH_INVALID_CREDENTIALS",
      //   "edge_cases": ["Empty username", "Empty password", "SQL injection attempt in username"],
      //   "mocking_requirements": ["Mock UserRepository to simulate database access", "Mock TokenGenerator"],
      //   "architecture_issue_addressed": "Security concern around authentication validation"
      // }
    ],
    "integration_tests": [
      {
        "description": "Detailed description of what this integration test should verify",
        "components_involved": ["string (List of components/modules interacting)"],
        "target_element_ids": ["string (The element_ids from system_design.code_elements that this test targets)"],
        "scenario": "string (Detailed description of the integration scenario)",
        "setup_requirements": "string (Required setup for this test)",
        "assertions": ["string (Specific assertions this test should make)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "description": "Test that user login process correctly generates and stores authentication token",
      //   "components_involved": ["AuthService", "TokenGenerator", "UserRepository", "SessionManager"],
      //   "target_element_ids": ["auth_service_login_function", "token_generator_create_token", "session_manager_store"],
      //   "scenario": "User logs in with valid credentials, system generates token and stores in session",
      //   "setup_requirements": "Valid user in database, mocked TokenGenerator configured for verification",
      //   "assertions": ["Token is correctly formatted JWT", "Token contains expected user claims", "Session contains token reference"],
      //   "architecture_issue_addressed": "Logical gap in token generation and session management interaction"
      // }
    ],
    "property_based_tests": [
      {
        "description": "Detailed description of the property to test",
        "target_element": "string (The element name from system_design.code_elements)",
        "target_element_id": "string (The element_id from system_design.code_elements that this test targets)",
        "input_generators": ["string (Description of data generators)"],
        "property_assertions": ["string (Assertions about the property being tested)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "description": "Test that product price calculation is always non-negative regardless of inputs",
      //   "target_element": "PricingService.calculateFinalPrice",
      //   "target_element_id": "pricing_service_calculate_function",
      //   "input_generators": ["Random base prices between -100 and 1000", "Random discount percentages between 0 and 100"],
      //   "property_assertions": ["Final price should always be >= 0", "If no discounts apply, final price equals base price"],
      //   "architecture_issue_addressed": "Optimization suggestion regarding input validation in pricing calculations"
      // }
    ],
    "acceptance_tests": [
      {
        "description": "Detailed description of the acceptance criterion being tested",
        "given": "string (Detailed precondition)",
        "when": "string (Detailed action)",
        "then": "string (Detailed expected outcome)",
        "target_feature": "string (The feature this test validates)",
        "target_element_ids": ["string (The element_ids that implement this feature)"],
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "description": "New users should be able to register for an account",
      //   "given": "A user is on the registration page and has not previously created an account",
      //   "when": "The user fills in valid registration information and submits the form",
      //   "then": "A new account should be created, the user should be logged in, and redirected to the dashboard",
      //   "target_feature": "User Registration",
      //   "target_element_ids": ["user_registration_controller", "user_service_create", "auth_service_login"],
      //   "architecture_issue_addressed": "Additional consideration for user onboarding flow"
      // }
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
      // Example:
      // "test_strategy": {
      //   "coverage_goal": "90% line coverage for core authentication and authorization components, 75% for other modules",
      //   "ui_test_approach": "Component snapshots for all UI elements, plus Playwright E2E tests for critical user flows",
      //   "test_priorities": ["Authentication flow", "Payment processing", "Data consistency between services"],
      //   "test_risks": ["Flaky tests due to complex async operations", "Difficult setup for payment gateway testing"],
      //   "critical_paths": [
      //     {
      //       "path_description": "User authentication through SSO provider",
      //       "components": ["SSOController", "AuthService", "TokenValidator", "UserRepository"],
      //       "element_ids": ["sso_controller_authenticate", "auth_service_validate", "token_validator", "user_repo_fetch"],
      //       "test_approach": "Mock SSO provider responses and verify correct token validation and user session creation"
      //     }
      //   ]
      // }
    }
  },
  "discussion": "string (Explanation of how the architecture review influenced the test refinements, including test strategies for addressing identified issues)"
}

**SEQUENTIAL PROCESSING INSTRUCTIONS:**

You MUST follow these steps IN ORDER to produce valid test specifications:

1️⃣ **ANALYZE INPUTS**
   - Carefully review the original test requirements from the feature group data
   - Study the architecture review findings, focusing on identified issues and recommendations
   - Understand the system design, particularly code_elements and their interactions
   - Note all element_ids that will need test coverage
   - Identify issues from the architecture review that should be addressed in tests

2️⃣ **REFINE UNIT TESTS**
   - For each unit test in the original requirements:
     * Enhance the description to be more specific and actionable
     * Ensure correct target_element and target_element_id references
     * Expand inputs to cover normal and edge cases
     * Detail expected outcomes precisely
     * Add edge cases based on architecture review findings
     * Specify necessary mocking requirements 
     * Link to architecture issues being addressed, if applicable
   - Add new unit tests for any gaps identified in the architecture review

3️⃣ **REFINE INTEGRATION TESTS**
   - For each integration test in the original requirements:
     * Make the description more comprehensive
     * List all components involved in the integration
     * Ensure all relevant target_element_ids are included
     * Expand the scenario description with detailed steps
     * Detail setup requirements precisely
     * Specify explicit assertions to validate
     * Link to architecture issues being addressed, if applicable
   - Add new integration tests for component interactions highlighted in the architecture review

4️⃣ **REFINE PROPERTY-BASED TESTS**
   - For each property-based test in the original requirements:
     * Make the property description more explicit
     * Ensure correct target_element and target_element_id references
     * Define comprehensive input generators
     * Specify precise property assertions
     * Link to architecture issues being addressed, if applicable
   - Add new property-based tests for properties implied by the architecture review

5️⃣ **REFINE ACCEPTANCE TESTS**
   - For each acceptance test in the original requirements:
     * Enhance the given-when-then structure with more detail
     * Link explicitly to target features
     * Associate with implementing target_element_ids
     * Link to architecture issues being addressed, if applicable
   - Add new acceptance tests for user-facing concerns identified in the architecture review

6️⃣ **DEVELOP TEST STRATEGY**
   - Refine coverage goals based on architecture review risk assessment
   - Adapt UI test approach to address architecture review findings
   - Prioritize tests based on critical issues identified in architecture review
   - Identify testing risks highlighted by the architecture review
   - Define critical paths requiring comprehensive test coverage

7️⃣ **SUMMARIZE IN DISCUSSION SECTION**
   - Explain how the architecture review influenced your test refinements
   - Highlight test strategies for addressing critical architecture issues
   - Discuss trade-offs in the testing approach
   - **IMPORTANT:** Be concise yet comprehensive

**CRITICAL CONSTRAINTS:**

1. ⚠️ You MUST maintain traceability:
   - **EVERY** test must reference correct target_element_ids from system_design.code_elements
   - **EVERY** test addressing an architecture issue must reference that issue 
   - **ALWAYS** use the exact element_ids from the system_design.code_elements array

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

**OUTPUT VALIDATION CRITERIA:**

Before finalizing your output, verify that:
1. Your JSON is valid and follows the exact schema provided
2. Every test has:
   - A clear, detailed description
   - Correct target_element and/or target_element_id references
   - Specific inputs/conditions and expected outcomes or assertions
   - Links to architecture issues where applicable
3. Your test strategy addresses all concerns raised in the architecture review
4. You've maintained strict traceability with element_ids from the system design
5. The discussion section provides a coherent explanation of your test refinements

Your refined test specifications will be used to implement actual test code in the subsequent test implementation phase, so ensure they provide clear, actionable guidance.
"""

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
      //   "code": "def test_authenticate_fails_with_invalid_credentials():\n    # Arrange\n    auth_service = AuthService()\n    username = 'nonexistent_user'\n    password = 'any_password'\n\n    # Act\n    result = auth_service.authenticate(username, password)\n\n    # Assert\n    assert result.success is False\n    assert result.error_code == 'AUTH_INVALID_CREDENTIALS'",
      //   "setup_requirements": "Mock UserRepository to return None for the nonexistent user",
      //   "architecture_issue_addressed": "Security concern regarding authentication validation"
      // }
    ],
    "integration_tests": [
      {
        "file": "string (path to integration test file)",
        "test_name": "string (descriptive integration test name)",
        "description": "string (description of what this integration test verifies)",
        "components_involved": ["string (list of components/modules interacting)"],
        "target_element_ids": ["string (element_ids from system_design.code_elements this test validates)"],
        "code": "string (complete, runnable integration test code)",
        "setup_requirements": "string (environment setup needed for this test)",
        "architecture_issue_addressed": "string (Optional: ID or description of architecture issue this test addresses)"
      }
      // Example:
      // {
      //   "file": "tests/integration/test_auth_flow.py",
      //   "test_name": "test_login_generates_and_stores_valid_token",
      //   "description": "Test that the login process correctly generates and stores an authentication token",
      //   "components_involved": ["AuthService", "TokenGenerator", "UserRepository", "SessionManager"],
      //   "target_element_ids": ["auth_service_login_function", "token_generator_create_token", "session_manager_store"],
      //   "code": "def test_login_generates_and_stores_valid_token():\n    # Arrange\n    user = create_test_user()\n    auth_service = get_auth_service()\n    session = {}\n\n    # Act\n    login_result = auth_service.login(user.username, 'correct_password', session)\n\n    # Assert\n    assert login_result.success is True\n    assert 'token' in session\n    token = session['token']\n    decoded = jwt.decode(token, verify=False)\n    assert decoded['user_id'] == user.id\n    assert decoded['exp'] > time.time()",
      //   "setup_requirements": "Database with test user, mock TokenGenerator for verification",
      //   "architecture_issue_addressed": "Logical gap in token generation and session management interaction"
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
      //   "code": "def test_new_user_registration():\n    # Given\n    app = create_test_app()\n    client = app.test_client()\n    username = f'testuser_{int(time.time())}'\n    \n    # When\n    response = client.post('/register', json={\n        'username': username,\n        'email': f'{username}@example.com',\n        'password': 'SecurePass123!'\n    })\n    \n    # Then\n    assert response.status_code == 200\n    data = response.get_json()\n    assert data['success'] is True\n    assert 'user_id' in data\n    \n    # Verify user is in database\n    user_service = get_user_service()\n    user = user_service.get_by_username(username)\n    assert user is not None\n    assert user.email == f'{username}@example.com'",
      //   "setup_requirements": "Flask test client, clean test database",
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

4️⃣ **IMPLEMENT INTEGRATION TESTS**
   - For each integration test in the specifications:
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

# Additional Context
{json.dumps(context or {}, indent=2)}

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
                logger.warning(f"Found {issue_count} issues in test implementations")
                critical_issues = sum(1 for issue in validation_issues if issue.get('severity') == 'critical')
                high_issues = sum(1 for issue in validation_issues if issue.get('severity') == 'high')
                other_issues = issue_count - critical_issues - high_issues
                
                logger.warning(f"Issues breakdown: {critical_issues} critical, {high_issues} high, {other_issues} medium/low")
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
            logger.error(f"Failed to parse JSON response: {e}")
            raise TestGenerationError(f"Invalid JSON response: {e}")
        except ValueError as e:
            logger.error(f"Invalid response structure: {e}")
            raise TestGenerationError(f"Invalid response structure: {e}")
    
    except Exception as e:
        logger.error(f"Error generating test implementations: {e}")
        logger.error(traceback.format_exc())
        raise TestGenerationError(f"Error generating test implementations: {e}")
