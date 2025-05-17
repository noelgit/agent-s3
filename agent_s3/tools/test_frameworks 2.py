"""
TestFrameworks: Provides functionality for working with different test frameworks.
Supports unit tests, integration tests, approval tests, and property-based tests.
"""

import os
import importlib
import inspect
import json
import logging
from typing import Dict, List, Set, Any, Optional, Tuple, Callable, Union
from pathlib import Path

logger = logging.getLogger(__name__)

class TestFrameworks:
    """Provides functionality for working with different test frameworks."""
    
    def __init__(self, coordinator=None):
        """Initialize with optional coordinator."""
        self.coordinator = coordinator
        self.bash_tool = coordinator.bash_tool if coordinator else None
        
        # Framework presence flags
        self.frameworks = {
            "pytest": False,
            "unittest": False,
            "hypothesis": False,
            "approvaltests": False,
            "jest": False,
            "mocha": False,
            "fast-check": False,
            "jest-image-snapshot": False
        }
        
        # Detect available frameworks
        self.detect_frameworks()
    
    def detect_frameworks(self) -> Dict[str, bool]:
        """
        Detect which test frameworks are available in the project.
        
        Returns:
            Dictionary mapping framework names to booleans
        """
        # Reset framework detection
        for framework in self.frameworks:
            self.frameworks[framework] = False
        
        # Try to detect Python frameworks first
        try:
            # Check for pytest
            try:
                importlib.import_module("pytest")
                self.frameworks["pytest"] = True
            except ImportError:
                pass
            
            # Check for unittest
            try:
                importlib.import_module("unittest")
                self.frameworks["unittest"] = True
            except ImportError:
                pass
            
            # Check for hypothesis (property-based testing)
            try:
                importlib.import_module("hypothesis")
                self.frameworks["hypothesis"] = True
            except ImportError:
                pass
            
            # Check for approvaltests
            try:
                importlib.import_module("approvaltests")
                self.frameworks["approvaltests"] = True
            except ImportError:
                pass
        except Exception as e:
            logger.warning(f"Error during Python framework detection: {e}")
        
        # For JS frameworks, check package.json if available
        if os.path.exists("package.json"):
            try:
                with open("package.json", "r") as f:
                    package_data = json.load(f)
                
                # Get dependencies and dev dependencies
                dependencies = package_data.get("dependencies", {})
                dev_dependencies = package_data.get("devDependencies", {})
                all_deps = {**dependencies, **dev_dependencies}
                
                # Check for Jest
                if "jest" in all_deps:
                    self.frameworks["jest"] = True
                
                # Check for Mocha
                if "mocha" in all_deps:
                    self.frameworks["mocha"] = True
                
                # Check for fast-check (property-based testing)
                if "fast-check" in all_deps:
                    self.frameworks["fast-check"] = True
                
                # Check for approval testing libs
                if "jest-image-snapshot" in all_deps:
                    self.frameworks["jest-image-snapshot"] = True
            except Exception as e:
                logger.warning(f"Error reading package.json: {e}")
        
        return self.frameworks
    
    def get_preferred_frameworks(self) -> Dict[str, str]:
        """
        Get the preferred frameworks for each test type.
        
        Returns:
            Dictionary mapping test types to framework names
        """
        # Determine preferred frameworks based on what's available
        preferred = {
            "unit": None,
            "integration": None,
            "approval": None,
            "property": None
        }
        
        # Unit testing frameworks
        if self.frameworks["pytest"]:
            preferred["unit"] = "pytest"
        elif self.frameworks["unittest"]:
            preferred["unit"] = "unittest"
        elif self.frameworks["jest"]:
            preferred["unit"] = "jest"
        elif self.frameworks["mocha"]:
            preferred["unit"] = "mocha"
        else:
            # Default fallbacks for unit testing
            preferred["unit"] = "pytest" if self._is_python_project() else "jest"
        
        # Integration testing frameworks (usually same as unit, with different setup)
        preferred["integration"] = preferred["unit"]
        
        # Property-based testing frameworks
        if self.frameworks["hypothesis"]:
            preferred["property"] = "hypothesis"
        elif self.frameworks["fast-check"]:
            preferred["property"] = "fast-check"
        else:
            # Default fallbacks
            preferred["property"] = "hypothesis" if self._is_python_project() else "fast-check"
        
        # Approval testing frameworks
        if self.frameworks["approvaltests"]:
            preferred["approval"] = "approvaltests"
        elif self.frameworks["jest-image-snapshot"]:
            preferred["approval"] = "jest-image-snapshot"
        else:
            # Default fallbacks
            preferred["approval"] = "approvaltests" if self._is_python_project() else "jest-image-snapshot"
        
        return preferred
    
    def install_framework(self, framework: str) -> bool:
        """
        Install a test framework.
        
        Args:
            framework: Name of the framework to install
            
        Returns:
            True if installation was successful, False otherwise
        """
        if not self.bash_tool:
            logger.error("No bash tool available for framework installation")
            return False
        
        install_commands = {
            "pytest": "pip install pytest pytest-cov",
            "unittest": "pip install pytest pytest-cov",  # unittest is built-in, but install pytest for features
            "hypothesis": "pip install hypothesis",
            "approvaltests": "pip install approvaltests",
            "jest": "npm install --save-dev jest",
            "mocha": "npm install --save-dev mocha chai",
            "fast-check": "npm install --save-dev fast-check",
            "jest-image-snapshot": "npm install --save-dev jest-image-snapshot"
        }
        
        if framework not in install_commands:
            logger.error(f"Unknown framework: {framework}")
            return False
        
        try:
            # Run installation command
            cmd = install_commands[framework]
            exit_code, output = self.bash_tool.run_command(cmd, timeout=300)
            
            if exit_code == 0:
                logger.info(f"Successfully installed {framework}")
                # Update framework detection
                self.frameworks[framework] = True
                return True
            else:
                logger.error(f"Failed to install {framework}: {output}")
                return False
        except Exception as e:
            logger.error(f"Error installing {framework}: {e}")
            return False
    
    def generate_test_file(self, implementation_file: str, test_type: str) -> Tuple[str, str]:
        """
        Generate a test file for an implementation file.
        
        Args:
            implementation_file: Path to the implementation file
            test_type: Type of test ('unit', 'integration', 'approval', 'property')
            
        Returns:
            Tuple of (test_file_path, test_file_content)
        """
        # Determine language
        is_python = implementation_file.endswith('.py')
        
        # Get preferred framework for this test type
        frameworks = self.get_preferred_frameworks()
        framework = frameworks.get(test_type)
        
        # Generate test file path
        test_file_path = self._get_test_file_path(implementation_file, test_type)
        
        # Generate test file content
        if is_python:
            content = self._generate_python_test(implementation_file, test_type, framework)
        else:
            content = self._generate_js_test(implementation_file, test_type, framework)
        
        return test_file_path, content
    
    def get_test_template(self, test_type: str, language: str = "python") -> str:
        """
        Get a template for a specific test type.
        
        Args:
            test_type: Type of test ('unit', 'integration', 'approval', 'property')
            language: Programming language ('python' or 'javascript')
            
        Returns:
            Template string
        """
        # Get preferred framework for test type
        frameworks = self.get_preferred_frameworks()
        framework = frameworks.get(test_type)
        
        if language == "python":
            return self._get_python_test_template(test_type, framework)
        else:
            return self._get_js_test_template(test_type, framework)
    
    def verify_tests(self, test_files: List[str], implementation_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Verify that tests are valid and runnable.
        
        Args:
            test_files: List of test files to verify
            implementation_file: Optional implementation file being tested
            
        Returns:
            Dictionary with verification results
        """
        results = {
            "valid": False,
            "files_checked": test_files,
            "implementation_file": implementation_file,
            "errors": [],
            "warnings": [],
            "syntax_valid": False,
            "imports_valid": False,
            "can_run": False
        }
        
        if not test_files:
            results["errors"].append("No test files provided")
            return results
        
        # Check syntax validity
        syntax_errors = []
        for test_file in test_files:
            try:
                if test_file.endswith('.py'):
                    # For Python, compile to check syntax
                    with open(test_file, 'r') as f:
                        compile(f.read(), test_file, 'exec')
                else:
                    # For JS, use bash_tool to run a syntax check
                    if self.bash_tool:
                        cmd = f"node --check {test_file}"
                        exit_code, output = self.bash_tool.run_command(cmd, timeout=10)
                        if exit_code != 0:
                            syntax_errors.append(f"Syntax error in {test_file}: {output}")
            except Exception as e:
                syntax_errors.append(f"Syntax error in {test_file}: {str(e)}")
        
        if syntax_errors:
            results["errors"].extend(syntax_errors)
        else:
            results["syntax_valid"] = True
        
        # Check imports validity (for Python files)
        import_errors = []
        for test_file in test_files:
            if test_file.endswith('.py'):
                try:
                    # Try to import the module
                    module_name = os.path.relpath(test_file, os.getcwd())
                    module_name = module_name.replace('/', '.').replace('\\', '.').replace('.py', '')
                    importlib.import_module(module_name)
                except ImportError as e:
                    import_errors.append(f"Import error in {test_file}: {str(e)}")
                except Exception as e:
                    import_errors.append(f"Error loading {test_file}: {str(e)}")
        
        if import_errors:
            results["warnings"].extend(import_errors)
        else:
            results["imports_valid"] = True
        
        # Try to run the tests if bash_tool is available
        if self.bash_tool:
            try:
                # Detect test runner
                runner = self._detect_test_runner(test_files[0])
                
                # Run the tests
                if runner:
                    run_cmd = ""
                    if runner == "pytest":
                        # Run with pytest, but skip actual collection for speed
                        run_cmd = f"pytest {' '.join(test_files)} --collect-only -q"
                    elif runner == "unittest":
                        run_cmd = f"python -m unittest -f {' '.join(test_files)}"
                    elif runner == "jest":
                        run_cmd = f"npx jest --bail {' '.join(test_files)}"
                    elif runner == "mocha":
                        run_cmd = f"npx mocha {' '.join(test_files)}"
                    
                    if run_cmd:
                        exit_code, output = self.bash_tool.run_command(run_cmd, timeout=60)
                        if exit_code != 0:
                            results["warnings"].append(f"Tests may not run correctly: {output}")
                        else:
                            results["can_run"] = True
            except Exception as e:
                results["warnings"].append(f"Could not verify if tests can run: {str(e)}")
        
        # Final validity check
        results["valid"] = results["syntax_valid"] and not results["errors"]
        
        return results
    
    def check_dependencies(self, test_type: str, language: str = "python") -> Dict[str, Any]:
        """
        Check if dependencies are satisfied for a specific test type.
        
        Args:
            test_type: Type of test ('unit', 'integration', 'approval', 'property')
            language: Programming language ('python' or 'javascript')
            
        Returns:
            Dictionary with dependency check results
        """
        # Map test types to frameworks
        test_type_frameworks = {
            "unit": ["pytest", "unittest", "jest", "mocha"],
            "integration": ["pytest", "unittest", "jest", "mocha"],
            "approval": ["approvaltests", "jest-image-snapshot"],
            "property": ["hypothesis", "fast-check"]
        }
        
        # Filter frameworks by language
        python_frameworks = ["pytest", "unittest", "hypothesis", "approvaltests"]
        js_frameworks = ["jest", "mocha", "fast-check", "jest-image-snapshot"]
        
        if language == "python":
            target_frameworks = [f for f in test_type_frameworks.get(test_type, []) if f in python_frameworks]
        else:
            target_frameworks = [f for f in test_type_frameworks.get(test_type, []) if f in js_frameworks]
        
        # Check each framework
        available_frameworks = []
        missing_frameworks = []
        
        for framework in target_frameworks:
            if self.frameworks.get(framework, False):
                available_frameworks.append(framework)
            else:
                missing_frameworks.append(framework)
        
        # Generate install commands for missing frameworks
        install_commands = []
        for framework in missing_frameworks:
            if framework in ["pytest", "unittest"]:
                install_commands.append("pip install pytest pytest-cov")
            elif framework == "hypothesis":
                install_commands.append("pip install hypothesis")
            elif framework == "approvaltests":
                install_commands.append("pip install approvaltests")
            elif framework == "jest":
                install_commands.append("npm install --save-dev jest")
            elif framework == "mocha":
                install_commands.append("npm install --save-dev mocha chai")
            elif framework == "fast-check":
                install_commands.append("npm install --save-dev fast-check")
            elif framework == "jest-image-snapshot":
                install_commands.append("npm install --save-dev jest-image-snapshot")
        
        return {
            "test_type": test_type,
            "language": language,
            "available_frameworks": available_frameworks,
            "missing_frameworks": missing_frameworks,
            "has_required_dependencies": len(available_frameworks) > 0,
            "install_commands": install_commands
        }
    
    def _is_python_project(self) -> bool:
        """Determine if the project is primarily Python-based."""
        # Simple heuristic based on file counts
        py_count = sum(1 for _ in Path(".").glob("**/*.py"))
        js_count = sum(1 for _ in Path(".").glob("**/*.js"))
        ts_count = sum(1 for _ in Path(".").glob("**/*.ts"))
        
        return py_count > (js_count + ts_count)
    
    def _get_test_file_path(self, implementation_file: str, test_type: str) -> str:
        """Generate a test file path based on implementation file and test type."""
        file_path = Path(implementation_file)
        stem = file_path.stem
        
        # Different conventions for different test types
        if test_type == "unit":
            if file_path.suffix == ".py":
                return f"tests/test_{stem}.py"
            else:
                return f"tests/{stem}.test.js"
        elif test_type == "integration":
            if file_path.suffix == ".py":
                return f"tests/integration/test_integration_{stem}.py"
            else:
                return f"tests/integration/{stem}.integration.test.js"
        elif test_type == "approval":
            if file_path.suffix == ".py":
                return f"tests/approval/test_approval_{stem}.py"
            else:
                return f"tests/approval/{stem}.approval.test.js"
        elif test_type == "property":
            if file_path.suffix == ".py":
                return f"tests/property/test_property_{stem}.py"
            else:
                return f"tests/property/{stem}.property.test.js"
        else:
            # Default
            if file_path.suffix == ".py":
                return f"tests/test_{stem}.py"
            else:
                return f"tests/{stem}.test.js"
    
    def _generate_python_test(self, implementation_file: str, test_type: str, framework: str) -> str:
        """Generate Python test file content."""
        file_path = Path(implementation_file)
        module_name = file_path.stem
        
        # Import statements
        if framework == "pytest":
            imports = f"import pytest\nimport {module_name}\n"
        elif framework == "unittest":
            imports = f"import unittest\nimport {module_name}\n"
        else:
            imports = f"import {module_name}\n"
        
        # Framework-specific imports
        if test_type == "property" and framework == "hypothesis":
            imports += "from hypothesis import given, strategies as st\n"
        elif test_type == "approval" and framework == "approvaltests":
            imports += "from approvaltests import verify\n"
        
        # Choose template based on test type and framework
        template = self._get_python_test_template(test_type, framework)
        
        # Replace placeholders
        template = template.replace("{{MODULE_NAME}}", module_name)
        template = template.replace("{{CLASS_NAME}}", f"{module_name.title()}Tests")
        
        return imports + "\n" + template
    
    def _generate_js_test(self, implementation_file: str, test_type: str, framework: str) -> str:
        """Generate JavaScript/TypeScript test file content."""
        file_path = Path(implementation_file)
        module_name = file_path.stem
        
        # Determine import style based on file extension
        is_ts = file_path.suffix in [".ts", ".tsx"]
        
        # Import statements
        if is_ts:
            imports = f"import * as {module_name} from '../{module_name}';\n"
        else:
            imports = f"const {module_name} = require('../{module_name}');\n"
        
        # Framework-specific imports
        if framework == "jest":
            # Jest doesn't need explicit imports
            pass
        elif framework == "mocha":
            imports += "const { expect } = require('chai');\n"
        
        if test_type == "property" and framework == "fast-check":
            imports += "const fc = require('fast-check');\n"
        elif test_type == "approval" and framework == "jest-image-snapshot":
            imports += "const { toMatchImageSnapshot } = require('jest-image-snapshot');\n"
            imports += "expect.extend({ toMatchImageSnapshot });\n"
        
        # Choose template based on test type and framework
        template = self._get_js_test_template(test_type, framework)
        
        # Replace placeholders
        template = template.replace("{{MODULE_NAME}}", module_name)
        
        return imports + "\n" + template
    
    def _get_python_test_template(self, test_type: str, framework: str) -> str:
        """Get a Python test template for a specific test type and framework."""
        if test_type == "unit":
            if framework == "pytest":
                return """
def test_{{MODULE_NAME}}_functionality():
    # TODO: Implement test
    assert True

def test_{{MODULE_NAME}}_edge_cases():
    # TODO: Implement edge case tests
    assert True
"""
            elif framework == "unittest":
                return """
class {{CLASS_NAME}}(unittest.TestCase):
    def test_functionality(self):
        # TODO: Implement test
        self.assertTrue(True)
        
    def test_edge_cases(self):
        # TODO: Implement edge case tests
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
"""
        elif test_type == "integration":
            if framework == "pytest":
                return """
@pytest.mark.integration
def test_{{MODULE_NAME}}_integration():
    # TODO: Implement integration test
    assert True

def test_{{MODULE_NAME}}_with_dependencies():
    # TODO: Test interaction with other components
    assert True
"""
            elif framework == "unittest":
                return """
class {{CLASS_NAME}}Integration(unittest.TestCase):
    def test_integration(self):
        # TODO: Implement integration test
        self.assertTrue(True)
        
    def test_with_dependencies(self):
        # TODO: Test interaction with other components
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
"""
        elif test_type == "approval":
            if framework == "approvaltests":
                return """
def test_{{MODULE_NAME}}_output_approval():
    # Generate output from the module
    actual_output = str({{MODULE_NAME}})  # TODO: Replace with actual output generation
    
    # Verify output matches approved version
    verify(actual_output)

def test_{{MODULE_NAME}}_complex_approval():
    # TODO: Generate more complex output to verify
    complex_output = "Sample output"
    
    # Verify output matches approved version
    verify(complex_output)
"""
            else:
                return """
def test_{{MODULE_NAME}}_output_approval():
    # Generate output from the module
    actual_output = str({{MODULE_NAME}})  # TODO: Replace with actual output generation
    
    # Compare with expected output
    expected_output = "Expected output"
    assert actual_output == expected_output
"""
        elif test_type == "property":
            if framework == "hypothesis":
                return """
@given(st.integers(), st.integers())
def test_{{MODULE_NAME}}_property(a, b):
    # TODO: Implement property-based test
    # This test runs with many random inputs
    assert a + b == b + a  # Example property: addition is commutative

@given(st.text())
def test_{{MODULE_NAME}}_string_property(s):
    # TODO: Implement string property test
    assert len(s) >= 0  # Example property: string length is non-negative
"""
            else:
                return """
def test_{{MODULE_NAME}}_property():
    # TODO: Implement property-based test using a different approach
    for i in range(100):
        a = i
        b = i * 2
        assert a + b == b + a  # Example property: addition is commutative
"""
        
        # Default template
        return """
def test_{{MODULE_NAME}}():
    # TODO: Implement test
    assert True
"""
    
    def _get_js_test_template(self, test_type: str, framework: str) -> str:
        """Get a JavaScript test template for a specific test type and framework."""
        if test_type == "unit":
            if framework == "jest":
                return """
describe('{{MODULE_NAME}}', () => {
  test('basic functionality', () => {
    // TODO: Implement test
    expect(true).toBe(true);
  });
  
  test('edge cases', () => {
    // TODO: Implement edge case tests
    expect(true).toBe(true);
  });
});
"""
            elif framework == "mocha":
                return """
describe('{{MODULE_NAME}}', function() {
  it('should have basic functionality', function() {
    // TODO: Implement test
    expect(true).to.equal(true);
  });
  
  it('should handle edge cases', function() {
    // TODO: Implement edge case tests
    expect(true).to.equal(true);
  });
});
"""
        elif test_type == "integration":
            if framework == "jest":
                return """
describe('{{MODULE_NAME}} Integration', () => {
  test('integration with dependencies', () => {
    // TODO: Implement integration test
    expect(true).toBe(true);
  });
  
  test('component interaction', () => {
    // TODO: Test interaction with other components
    expect(true).toBe(true);
  });
});
"""
            elif framework == "mocha":
                return """
describe('{{MODULE_NAME}} Integration', function() {
  it('should integrate with dependencies', function() {
    // TODO: Implement integration test
    expect(true).to.equal(true);
  });
  
  it('should interact with other components', function() {
    // TODO: Test interaction with other components
    expect(true).to.equal(true);
  });
});
"""
        elif test_type == "approval":
            if framework == "jest-image-snapshot":
                return """
describe('{{MODULE_NAME}} Approval', () => {
  test('output matches approved snapshot', () => {
    // Generate output from the module
    const actualOutput = '{{MODULE_NAME}} output';  // TODO: Replace with actual output generation
    
    // Match against approved snapshot
    expect(actualOutput).toMatchSnapshot();
  });
  
  test('complex output matches approved snapshot', () => {
    // TODO: Generate more complex output to verify
    const complexOutput = { key: 'value' };
    
    // Match against approved snapshot
    expect(complexOutput).toMatchSnapshot();
  });
});
"""
            else:
                return """
describe('{{MODULE_NAME}} Approval', () => {
  test('output matches expected value', () => {
    // Generate output from the module
    const actualOutput = '{{MODULE_NAME}} output';  // TODO: Replace with actual output generation
    
    // Compare with expected output
    const expectedOutput = '{{MODULE_NAME}} output';
    expect(actualOutput).toBe(expectedOutput);
  });
});
"""
        elif test_type == "property":
            if framework == "fast-check":
                return """
describe('{{MODULE_NAME}} Properties', () => {
  test('commutative property', () => {
    // Property-based test using fast-check
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => {
        // TODO: Replace with actual property test
        return a + b === b + a;  // Example property: addition is commutative
      })
    );
  });
  
  test('string property', () => {
    fc.assert(
      fc.property(fc.string(), (s) => {
        // TODO: Replace with actual property test
        return s.length >= 0;  // Example property: string length is non-negative
      })
    );
  });
});
"""
            else:
                return """
describe('{{MODULE_NAME}} Properties', () => {
  test('should verify properties', () => {
    // Manual property testing approach
    for (let i = 0; i < 100; i++) {
      const a = i;
      const b = i * 2;
      // TODO: Replace with actual property test
      expect(a + b).toBe(b + a);  // Example property: addition is commutative
    }
  });
});
"""
        
        # Default template
        return """
describe('{{MODULE_NAME}}', () => {
  test('should work correctly', () => {
    // TODO: Implement test
    expect(true).toBe(true);
  });
});
"""
    
    def _detect_test_runner(self, test_file: str) -> str:
        """Detect the test runner based on a test file."""
        # Try a simple file-content check first
        try:
            with open(test_file, 'r') as f:
                content = f.read()
                
                if test_file.endswith('.py'):
                    # Check for pytest usage
                    if 'pytest' in content:
                        return "pytest"
                    # Check for unittest usage
                    elif 'unittest' in content:
                        return "unittest"
                    else:
                        return "pytest"  # Default to pytest for Python
                else:
                    # JavaScript testing
                    if 'jest' in content:
                        return "jest"
                    elif 'mocha' in content:
                        return "mocha"
                    else:
                        return "jest"  # Default to jest for JS
        except Exception:
            # Fall back to file name based detection
            if test_file.endswith('.py'):
                return "pytest"
            else:
                return "jest"