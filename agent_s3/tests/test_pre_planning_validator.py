#!/usr/bin/env python3
"""Test for the PrePlanningValidator class."""
import unittest

from agent_s3.pre_planner_json_validator import PrePlannerJsonValidator as PrePlanningValidator

class TestPrePlanningValidator(unittest.TestCase):
    """Tests for the PrePlanningValidator class."""

    def setUp(self):
        """Set up the validator and sample data."""
        self.validator = PrePlanningValidator()

        # Valid test data
        self.valid_data = {
            "feature_groups": [
                {
                    "group_name": "Core Features",
                    "group_description": "Essential functionality for the system",
                    "features": [
                        {
                            "name": "User Authentication",
                            "description": "Allow users to sign up and log in with secure credentials",
                            "complexity": 3,
                            "implementation_steps": [
                                {"id": "s1", "description": "Setup auth API"},
                                {"id": "s2", "description": "Create login form"},
                                {"id": "s3", "description": "Implement session management"}
                            ],
                            "risk_assessment": {
                                "risk_level": "high",
                                "concerns": ["Security vulnerabilities", "Data privacy issues"],
                                "security_concerns": ["password handling"]
                            },
                            "test_requirements": {
                                "unit_tests": [
                                    {
                                        "description": "password hashing validation",
                                        "implementation_step_id": "s1",
                                    },
                                    {
                                        "description": "login validation",
                                        "implementation_step_id": "s2",
                                    }
                                ],
                                "integration_tests": [
                                    {
                                        "description": "auth flow",
                                        "implementation_step_id": "s3",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

    def test_structure_validation_success(self):
        """Test that structure validation passes for valid data."""
        is_valid, errors = self.validator.validate_structure(self.valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_structure_validation_failure(self):
        """Test that structure validation fails for invalid data."""
        invalid_data = {"missing_feature_groups": []}
        is_valid, errors = self.validator.validate_structure(invalid_data)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_complete_validation(self):
        """Test that complete validation works."""
        is_valid, result = self.validator.validate_all(self.valid_data)
        self.assertTrue(is_valid)
        self.assertEqual(result["metadata"]["feature_count"], 1)
        self.assertEqual(result["metadata"]["group_count"], 1)

    def test_complete_validation_structure_failure(self):
        """Validation should aggregate errors when structure is invalid."""
        invalid_data = {
            "feature_groups": [
                {
                    "group_name": "Security",
                    # Missing group_description triggers structure error
                    "features": [
                        {
                            "name": "Auth",  # duplicated below for semantic error
                            "description": "Login system",
                            "complexity": 3,
                            # Missing risk_assessment triggers security error
                        }
                    ],
                },
                {
                    "group_name": "More Security",
                    "group_description": "desc",
                    "features": [
                        {
                            "name": "Auth",  # duplicate name
                            "description": "Another",
                            "complexity": 2,
                        }
                    ],
                },
            ]
        }

        is_valid, result = self.validator.validate_all(invalid_data)
        self.assertFalse(is_valid)
        self.assertGreater(len(result["errors"]["structure"]), 0)
        self.assertGreater(len(result["errors"]["semantic"]), 0)
        self.assertGreater(len(result["errors"]["security"]), 0)

if __name__ == "__main__":
    unittest.main()
