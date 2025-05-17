"""
TestRunnerTool: Detects and runs tests, parses coverage reports.
Provides structured failure information for debugging.
"""
import os
import re
import subprocess
import json
from typing import Dict, Any, List, Optional, Tuple

class TestRunnerTool:
    """Detects test runner, runs tests, parses outputs and coverage reports."""
    def __init__(self, bash_tool):
        self.bash_tool = bash_tool

    def detect_runner(self) -> str:
        """Detects the test runner (pytest, unittest, etc.) based on project files/imports."""
        if os.path.exists("pytest.ini") or os.path.exists(".pytest_cache"):
            return "pytest"
        if os.path.exists("pyproject.toml"):
            with open("pyproject.toml", "r") as f:
                if "[tool.pytest.ini_options]" in f.read():
                    return "pytest"
        # Fallback: check for unittest imports in tests/
        for root, _, files in os.walk("tests"):
            for file in files:
                if file.endswith(".py"):
                    with open(os.path.join(root, file), "r") as f:
                        if "import unittest" in f.read():
                            return "unittest"
        return "pytest"  # Default

    def run_tests(self, test_command: str = None, test_path: str = None, test_file: str = None, timeout: int = 300) -> Dict[str, Any]:
        """Run tests for the project and provide structured failure information.
        
        Args:
            test_command: Optional specific test command to run
            test_path: Optional path to test directory
            test_file: Optional specific test file to run
            timeout: Maximum time in seconds to wait for tests to complete
            
        Returns:
            Dictionary with test results, including structured failure information if tests fail
        """
        if test_command:
            # Use the provided command directly
            cmd = test_command
        else:
            # Auto-detect runner and build command
            runner = self.detect_runner()
            
            # Build appropriate command based on runner
            if runner == "pytest":
                cmd = "python -m pytest"
                if test_file:
                    cmd += f" {test_file}"
                elif test_path:
                    cmd += f" {test_path}"
                cmd += " -v"  # Verbose output for better failure parsing
            elif runner == "unittest":
                cmd = "python -m unittest"
                if test_file:
                    cmd += f" {test_file}"
                elif test_path:
                    cmd += f" discover {test_path}"
            else:
                # Default to pytest
                cmd = "python -m pytest"
                if test_file:
                    cmd += f" {test_file}"
                elif test_path:
                    cmd += f" {test_path}"
        
        # Add test coverage data collection
        if "pytest" in cmd and "--cov" not in cmd:
            cmd += " --cov --cov-report=json:.coverage.json"
            
        # Run the test command
        result = self.bash_tool.run_command(cmd, timeout=timeout)
        success = result.get("return_code", 1) == 0
        output = result.get("output", "")
        
        # Parse the test output for structured information
        test_results = {
            "success": success,
            "output": output,
            "command": cmd
        }
        
        # Add coverage information if available
        coverage = self._parse_coverage()
        if coverage is not None:
            test_results["coverage"] = coverage
        
        # If tests failed, provide structured information about failures
        if not success:
            failure_info = self._parse_test_failures(output)
            test_results["failure_info"] = failure_info
            
            # Add regression test info if applicable
            if test_file:
                regression_info = self._check_for_regressions(test_file)
                if regression_info:
                    test_results["regression_info"] = regression_info
                    
        return test_results
    
    def run_regression_tests(self, feature_group: str = None) -> Dict[str, Any]:
        """Run regression tests after a fix has been applied.
        
        Args:
            feature_group: Optional feature group identifier to limit regression scope
            
        Returns:
            Dictionary with regression test results
        """
        # Determine the tests to run for regression checking
        if feature_group:
            # Run tests specific to the feature group
            cmd = f"python -m pytest tests/test_{feature_group.lower().replace(' ', '_')}.py -v"
        else:
            # Run all tests
            cmd = "python -m pytest -v"
            
        # Run the tests
        result = self.bash_tool.run_command(cmd, timeout=300)
        success = result.get("return_code", 1) == 0
        output = result.get("output", "")
        
        # Parse for structured information
        regression_results = {
            "success": success,
            "output": output,
            "command": cmd
        }
        
        # Add detailed failure info if tests failed
        if not success:
            regression_results["failure_info"] = self._parse_test_failures(output)
            
        return regression_results
    
    def _parse_coverage(self) -> Optional[float]:
        """Parse coverage report if available."""
        try:
            if os.path.exists(".coverage.json"):
                with open(".coverage.json", "r") as f:
                    data = json.load(f)
                # Extract coverage percentage
                if "totals" in data and "percent_covered" in data["totals"]:
                    return float(data["totals"]["percent_covered"])
        except Exception:
            pass
        return None
    
    def _parse_test_failures(self, output: str) -> List[Dict[str, Any]]:
        """Parse test output to extract structured failure information.
        
        Args:
            output: Raw test output
            
        Returns:
            List of dictionaries with structured failure information
        """
        failures = []
        
        # Try to extract pytest failures
        if 'FAILED' in output:
            # First try to extract full test failure sections
            test_sections = re.findall(r'(_{5,}\s+(.+?)\s+_{5,}.*?(?:\n\n|$))', output, re.DOTALL)
            
            for section_idx, (section, test_path) in enumerate(test_sections):
                # Extract test name, class, and file
                test_path_parts = test_path.split('::')
                test_file = test_path_parts[0] if test_path_parts else None
                test_class = test_path_parts[1] if len(test_path_parts) > 1 else None
                test_name = test_path_parts[-1] if test_path_parts else None
                
                # Extract traceback section
                traceback_match = re.search(r'(?:.*?E\s+)([^\n]+(?:\n\s+[^\n]+)*)', section, re.DOTALL)
                traceback_text = traceback_match.group(1).strip() if traceback_match else None
                
                # Try to extract line number
                line_match = re.search(r'(?:.*?):(\d+)(?:\:|\s|$)', section)
                line_number = int(line_match.group(1)) if line_match else None
                
                # Try to extract assertion details
                assertion_match = re.search(r'(?:AssertionError|assert)\s+(.*?)(?:\n|$)', section, re.MULTILINE)
                assertion_text = assertion_match.group(1).strip() if assertion_match else None
                
                # Try to parse expected vs actual in different formats
                expected = None
                actual = None
                
                # Format: E   assert X == Y
                eq_match = re.search(r'assert\s+(.+?)\s*==\s*(.+?)(?:\n|$|\s+#)', section, re.MULTILINE)
                if eq_match:
                    actual = eq_match.group(1).strip()
                    expected = eq_match.group(2).strip()
                
                # Format: E   assert X > Y
                gt_match = re.search(r'assert\s+(.+?)\s*>\s*(.+?)(?:\n|$|\s+#)', section, re.MULTILINE)
                if gt_match and not expected and not actual:
                    actual = gt_match.group(1).strip()
                    compared_to = gt_match.group(2).strip()
                    expected = f"{actual} > {compared_to}"
                
                # Format: AssertionError: Expected X, got Y
                human_match = re.search(r'Expected\s+(.*?),\s+got\s+(.*?)(?:\n|$|\s+#)', section, re.IGNORECASE)
                if human_match and not expected and not actual:
                    expected = human_match.group(1).strip()
                    actual = human_match.group(2).strip()
                
                # Extract context variables and their values
                variable_values = {}
                locals_match = re.search(r'(?:-+ locals -+\n)(.*?)(?:\n\n|\n-+|$)', section, re.DOTALL)
                if locals_match:
                    locals_section = locals_match.group(1)
                    var_matches = re.findall(r'(\w+)\s+=\s+(.+?)(?:\n|$)', locals_section)
                    for var_name, var_value in var_matches:
                        variable_values[var_name] = var_value.strip()
                
                # Build comprehensive failure info
                failure_info = {
                    "id": section_idx + 1,
                    "test_name": test_name,
                    "test_file": test_file,
                    "test_class": test_class,
                    "line_number": line_number,
                    "traceback": traceback_text,
                    "details": section.strip(),
                    "assertion": assertion_text
                }
                
                if expected is not None:
                    failure_info["expected"] = expected
                
                if actual is not None:
                    failure_info["actual"] = actual
                
                if variable_values:
                    failure_info["variables"] = variable_values
                
                failures.append(failure_info)
            
            # If we couldn't extract sections, fall back to simpler pattern matching
            if not failures:
                # Look for individual failure blocks
                failure_blocks = re.findall(r'(E\s+.+?)\n\n', output, re.DOTALL)
                for i, block in enumerate(failure_blocks):
                    # Try to extract test name, file, and line number
                    test_name_match = re.search(r'(?:.*?::)?(test_\w+)', output)
                    file_match = re.search(r'(\w+\.py):(\d+)', output)
                    
                    failure_info = {
                        "id": i + 1,
                        "details": block.strip()
                    }
                    
                    if test_name_match:
                        failure_info["test_name"] = test_name_match.group(1)
                    
                    if file_match:
                        failure_info["test_file"] = file_match.group(1)
                        failure_info["line_number"] = int(file_match.group(2))
                    
                    # Try to extract expected vs actual values
                    expected_match = re.search(r'E\s+assert\s+(.+?)\s*==\s*(.+?)$', block, re.MULTILINE)
                    if expected_match:
                        failure_info["expected"] = expected_match.group(2).strip()
                        failure_info["actual"] = expected_match.group(1).strip()
                    
                    failures.append(failure_info)
                
        # If no pytest failures found, try unittest patterns
        elif 'FAIL:' in output:
            # Look for unittest failure patterns
            unittest_failures = re.findall(r'FAIL: (\w+) \(([\w\.]+)\)\n(.*?)(?=\n\n)', output, re.DOTALL)
            for i, (test_name, test_class, details) in enumerate(unittest_failures):
                # Try to extract file and line number
                file_match = re.search(r'File "([^"]+)", line (\d+)', details)
                file_path = file_match.group(1) if file_match else None
                line_number = int(file_match.group(2)) if file_match else None
                
                failure_info = {
                    "id": i + 1,
                    "test_name": test_name,
                    "test_class": test_class,
                    "test_file": os.path.basename(file_path) if file_path else None,
                    "file_path": file_path,
                    "line_number": line_number,
                    "details": details.strip(),
                    "traceback": details.strip()
                }
                
                # Try to extract expected vs actual values
                assertion_match = re.search(r'AssertionError: (.*?)$', details, re.MULTILINE)
                if assertion_match:
                    assertion_text = assertion_match.group(1)
                    failure_info["assertion"] = assertion_text
                    
                    # Check for expected/actual in the assertion text
                    expected_actual_match = re.search(r'Expected\s+(.*?),\s+got\s+(.*?)(?:\n|$)', assertion_text, re.IGNORECASE)
                    if expected_actual_match:
                        failure_info["expected"] = expected_actual_match.group(1).strip()
                        failure_info["actual"] = expected_actual_match.group(2).strip()
                
                failures.append(failure_info)
        
        # If no structured information could be extracted, add the raw output
        if not failures:
            failures.append({
                "id": 1,
                "details": "Could not parse structured failure information",
                "raw_output": output
            })
        
        # Add failure category for each failure to help debugging
        for failure in failures:
            failure["failure_category"] = self._categorize_test_failure(failure)
            
            # Add a plausibility check - could this be a bad test vs bad implementation?
            failure["possible_bad_test"] = self._check_test_plausibility(failure)
        
        return failures
        
    def _categorize_test_failure(self, failure: Dict[str, Any]) -> str:
        """Categorize test failure to help with debugging strategy.
        
        Args:
            failure: Dictionary with failure information
            
        Returns:
            Category string
        """
        details = failure.get("details", "").lower()
        assertion = failure.get("assertion", "").lower()
        traceback = failure.get("traceback", "").lower()
        
        # Look for different patterns to categorize the failure
        if "typeerror" in details or "typeerror" in traceback:
            return "TYPE_ERROR"
        elif "attributeerror" in details or "attributeerror" in traceback:
            return "ATTRIBUTE_ERROR"
        elif "importerror" in details or "importerror" in traceback or "modulenotfounderror" in details:
            return "IMPORT_ERROR"
        elif "nameerror" in details or "nameerror" in traceback:
            return "NAME_ERROR"
        elif "assertionerror" in details or "assertion" in details:
            if "expected" in failure and "actual" in failure:
                return "VALUE_MISMATCH"
            elif "none" in traceback or "none" in assertion:
                return "UNEXPECTED_NONE"
            elif "true" in assertion or "false" in assertion:
                return "BOOLEAN_CHECK_FAILED"
            else:
                return "ASSERTION_ERROR"
        elif "syntaxerror" in details or "syntaxerror" in traceback:
            return "SYNTAX_ERROR"
        elif "keyerror" in details or "keyerror" in traceback:
            return "KEY_ERROR"
        elif "indexerror" in details or "indexerror" in traceback:
            return "INDEX_ERROR"
        elif "valuerror" in details or "valuerror" in traceback:
            return "VALUE_ERROR"
        elif "permission" in details or "permission" in traceback:
            return "PERMISSION_ERROR"
        elif "timeout" in details or "timeout" in traceback:
            return "TIMEOUT_ERROR"
        elif "file not found" in details or "no such file" in details:
            return "FILE_NOT_FOUND"
        elif "indentation" in details:
            return "INDENTATION_ERROR"
        else:
            return "UNKNOWN_ERROR"
            
    def _check_test_plausibility(self, failure: Dict[str, Any]) -> bool:
        """Perform a heuristic check to see if the failure might be due to a bad test.
        
        Args:
            failure: Dictionary with failure information
            
        Returns:
            True if the test itself might be problematic, False otherwise
        """
        details = failure.get("details", "").lower()
        test_name = failure.get("test_name", "").lower()
        test_file = failure.get("test_file", "").lower()
        traceback = failure.get("traceback", "").lower()
        
        # Heuristics for suspicious test failures
        
        # 1. Test is looking for a function/attribute that doesn't exist in typical naming conventions
        if "attributeerror" in traceback and test_name and not re.match(r'^test_\w+$', test_name):
            return True
            
        # 2. Test has syntax errors in the test itself
        if "syntaxerror" in traceback and "test" in traceback:
            return True
            
        # 3. Test is trying to import a non-existent module
        if "modulenotfounderror" in traceback and "test" in traceback:
            return True
            
        # 4. Test is asserting specific string formats that may be too rigid
        if "assertionerror" in traceback and "expected" in failure and "actual" in failure:
            expected = failure.get("expected", "")
            actual = failure.get("actual", "")
            
            # If actual and expected are similar but just formatting differences
            if (expected and actual and 
                actual.strip().replace(" ", "") == expected.strip().replace(" ", "") or
                actual.strip().lower() == expected.strip().lower()):
                return True
                
        # 5. Test is checking for very specific error messages that may change
        if "assertionerror" in traceback and "error message" in traceback.lower():
            return True
            
        # Generally assume the test is valid (most test failures are implementation issues)
        return False
    
    def _check_for_regressions(self, fixed_test_file: str) -> List[Dict[str, Any]]:
        """Run broader tests to check for regressions after a fix.
        
        Args:
            fixed_test_file: The test file that was just fixed
            
        Returns:
            List of dictionaries with regression information
        """
        # Skip the test file that was just fixed to avoid duplication
        cmd = f"python -m pytest --ignore={fixed_test_file} -v"
        
        # Run the tests
        result = self.bash_tool.run_command(cmd, timeout=300)
        success = result.get("return_code", 1) == 0
        output = result.get("output", "")
        
        # If successful, no regressions
        if success:
            return []
        
        # If failures, parse them as regressions
        regression_failures = self._parse_test_failures(output)
        for failure in regression_failures:
            failure["is_regression"] = True
        
        return regression_failures
    
    def validate_test_integrity(self, test_code: str, implementation_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Perform heuristic check if test is valid against implementation plan.
        
        Args:
            test_code: The test code to validate
            implementation_plan: The implementation plan to check against
            
        Returns:
            Dictionary with validation results
        """
        # Extract expected function names, parameters, return types from plan
        expected_elements = self._extract_expected_elements(implementation_plan)
        
        # Extract function names, parameters, assertions from test code
        test_elements = self._extract_test_elements(test_code)
        
        # Check for mismatches
        mismatches = []
        for func_name, details in expected_elements.get("functions", {}).items():
            # Check if function is tested
            if func_name not in test_elements.get("tested_functions", []):
                mismatches.append({
                    "type": "missing_test",
                    "function": func_name,
                    "message": f"No tests found for function '{func_name}'"
                })
                continue
                
            # Check parameter consistency
            expected_params = details.get("params", [])
            tested_params = test_elements.get("function_params", {}).get(func_name, [])
            
            if set(expected_params) != set(tested_params) and expected_params:
                mismatches.append({
                    "type": "parameter_mismatch",
                    "function": func_name,
                    "expected_params": expected_params,
                    "tested_params": tested_params,
                    "message": f"Parameter mismatch for function '{func_name}'"
                })
        
        # Check if test has assertions for expected behaviors
        behaviors = expected_elements.get("behaviors", [])
        assertions = test_elements.get("assertions", [])
        
        for behavior in behaviors:
            if not any(self._assertion_covers_behavior(assertion, behavior) for assertion in assertions):
                mismatches.append({
                    "type": "missing_assertion",
                    "behavior": behavior,
                    "message": f"No assertions found for behavior: {behavior}"
                })
        
        # Return validation results
        return {
            "valid": len(mismatches) == 0,
            "mismatches": mismatches,
            "expected_elements": expected_elements,
            "test_elements": test_elements
        }
    
    def _extract_expected_elements(self, implementation_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Extract expected elements from implementation plan."""
        result = {
            "functions": {},
            "behaviors": []
        }
        
        # Extract function details
        for step in implementation_plan.get("steps", []):
            if "function" in step:
                func_name = step["function"]
                result["functions"][func_name] = {
                    "params": step.get("parameters", []),
                    "return_type": step.get("return_type")
                }
            
            # Extract expected behaviors
            if "description" in step:
                result["behaviors"].append(step["description"])
            
            if "edge_cases" in step:
                for edge_case in step["edge_cases"]:
                    result["behaviors"].append(f"Handle edge case: {edge_case}")
        
        return result
    
    def _extract_test_elements(self, test_code: str) -> Dict[str, Any]:
        """Extract elements from test code."""
        result = {
            "tested_functions": [],
            "function_params": {},
            "assertions": []
        }
        
        # Extract tested functions
        function_calls = re.findall(r'(\w+)\((.*?)\)', test_code)
        for func_name, params in function_calls:
            if func_name not in ["assert", "assertEqual", "assertTrue", "assertFalse"]:
                if func_name not in result["tested_functions"]:
                    result["tested_functions"].append(func_name)
                
                # Extract parameters for the function call
                param_list = [p.strip() for p in params.split(",") if p.strip()]
                if func_name not in result["function_params"]:
                    result["function_params"][func_name] = param_list
        
        # Extract assertions
        pytest_assertions = re.findall(r'assert\s+(.*?)(?:$|#)', test_code, re.MULTILINE)
        unittest_assertions = re.findall(r'assert\w+\((.*?)\)', test_code)
        
        result["assertions"] = pytest_assertions + unittest_assertions
        
        return result
    
    def _assertion_covers_behavior(self, assertion: str, behavior: str) -> bool:
        """Check if an assertion likely covers a behavior."""
        # Simple heuristic: check keyword overlap
        behavior_words = set(re.findall(r'\b\w+\b', behavior.lower()))
        assertion_words = set(re.findall(r'\b\w+\b', assertion.lower()))
        
        overlap = behavior_words.intersection(assertion_words)
        return len(overlap) >= 2  # At least 2 words in common
