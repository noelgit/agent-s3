"""Tests for agentic aspects of the CodeGenerator class."""

from unittest.mock import MagicMock
import unittest

from agent_s3.code_generator import CodeGenerator


class TestCodeGeneratorAgentic(unittest.TestCase):
    """Tests for helper methods in CodeGenerator used for agentic generation."""

    def test_extract_relevant_tests_missing_categories(self):
        """Ensure missing test categories are ignored without errors."""
        coordinator = MagicMock()
        coordinator.scratchpad = MagicMock()
        coordinator.llm = None
        coordinator.file_tool = None
        coordinator.memory_manager = None
        coordinator.code_analysis_tool = None
        code_generator = CodeGenerator(coordinator)

        tests = {
            "unit_tests": [
                {
                    "file": "src/module.py",
                    "tested_functions": ["module.func"],
                }
            ],
            "integration_tests": [
                {
                    "components_involved": ["module"],
                }
            ],
        }

        result = code_generator._extract_relevant_tests(tests, "src/module.py")
        self.assertIn("unit_tests", result)
        self.assertIn("integration_tests", result)
        self.assertNotIn("property_based_tests", result)
        self.assertNotIn("acceptance_tests", result)
        self.assertIsInstance(result["unit_tests"], list)
        self.assertIsInstance(result["integration_tests"], list)


if __name__ == "__main__":
    unittest.main()
