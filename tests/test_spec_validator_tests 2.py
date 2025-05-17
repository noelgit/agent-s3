"""
Tests the test specification validation features.
"""
import unittest
from unittest import mock
import logging
from typing import Dict, Any

from agent_s3.test_spec_validator import (
    extract_element_ids_from_system_design,
    extract_architecture_issues,
    extract_referenced_element_ids,
    extract_addressed_issues,
    validate_element_ids,
    validate_architecture_issue_coverage,
    validate_test_priority_consistency,
    validate_and_repair_test_specifications
)

class TestSpecValidatorTests(unittest.TestCase):
    
    def setUp(self):
        logging.disable(logging.CRITICAL)  # Disable logging during tests
        
        # Create sample system design with element IDs
        self.sample_system_design = {
            "code_elements": [
                {"element_id": "user_service", "name": "UserService", "description": "Handles user operations"},
                {"element_id": "auth_controller", "name": "AuthController", "description": "Manages authentication"},
                {"element_id": "data_validator", "name": "DataValidator", "description": "Validates input data"}
            ],
            "architecture": {
                "components": [
                    {"element_id": "frontend_component", "name": "Frontend", "description": "UI layer"}
                ]
            }
        }
        
        # Create sample architecture review with issues
        self.sample_architecture_review = {
            "logical_gaps": [
                {
                    "id": "gap_1",
                    "description": "Missing error handling in authentication flow",
                    "severity": "High"
                },
                {
                    "id": "gap_2",
                    "description": "Incomplete validation for user input",
                    "severity": "Medium"
                }
            ],
            "security_concerns": [
                {
                    "id": "sec_1",
                    "description": "Insufficient password hashing",
                    "severity": "Critical"
                }
            ],
            "optimization_opportunities": [
                {
                    "id": "opt_1",
                    "description": "Database query optimization",
                    "severity": "Low"
                }
            ]
        }
        
        # Create sample test specifications with issues
        self.sample_test_specs = {
            "unit_tests": [
                {
                    "description": "Test user login with valid credentials",
                    "target_element": "AuthController",
                    "target_element_id": "auth_controller",
                    "inputs": ["username=valid", "password=valid"],
                    "expected_outcome": "User is authenticated",
                    "architecture_issue_addressed": "sec_1",
                    "priority": "High"  # Should be Critical as the security issue is Critical
                },
                {
                    "description": "Test data validation",
                    "target_element": "DataValidator",
                    "target_element_id": "invalid_id",  # Invalid element ID
                    "inputs": ["data=test"],
                    "expected_outcome": "Data is validated"
                }
            ],
            "integration_tests": [
                {
                    "description": "Test authentication flow",
                    "components_involved": ["AuthController", "UserService"],
                    "target_element_ids": ["auth_controller", "user_service"],
                    "scenario": "User logs in and accesses profile",
                    "architecture_issue_addressed": "gap_1",
                    "priority": "Medium"  # Matches severity of High issue
                }
            ]
        }
    
    def tearDown(self):
        logging.disable(logging.NOTSET)  # Re-enable logging
    
    def test_extract_element_ids_from_system_design(self):
        result = extract_element_ids_from_system_design(self.sample_system_design)
        expected = {"user_service", "auth_controller", "data_validator", "frontend_component"}
        self.assertEqual(result, expected)
    
    def test_extract_architecture_issues(self):
        result = extract_architecture_issues(self.sample_architecture_review)
        self.assertEqual(len(result), 4)  # 2 logical gaps, 1 security concern, 1 optimization
        
        # Check if the security concern with Critical severity is included
        security_issues = [issue for issue in result if issue["issue_type"] == "security_concern"]
        self.assertEqual(len(security_issues), 1)
        self.assertEqual(security_issues[0]["severity"], "Critical")
    
    def test_extract_referenced_element_ids(self):
        result = extract_referenced_element_ids(self.sample_test_specs)
        expected = {"auth_controller", "invalid_id", "user_service"}
        self.assertEqual(result, expected)
    
    def test_extract_addressed_issues(self):
        result = extract_addressed_issues(self.sample_test_specs)
        expected = {"sec_1", "gap_1"}
        self.assertEqual(result, expected)
    
    def test_validate_element_ids(self):
        result = validate_element_ids(self.sample_test_specs, self.sample_system_design)
        self.assertEqual(len(result), 1)  # One invalid element ID (invalid_id)
        self.assertEqual(result[0]["issue_type"], "invalid_element_id")
        self.assertEqual(result[0]["element_id"], "invalid_id")
    
    def test_validate_architecture_issue_coverage(self):
        result = validate_architecture_issue_coverage(self.sample_test_specs, self.sample_architecture_review)
        # There should be no issues for gap_1 and sec_1 as they are covered, but gap_2 is not covered
        self.assertEqual(len(result), 0)  # All critical/high issues are covered
        
        # Add a new critical issue that's not covered and test again
        self.sample_architecture_review["logical_gaps"].append({
            "id": "gap_3",
            "description": "Critical issue not covered",
            "severity": "Critical"
        })
        
        result = validate_architecture_issue_coverage(self.sample_test_specs, self.sample_architecture_review)
        self.assertEqual(len(result), 1)  # One critical issue not covered
        self.assertEqual(result[0]["issue_type"], "unaddressed_critical_issue")
    
    def test_validate_test_priority_consistency(self):
        result = validate_test_priority_consistency(self.sample_test_specs, self.sample_architecture_review)
        self.assertEqual(len(result), 2)  # Two priority mismatches
        
        # Find the Critical/High mismatch for security issue
        sec_mismatch = next((r for r in result if r["expected_priority"] == "Critical"), None)
        self.assertIsNotNone(sec_mismatch)
        self.assertEqual(sec_mismatch["issue_type"], "priority_mismatch")
        self.assertEqual(sec_mismatch["actual_priority"], "High")
        
        # Find the High/Medium mismatch for gap issue
        gap_mismatch = next((r for r in result if r["expected_priority"] == "High"), None)
        self.assertIsNotNone(gap_mismatch)
        self.assertEqual(gap_mismatch["issue_type"], "priority_mismatch")
        self.assertEqual(gap_mismatch["actual_priority"], "Medium")
    
    def test_validate_and_repair_test_specifications(self):
        repaired_specs, issues, was_repaired = validate_and_repair_test_specifications(
            self.sample_test_specs, self.sample_system_design, self.sample_architecture_review
        )
        
        # Check that validation found issues
        self.assertTrue(len(issues) > 0)
        
        # Check that repairs were made
        self.assertTrue(was_repaired)
        
        # Check that priority was updated from High to Critical for the security issue
        self.assertEqual(repaired_specs["unit_tests"][0]["priority"], "Critical")


if __name__ == "__main__":
    unittest.main()
