import unittest
import json

from agent_s3.tools.security_validator import (
    validate_cross_phase_security,
    validate_security_testing_coverage,
    _extract_security_concerns,
    _extract_tested_concerns,
    _analyze_security_test_coverage,
    _calculate_security_score,
    generate_security_report
)

class TestSecurityValidator(unittest.TestCase):
    """Test suite for security validator functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Sample architecture review with security concerns
        self.architecture_review = {
            "security_concerns": [
                {
                    "id": "SC1",
                    "description": "Input validation needed",
                    "impact": "Could allow injection attacks",
                    "severity": "Critical",
                    "recommendation": "Implement input validation",
                    "affected_elements": ["user_service"]
                },
                {
                    "id": "SC2",
                    "description": "Authentication mechanism is weak",
                    "impact": "Unauthorized access risk",
                    "severity": "High",
                    "recommendation": "Use strong authentication",
                    "affected_elements": ["auth_controller"]
                },
                {
                    "id": "SC3",
                    "description": "Logging insufficient for audit",
                    "impact": "Difficult to track security events",
                    "severity": "Medium",
                    "recommendation": "Enhance logging",
                    "affected_elements": ["logging_service"]
                }
            ],
            "logical_gaps": [
                {
                    "id": "LG1",
                    "description": "Error handling needs security improvements",
                    "impact": "Information disclosure risk",
                    "severity": "Medium",
                    "recommendation": "Implement secure error handling",
                    "affected_elements": ["error_handler"]
                }
            ]
        }
        
        # Sample implementation plan
        self.implementation_plan = {
            "user_service.py": [
                {
                    "function": "def validate_user_input(data: Dict):",
                    "description": "Validate user input to prevent injection",
                    "element_id": "user_service",
                    "steps": [
                        {
                            "step_description": "Sanitize input to prevent SQL injection",
                            "error_handling_notes": "Raise ValidationError for invalid input"
                        },
                        {
                            "step_description": "Validate input format",
                            "error_handling_notes": "Log validation failures"
                        }
                    ],
                    "edge_cases": ["Empty input", "Special characters"],
                    "architecture_issues_addressed": ["SC1"]
                }
            ],
            "auth_controller.py": [
                {
                    "function": "def authenticate_user(username: str, password: str) -> bool:",
                    "description": "Authenticate user with credentials",
                    "element_id": "auth_controller",
                    "steps": [
                        {
                            "step_description": "Verify password hash",
                            "error_handling_notes": ""
                        }
                    ],
                    "edge_cases": ["Invalid credentials"],
                    "architecture_issues_addressed": ["SC2"]
                }
            ]
        }
        
        # Sample test implementations
        self.test_implementations = {
            "tests": {
                "unit_tests": [
                    {
                        "file": "test_user_service.py",
                        "test_name": "test_validate_user_input",
                        "description": "Test input validation prevents SQL injection",
                        "target_element_ids": ["user_service"],
                        "code": "def test_validate_user_input():\n    with pytest.raises(ValidationError):\n        validate_user_input({\"input\": \"'; DROP TABLE users; --\"})",
                        "architecture_issues_addressed": ["SC1"]
                    }
                ],
                "security_tests": [
                    {
                        "file": "test_auth_security.py",
                        "test_name": "test_auth_brute_force_prevention",
                        "description": "Test authentication brute force prevention",
                        "target_element_ids": ["auth_controller"],
                        "code": "def test_auth_brute_force_prevention():\n    for _ in range(10):\n        assert not authenticate_user('admin', 'wrong_password')\n    # Check account is temporarily locked\n    assert get_account_status('admin') == 'locked'",
                        "architecture_issues_addressed": ["SC2"]
                    }
                ]
            }
        }
        
        # Sample with missing test coverage
        self.test_implementations_incomplete = {
            "tests": {
                "unit_tests": [
                    {
                        "file": "test_user_service.py",
                        "test_name": "test_validate_user_input",
                        "description": "Test input validation prevents SQL injection",
                        "target_element_ids": ["user_service"],
                        "code": "def test_validate_user_input():\n    with pytest.raises(ValidationError):\n        validate_user_input({\"input\": \"'; DROP TABLE users; --\"})",
                        "architecture_issues_addressed": ["SC1"]
                    }
                ]
            }
        }
        
        # Sample with implementation missing security
        self.implementation_plan_incomplete = {
            "user_service.py": [
                {
                    "function": "def validate_user_input(data: Dict):",
                    "description": "Validate user input",
                    "element_id": "user_service",
                    "steps": [
                        {
                            "step_description": "Check input format",
                            "error_handling_notes": "Log validation failures"
                        }
                    ],
                    "edge_cases": ["Empty input"],
                    "architecture_issues_addressed": ["SC1"]
                }
            ]
        }

    def test_extract_security_concerns(self):
        """Test extraction of security concerns from architecture review."""
        concerns = _extract_security_concerns(self.architecture_review)
        
        # Check if all concerns are extracted
        self.assertEqual(len(concerns), 4)  # 3 explicit security concerns + 1 security-related logical gap
        
        # Check if security concerns have correct issue_type
        for concern in concerns:
            self.assertEqual(concern["issue_type"], "security_concern")
        
        # Check if logical gap with security relevance is included
        security_gap_ids = [concern["id"] for concern in concerns]
        self.assertIn("LG1", security_gap_ids)

    def test_extract_tested_concerns(self):
        """Test extraction of security concerns that have tests."""
        concerns = _extract_security_concerns(self.architecture_review)
        tested_concerns = _extract_tested_concerns(self.test_implementations, concerns)
        
        # Check if both explicitly tested concerns are detected
        self.assertEqual(len(tested_concerns), 2)
        self.assertIn("SC1", tested_concerns)
        self.assertIn("SC2", tested_concerns)

    def test_validate_cross_phase_security_valid(self):
        """Test validation of cross-phase security with valid data."""
        is_valid, validation_details, issues = validate_cross_phase_security(
            self.architecture_review,
            self.implementation_plan,
            self.test_implementations
        )
        
        # Should be valid since critical/high security concerns are addressed in both implementation and testing
        self.assertTrue(is_valid)
        
        # Check if score is calculated
        self.assertGreater(validation_details["overall_security_score"], 0.0)
        
        # There might be some medium/low issues but not critical/high
        critical_high_issues = [i for i in issues if i["severity"] in ["critical", "high"]]
        self.assertEqual(len(critical_high_issues), 0)

    def test_validate_cross_phase_security_invalid(self):
        """Test validation of cross-phase security with invalid data."""
        is_valid, validation_details, issues = validate_cross_phase_security(
            self.architecture_review,
            self.implementation_plan_incomplete,  # Missing proper security steps
            self.test_implementations_incomplete  # Missing SC2 test coverage
        )
        
        # Should be invalid due to missing security implementation and test coverage
        self.assertFalse(is_valid)
        
        # Check for specific issues
        issue_types = [issue["issue_type"] for issue in issues]
        self.assertIn("critical_concern_not_tested", issue_types)  # SC2 is high severity but not tested

    def test_validate_security_testing_coverage(self):
        """Test validation of security testing coverage."""
        concerns = _extract_security_concerns(self.architecture_review)
        
        # Complete test coverage for critical/high concerns
        complete_issues = validate_security_testing_coverage(self.test_implementations, concerns)
        critical_high_issues = [i for i in complete_issues if i["severity"] in ["critical", "high"]]
        self.assertEqual(len(critical_high_issues), 0)
        
        # Incomplete test coverage missing high severity concern (SC2)
        incomplete_issues = validate_security_testing_coverage(self.test_implementations_incomplete, concerns)
        critical_high_issues = [i for i in incomplete_issues if i["severity"] in ["critical", "high"]]
        self.assertGreater(len(critical_high_issues), 0)
        
        # Check for specific issue type
        issue_types = [issue["issue_type"] for issue in incomplete_issues]
        self.assertIn("untested_security_concern", issue_types)

    def test_analyze_security_test_coverage(self):
        """Test analysis of security test coverage."""
        coverage = _analyze_security_test_coverage(self.test_implementations)
        
        # Should detect security tests
        self.assertGreater(coverage["security_test_count"], 0)
        
        # Should detect OWASP categories
        self.assertGreater(len(coverage["owasp_categories"]), 0)
        
        # Check for specific test types
        self.assertIn("security_tests", coverage["test_types"])

    def test_calculate_security_score(self):
        """Test calculation of security score."""
        # Create validation details with perfect coverage
        perfect_details = {
            "phases": {
                "architecture": {
                    "total_security_concerns": 3,
                    "properly_documented_concerns": 3,
                    "missing_critical_security_aspects": []
                },
                "implementation": {
                    "coverage_ratio": 1.0
                },
                "testing": {
                    "coverage_ratio": 1.0
                }
            },
            "cross_phase_issues": []
        }
        
        # Create validation details with poor coverage
        poor_details = {
            "phases": {
                "architecture": {
                    "total_security_concerns": 3,
                    "properly_documented_concerns": 1,
                    "missing_critical_security_aspects": ["Authentication", "Authorization"]
                },
                "implementation": {
                    "coverage_ratio": 0.5
                },
                "testing": {
                    "coverage_ratio": 0.3
                }
            },
            "cross_phase_issues": ["Issue 1", "Issue 2", "Issue 3"]
        }
        
        perfect_score = _calculate_security_score(perfect_details)
        poor_score = _calculate_security_score(poor_details)
        
        # Perfect score should be close to 1.0
        self.assertGreater(perfect_score, 0.9)
        
        # Poor score should be much lower
        self.assertLess(poor_score, 0.7)
        
        # Perfect score should be higher than poor score
        self.assertGreater(perfect_score, poor_score)

    def test_generate_security_report(self):
        """Test generation of security report."""
        # Test JSON report
        json_report = generate_security_report(
            self.architecture_review,
            self.implementation_plan,
            self.test_implementations,
            "json"
        )
        
        # Ensure it's valid JSON
        try:
            report_data = json.loads(json_report)
            self.assertIn("summary", report_data)
            self.assertIn("security_concerns", report_data)
            self.assertIn("issues", report_data)
        except json.JSONDecodeError:
            self.fail("JSON report is not valid JSON")
        
        # Test Markdown report
        md_report = generate_security_report(
            self.architecture_review,
            self.implementation_plan,
            self.test_implementations,
            "markdown"
        )
        
        # Basic check for markdown format
        self.assertIn("# Security Validation Report", md_report)
        self.assertIn("## Summary", md_report)
        self.assertIn("Security Score", md_report)


if __name__ == "__main__":
    unittest.main()
