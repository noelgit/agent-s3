"""
Unified JSON utilities for extracting, validating, and repairing JSON structures.

This module provides consistent JSON handling functions used across the codebase,
eliminating duplication in pre_planner, planner, and other components.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Tuple, Callable

logger = logging.getLogger(__name__)


class JSONValidationError(Exception):
    """Exception raised when JSON validation fails."""

    pass


def sanitize_text(text: str) -> str:
    """Escape newlines and control characters in ``text``.

    This helper ensures strings written to logs or JSON files do not contain
    raw control characters that could break formatting or terminal output.

    Args:
        text: The text to sanitize.

    Returns:
        The sanitized text with newlines and other control characters escaped.
    """

    if not isinstance(text, str):
        text = str(text)

    # Escape backslashes first to avoid double escaping
    text = text.replace("\\", "\\\\")
    # Replace common whitespace control chars with escaped sequences
    text = text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    # Remove remaining ASCII control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON from text that might contain markdown or other formatting.

    This function attempts multiple strategies to find valid JSON content:
    1. Extract from code blocks (```json ... ```)
    2. Look for properly formed JSON objects with outer braces
    3. Try to parse the whole text as JSON if it appears to be JSON

    Args:
        text: Text that might contain JSON

    Returns:
        Extracted JSON string or None if no valid JSON found
    """
    if not text:
        return None

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
        # Try to find the most likely JSON object (often the largest one)
        potential_jsons = []
        for potential_json in matches:
            try:
                json.loads(potential_json)  # Test if valid
                potential_jsons.append(potential_json)
            except json.JSONDecodeError:
                continue
        if potential_jsons:
            return max(potential_jsons, key=len)  # Return largest valid JSON found

    # Last resort: try parsing the whole text if it looks like JSON
    if text.strip().startswith("{") and text.strip().endswith("}"):
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            pass  # Fall through if parsing whole text fails

    return None


def parse_json_from_llm_response(
    response: str,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Parse and validate JSON from an LLM response with detailed error reporting.

    Args:
        response: LLM response that may contain JSON

    Returns:
        Tuple of:
        - success: Boolean indicating if valid JSON was extracted
        - data: Parsed JSON data (empty dict if parsing failed)
        - error_message: Error message if parsing failed, None if successful
    """
    data = {}
    error_message = None

    # Try to parse the response as JSON directly
    try:
        if isinstance(response, str):
            data = json.loads(response)
        elif isinstance(response, dict):
            # Response might already be parsed JSON
            data = response
        else:
            error_message = (
                f"LLM response is not a string or dictionary. Type: {type(response)}"
            )
            logger.warning(error_message)

    except json.JSONDecodeError as e:
        error_message = f"Response is not valid JSON: {e}. Attempting extraction."
        logger.warning(error_message)

    # If direct parsing failed or wasn't possible, try extraction
    if not data and isinstance(response, str):
        json_text = extract_json_from_text(response)
        if json_text:
            try:
                data = json.loads(json_text)
                error_message = None  # Reset error if extraction and parsing succeeded
            except json.JSONDecodeError as e:
                error_message = f"Extracted text is not valid JSON: {e}"
                logger.warning(error_message)
                data = {}  # Ensure data is empty dict if parsing extracted text fails
        else:
            error_message = "Could not extract JSON object from LLM response text."
            logger.warning(error_message)

    # Return the results
    return bool(data), data, error_message


def validate_json_against_schema(
    data: Dict[str, Any], schema: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate JSON data against a schema definition.

    Args:
        data: The JSON data to validate
        schema: A schema defining required keys and value types

    Returns:
        Tuple of:
        - is_valid: Boolean indicating if the data is valid
        - errors: List of validation error messages
    """
    errors = []

    # Base case: schema is a primitive type
    if not isinstance(schema, dict):
        if schema is not None and not isinstance(data, schema):
            errors.append(f"Expected {schema.__name__}, got {type(data).__name__}")
        return not errors, errors

    # Check required fields are present and have correct types
    for key, expected_type in schema.items():
        if key not in data:
            errors.append(f"Missing required key: '{key}'")
            continue

        value = data[key]

        # Handle different schema types
        if isinstance(expected_type, dict):
            # Nested schema
            if not isinstance(value, dict):
                errors.append(
                    f"Value for '{key}' should be an object, got {type(value).__name__}"
                )
                continue

            # Recursively validate nested schema
            valid, sub_errors = validate_json_against_schema(value, expected_type)
            if not valid:
                for error in sub_errors:
                    errors.append(f"{key}.{error}")

        elif isinstance(expected_type, list) and len(expected_type) == 1:
            # Array with schema for items
            if not isinstance(value, list):
                errors.append(
                    f"Value for '{key}' should be an array, got {type(value).__name__}"
                )
                continue

            # Validate each item in the array
            item_schema = expected_type[0]
            for i, item in enumerate(value):
                if isinstance(item_schema, dict):
                    valid, sub_errors = validate_json_against_schema(item, item_schema)
                    if not valid:
                        for error in sub_errors:
                            errors.append(f"{key}[{i}].{error}")
                elif not isinstance(item, item_schema):
                    errors.append(
                        f"{key}[{i}] should be {item_schema.__name__}, got {type(item).__name__}"
                    )

        elif not isinstance(value, expected_type):
            # Simple type validation
            errors.append(
                f"Value for '{key}' should be {expected_type.__name__}, got {type(value).__name__}"
            )

    return not errors, errors


def repair_json_structure(
    data: Dict[str, Any],
    schema: Dict[str, Any],
    default_generators: Dict[str, Callable] | None = None,
) -> Dict[str, Any]:
    """Attempt to repair a JSON structure to match a schema."""

    if not default_generators:
        default_generators = {}

    def _default_for_type(typ: Any) -> Any:
        if typ is str:
            return ""
        if typ is int:
            return 0
        if typ is float:
            return 0.0
        if typ is bool:
            return False
        if typ is list:
            return []
        if typ is dict:
            return {}
        return None

    def _repair_value(value: Any, expected: Any) -> Any:
        """Recursively repair a value according to the expected schema."""
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                value = {}
            return repair_json_structure(value, expected, default_generators)
        if isinstance(expected, list):
            item_schema = expected[0] if expected else None
            if not isinstance(value, list):
                value = []
            if item_schema is None:
                return value
            return [_repair_value(item, item_schema) for item in value]
        if not isinstance(value, expected):
            return _default_for_type(expected)
        return value

    repaired: Dict[str, Any] = {}

    for key, expected_type in schema.items():
        if key not in data:
            if key in default_generators:
                repaired[key] = default_generators[key]()
            else:
                repaired[key] = _repair_value(None, expected_type)
            continue

        repaired[key] = _repair_value(data[key], expected_type)

    return repaired


def validate_and_repair_json(
    response_text: str,
    schema: Dict[str, Any],
    default_generators: Optional[Dict[str, Callable]] = None,
    original_request: Optional[str] = None,
) -> Tuple[bool, Dict[str, Any], Optional[str]]:
    """
    Combined function to extract, validate, and optionally repair JSON from an LLM response.

    Args:
        response_text: The LLM response text
        schema: Schema to validate against
        default_generators: Optional mapping of keys to functions that generate default values
        original_request: Optional original request text for context in errors

    Returns:
        Tuple of:
        - success: Whether valid JSON was obtained (either directly or after repair)
        - data: The extracted and optionally repaired JSON data
        - error_message: Error message if unsuccessful, or repair notes if successful with repairs
    """
    # Extract and parse JSON
    success, data, error_message = parse_json_from_llm_response(response_text)

    if not success:
        return False, {}, error_message

    # Validate against schema
    is_valid, validation_errors = validate_json_against_schema(data, schema)

    if is_valid:
        return True, data, None

    # Attempt repair if validation failed
    if default_generators:
        try:
            repaired_data = repair_json_structure(data, schema, default_generators)

            # Validate the repaired data
            repaired_valid, repaired_errors = validate_json_against_schema(
                repaired_data, schema
            )

            if repaired_valid:
                # Repaired successfully
                return (
                    True,
                    repaired_data,
                    f"JSON was repaired. Original issues: {', '.join(validation_errors)}",
                )
            else:
                # Repair didn't fully fix issues
                return (
                    False,
                    data,
                    f"Validation failed and repair was incomplete: {', '.join(repaired_errors)}",
                )
        except Exception as e:
            # Repair failed with exception
            return (
                False,
                data,
                f"JSON repair failed: {str(e)}. Original validation errors: {', '.join(validation_errors)}",
            )

    # No repair attempted
    return False, data, f"JSON validation failed: {', '.join(validation_errors)}"


def get_openrouter_json_params() -> Dict[str, Any]:
    """
    Get parameters for OpenRouter API to enforce JSON output.

    Returns:
        Dictionary of parameters for the API call
    """
    return {
        "response_format": {"type": "json_object"},  # Force JSON output format
        "headers": {"Accept": "application/json"},  # Request JSON MIME type
        "temperature": 0.1,  # Lower temperature for consistent formatting
        "max_tokens": 4096,  # Ensure enough space for full JSON response
        "top_p": 0.2,  # Narrow token selection for consistent formatting
    }


try:
    from agent_s3.planner.json_schema import validate_json_schema
except ImportError:

    def validate_json_schema(data: Dict[str, Any]) -> None:
        """Fallback stub when planner_json_enforced.validate_json_schema is unavailable."""
        raise ImportError(
            "validate_json_schema could not be imported from planner_json_enforced"
        )
