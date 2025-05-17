"""
Tests for the implementation validator module.
"""

import os
import sys
import unittest
import json
from pathlib import Path

# Add agent_s3 to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_s3.tools.implementation_validator import (
    validate_implementation_plan,
    repair_implementation_plan,
    _extract_element_ids_from_system_design,
    _extract_architecture_issues,
    _extract_test_requirements
)


class TestImplementationValidator(unittest.TestCase):
    """Tests for the implementation validator module."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Minimal system design for testing
        self.system_design = {
            "code_elements": [
                {
                    "element_id": "element1",
                    "name": "TestClass",
                    "type": "class",
                    "description": "Test class"
                },
                {
                    "element_id": "element2",
                    "name": "test_function",
                    "type": "function",
                    "description": "Test function"
                }
            ]
        }
        
        # Minimal architecture review for testing
        self.architecture_review = {
            "logical_gaps": [
                {
                    "id": "LG1",
                    "description": "Missing error handling",
                    "severity": "High",
                    "affected_elements": ["element1"]
                }
            ],
            "security_concerns": [
                {
                    "id": "SC1",
                    "description": "Input validation needed",
                    "severity": "Critical",
                    "affected_elements": ["element2"]
                }
            ]
        }
        
        # Minimal test implementations for testing
        self.test_implementations = {
            "tests": {
                "unit_tests": [
                    {
                        "name": "test_function_with_invalid_input",
                        "target_element_ids": ["element2"],
                        "code": "def test_function_with_invalid_input():\n    with pytest.raises(ValueError):\n        test_function(None)"
                    }
                ]
            }
        }
        
        # Valid implementation plan for testing
        self.valid_implementation_plan = {
            "file1.py": [
                {
                    "function": "def test_function(input_data: str) -> bool:",
                    "description": "Test function implementation",
                    "element_id": "element2",
                    "steps": [
                        {
                            "step_description": "Validate input",
                            "error_handling_notes": "Raise ValueError for None input"
                        },
                        {
                            "step_description": "Process input",
                            "relevant_data_structures": ["str"]
                        }
                    ],
                    "edge_cases": ["Handle None input", "Handle empty string"],
                    "architecture_issues_addressed": ["SC1"]
                }
            ],
            "file2.py": [
                {
                    "function": "class TestClass:",
                    "description": "Test class implementation",
                    "element_id": "element1",
                    "steps": [
                        {
                            "step_description": "Implement constructor",
                            "pseudo_code": "def __init__(self): pass"
                        }
                    ],
                    "edge_cases": [],
                    "architecture_issues_addressed": ["LG1"]
                }
            ]
        }
        
        # Invalid implementation plan for testing
        self.invalid_implementation_plan = {
            "file1.py": [
                {
                    "function": "def wrong_function():",
                    "description": "Wrong function implementation",
                    "element_id": "invalid_element",  # Invalid element_id
                    "steps": []  # Missing steps
                }
            ]
        }

    def test_extract_element_ids(self):
        """Test extraction of element IDs from system design."""
        element_ids = _extract_element_ids_from_system_design(self.system_design)
        self.assertEqual(element_ids, {"element1", "element2"})

    def test_extract_architecture_issues(self):
        """Test extraction of architecture issues."""
        issues = _extract_architecture_issues(self.architecture_review)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0]["id"], "LG1")
        self.assertEqual(issues[1]["id"], "SC1")

    def test_extract_test_requirements(self):
        """Test extraction of test requirements."""
        requirements = _extract_test_requirements(self.test_implementations)
        self.assertTrue("element2" in requirements)
        self.assertEqual(len(requirements["element2"]), 1)

    def test_validate_valid_plan(self):
        """Test validation of a valid implementation plan."""
        validated_plan, validation_issues, needs_repair = validate_implementation_plan(
            self.valid_implementation_plan,
            self.system_design,
            self.architecture_review,
            self.test_implementations
        )
        
        self.assertFalse(needs_repair)
        self.assertEqual(len(validation_issues), 0)

    def test_validate_invalid_plan(self):
        """Test validation of an invalid implementation plan."""
        validated_plan, validation_issues, needs_repair = validate_implementation_plan(
            self.invalid_implementation_plan,
            self.system_design,
            self.architecture_review,
            self.test_implementations
        )
        
        self.assertTrue(needs_repair)
        self.assertGreater(len(validation_issues), 0)
        
        # Check for specific issues
        issue_types = [issue["issue_type"] for issue in validation_issues]
        self.assertIn("invalid_element_id", issue_types)
        self.assertIn("missing_steps", issue_types)
        self.assertIn("missing_element_implementation", issue_types)
        self.assertIn("unaddressed_critical_issue", issue_types)

    def test_repair_plan(self):
        """Test repairing an invalid implementation plan."""
        validated_plan, validation_issues, needs_repair = validate_implementation_plan(
            self.invalid_implementation_plan,
            self.system_design,
            self.architecture_review,
            self.test_implementations
        )
        
        repaired_plan = repair_implementation_plan(
            validated_plan,
            validation_issues,
            self.system_design,
            self.architecture_review,
            self.test_implementations
        )
        
        # Check that the repaired plan has the correct elements
        implemented_elements = set()
        for file_path, functions in repaired_plan.items():
            for function in functions:
                if "element_id" in function and function["element_id"] in {"element1", "element2"}:
                    implemented_elements.add(function["element_id"])
        
        self.assertEqual(implemented_elements, {"element1", "element2"})
        
        # Check that steps are added
        has_steps = True
        for file_path, functions in repaired_plan.items():
            for function in functions:
                if not function.get("steps", []):
                    has_steps = False
        
        self.assertTrue(has_steps)


if __name__ == "__main__":
    unittest.main()
