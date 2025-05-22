#!/usr/bin/env python3
"""Test the PrePlanningValidator with more complex and error-prone data."""

import unittest
from agent_s3.pre_planning_validator import PrePlanningValidator

class TestComplexValidation(unittest.TestCase):
    """Tests for complex validation scenarios."""
    
    def setUp(self):
        """Set up the validator and sample data."""
        self.validator = PrePlanningValidator()
        
    def test_security_validation(self):
        """Test security validation catches security issues."""
        data = {
            "feature_groups": [
                {
                    "group_name": "Security Features",
                    "group_description": "Security functionality for the system",
                    "features": [
                        {
                            "name": "User Authentication",
                            "description": "Secure login system with password handling",
                            "complexity": 3,
                            # Missing risk assessment for a security feature
                        }
                    ]
                }
            ]
        }
        
        # Security validation should fail
        is_valid, errors = self.validator.validate_security(data)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)
        
    def test_semantic_coherence(self):
        """Test semantic coherence validation."""
        data = {
            "feature_groups": [
                {
                    "group_name": "Features Group A",
                    "group_description": "First group",
                    "features": [
                        {
                            "name": "Duplicate Feature",
                            "description": "Feature with duplicate name",
                            "complexity": 1
                        }
                    ]
                },
                {
                    "group_name": "Features Group B",
                    "group_description": "Second group",
                    "features": [
                        {
                            "name": "Duplicate Feature",  # Duplicate name
                            "description": "Another feature with same name",
                            "complexity": 2
                        }
                    ]
                }
            ]
        }
        
        # Semantic validation should fail due to duplicate names
        is_valid, errors = self.validator.validate_semantic_coherence(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("Duplicate feature name" in error for error in errors))

if __name__ == "__main__":
    unittest.main()
