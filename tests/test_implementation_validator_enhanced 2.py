"""
Tests for the enhanced implementation validator functions.
"""

import os
import sys
import unittest
import json
from pathlib import Path

# Add agent_s3 to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_s3.tools.implementation_validator import (
    _calculate_implementation_metrics,
    _validate_implementation_quality,
    _validate_implementation_security,
    _validate_implementation_test_alignment
)


class TestImplementationValidatorEnhanced(unittest.TestCase):
    """Tests for the enhanced implementation validator functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Minimal implementation plan for testing
        self.implementation_plan = {
            "file1.py": [
                {
                    "function": "def test_function(input_data: str) -> bool:",
                    "description": "Test function implementation",
                    "element_id": "element1",
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
                },
                {
                    "function": "def auth_function(user_id: str, password: str) -> bool:",
                    "description": "Authenticate user",
                    "element_id": "element2",
                    "steps": [
                        {
                            "step_description": "Process authentication",
                            "error_handling_notes": "Handle invalid credentials"
                        }
                    ],
                    "edge_cases": [],
                    "architecture_issues_addressed": []
                }
            ],
            "file2.py": [
                {
                    "function": "class TestClass:",
                    "description": "Test class implementation",
                    "element_id": "element3",
                    "steps": [
                        {
                            "step_description": "Initialize class",
                            "error_handling_notes": ""
                        }
                    ],
                    "edge_cases": [],
                    "architecture_issues_addressed": []
                }
            ]
        }
        
        # Architecture issues for testing
        self.architecture_issues = [
            {
                "id": "SC1",
                "description": "Input validation needed",
                "severity": "High",
                "issue_type": "security_concern"
            },
            {
                "id": "SC2",
                "description": "Authentication needs improvement",
                "severity": "Critical",
                "issue_type": "security_concern"
            },
            {
                "id": "LG1",
                "description": "Error handling improvement",
                "severity": "Medium",
                "issue_type": "logical_gap"
            }
        ]
        
        # Test requirements for testing
        self.test_requirements = {
            "element1": [
                {
                    "name": "test_function_with_invalid_input",
                    "description": "Test should validate that function rejects None input",
                    "code": "def test_function_with_invalid_input():\n    with pytest.raises(ValueError):\n        test_function(None)"
                }
            ],
            "element2": [
                {
                    "name": "test_auth_function",
                    "description": "Test should verify authentication with valid and invalid credentials",
                    "code": "def test_auth_function():\n    assert auth_function('user1', 'valid_pass')\n    assert not auth_function('user1', 'invalid_pass')"
                }
            ],
            "element4": [
                {
                    "name": "test_missing_element",
                    "description": "Test for an element not implemented",
                    "code": "def test_missing_element():\n    assert missing_element()"
                }
            ]
        }
        
        # Element IDs for testing
        self.element_ids = {"element1", "element2", "element3", "element4"}
    
    def test_calculate_implementation_metrics(self):
        """Test calculation of implementation metrics."""
        metrics = _calculate_implementation_metrics(
            self.implementation_plan,
            self.element_ids,
            self.architecture_issues,
            self.test_requirements
        )
        
        # Check that all expected metrics exist
        self.assertIn("element_coverage_score", metrics)
        self.assertIn("architecture_issue_addressal_score", metrics)
        self.assertIn("test_coverage_score", metrics)
        self.assertIn("implementation_completeness_score", metrics)
        self.assertIn("overall_score", metrics)
        
        # Check element coverage (3 out of 4 elements implemented)
        self.assertAlmostEqual(metrics["element_coverage_score"], 0.75)
        
        # Check architecture issue addressal (1 out of 2 critical/high issues addressed)
        self.assertAlmostEqual(metrics["architecture_issue_addressal_score"], 0.5)
        
        # Check test coverage (2 out of 3 elements with tests are implemented)
        self.assertAlmostEqual(metrics["test_coverage_score"], 2/3)
        
        # Check implementation completeness (subjective, but should be a value between 0 and 1)
        self.assertGreaterEqual(metrics["implementation_completeness_score"], 0.0)
        self.assertLessEqual(metrics["implementation_completeness_score"], 1.0)
        
        # Check overall score (should be a weighted average)
        self.assertGreaterEqual(metrics["overall_score"], 0.0)
        self.assertLessEqual(metrics["overall_score"], 1.0)
    
    def test_validate_implementation_quality(self):
        """Test validation of implementation quality."""
        # Create metrics with low scores to trigger issues
        metrics = {
            "overall_score": 0.65,
            "element_coverage_score": 0.75,
            "implementation_completeness_score": 0.7,
            "test_coverage_score": 0.5,
            "architecture_issue_addressal_score": 0.5
        }
        
        issues = _validate_implementation_quality(self.implementation_plan, metrics)
        
        # Should have at least one issue due to low overall score
        self.assertGreaterEqual(len(issues), 1)
        
        # Check that issues have the expected fields
        for issue in issues:
            self.assertIn("issue_type", issue)
            self.assertIn("severity", issue)
            self.assertIn("description", issue)
        
        # Check for specific issue types
        issue_types = [issue["issue_type"] for issue in issues]
        self.assertIn("low_quality_score", issue_types)
        
        # Test with minimal steps
        minimal_steps_plan = {
            "file1.py": [
                {
                    "function": "def minimal_function():",
                    "description": "Function with minimal steps",
                    "element_id": "element1",
                    "steps": [
                        {
                            "step_description": "Only one step"
                        }
                    ],
                    "edge_cases": [],
                    "architecture_issues_addressed": []
                }
            ]
        }
        
        issues = _validate_implementation_quality(minimal_steps_plan, metrics)
        
        # Should flag insufficient steps
        insufficient_steps_issues = [issue for issue in issues if issue["issue_type"] == "insufficient_steps"]
        self.assertGreaterEqual(len(insufficient_steps_issues), 1)
    
    def test_validate_implementation_security(self):
        """Test validation of implementation security."""
        issues = _validate_implementation_security(self.implementation_plan, self.architecture_issues)
        
        # Check that we have security issues
        self.assertGreaterEqual(len(issues), 1)
        
        # Check for unaddressed security issue (SC2)
        unaddressed_issues = [issue for issue in issues if issue["issue_type"] == "unaddressed_security_issue"]
        self.assertGreaterEqual(len(unaddressed_issues), 1)
        self.assertEqual(unaddressed_issues[0]["arch_issue_id"], "SC2")
        
        # Check for security validation in auth function
        missing_validation_issues = [issue for issue in issues if issue["issue_type"] == "missing_security_validation"]
        self.assertGreaterEqual(len(missing_validation_issues), 1)
        
        # Create a more secure implementation plan
        secure_plan = {
            "file1.py": [
                {
                    "function": "def auth_function(user_id: str, password: str) -> bool:",
                    "description": "Authenticate user",
                    "element_id": "element2",
                    "steps": [
                        {
                            "step_description": "Validate input parameters",
                            "error_handling_notes": "Raise ValueError for empty credentials"
                        },
                        {
                            "step_description": "Sanitize inputs to prevent injection",
                            "error_handling_notes": ""
                        },
                        {
                            "step_description": "Hash password and compare with stored hash",
                            "error_handling_notes": ""
                        },
                        {
                            "step_description": "Generate and return auth token",
                            "error_handling_notes": ""
                        }
                    ],
                    "edge_cases": ["Handle empty credentials", "Handle expired tokens"],
                    "architecture_issues_addressed": ["SC2"]
                }
            ]
        }
        
        secure_issues = _validate_implementation_security(secure_plan, self.architecture_issues)
        
        # Should have fewer security issues
        self.assertLess(len(secure_issues), len(issues))
    
    def test_validate_implementation_test_alignment(self):
        """Test validation of implementation test alignment."""
        issues = _validate_implementation_test_alignment(self.implementation_plan, self.test_requirements)
        
        # Check for unimplemented tested element (element4)
        unimplemented_issues = [issue for issue in issues if issue["issue_type"] == "unimplemented_tested_element"]
        self.assertGreaterEqual(len(unimplemented_issues), 1)
        self.assertEqual(unimplemented_issues[0]["element_id"], "element4")
        
        # Check for missing test behaviors in the auth function
        # The auth function doesn't have steps that cover "verify authentication with valid and invalid credentials"
        missing_behaviors_issues = [issue for issue in issues if issue["issue_type"] == "missing_test_behaviors"]
        self.assertGreaterEqual(len(missing_behaviors_issues), 1)
        
        # Create an implementation with better test alignment
        aligned_plan = {
            "file1.py": [
                {
                    "function": "def auth_function(user_id: str, password: str) -> bool:",
                    "description": "Authenticate user with valid and invalid credentials",
                    "element_id": "element2",
                    "steps": [
                        {
                            "step_description": "Validate input credentials",
                            "error_handling_notes": ""
                        },
                        {
                            "step_description": "Verify user credentials against database",
                            "error_handling_notes": ""
                        },
                        {
                            "step_description": "Return true for valid credentials and false for invalid ones",
                            "error_handling_notes": ""
                        }
                    ],
                    "edge_cases": ["Handle invalid credentials", "Handle non-existent user"],
                    "architecture_issues_addressed": ["SC2"]
                }
            ]
        }
        
        aligned_issues = _validate_implementation_test_alignment(aligned_plan, {
            "element2": self.test_requirements["element2"]
        })
        
        # Should have fewer test alignment issues
        self.assertEqual(len(aligned_issues), 0)


if __name__ == '__main__':
    unittest.main()
