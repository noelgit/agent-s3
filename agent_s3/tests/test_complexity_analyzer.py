#!/usr/bin/env python3
"""Test for the ComplexityAnalyzer class."""
import unittest

from agent_s3.complexity_analyzer import ComplexityAnalyzer

class TestComplexityAnalyzer(unittest.TestCase):
    """Tests for the ComplexityAnalyzer class."""

    def setUp(self):
        """Set up the analyzer and sample data."""
        self.analyzer = ComplexityAnalyzer()

        # Sample low-complexity data
        self.low_complexity_data = {
            "feature_groups": [
                {
                    "group_name": "Simple Features",
                    "group_description": "Basic functionality",
                    "features": [
                        {
                            "name": "Simple UI Update",
                            "description": "Update button color and text",
                            "complexity": 1,
                            "implementation_steps": [
                                {"description": "Change button color", "file_path": "src/components/Button.js"}
                            ]
                        }
                    ]
                }
            ]
        }

        # Sample high-complexity data
        self.high_complexity_data = {
            "feature_groups": [
                {
                    "group_name": "Security Features",
                    "group_description": "Authentication and authorization",
                    "features": [
                        {
                            "name": "OAuth Integration",
                            "description": "Implement OAuth2 with JWT tokens for secure API authorization",
                            "complexity": 4,
                            "implementation_steps": [
                                {"description": "Setup OAuth endpoints", "file_path": "src/auth/oauth.js"},
                                {"description": "Create JWT validation", "file_path": "src/auth/jwt.js"},
                                {"description": "Implement token storage", "file_path": "src/auth/token-store.js"},
                                {"description": "Create authentication middleware", "file_path": "src/middleware/auth.js"},
                                {"description": "Update user model", "file_path": "src/models/user.js"},
                                {"description": "Add protected routes", "file_path": "src/routes/protected.js"}
                            ]
                        },
                        {
                            "name": "Password Policy",
                            "description": "Implement secure password policy with encryption and validation",
                            "complexity": 3,
                            "implementation_steps": [
                                {"description": "Create password validator", "file_path": "src/auth/password.js"},
                                {"description": "Implement password hashing", "file_path": "src/auth/encryption.js"},
                                {"description": "Create password reset flow", "file_path": "src/auth/reset.js"}
                            ]
                        }
                    ]
                }
            ]
        }

    def test_low_complexity_assessment(self):
        """Test that low complexity tasks are assessed correctly."""
        result = self.analyzer.assess_complexity(self.low_complexity_data, "Update the button styling")
        self.assertLess(result["score"], 40)
        self.assertLessEqual(result["level"], 2)
        self.assertFalse(result["is_complex"])

    def test_high_complexity_assessment(self):
        """Test that high complexity tasks are assessed correctly."""
        result = self.analyzer.assess_complexity(
            self.high_complexity_data,
            "Implement secure authentication system with OAuth2 integration and database transaction support"
        )
        self.assertGreater(result["score"], 40)
        self.assertGreaterEqual(result["level"], 3)
        self.assertTrue(result["is_complex"])

    def test_security_factor_detection(self):
        """Test that security terms are properly detected and increase complexity."""
        # Add security terms to description
        security_description = "Implement login system with password encryption and token authentication"
        result = self.analyzer.assess_complexity(self.low_complexity_data, security_description)

        # Ensure security factor is present and non-zero
        self.assertIn("security_sensitivity", result["factors"])
        self.assertGreater(result["factors"]["security_sensitivity"], 0)

if __name__ == "__main__":
    unittest.main()
