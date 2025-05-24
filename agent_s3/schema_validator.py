import logging
import json
import re
from typing import Dict, List, Any, Optional, Union, TypeVar, Type, Callable
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


def get_json_system_prompt() -> str:
    """
    Get the system prompt that enforces JSON output format.

    Returns:
        Properly formatted system prompt string
    """
    return """You are given this JSON skeleton for feature groups with detailed feature definitions, test requirements, dependencies, risk assessments, and system design. Fill in the arrays with concise and accurate information based on the development request.

CRITICAL INSTRUCTION: You MUST respond in valid JSON format ONLY, conforming EXACTLY to this schema:
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
            "unit_tests": [string],
            "integration_tests": [string],
            "acceptance_tests": [
              {
                "given": string,
                "when": string,
                "then": string
              }
            ],
            "test_strategy": {
              "coverage_goal": string,
              "ui_test_approach": string
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
          "system_design": "A detailed, function-level description of the architecture, components, and interactions required to implement this feature. Include actual function stubs with proper names, parameters, return types and docstrings. This should provide a clear blueprint of the implementation, including data flow, key algorithms, and any architectural patterns or design principles applied."
        }
      ]
    }
  ]
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
- For each feature, provide a detailed, function-level description of the system architecture, including all relevant components and their interactions.
- Include proper function stubs with accurate function names, parameters, return types, and docstrings.
- The function signatures must be complete and correctly typed based on the project's language and conventions.
- Clearly describe data flow, key algorithms, and any architectural patterns or design principles used.
- Ensure the design is consistent with the overall system architecture and follows industry best practices.

Comprehensive Test Planning:
- For every function, clearly specify:
  - The test files to be created or updated
  - The structure and names of test suites
  - A list of individual test cases, including their inputs, expected outputs, and edge cases
- Ensure complete consistency between function names in the system design and test plan sections.
- Explicitly include all relevant test types required by the test_requirements object for each feature (such as unit, integration, property-based, acceptance, approval, or any custom types).
- The test plan must be organized, modular, and directly compatible with the project's testing framework and conventions, so it can be implemented without further clarification.

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

- Apply OWASP Top 10 security practices, input validation, secure credential storage, and proper session handling (for requirements and risk assessment).
- Consider performance: time complexity, resource usage, database query efficiency, and memory management (for architectural and design decisions).
- Follow code quality standards: SOLID principles, modularity, clear naming, error handling, and DRY (for feature decomposition and design).
- Ensure accessibility: WCAG 2.1 AA, semantic HTML, ARIA, keyboard navigation, and screen reader support (for requirements and acceptance criteria).
- Adhere to project-specific guidelines for architecture, tech stack, error handling, UI/UX, testing, and development workflow.
- For test planning, include all relevant test types (unit, integration, property-based, acceptance, approval), and ensure test coverage for public and authenticated functionality.
- Consider maintainability, backwards compatibility, and progressive enhancement in your decomposition and design.
- Document requirements, assumptions, and architectural decisions clearly.
- When specifying dependencies, use secure, modular, and maintainable patterns.
- For risk assessment, include security, performance, and maintainability concerns.

Only use information from the user request, provided instructions, and system messages. Do not add, assume, or hallucinate features, requirements, or behaviors not explicitly specified.
""""""Schema validation module for LLM responses.

This module defines Pydantic models for validating LLM responses and provides
utility functions for robust parsing and validation of LLM responses.
"""
logger = logging.getLogger(__name__)

# Type variable for generic type hints
T = TypeVar('T', bound=BaseModel)


# Plan schema models
class TestCase(BaseModel):
    """Schema for a single test case in the test specification."""
    description: str = Field(..., description="Description of the test case")
    inputs: Dict[str, Any] = Field(..., description="Test inputs")
    expected_output: Optional[Any] = Field(None, description="Expected output value")
    expected_exception: Optional[str] = Field(None, description="Expected exception if any")
    assertions: List[str] = Field(..., description="List of assertions for the test case")


class TestScenario(BaseModel):
    """Schema for a test scenario in the test specification."""
    function: str = Field(..., description="Name of the function/method being tested")
    cases: List[TestCase] = Field(..., description="List of test cases for this function")


class SecurityTest(BaseModel):
    """Schema for a security test in the test specification."""
    description: str = Field(..., description="Description of the security test")
    inputs: Optional[Dict[str, Any]] = Field(None, description="Test inputs")
    expected_behavior: Optional[str] = Field(None, description="Expected behavior description")
    expected_output: Optional[Any] = Field(None, description="Expected output value")
    assertions: Optional[List[str]] = Field(None, description="List of assertions for the test case")


class PropertyTest(BaseModel):
    """Schema for a property-based test in the test specification."""
    description: str = Field(..., description="Description of the property being tested")
    generators: Dict[str, str] = Field(..., description="Input generators for property testing")
    property_statement: str = Field(..., description="Statement of the property being tested")
    assertions: List[str] = Field(..., description="List of assertions for the property test")


class ApprovalTest(BaseModel):
    """Schema for an approval test in the test specification."""
    description: str = Field(..., description="Description of the output being approved")
    test_subject: str = Field(..., description="Function or method being tested")
    inputs: Optional[Dict[str, Any]] = Field(None, description="Test inputs")
    output_format: str = Field(..., description="Format of the expected output (text, JSON, image, etc.)")
    baseline_file: Optional[str] = Field(None, description="Path to the baseline file if applicable")


class TestSpecification(BaseModel):
    """Schema for a test specification in the plan."""
    implementation_file: str = Field(..., description="Path to the implementation file")
    test_file: str = Field(..., description="Path to the test file")
    framework: str = Field(..., description="Testing framework to use")
    test_types: List[str] = Field(default=["unit"], description="Types of tests included (unit, integration, approval, property)")
    scenarios: List[TestScenario] = Field(..., description="List of test scenarios")
    security_tests: Optional[List[SecurityTest]] = Field(None, description="List of security-related tests")
    property_tests: Optional[List[PropertyTest]] = Field(None, description="List of property-based tests")
    approval_tests: Optional[List[ApprovalTest]] = Field(None, description="List of approval tests")
    dependencies: Optional[List[str]] = Field(None, description="List of dependencies required for testing")


class Plan(BaseModel):
    """Schema for a plan generated by the planner."""
    discussion: str = Field(..., description="Discussion about implementation approaches")
    plan: List[str] = Field(..., description="Ordered list of implementation steps")
    test_specifications: List[TestSpecification] = Field(
        ..., description="List of test specifications for implementation files"
    )
    dependencies: Optional[List[str]] = Field(None, description="List of dependencies required for implementation")
    backward_compatibility: Optional[str] = Field(None, description="Analysis of backward compatibility implications")
    performance_impact: Optional[str] = Field(None, description="Analysis of performance impact")
    security_implications: Optional[str] = Field(None, description="Analysis of security implications")


# Code generation schema models
class GeneratedCodeFile(BaseModel):
    """Schema for a generated code file."""
    filename: str = Field(..., description="Name of the file")
    content: str = Field(..., description="Content of the file")


class CodeGeneration(BaseModel):
    """Schema for code generated by the code generator."""
    files: List[GeneratedCodeFile] = Field(..., description="List of generated code files")


# Persona debate schema models
class PersonaResponse(BaseModel):
    """Schema for a persona's response in the debate."""
    perspective: str = Field(..., description="The persona's perspective")
    agreement: bool = Field(..., description="Whether the persona agrees with the current direction")


class FinalAgreement(BaseModel):
    """Schema for the final agreement from the persona debate."""
    feature_summary: str = Field(..., description="Concise summary of the feature")
    execution_plan: List[str] = Field(..., description="Step-by-step execution plan")
    validation_tests: List[str] = Field(..., description="List of validation tests")
    consistency_checks: List[str] = Field(..., description="List of consistency checks")


def validate_llm_response(response: str, model_class: Type[T], sanitize: bool = True) -> tuple[bool,
     Union[T, str]]:    """
    Validate an LLM response against a Pydantic model schema.

    Args:
        response: The raw LLM response string
        model_class: The Pydantic model class to validate against
        sanitize: Whether to sanitize the response before parsing

    Returns:
        A tuple of (success, result), where result is either the validated model instance
        or an error message string if validation failed
    """
    if sanitize:
        response = sanitize_response(response)

    # First, try to extract JSON if needed
    json_data = extract_json(response)
    if not json_data:
        return False, "Failed to extract valid JSON from LLM response"

    # Then, try to validate against the model
    try:
        if hasattr(model_class, "model_validate"):
            instance = model_class.model_validate(json_data)
        else:
            instance = model_class.parse_obj(json_data)
        return True, instance
    except ValidationError as e:
        error_message = f"Validation failed: {str(e)}"
        logger.error(error_message)
        return False, error_message
    except Exception as e:
        error_message = f"Unexpected error during validation: {type(e).__name__}: {str(e)}"
        logger.error(error_message)
        return False, error_message


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract a JSON object from text that might contain other content.

    Args:
        text: The text that might contain JSON

    Returns:
        Parsed JSON object or None if extraction failed
    """
    # Try to extract JSON from markdown code blocks first
    json_block_pattern = r'```(?:json)?\n([\s\S]*?)\n```'
    json_matches = re.findall(json_block_pattern, text)

    if json_matches:
        for json_str in json_matches:
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                continue

    # If no code blocks or they didn't contain valid JSON, try finding JSON with brackets
    try:
        # Look for {...} pattern that might be JSON
        brace_pattern = r'(\{[\s\S]*\})'
        brace_matches = re.findall(brace_pattern, text)

        for potential_json in brace_matches:
            try:
                return json.loads(potential_json)
            except json.JSONDecodeError:
                continue

        # As a last resort, try to parse the whole text as JSON
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to extract JSON from text")
        return None


def sanitize_response(text: str) -> str:
    """
    Sanitize an LLM response to remove potentially harmful content.

    Args:
        text: The raw LLM response text

    Returns:
        Sanitized text
    """
    # Remove any potential script or executable content
    if text:
        # Remove script tags that might be used for XSS
        text = re.sub(r'<script[\s\S]*?</script>', '[REMOVED_SCRIPT]', text)

        # Remove potential shell command injections
        text = re.sub(r'(?:^|\s)(rm|sudo|chmod)\s+-[rf]', '[REMOVED_COMMAND]', text)

        # Remove exec or eval expressions
        text = re.sub(r'(?:exec|eval|system)\s*\(', '[REMOVED_EXEC](', text)

    return text


def parse_with_fallback(response: str, parser_func: Callable, fallback_value: Any,
                       log_prefix: str = "") -> Any:
    """
    Parse an LLM response with a custom parser function and return a fallback value if parsing fails.

    Args:
        response: The raw LLM response text
        parser_func: The parsing function to use
        fallback_value: The fallback value to return if parsing fails
        log_prefix: Prefix for log messages

    Returns:
        Parsed value or fallback value
    """
    if not response:
        logger.warning("%s", {log_prefix} Empty response received)
        return fallback_value

    try:
        return parser_func(response)
    except Exception as e:
        logger.error("%s", {log_prefix} Error parsing response: {type(e).__name__}: {str(e)})
        logger.error("%s", {log_prefix} Response snippet: {response[:100]}...)
        return fallback_value


def extract_code_blocks(text: str) -> Dict[str, str]:
    """
    Extract code blocks from text with their filenames.

    Args:
        text: The text containing code blocks

    Returns:
        Dictionary mapping filenames to code content
    """
    # Pattern for code blocks with filename in language specifier
    pattern = r'```([^\n]+)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)

    code_files = {}
    for lang_spec, code in matches:
        # Extract filename from language specifier
        if '.' in lang_spec:
            # Assume the language specifier is or contains the filename
            filename = lang_spec.strip()
        else:
            # Check if there's a filename comment at the start of the code
            filename_match = re.match(r'^\s*#\s*([^\n]+\.[a-zA-Z0-9]+)', code)
            if filename_match:
                filename = filename_match.group(1).strip()
            else:
                # No filename found, use a generic name with the language
                filename = f"generated_code.{lang_spec}"

        code_files[filename] = sanitize_response(code)

    return code_files


class JsonValidator:
    """Ensures JSON output conforms to expected schema."""

    def __init__(self, scratchpad=None, config=None):
        """
        Initialize the JSON validator.

        Args:
            scratchpad: Optional scratchpad for logging
            config: Optional configuration dict
        """
        self.scratchpad = scratchpad
        self.config = config or {}

    def validate_plan_json(self, plan: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate that a plan conforms to the expected JSON structure.

        Args:
            plan: The plan JSON to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(plan, dict):
            return False, "Plan must be a dictionary"

        # Check for required top-level sections
        required_sections = ["functional_plan", "test_plan"]
        for section in required_sections:
            if section not in plan:
                return False, f"Missing required section: {section}"

        # Validate functional_plan section
        functional_plan = plan.get("functional_plan", {})
        if not isinstance(functional_plan, dict):
            return False, "functional_plan must be a dictionary"

        func_required_fields = ["overview", "steps", "file_changes", "functions"]
        for field in func_required_fields:
            if field not in functional_plan:
                return False, f"functional_plan missing required field: {field}"

        # Validate steps and functions are lists
        if not isinstance(functional_plan.get("steps", []), list):
            return False, "functional_plan.steps must be a list"

        if not isinstance(functional_plan.get("functions", []), list):
            return False, "functional_plan.functions must be a list"

        if not isinstance(functional_plan.get("file_changes", []), list):
            return False, "functional_plan.file_changes must be a list"

        # Validate test_plan section
        test_plan = plan.get("test_plan", {})
        if not isinstance(test_plan, dict):
            return False, "test_plan must be a dictionary"

        test_required_fields = ["test_files", "test_scenarios", "test_cases"]
        for field in test_required_fields:
            if field not in test_plan:
                return False, f"test_plan missing required field: {field}"

        # Validate test arrays are lists
        if not isinstance(test_plan.get("test_files", []), list):
            return False, "test_plan.test_files must be a list"

        if not isinstance(test_plan.get("test_scenarios", []), list):
            return False, "test_plan.test_scenarios must be a list"

        if not isinstance(test_plan.get("test_cases", []), list):
            return False, "test_plan.test_cases must be a list"

        # All validations passed
        return True, None

    def enforce_json_format(self, llm_client, response: str, retry_count: int = 3) -> Dict[str,
         Any]:        """
        Ensure response is valid JSON, retry with LLM if not.

        Args:
            llm_client: The LLM client to use for retries
            response: The response text to validate
            retry_count: Number of retries allowed

        Returns:
            Validated JSON object
        """
        # First, try to parse and validate as is
        try:
            json_data = extract_json(response)
            if json_data:
                is_valid, error_msg = self.validate_plan_json(json_data)
                if is_valid:
                    if self.scratchpad:
                        self.scratchpad.log("JsonValidator", "Response is valid JSON with correct structure")
                    return json_data
                else:
                    if self.scratchpad:
                        self.scratchpad.log("JsonValidator", f"JSON structure error: {error_msg}")
        except Exception as e:
            if self.scratchpad:
                self.scratchpad.log("JsonValidator", f"JSON parsing error: {str(e)}")

        # JSON is invalid or missing required structure, try to fix with retries
        for attempt in range(retry_count):
            try:
                if self.scratchpad:
                    self.scratchpad.log("JsonValidator", f"Retry attempt {attempt+
                        1}/{retry_count} to fix JSON format")
                # Create correction prompt
                correction_prompt = self._create_correction_prompt(response)

                # Call LLM for correction
                from agent_s3.llm_utils import cached_call_llm

                # Get config for LLM calls
                llm_config = {}
                if self.config:
                    llm_config = self.config

                # Add JSON parameters
                json_params = {
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1  # Lower temperature for more deterministic JSON generation
                }

                # Merge JSON parameters with llm_config
                for key, value in json_params.items():
                    llm_config[key] = value

                # Call LLM with retry prompt
                result = cached_call_llm(correction_prompt, llm_client, **llm_config)

                if not result.get('success'):
                    if self.scratchpad:
                        self.scratchpad.log("JsonValidator", f"LLM retry failed: {result.get('error', 'Unknown error')}")
                    continue

                corrected_response = result.get('response', '')

                # Try to parse and validate the corrected response
                json_data = extract_json(corrected_response)
                if json_data:
                    is_valid, error_msg = self.validate_plan_json(json_data)
                    if is_valid:
                        if self.scratchpad:
                            self.scratchpad.log("JsonValidator", f"Successfully corrected JSON format on attempt {attempt+
                                                                                                1}")                        return json_data
                    else:
                        if self.scratchpad:
                            self.scratchpad.log("JsonValidator", f"Corrected JSON still has structure error: {error_msg}")
                else:
                    if self.scratchpad:
                        self.scratchpad.log("JsonValidator", "Failed to extract valid JSON from corrected response")

            except Exception as e:
                if self.scratchpad:
                    self.scratchpad.log("JsonValidator", f"Error during JSON correction: {str(e)}")

        # All retries failed, create a minimal valid structure
        if self.scratchpad:
            self.scratchpad.log("JsonValidator", "All JSON correction attempts failed. Creating fallback structure.")

        return self._create_fallback_json()

    def _create_correction_prompt(self, response: str) -> str:
        """
        Create a prompt to correct JSON formatting issues.

        Args:
            response: The invalid response

        Returns:
            Correction prompt
        """
        prompt = """You are a JSON repair expert. A previous response was meant to be valid JSON with the required structure below, but it has formatting issues or is missing required fields.

Required JSON structure:
```
{
  "functional_plan": {
    "overview": "Brief overview of the implementation approach",
    "steps": [
      "Step 1: Do X",
      "Step 2: Do Y"
    ],
    "file_changes": [
      {
        "file_path": "path/to/file.py",
        "change_type": "create|modify|delete",
        "description": "What changes will be made to this file"
      }
    ],
    "functions": [
      {
        "name": "function_name",
        "description": "What this function does",
        "parameters": ["param1", "param2"],
        "return_value": "What this function returns"
      }
    ],
    "dependencies": [
      "dependency1",
      "dependency2"
    ],
    "risks": [
      "Potential risk 1",
      "Potential risk 2"
    ]
  },
  "test_plan": {
    "test_files": [
      {
        "file_path": "tests/path/to/test_file.py",
        "implementation_file": "path/to/file.py",
        "framework": "pytest"
      }
    ],
    "test_scenarios": [
      {
        "name": "Scenario name",
        "description": "What this scenario tests"
      }
    ],
    "test_cases": [
      {
        "name": "test_function_name",
        "inputs": {"param1": "value1", "param2": "value2"},
        "expected_output": "expected result",
        "assertions": ["assert result == expected"]
      }
    ],
    "mocking_strategy": "Description of how external dependencies will be mocked",
    "coverage_targets": "80% line coverage, 100% of critical paths"
  }
}
```

Please fix the JSON to match this structure, preserving as much of the original content as possible. Your output must be ONLY valid JSON with no additional text.

Original response:
```
"""

        # Truncate response if too long
        max_chars = 6000  # Reasonable token limit to leave room for output
        truncated_response = response
        if len(response) > max_chars:
            truncated_response = response[:max_chars] + "...[truncated]"

        prompt += f"{truncated_response}\n```"

        return prompt

    def _create_fallback_json(self, prompt_moderator=None) -> Dict[str, Any]:
        """
        Raise an exception instead of creating a fallback JSON structure.

        Args:
            prompt_moderator: Optional prompt moderator to notify the user

        Raises:
            ValidationError: Always raises this exception to notify of validation failure
        """
        error_message = "JSON validation failed. Unable to generate valid JSON structure. The system cannot proceed with invalid JSON structure as it would propagate errors."

        # Log the error
        logger.error(error_message)

        # Explicitly notify user if prompt_moderator is available
        if prompt_moderator is not None:
            prompt_moderator.notify_user(error_message, level="error")
        # Check if we have a scratchpad for user notification
        elif self.scratchpad and hasattr(self.scratchpad, 'notify_user'):
            self.scratchpad.notify_user(error_message, level="error")
        else:
            # Fallback to printing to console if no notification mechanism available
            print(f"\n❌ ERROR: {error_message}")

        raise ValueError(error_message)
