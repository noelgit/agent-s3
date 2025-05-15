"""Unit tests for the TestFrameworks class."""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json
import tempfile
import sys
from pathlib import Path

from agent_s3.tools.test_frameworks import TestFrameworks


class TestTestFrameworks(unittest.TestCase):
    """Tests for the TestFrameworks class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_coordinator = MagicMock()
        self.mock_coordinator.bash_tool = MagicMock()
        self.test_frameworks = TestFrameworks(self.mock_coordinator)
        
        # Reset frameworks detection
        self.test_frameworks.frameworks = {
            "pytest": False,
            "unittest": False,
            "hypothesis": False,
            "approvaltests": False,
            "jest": False,
            "mocha": False,
            "fast-check": False,
            "jest-image-snapshot": False
        }
    
    @patch('importlib.import_module')
    def test_detect_frameworks_python(self, mock_import):
        """Test detecting Python test frameworks."""
        # Mock successful import for pytest and hypothesis
        def mock_import_module(name):
            if name in ["pytest", "hypothesis"]:
                return MagicMock()
            raise ImportError(f"No module named '{name}'")
            
        mock_import.side_effect = mock_import_module
        
        # No package.json, so no JS frameworks should be detected
        with patch('os.path.exists', return_value=False):
            frameworks = self.test_frameworks.detect_frameworks()
        
        # Check detection results
        self.assertTrue(frameworks["pytest"])
        self.assertFalse(frameworks["unittest"])  # Should fail import
        self.assertTrue(frameworks["hypothesis"])
        self.assertFalse(frameworks["approvaltests"])
        self.assertFalse(frameworks["jest"])  # No package.json
        
    @patch('builtins.open', new_callable=mock_open, read_data='{"devDependencies": {"jest": "^27.0.0", "jest-image-snapshot": "^4.0.0"}}')
    def test_detect_frameworks_js(self, mock_file):
        """Test detecting JavaScript test frameworks."""
        # Mock package.json exists
        with patch('os.path.exists', return_value=True):
            # Mock importlib to fail for all Python frameworks
            with patch('importlib.import_module', side_effect=ImportError):
                frameworks = self.test_frameworks.detect_frameworks()
        
        # Check detection results
        self.assertFalse(frameworks["pytest"])  # Import failed
        self.assertFalse(frameworks["unittest"])
        self.assertTrue(frameworks["jest"])  # Found in package.json
        self.assertFalse(frameworks["mocha"])  # Not in package.json
        self.assertTrue(frameworks["jest-image-snapshot"])  # Found in package.json
        
    def test_get_preferred_frameworks_python(self):
        """Test getting preferred frameworks for Python."""
        # Set up Python frameworks
        self.test_frameworks.frameworks = {
            "pytest": True,
            "unittest": True,
            "hypothesis": True,
            "approvaltests": True,
            "jest": False,
            "mocha": False,
            "fast-check": False,
            "jest-image-snapshot": False
        }
        
        # Mock _is_python_project to return True
        with patch.object(self.test_frameworks, '_is_python_project', return_value=True):
            preferred = self.test_frameworks.get_preferred_frameworks()
        
        # Check preferred frameworks
        self.assertEqual(preferred["unit"], "pytest")
        self.assertEqual(preferred["integration"], "pytest")
        self.assertEqual(preferred["property"], "hypothesis")
        self.assertEqual(preferred["approval"], "approvaltests")
        
    def test_get_preferred_frameworks_js(self):
        """Test getting preferred frameworks for JavaScript."""
        # Set up JS frameworks
        self.test_frameworks.frameworks = {
            "pytest": False,
            "unittest": False,
            "hypothesis": False,
            "approvaltests": False,
            "jest": True,
            "mocha": True,
            "fast-check": True,
            "jest-image-snapshot": True
        }
        
        # Mock _is_python_project to return False
        with patch.object(self.test_frameworks, '_is_python_project', return_value=False):
            preferred = self.test_frameworks.get_preferred_frameworks()
        
        # Check preferred frameworks
        self.assertEqual(preferred["unit"], "jest")
        self.assertEqual(preferred["integration"], "jest")
        self.assertEqual(preferred["property"], "fast-check")
        self.assertEqual(preferred["approval"], "jest-image-snapshot")
        
    def test_get_preferred_frameworks_fallback(self):
        """Test getting preferred frameworks when none are detected."""
        # No frameworks detected
        self.test_frameworks.frameworks = {
            "pytest": False,
            "unittest": False,
            "hypothesis": False,
            "approvaltests": False,
            "jest": False,
            "mocha": False,
            "fast-check": False,
            "jest-image-snapshot": False
        }
        
        # Mock _is_python_project to return True
        with patch.object(self.test_frameworks, '_is_python_project', return_value=True):
            preferred = self.test_frameworks.get_preferred_frameworks()
        
        # Check fallback frameworks for Python
        self.assertEqual(preferred["unit"], "pytest")
        self.assertEqual(preferred["property"], "hypothesis")
        self.assertEqual(preferred["approval"], "approvaltests")
        
        # Now test JS fallbacks
        with patch.object(self.test_frameworks, '_is_python_project', return_value=False):
            preferred = self.test_frameworks.get_preferred_frameworks()
        
        # Check fallback frameworks for JS
        self.assertEqual(preferred["unit"], "jest")
        self.assertEqual(preferred["property"], "fast-check")
        self.assertEqual(preferred["approval"], "jest-image-snapshot")
    
    def test_install_framework(self):
        """Test installing a test framework."""
        # Mock bash_tool.run_command to return success
        self.mock_coordinator.bash_tool.run_command.return_value = (0, "Successfully installed")
        
        # Test installing pytest
        result = self.test_frameworks.install_framework("pytest")
        
        # Check result and bash_tool calls
        self.assertTrue(result)
        self.mock_coordinator.bash_tool.run_command.assert_called_once()
        self.assertTrue("pip install pytest" in self.mock_coordinator.bash_tool.run_command.call_args[0][0])
        
        # Check framework was marked as installed
        self.assertTrue(self.test_frameworks.frameworks["pytest"])
        
    def test_install_framework_failure(self):
        """Test installing a framework with failure."""
        # Mock bash_tool.run_command to return failure
        self.mock_coordinator.bash_tool.run_command.return_value = (1, "Installation failed")
        
        # Test installing jest
        result = self.test_frameworks.install_framework("jest")
        
        # Check result and bash_tool calls
        self.assertFalse(result)
        self.mock_coordinator.bash_tool.run_command.assert_called_once()
        self.assertTrue("npm install" in self.mock_coordinator.bash_tool.run_command.call_args[0][0])
        
        # Check framework was not marked as installed
        self.assertFalse(self.test_frameworks.frameworks["jest"])
        
    def test_generate_test_file_python(self):
        """Test generating a Python test file."""
        # Set up frameworks
        self.test_frameworks.frameworks = {"pytest": True}
        
        # Mock _is_python_project to return True
        with patch.object(self.test_frameworks, '_is_python_project', return_value=True):
            # Generate a unit test file for a Python module
            test_file_path, content = self.test_frameworks.generate_test_file(
                "src/module.py", "unit"
            )
        
        # Check test file path
        self.assertEqual(test_file_path, "tests/test_module.py")
        
        # Check content contains expected elements
        self.assertIn("import pytest", content)
        self.assertIn("def test_", content)
        self.assertIn("assert", content)
        
    def test_generate_test_file_js(self):
        """Test generating a JavaScript test file."""
        # Set up frameworks
        self.test_frameworks.frameworks = {"jest": True}
        
        # Mock _is_python_project to return False
        with patch.object(self.test_frameworks, '_is_python_project', return_value=False):
            # Generate an integration test file for a JS module
            test_file_path, content = self.test_frameworks.generate_test_file(
                "src/component.js", "integration"
            )
        
        # Check test file path
        self.assertEqual(test_file_path, "tests/integration/component.integration.test.js")
        
        # Check content contains expected elements
        self.assertIn("describe", content)
        self.assertIn("Integration", content)
        self.assertIn("expect", content)
        
    def test_get_test_template(self):
        """Test getting test templates for different types."""
        # Get templates for different test types
        unit_template = self.test_frameworks.get_test_template("unit", "python")
        integration_template = self.test_frameworks.get_test_template("integration", "python")
        approval_template = self.test_frameworks.get_test_template("approval", "python")
        property_template = self.test_frameworks.get_test_template("property", "python")
        
        # Check templates contain appropriate content
        self.assertIn("def test_", unit_template)
        self.assertIn("@pytest.mark.integration", integration_template)
        self.assertIn("verify(", approval_template)
        self.assertIn("@given(", property_template)
        
        # Check JS templates
        unit_js_template = self.test_frameworks.get_test_template("unit", "javascript")
        integration_js_template = self.test_frameworks.get_test_template("integration", "javascript")
        
        # Check JS templates contain appropriate content
        self.assertIn("describe(", unit_js_template)
        self.assertIn("expect(", unit_js_template)
        self.assertIn("Integration", integration_js_template)
        
    @patch('os.path.isfile')
    def test_verify_tests_python(self, mock_isfile):
        """Test verifying Python test files."""
        # Mock file existence check
        mock_isfile.return_value = True
        
        # Mock compile and import to succeed
        with patch('builtins.compile', return_value=None):
            with patch('importlib.import_module', return_value=MagicMock()):
                # Mock bash_tool to indicate tests can run
                self.mock_coordinator.bash_tool.run_command.return_value = (0, "All tests passed")
                
                # Verify test files
                result = self.test_frameworks.verify_tests(
                    ["tests/test_module.py"],
                    "src/module.py"
                )
        
        # Check verification result
        self.assertTrue(result["valid"])
        self.assertTrue(result["syntax_valid"])
        self.assertTrue(result["imports_valid"])
        self.assertTrue(result["can_run"])
        self.assertEqual(len(result["errors"]), 0)
        
    @patch('os.path.isfile')
    def test_verify_tests_syntax_error(self, mock_isfile):
        """Test verifying tests with syntax errors."""
        # Mock file existence check
        mock_isfile.return_value = True
        
        # Mock compile to raise syntax error
        with patch('builtins.compile', side_effect=SyntaxError("invalid syntax")):
            # Verify test files
            result = self.test_frameworks.verify_tests(
                ["tests/test_module.py"],
                "src/module.py"
            )
        
        # Check verification result
        self.assertFalse(result["valid"])
        self.assertFalse(result["syntax_valid"])
        self.assertGreater(len(result["errors"]), 0)
        
    def test_check_dependencies(self):
        """Test checking dependencies for a test type."""
        # Set up frameworks
        self.test_frameworks.frameworks = {
            "pytest": True,
            "hypothesis": False
        }
        
        # Check dependencies for unit tests (Python)
        result = self.test_frameworks.check_dependencies("unit", "python")
        
        # Check result
        self.assertTrue(result["has_required_dependencies"])
        self.assertIn("pytest", result["available_frameworks"])
        self.assertEqual(len(result["missing_frameworks"]), 0)
        
        # Check dependencies for property tests (Python)
        result = self.test_frameworks.check_dependencies("property", "python")
        
        # Check result
        self.assertFalse(result["has_required_dependencies"])
        self.assertEqual(len(result["available_frameworks"]), 0)
        self.assertIn("hypothesis", result["missing_frameworks"])
        self.assertGreater(len(result["install_commands"]), 0)
        
    def test_is_python_project(self):
        """Test detecting if project is primarily Python-based."""
        # Create a mock file structure
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create Python files
            os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)
            Path(os.path.join(temp_dir, "src", "module1.py")).touch()
            Path(os.path.join(temp_dir, "src", "module2.py")).touch()
            
            # Create JS file
            Path(os.path.join(temp_dir, "src", "script.js")).touch()
            
            # Change working directory to temp_dir
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            try:
                # Test with more Python files than JS
                result = self.test_frameworks._is_python_project()
                self.assertTrue(result)
                
                # Create more JS files to flip the balance
                Path(os.path.join(temp_dir, "src", "script2.js")).touch()
                Path(os.path.join(temp_dir, "src", "script3.js")).touch()
                Path(os.path.join(temp_dir, "src", "script4.js")).touch()
                
                # Test again with more JS files
                result = self.test_frameworks._is_python_project()
                self.assertFalse(result)
            finally:
                # Restore original working directory
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()