"""Mock LLM responses for system tests.

This module contains realistic mock responses for LLM calls used in system tests.
The responses follow the expected patterns and formats of real LLM responses.
"""

import json
import re
from typing import Dict, Any, List, Optional, Tuple

class MockLLMResponses:
    """Provides realistic mock responses for LLM calls."""

    @staticmethod
    def create_plan_response(task: str, file_paths: List[str] = None) -> Dict[str, Any]:
        """Generate a mock plan response for the given task.

        Args:
            task: The task description
            file_paths: Optional list of file paths to include in the plan

        Returns:
            Dict containing the mock plan response
        """
        # Extract keywords from the task to customize the response
        task_lower = task.lower()

        # Determine response type based on task
        if "add" in task_lower or "create" in task_lower or "implement" in task_lower:
            return MockLLMResponses._create_feature_addition_plan(task, file_paths)
        elif "fix" in task_lower or "bug" in task_lower or "issue" in task_lower:
            return MockLLMResponses._create_bug_fix_plan(task, file_paths)
        elif "refactor" in task_lower or "improve" in task_lower or "optimize" in task_lower:
            return MockLLMResponses._create_refactoring_plan(task, file_paths)
        else:
            # Default to feature addition
            return MockLLMResponses._create_feature_addition_plan(task, file_paths)

    @staticmethod
    def _create_feature_addition_plan(task: str, file_paths: List[str] = None) -> Dict[str, Any]:
        """Create a plan response for feature addition tasks.

        Args:
            task: The task description
            file_paths: Optional list of file paths to include in the plan

        Returns:
            Dict containing the mock plan response
        """
        # Extract potential module/functionality name from task
        feature_match = re.search(r'(?:add|create|implement)\s+(?:a|an)?\s*([a-zA-Z_]+(?:\s+
            [a-zA-Z_]+
                )?)', task.lower())        feature_name = feature_match.group(1) if feature_match else "new_feature"        feature_name = feature_name.replace(" ", "_")

        # Generate file paths if not provided
        if not file_paths:
            file_paths = [f"src/{feature_name}.py", f"tests/test_{feature_name}.py"]

        # Create implementation files list, excluding test files
        implementation_files = [f for f in file_paths if not (f.startswith("test_") or "/test_" in f)]

        # Generate plan with test specifications
        plan = {
            "discussion": f"This task involves adding new functionality for {feature_name}. " +
                         "We'll need to create/modify the implementation files and add comprehensive tests.",
            "plan": [
                f"Create/update {implementation_files[0]} with the new {feature_name} functionality",
                f"Add unit tests in {file_paths[1] if len(file_paths) > 1 else 'tests/test_' +
                     implementation_files[0].split('/')[-1]}",                "Verify tests pass and coverage is adequate"
            ],
            "test_specifications": []
        }

        # Generate test specifications for each implementation file
        for impl_file in implementation_files:
            # Generate a test file path based on the implementation file
            if impl_file.startswith("src/"):
                test_file = impl_file.replace("src/", "tests/test_")
            else:
                test_file = f"tests/test_{os.path.basename(impl_file)}"

            # Create test specification
            test_spec = {
                "implementation_file": impl_file,
                "test_file": test_file,
                "framework": "pytest",
                "scenarios": [
                    {
                        "function": f"{feature_name}_function",
                        "cases": [
                            {
                                "description": "Test basic functionality",
                                "inputs": {"param1": "value1", "param2": "value2"},
                                "expected_output": "expected result",
                                "assertions": [f"assert {feature_name}_function('value1', 'value2') == 'expected result'"]
                            },
                            {
                                "description": "Test edge case",
                                "inputs": {"param1": "", "param2": None},
                                "expected_output": "default result",
                                "assertions": [f"assert {feature_name}_function('', None) == 'default result'"]
                            },
                            {
                                "description": "Test error case",
                                "inputs": {"param1": None, "param2": "value2"},
                                "expected_exception": "ValueError",
                                "assertions": [f"with pytest.raises(ValueError):", f"    {feature_name}_function(None, 'value2')"]
                            }
                        ]
                    }
                ],
                "security_tests": [
                    {
                        "description": "Test input validation",
                        "inputs": {"param1": "<script>alert('xss')</script>", "param2": "value2"},
                        "expected_behavior": "Should sanitize input to prevent XSS",
                        "assertions": [
                            f"result = {feature_name}_function('<script>alert(\\'xss\\')</script>', 'value2')",
                            "assert '<script>' not in result"
                        ]
                    }
                ]
            }

            plan["test_specifications"].append(test_spec)

        return plan

    @staticmethod
    def _create_bug_fix_plan(task: str, file_paths: List[str] = None) -> Dict[str, Any]:
        """Create a plan response for bug fix tasks.

        Args:
            task: The task description
            file_paths: Optional list of file paths to include in the plan

        Returns:
            Dict containing the mock plan response
        """
        # Extract potential bug details from task
        bug_match = re.search(r'fix\s+([a-zA-Z_]+(?:\s+[a-zA-Z_]+)?)', task.lower())
        bug_area = bug_match.group(1) if bug_match else "bug"
        bug_area = bug_area.replace(" ", "_")

        # Generate file paths if not provided
        if not file_paths:
            file_paths = [f"src/{bug_area}.py", f"tests/test_{bug_area}.py"]

        # Create implementation files list, excluding test files
        implementation_files = [f for f in file_paths if not (f.startswith("test_") or "/test_" in f)]

        # Generate plan with test specifications
        plan = {
            "discussion": f"This task involves fixing a bug in the {bug_area} functionality. " +
                         "The issue appears to be related to input validation or error handling. " +
                         "We'll need to update the implementation and add tests to verify the fix.",
            "plan": [
                f"Fix the bug in {implementation_files[0]}",
                f"Add regression tests in {file_paths[1] if len(file_paths) > 1 else 'tests/test_' +
                     implementation_files[0].split('/')[-1]}",                "Verify tests pass and the bug is fixed"
            ],
            "test_specifications": []
        }

        # Generate test specifications for each implementation file
        for impl_file in implementation_files:
            # Generate a test file path based on the implementation file
            if impl_file.startswith("src/"):
                test_file = impl_file.replace("src/", "tests/test_")
            else:
                test_file = f"tests/test_{os.path.basename(impl_file)}"

            # Create test specification
            test_spec = {
                "implementation_file": impl_file,
                "test_file": test_file,
                "framework": "pytest",
                "scenarios": [
                    {
                        "function": f"{bug_area}_function",
                        "cases": [
                            {
                                "description": "Test bug fix",
                                "inputs": {"param1": "edge_case_value", "param2": "normal_value"},
                                "expected_output": "corrected_result",
                                "assertions": [f"assert {bug_area}_function('edge_case_value', 'normal_value') == 'corrected_result'"]
                            },
                            {
                                "description": "Test regression case",
                                "inputs": {"param1": "normal_value", "param2": "normal_value"},
                                "expected_output": "expected_result",
                                "assertions": [f"assert {bug_area}_function('normal_value', 'normal_value') == 'expected_result'"]
                            }
                        ]
                    }
                ]
            }

            plan["test_specifications"].append(test_spec)

        return plan

    @staticmethod
    def _create_refactoring_plan(task: str, file_paths: List[str] = None) -> Dict[str, Any]:
        """Create a plan response for refactoring tasks.

        Args:
            task: The task description
            file_paths: Optional list of file paths to include in the plan

        Returns:
            Dict containing the mock plan response
        """
        # Extract potential refactoring area from task
        refactor_match = re.search(r'(?:refactor|improve|optimize)\s+([a-zA-Z_]+(?:\s+[a-zA-Z_]+
            )?)', task.lower())        refactor_area = refactor_match.group(1) if refactor_match else "component"
        refactor_area = refactor_area.replace(" ", "_")

        # Generate file paths if not provided
        if not file_paths:
            file_paths = [f"src/{refactor_area}.py", f"tests/test_{refactor_area}.py"]

        # Create implementation files list, excluding test files
        implementation_files = [f for f in file_paths if not (f.startswith("test_") or "/test_" in f)]

        # Generate plan with test specifications
        plan = {
            "discussion": f"This task involves refactoring the {refactor_area} to improve " +
                         "maintainability, performance, or code quality. " +
                         "We'll need to refactor the implementation while ensuring existing functionality is preserved.",
            "plan": [
                f"Refactor {implementation_files[0]} to improve {refactor_area}",
                "Ensure existing tests still pass",
                f"Add additional tests in {file_paths[1] if len(file_paths) > 1 else 'tests/test_' +
                     implementation_files[0].split('/')[-1]} to cover edge cases",                "Verify tests pass and functionality is preserved"
            ],
            "test_specifications": []
        }

        # Generate test specifications for each implementation file
        for impl_file in implementation_files:
            # Generate a test file path based on the implementation file
            if impl_file.startswith("src/"):
                test_file = impl_file.replace("src/", "tests/test_")
            else:
                test_file = f"tests/test_{os.path.basename(impl_file)}"

            # Create test specification with approval tests for refactoring
            test_spec = {
                "implementation_file": impl_file,
                "test_file": test_file,
                "framework": "pytest",
                "scenarios": [
                    {
                        "function": f"{refactor_area}_function",
                        "cases": [
                            {
                                "description": "Test existing functionality is preserved",
                                "inputs": {"param1": "test_value", "param2": "test_value2"},
                                "expected_output": "expected_result",
                                "assertions": [f"assert {refactor_area}_function('test_value', 'test_value2') == 'expected_result'"]
                            }
                        ]
                    }
                ],
                "approval_tests": [
                    {
                        "description": "Test refactored function behavior matches approved behavior",
                        "function": f"{refactor_area}_function",
                        "inputs": [
                            {"param1": "value1", "param2": "value2"},
                            {"param1": "edge_case", "param2": "value2"},
                            {"param1": "value1", "param2": "edge_case"}
                        ],
                        "verification": "output matches approved baseline"
                    }
                ]
            }

            plan["test_specifications"].append(test_spec)

        return plan

    @staticmethod
    def generate_code_response(task: str, plan: Dict[str, Any]) -> Dict[str, str]:
        """Generate mock code response for the given task and plan.

        Args:
            task: The task description
            plan: The plan dictionary

        Returns:
            Dict mapping file paths to generated code
        """
        # Extract information from the plan
        implementation_files = []
        test_files = []

        # Extract implementation and test files from test specifications
        for test_spec in plan.get("test_specifications", []):
            impl_file = test_spec.get("implementation_file")
            test_file = test_spec.get("test_file")

            if impl_file and impl_file not in implementation_files:
                implementation_files.append(impl_file)

            if test_file and test_file not in test_files:
                test_files.append(test_file)

        # Generate code for each file
        code_response = {}

        # Generate implementation files
        for impl_file in implementation_files:
            # Extract function names from test specs
            function_names = []
            for test_spec in plan.get("test_specifications", []):
                if test_spec.get("implementation_file") == impl_file:
                    for scenario in test_spec.get("scenarios", []):
                        function_name = scenario.get("function")
                        if function_name and function_name not in function_names:
                            function_names.append(function_name)

            # Generate implementation code
            impl_code = MockLLMResponses._generate_implementation_code(impl_file, function_names, task)
            code_response[impl_file] = impl_code

        # Generate test files
        for test_file in test_files:
            # Find corresponding test spec
            test_spec = None
            for spec in plan.get("test_specifications", []):
                if spec.get("test_file") == test_file:
                    test_spec = spec
                    break

            if test_spec:
                # Generate test code
                test_code = MockLLMResponses._generate_test_code(test_file, test_spec, task)
                code_response[test_file] = test_code

        return code_response

    @staticmethod
    def _generate_implementation_code(file_path: str, function_names: List[str], task: str) -> str:
        """Generate implementation code for a file.

        Args:
            file_path: The file path
            function_names: List of function names to implement
            task: The original task description

        Returns:
            Generated implementation code
        """
        module_name = os.path.basename(file_path).replace(".py", "")
        is_python = file_path.endswith(".py")

        if is_python:
            # Generate Python implementation
            code = f'"""{module_name} module.\n\nImplements functionality for {module_name}.\n"""\n\n'

            # Import statements
            code += "import logging\nfrom typing import Any, Dict, List, Optional, Union\n\n"

            # Logger setup
            code += f"logger = logging.getLogger(__name__)\n\n"

            # Add functions
            for function_name in function_names:
                code += f"def {function_name}(param1: str, param2: Optional[str] = None) -> str:\n"
                code += f'    """\n    {function_name} implementation.\n\n'
                code +
                    = f"    Args:\n        param1: First parameter\n        param2: Second parameter (optional)\n\n"                code +
                                                = f"    Returns:\n        Result string\n\n"                code +
                            = f"    Raises:\n        ValueError: If param1 is None\n    \"\"\"\n"                code += f"    # Validate inputs\n"
                code += f"    if param1 is None:\n"
                code += f"        logger.error(\"param1 cannot be None\")\n"
                code += f"        raise ValueError(\"param1 cannot be None\")\n\n"
                code += f"    # Sanitize inputs\n"
                code += f"    if isinstance(param1, str):\n"
                code +
                    = f"        param1 = param1.replace('<script>', '').replace('</script>', '')\n\n"                code +
                                                = f"    # Process based on params\n"                code +
                            = f"    if not param2:\n"                code += f"        return f\"default result for {{param1}}\"\n\n"
                code += f"    return f\"result for {{param1}} and {{param2}}\"\n\n"
        else:
            # Default to empty string for non-Python files
            code = f"// Implementation for {file_path}\n"

        return code

    @staticmethod
    def _generate_test_code(file_path: str, test_spec: Dict[str, Any], task: str) -> str:
        """Generate test code for a file.

        Args:
            file_path: The file path
            test_spec: The test specification
            task: The original task description

        Returns:
            Generated test code
        """
        module_name = os.path.basename(file_path).replace(".py", "").replace("test_", "")
        implementation_file = test_spec.get("implementation_file", f"src/{module_name}.py")
        impl_import_path = implementation_file.replace("/", ".").replace(".py", "")

        # Generate Python test code
        code = f'"""Tests for the {module_name} module."""\n\n'

        # Import statements
        code += "import pytest\n"

        # Import the module based on the implementation file path
        if implementation_file.startswith("src/"):
            # Convert src/path/to/module.py to from src.path.to import module
            import_path = implementation_file[:-3].replace("/", ".")
            module_name = import_path.split(".")[-1]
            parent_path = ".".join(import_path.split(".")[:-1])
            code += f"from {parent_path} import {module_name}\n\n"
        else:
            # Just import directly
            code += f"import {impl_import_path.split('.')[-1]}\n\n"

        # Generate test class
        code += f"class Test{module_name.capitalize()}:\n"

        # Add test methods for each scenario
        for scenario in test_spec.get("scenarios", []):
            function_name = scenario.get("function", "unknown_function")

            for i, case in enumerate(scenario.get("cases", [])):
                # Create test method name
                description = case.get("description", f"test_case_{i+1}")
                test_method_name = f"test_{function_name}_{description.lower().replace(' ', '_')}"

                # Start test method
                code += f"    def {test_method_name}(self):\n"
                code += f"        \"\"\"Test {description.lower()}.\"\"\"\n"

                # Handle different test cases
                if case.get("expected_exception"):
                    # Exception test
                    exception_type = case.get("expected_exception")
                    inputs = case.get("inputs", {})
                    params = ", ".join([f"{k}={repr(v)}" for k, v in inputs.items()])

                    code += f"        with pytest.raises({exception_type}):\n"
                    code += f"            {function_name}({params})\n\n"
                else:
                    # Normal assertion test
                    inputs = case.get("inputs", {})
                    params = ", ".join([f"{k}={repr(v)}" for k, v in inputs.items()])
                    expected = case.get("expected_output", "expected_result")

                    code += f"        result = {function_name}({params})\n"
                    code += f"        assert result == {repr(expected)}\n\n"

        # Add security tests
        for security_test in test_spec.get("security_tests", []):
            description = security_test.get("description", "security_test")
            test_method_name = f"test_security_{description.lower().replace(' ', '_')}"

            # Start test method
            code += f"    def {test_method_name}(self):\n"
            code += f"        \"\"\"Test {description.lower()}.\"\"\"\n"

            # Add assertions from security test
            for assertion in security_test.get("assertions", []):
                code += f"        {assertion}\n"

            code += "\n"

        return code

    @staticmethod
    def analyze_error(error_message: str, code_context: str = None) -> Dict[str, Any]:
        """Generate a mock error analysis response.

        Args:
            error_message: The error message to analyze
            code_context: Optional code context

        Returns:
            Dict containing the error analysis
        """
        # Extract information from the error message
        error_type_match = re.search(r'([A-Za-z]+Error|Exception):', error_message)
        error_type = error_type_match.group(1) if error_type_match else "UnknownError"

        line_number_match = re.search(r'line (\d+)', error_message)
        line_number = line_number_match.group(1) if line_number_match else "unknown"

        file_path_match = re.search(r'File "([^"]+)"', error_message)
        file_path = file_path_match.group(1) if file_path_match else "unknown_file.py"

        # Generate analysis based on error type
        if error_type == "SyntaxError":
            analysis = {
                "error_type": "SyntaxError",
                "file": file_path,
                "line_number": line_number,
                "analysis": "There appears to be a syntax error in the code.",
                "suggested_fix": "Check for missing or extra parentheses, brackets, or quotes.",
                "severity": "critical"
            }
        elif error_type == "TypeError":
            analysis = {
                "error_type": "TypeError",
                "file": file_path,
                "line_number": line_number,
                "analysis": "There's a type mismatch in the function arguments or operations.",
                "suggested_fix": "Ensure all function arguments are of the correct type.",
                "severity": "high"
            }
        elif error_type == "ImportError" or error_type == "ModuleNotFoundError":
            analysis = {
                "error_type": error_type,
                "file": file_path,
                "line_number": line_number,
                "analysis": "A module or import is missing or cannot be found.",
                "suggested_fix": "Check that the module is installed or the import path is correct.",
                "severity": "medium"
            }
        elif error_type == "AttributeError":
            analysis = {
                "error_type": "AttributeError",
                "file": file_path,
                "line_number": line_number,
                "analysis": "Trying to access an attribute or method that doesn't exist.",
                "suggested_fix": "Verify the object has the attribute or method being accessed.",
                "severity": "high"
            }
        else:
            # Generic error analysis
            analysis = {
                "error_type": error_type,
                "file": file_path,
                "line_number": line_number,
                "analysis": f"An error of type {error_type} occurred.",
                "suggested_fix": "Review the error message and check the code at the specified line.",
                "severity": "medium"
            }

        return analysis
