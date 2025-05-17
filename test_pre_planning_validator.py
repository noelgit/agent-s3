#!/usr/bin/env python3
"""Test for the PrePlanningValidator class."""

import unittest
from agent_s3.pre_planning_validator import PrePlanningValidator, ValidationError

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
                            "implementation_steps": ["Setup auth API", "Create login form", "Implement session management"],
                            "risk_assessment": {
                                "risk_level": "high",
                                "concerns": ["Security vulnerabilities", "Data privacy issues"]
                            },
                            "test_requirements": {
                                "unit_tests": ["Test password hashing", "Test login validation"],
                                "integration_tests": ["Test auth flow"]
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

if __name__ == "__main__":
    unittest.main()
