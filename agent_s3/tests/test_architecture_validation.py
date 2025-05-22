"""
Test cases for the architecture review validation system.
"""

import unittest

from agent_s3.tools.phase_validator import validate_security_concerns
from agent_s3.test_spec_validator import (
    validate_priority_alignment, 
    validate_architecture_issue_coverage,
    validate_and_repair_test_specifications
)

class TestArchitectureReviewValidation(unittest.TestCase):
    """Test cases for architecture review validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Sample architecture review with security concerns
        self.architecture_review = {
            "logical_gaps": [
                {
                    "id": "GAP-1",
                    "description": "Error handling is inconsistent across modules",
                    "severity": "Medium"
                }
            ],
            "security_concerns": [
                {
                    "id": "SEC-1",
                    "description": "User input is not validated before processing",
                    "impact": "Could lead to injection attacks",
                    "recommendation": "Implement input validation",
                    "target_element_ids": ["input_processor"],
                    "severity": "High"
                },
                {
                    "id": "SEC-2",
                    "description": "Authentication tokens not checked for expiration",
                    "impact": "Expired tokens could be reused",
                    "recommendation": "Add token expiration validation",
                    "target_element_ids": ["auth_validator"],
                    "severity": "Critical"
                }
            ]
        }
        
        # Sample test specifications
        self.test_specs = {
            "unit_tests": [
                {
                    "description": "Test input validation",
                    "target_element_id": "input_processor",
                    "architecture_issue_addressed": "SEC-1",
                    "priority": "Medium"  # Should be High
                }
            ],
            "integration_tests": [
                {
                    "description": "Test token validation",
                    "target_element_ids": ["auth_validator"],
                    "architecture_issue_addressed": "SEC-2",
                    "priority": "Critical"  # Correct priority
                }
            ]
        }
        
        # Sample system design
        self.system_design = {
            "code_elements": [
                {"element_id": "input_processor", "name": "InputProcessor"},
                {"element_id": "auth_validator", "name": "AuthTokenValidator"}
            ]
        }
    
    def test_security_concerns_validation(self):
        """Test validation of security concerns."""
        is_valid, error_message, details = validate_security_concerns(self.architecture_review)
        
        # All security concerns are properly documented
        self.assertTrue(is_valid)
        self.assertEqual(details["total_security_concerns"], 2)
        self.assertEqual(details["properly_documented_concerns"], 2)
        
        # Test with incomplete security concern
        incomplete_review = {
            "security_concerns": [
                {
                    "id": "SEC-1",
                    "description": "User input is not validated before processing",
                    # Missing impact and recommendation
                    "target_element_ids": ["input_processor"],
                    "severity": "High"
                }
            ]
        }
        
        is_valid, error_message, details = validate_security_concerns(incomplete_review)
        
        # Should fail validation
        self.assertFalse(is_valid)
        self.assertEqual(details["properly_documented_concerns"], 0)
        self.assertEqual(len(details["incomplete_security_concerns"]), 1)
    
    def test_priority_alignment(self):
        """Test validation of priority alignment between architecture issues and tests."""
        validation_issues = validate_priority_alignment(self.test_specs, self.architecture_review)
        
        # Should have one issue with the unit test priority
        self.assertEqual(len(validation_issues), 1)
        self.assertEqual(validation_issues[0]["issue_type"], "priority_alignment")
        self.assertEqual(validation_issues[0]["test_priority"], "Medium")
        self.assertIn("High", validation_issues[0]["allowed_priorities"])
    
    def test_architecture_issue_coverage(self):
        """Test validation of architecture issue coverage."""
        validation_issues = validate_architecture_issue_coverage(self.test_specs, self.architecture_review)
        
        # All critical issues are addressed by tests
        self.assertEqual(len(validation_issues), 0)
        
        # Test with missing coverage for a critical issue
        self.architecture_review["security_concerns"].append({
            "id": "SEC-3",
            "description": "Unaddressed security issue",
            "impact": "Security vulnerability",
            "recommendation": "Fix it",
            "target_element_ids": ["missing_element"],
            "severity": "Critical",
            "issue_type": "security_concern"
        })
        
        validation_issues = validate_architecture_issue_coverage(self.test_specs, self.architecture_review)
        
        # Should now have an issue for the unaddressed critical security concern
        self.assertEqual(len(validation_issues), 1)
        self.assertEqual(validation_issues[0]["issue_type"], "unaddressed_critical_issue")
        self.assertEqual(validation_issues[0]["severity"], "Critical")
    
    def test_validate_and_repair(self):
        """Test validation and repair of test specifications."""
        repaired_specs, validation_issues, was_repaired = validate_and_repair_test_specifications(
            self.test_specs, self.system_design, self.architecture_review
        )
        
        # Should repair the priority alignment issue
        self.assertTrue(was_repaired)
        self.assertEqual(len(validation_issues), 1)
        
        # Check that the priority was fixed
        self.assertEqual(repaired_specs["unit_tests"][0]["priority"], "High")

if __name__ == "__main__":
    unittest.main()
