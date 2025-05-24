"""Test the agent's ability to create context-aware plans.

These tests verify that the planning process properly considers:
1. Existing code style and patterns
2. Project structure and organization
3. Existing functionality to avoid duplication
4. Dependencies and requirements
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.coordinator import Coordinator
from agent_s3.planner import Planner


@pytest.fixture
def styled_project(workspace):
    """Create a project with a specific coding style for testing style adherence."""
    # Create directories
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()

    # Create a Python file with very specific style conventions
    math_utils_path = workspace / "src" / "math_utils.py"
    math_utils_content = """# math_utils.py
# Copyright (c) 2023 Example Company
#
# Math utility functions with company-standard error handling and logging

import logging
from typing import Union, Optional, List, Dict, Any, Tuple

# Configure logger
logger = logging.getLogger(__name__)

# Type aliases
Number = Union[int, float]
NumberSequence = List[Number]

# Error codes
ERROR_INVALID_INPUT = "MATH-001"
ERROR_DIVIDE_BY_ZERO = "MATH-002"
ERROR_OVERFLOW = "MATH-003"

def validate_number(value: Any) -> Number:
    \"\"\"
    Validate that a value is a number.

    Parameters:
        value: The value to validate

    Returns:
        The value, if it's a valid number

    Raises:
        TypeError: If the value is not a number
    \"\"\"
    if not isinstance(value, (int, float)):
        logger.error("%s", {ERROR_INVALID_INPUT}: Invalid number: {value})
        raise TypeError(f"{ERROR_INVALID_INPUT}: Expected a number, got {type(value).__name__}")
    return value

def add(a: Number, b: Number) -> Number:
    \"\"\"
    Add two numbers with input validation.

    Parameters:
        a: First number
        b: Second number

    Returns:
        Sum of the two numbers

    Raises:
        TypeError: If inputs are not numbers
    \"\"\"
    # Validate inputs
    a = validate_number(a)
    b = validate_number(b)

    # Perform operation and log
    result = a + b
    logger.debug("%s", Addition: {a} + {b} = {result})

    return result

def divide(numerator: Number, denominator: Number) -> Number:
    \"\"\"
    Divide numerator by denominator with validation.

    Parameters:
        numerator: The number to divide
        denominator: The number to divide by

    Returns:
        Result of the division

    Raises:
        TypeError: If inputs are not numbers
        ValueError: If denominator is zero
    \"\"\"
    # Validate inputs
    numerator = validate_number(numerator)
    denominator = validate_number(denominator)

    # Check for zero denominator
    if denominator == 0:
        logger.error("%s", {ERROR_DIVIDE_BY_ZERO}: Division by zero attempted)
        raise ValueError(f"{ERROR_DIVIDE_BY_ZERO}: Cannot divide by zero")

    # Perform operation and log
    result = numerator / denominator
    logger.debug("%s", Division: {numerator} / {denominator} = {result})

    return result
"""

    with open(math_utils_path, "w") as f:
        f.write(math_utils_content)

    # Create a test file with matching style
    test_path = workspace / "tests" / "test_math_utils.py"
    test_content = """# test_math_utils.py
# Copyright (c) 2023 Example Company

import unittest
import logging
from src.math_utils import add, divide, validate_number
from src.math_utils import ERROR_INVALID_INPUT, ERROR_DIVIDE_BY_ZERO

class TestMathUtils(unittest.TestCase):
    \"\"\"Test suite for math utility functions.\"\"\"

    def setUp(self) -> None:
        \"\"\"Set up test environment.\"\"\"
        # Disable logging for tests
        logging.disable(logging.CRITICAL)

    def tearDown(self) -> None:
        \"\"\"Clean up after tests.\"\"\"
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def test_validate_number_valid(self) -> None:
        \"\"\"Test validate_number with valid inputs.\"\"\"
        self.assertEqual(validate_number(5), 5)
        self.assertEqual(validate_number(3.14), 3.14)

    def test_validate_number_invalid(self) -> None:
        \"\"\"Test validate_number with invalid inputs.\"\"\"
        with self.assertRaises(TypeError) as cm:
            validate_number("not a number")
        self.assertIn(ERROR_INVALID_INPUT, str(cm.exception))

    def test_add_valid(self) -> None:
        \"\"\"Test add with valid inputs.\"\"\"
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(1.5, 2.5), 4.0)

    def test_add_invalid(self) -> None:
        \"\"\"Test add with invalid inputs.\"\"\"
        with self.assertRaises(TypeError) as cm:
            add("2", 3)
        self.assertIn(ERROR_INVALID_INPUT, str(cm.exception))

    def test_divide_valid(self) -> None:
        \"\"\"Test divide with valid inputs.\"\"\"
        self.assertEqual(divide(6, 3), 2)
        self.assertEqual(divide(5, 2), 2.5)

    def test_divide_by_zero(self) -> None:
        \"\"\"Test divide with zero denominator.\"\"\"
        with self.assertRaises(ValueError) as cm:
            divide(5, 0)
        self.assertIn(ERROR_DIVIDE_BY_ZERO, str(cm.exception))
"""

    with open(test_path, "w") as f:
        f.write(test_content)

    return {
        "root": workspace,
        "math_utils_path": math_utils_path,
        "test_path": test_path
    }


def test_planning_adapts_to_code_style(styled_project, test_config, scratchpad):
    """Test that the planner adapts to existing code style patterns."""
    # Create Coordinator with necessary components
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)

    # Create a task that requires implementing a new function
    task = "Add a subtract function to the math_utils module"

    # Create a mock LLM response for the planner
    with patch('agent_s3.llm_utils.cached_call_llm') as mock_llm:
        # Define a response that should adopt the existing code style
        mock_llm.return_value = {
            'success': True,
            'response': json.dumps({
                "discussion": "I'll implement a subtract function following the project's style conventions.",
                "plan": [
                    "Add a subtract function to src/math_utils.py following existing style patterns",
                    "Add tests for the subtract function to tests/test_math_utils.py following existing test patterns",
                    "Ensure the function includes proper type hints, docstrings, and error handling"
                ],
                "test_specifications": [
                    {
                        "implementation_file": "src/math_utils.py",
                        "test_file": "tests/test_math_utils.py",
                        "framework": "unittest",
                        "scenarios": [
                            {
                                "function": "subtract",
                                "cases": [
                                    {
                                        "description": "Test subtract with valid inputs",
                                        "inputs": {"a": 5, "b": 3},
                                        "expected_output": 2,
                                        "assertions": ["self.assertEqual(subtract(5, 3), 2)"]
                                    },
                                    {
                                        "description": "Test subtract with negative result",
                                        "inputs": {"a": 2, "b": 5},
                                        "expected_output": -3,
                                        "assertions": ["self.assertEqual(subtract(2, 5), -3)"]
                                    },
                                    {
                                        "description": "Test subtract with invalid inputs",
                                        "inputs": {"a": "2", "b": 5},
                                        "expected_exception": "TypeError",
                                        "assertions": ["with self.assertRaises(TypeError) as cm:", "self.assertIn(ERROR_INVALID_INPUT, str(cm.exception))"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })
        }

        # Create a Planner instance with the mock coordinator
        planner = Planner(coordinator=coordinator)

        # Call create_plan
        plan = planner.create_plan(task)

        # Verify the plan contains the expected elements
        assert "subtract function" in plan.lower()
        assert "ERROR_INVALID_INPUT" in plan
        assert "proper type hints" in plan.lower() or "typing" in plan.lower()
        assert "validate_number" in plan
        assert "test_subtract" in plan.lower()
        assert "logger.debug" in plan.lower()

        # The plan should reference the company's style
        assert "following existing style patterns" in plan.lower()


def test_planning_considers_project_structure(basic_project, test_config, scratchpad):
    """Test that the planner considers the existing project structure."""
    # Set up coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)

    # Task to create a new module
    task = "Create a new module for date handling functions"

    # Mock the LLM response
    with patch('agent_s3.llm_utils.cached_call_llm') as mock_llm:
        mock_llm.return_value = {
            'success': True,
            'response': json.dumps({
                "discussion": "I'll create a new date handling module following the project structure.",
                "plan": [
                    "Create a new module src/date_utils.py with date handling functions",
                    "Create tests/test_date_utils.py for testing the new module",
                    "Implement basic date functions: format_date, parse_date, date_difference"
                ],
                "test_specifications": [
                    {
                        "implementation_file": "src/date_utils.py",
                        "test_file": "tests/test_date_utils.py",
                        "framework": "unittest",
                        "scenarios": [
                            {
                                "function": "format_date",
                                "cases": [
                                    {
                                        "description": "Test formatting a date",
                                        "inputs": {"date": "2023-04-15", "format": "%B %d, %Y"},
                                        "expected_output": "April 15, 2023",
                                        "assertions": ["self.assertEqual(format_date('2023-04-15', '%B %d, %Y'), 'April 15, 2023')"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })
        }

        # Create a planner
        planner = Planner(coordinator=coordinator)

        # Get the plan
        plan = planner.create_plan(task)

        # Verify the plan respects the project structure
        assert "src/date_utils.py" in plan
        assert "tests/test_date_utils.py" in plan
        assert "unittest" in plan.lower()


def test_planning_avoids_duplication(basic_project, test_config, scratchpad):
    """Test that the planner avoids duplicating existing functionality."""
    # Set up coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)

    # Add another greeting function
    greetings_path = basic_project["module_file"]
    with open(greetings_path, "a") as f:
        f.write("\ndef formal_greeting(name):\n    return f\"Good day, {name}.\"\n")

    # Task that might duplicate existing functionality
    task = "Add a greeting function that is more formal"

    # Mock the LLM response to show awareness of existing functions
    with patch('agent_s3.llm_utils.cached_call_llm') as mock_llm:
        mock_llm.return_value = {
            'success': True,
            'response': json.dumps({
                "discussion": "I notice there's already a formal_greeting function in the module. " +
                                                                                         "Instead of duplicating, I'll create a very_formal_greeting function that's even more formal.",
                "plan": [
                    "Add a very_formal_greeting function to src/greetings.py that's more formal than the existing formal_greeting",
                    "Add tests for the new function",
                    "Ensure there's no duplication with existing functions"
                ],
                "test_specifications": [
                    {
                        "implementation_file": "src/greetings.py",
                        "test_file": "tests/test_greetings.py",
                        "framework": "unittest",
                        "scenarios": [
                            {
                                "function": "very_formal_greeting",
                                "cases": [
                                    {
                                        "description": "Test very formal greeting",
                                        "inputs": {"name": "Smith"},
                                        "expected_output": "I bid you good day, esteemed Smith.",
                                        "assertions": ["self.assertEqual(very_formal_greeting('Smith'), 'I bid you good day, esteemed Smith.')"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })
        }

        # Create a planner
        planner = Planner(coordinator=coordinator)

        # Get the plan
        plan = planner.create_plan(task)

        # Verify the plan acknowledges existing functionality
        assert "formal_greeting" in plan
        assert "already" in plan.lower() or "existing" in plan.lower()
        assert "very_formal_greeting" in plan
        assert "no duplication" in plan.lower()


def test_planning_considers_dependencies(workspace, test_config, scratchpad):
    """Test that the planner considers project dependencies."""
    # Create a project with dependencies
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()

    # Create a requirements.txt file
    req_file = workspace / "requirements.txt"
    req_file.write_text("requests==2.28.1\npandas==1.5.3\n")

    # Create a simple module that uses these libraries
    api_module = workspace / "src" / "api_client.py"
    api_module.write_text("""
import requests
import pandas as pd

def fetch_data(url):
    \"\"\"Fetch data from a URL and return as a DataFrame.\"\"\"
    response = requests.get(url)
    response.raise_for_status()
    return pd.DataFrame(response.json())

def get_status(url):
    \"\"\"Get the status code of a URL.\"\"\"
    response = requests.get(url)
    return response.status_code
""")

    # Set up coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)

    # Task to add functionality that would need new dependencies
    task = "Add a function to save the DataFrame to an Excel file"

    # Mock the LLM response
    with patch('agent_s3.llm_utils.cached_call_llm') as mock_llm:
        mock_llm.return_value = {
            'success': True,
            'response': json.dumps({
                "discussion": "Adding a function to save DataFrames to Excel will require the openpyxl package, which is needed by pandas to write Excel files.",
                "plan": [
                    "Add openpyxl as a dependency in requirements.txt",
                    "Add a save_to_excel function to src/api_client.py",
                    "Add tests for the new function"
                ],
                "dependencies": ["openpyxl>=3.0.0"],
                "backward_compatibility": "None",
                "test_specifications": [
                    {
                        "implementation_file": "src/api_client.py",
                        "test_file": "tests/test_api_client.py",
                        "framework": "unittest",
                        "scenarios": [
                            {
                                "function": "save_to_excel",
                                "cases": [
                                    {
                                        "description": "Test saving DataFrame to Excel",
                                        "setup": "df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})",
                                        "inputs": {"df": "df", "filepath": "test_output.xlsx"},
                                        "assertions": [
                                            "save_to_excel(df, 'test_output.xlsx')",
                                            "self.assertTrue(os.path.exists('test_output.xlsx'))",
                                            "df2 = pd.read_excel('test_output.xlsx')",
                                            "pd.testing.assert_frame_equal(df, df2)"
                                        ],
                                        "cleanup": "os.remove('test_output.xlsx') if os.path.exists('test_output.xlsx') else None"
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })
        }

        # Create a planner
        planner = Planner(coordinator=coordinator)

        # Get the plan
        plan = planner.create_plan(task)

        # Verify the plan considers dependencies
        assert "openpyxl" in plan
        assert "requirements.txt" in plan
        assert "save_to_excel" in plan
        assert "pandas" in plan
