import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys
from pathlib import Path

from agent_s3.tools.phase_validator import (
    validate_phase_transition,
    validate_user_modifications,
    validate_architecture_implementation,
    validate_test_coverage_against_risk
)

class TestPhaseValidation(unittest.TestCase):
    """Test suite for phase validation functions."""
    
    def test_validate_phase_transition(self):
        """Test validation of pre-planning to planning transition."""
        # Sample pre-planning data with technical constraints
        pre_plan_data = {
            "feature_groups": [
                {"group_name": "Group 1", "features": []}
            ],
            "technical_constraints": {
                "file_exclusions": ["*.config.js", "node_modules/*"]
            }
        }
        
        # Valid feature group
        valid_feature_group = {
            "group_name": "Authentication",
            "group_description": "User authentication features",
            "features": [
                {
                    "name": "User Login",
                    "description": "Allow users to log in",
                    "files_affected": ["src/auth/login.js", "src/components/LoginForm.js"]
                }
            ]
        }
        
        # Invalid feature group - missing required fields
        invalid_feature_group_1 = {
            "group_description": "Missing name",
            "features": []
        }
        
        # Invalid feature group - affects excluded files
        invalid_feature_group_2 = {
            "group_name": "Config",
            "group_description": "Configuration",
            "features": [
                {
                    "name": "Update Config",
                    "description": "Update configuration",
                    "files_affected": ["webpack.config.js", "src/config.js"]
                }
            ]
        }
        
        # Test valid case
        is_valid, message = validate_phase_transition(pre_plan_data, valid_feature_group)
        self.assertTrue(is_valid)
        
        # Test missing fields
        is_valid, message = validate_phase_transition(pre_plan_data, invalid_feature_group_1)
        self.assertFalse(is_valid)
        self.assertIn("Missing required fields", message)
        
        # Test excluded files
        is_valid, message = validate_phase_transition(pre_plan_data, invalid_feature_group_2)
        self.assertFalse(is_valid)
        self.assertIn("affects excluded file", message)
    
    def test_validate_user_modifications(self):
        """Test validation of user modifications."""
        # Valid modification
        valid_modification = "Add error handling for network failures in the authentication module."
        
        # Invalid modification - too short
        invalid_modification_1 = "OK"
        
        # Invalid modification - suggests deleting everything
        invalid_modification_2 = "I hate this plan. Delete everything and start over."
        
        # Test valid case
        is_valid, message = validate_user_modifications(valid_modification)
        self.assertTrue(is_valid)
        
        # Test too short
        is_valid, message = validate_user_modifications(invalid_modification_1)
        self.assertFalse(is_valid)
        self.assertIn("too short", message.lower())
        
        # Test destructive modification
        is_valid, message = validate_user_modifications(invalid_modification_2)
        self.assertFalse(is_valid)
        self.assertTrue(any(pattern in message for pattern in ["delete everything", "start over"]))
    
    def test_validate_architecture_implementation(self):
        """Test validation of architecture-implementation consistency."""
        # Sample architecture review
        architecture = {
            "logical_gaps": [
                {
                    "description": "Error handling for network failures",
                    "impact": "High",
                    "recommendation": "Add try/catch blocks",
                    "affected_components": ["src/api/client.js"]
                }
            ],
            "optimization_suggestions": [
                {
                    "description": "Cache API responses",
                    "benefit": "Improved performance",
                    "implementation_approach": "Use memory cache",
                    "affected_components": ["src/api/client.js"]
                }
            ],
            "additional_considerations": [
                "Security considerations for API keys"
            ]
        }
        
        # Implementation that addresses the concerns
        good_implementation = {
            "src/api/client.js": [
                {
                    "function": "async function fetchData(url)",
                    "description": "Fetch data with error handling and caching",
                    "steps": [
                        "Try to fetch from cache first",
                        "If not in cache, try API call with error handling",
                        "Cache the response",
                        "Return data"
                    ],
                    "edge_cases": [
                        "Network error",
                        "Server error",
                        "Cache expiration"
                    ]
                }
            ]
        }
        
        # Implementation missing error handling
        bad_implementation = {
            "src/api/client.js": [
                {
                    "function": "async function fetchData(url)",
                    "description": "Fetch data from API",
                    "steps": [
                        "Call API",
                        "Return data"
                    ],
                    "edge_cases": []
                }
            ]
        }
        
        # Implementation missing components
        incomplete_implementation = {
            "src/components/DataView.js": [
                {
                    "function": "function DataView(props)",
                    "description": "Display data",
                    "steps": ["Render data"],
                    "edge_cases": []
                }
            ]
        }
        
        # Test valid case
        is_valid, message, details = validate_architecture_implementation(architecture, good_implementation)
        self.assertTrue(is_valid)
        
        # Test implementation missing architecture concerns
        is_valid, message, details = validate_architecture_implementation(architecture, bad_implementation)
        self.assertFalse(is_valid)
        
        # Test missing components
        is_valid, message, details = validate_architecture_implementation(architecture, incomplete_implementation)
        self.assertFalse(is_valid)
        self.assertTrue("src/api/client.js" in details.get("missing_components", []))
    
    def test_validate_test_coverage_against_risk(self):
        """Test validation of test coverage against risk assessment."""
        # Sample risk assessment
        risk_assessment = {
            "critical_files": ["src/auth/login.js", "src/api/client.js"],
            "high_risk_areas": [
                {
                    "name": "Authentication",
                    "components": ["src/auth/login.js", "src/auth/session.js"]
                },
                {
                    "name": "API Communication",
                    "components": ["src/api/client.js"]
                }
            ],
            "edge_cases": True,
            "component_interactions": True,
            "required_test_characteristics": {
                "required_types": ["security", "performance"],
                "required_keywords": ["unauthorized", "injection", "benchmark"],
                "suggested_libraries": ["hypothesis", "pytest-benchmark"]
            }
        }
        
        # Good test coverage
        good_tests = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_success",
                    "description": "Test successful login",
                    "code": "...",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "integration_tests": [
                {
                    "file": "tests/api/client.test.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_client_fetch",
                    "description": "Test API client fetch with error handling",
                    "code": "...",
                    "setup_requirements": "Mock server"
                }
            ],
            "property_based_tests": [
                {
                    "file": "tests/auth/login.property.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_property",
                    "description": "Property tests for login",
                    "code": "...",
                    "setup_requirements": "Property test framework"
                }
            ],
            "acceptance_tests": []
        }
        
        # Missing critical file tests
        incomplete_tests = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_success",
                    "description": "Test successful login",
                    "code": "...",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "integration_tests": [],
            "property_based_tests": [],
            "acceptance_tests": []
        }
        
        # Missing required test types
        missing_test_types = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_success",
                    "description": "Test successful login",
                    "code": "...",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "integration_tests": [
                {
                    "file": "tests/api/client.test.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_client_fetch",
                    "description": "Test API client fetch",
                    "code": "...",
                    "setup_requirements": "Mock server"
                }
            ],
            "property_based_tests": [],
            "acceptance_tests": []
        }
        
        # Tests with required test characteristics
        tests_with_characteristics = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_unauthorized_access",
                    "description": "Test login rejects unauthorized access attempts",
                    "code": "def test_login_unauthorized_access():\n    # Test unauthorized access\n    assert auth.login('invalid', 'wrong') == False",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "security_tests": [
                {
                    "file": "tests/security/test_injection.js", 
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_sql_injection_prevention", 
                    "description": "Test that SQL injection attempts are blocked",
                    "code": "def test_sql_injection_prevention():\n    # Try SQL injection\n    malicious_input = \"' OR 1=1 --\"\n    assert auth.login(malicious_input, 'any') == False",
                    "setup_requirements": "Security test environment"
                }
            ],
            "performance_tests": [
                {
                    "file": "tests/performance/test_auth_benchmark.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_benchmark",
                    "description": "Benchmark API performance",
                    "code": "import pytest_benchmark\n\ndef test_api_benchmark(benchmark):\n    result = benchmark(lambda: api.fetch_data())\n    assert result.duration < 0.1",
                    "setup_requirements": "pytest-benchmark"
                }
            ],
            "integration_tests": [
                {
                    "file": "tests/api/client.test.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_client_fetch",
                    "description": "Test API client fetch with error handling",
                    "code": "from hypothesis import given, strategies as st\n\ndef test_api_client_fetch():\n    response = client.fetch('/test')\n    assert response.status == 200",
                    "setup_requirements": "Mock server, hypothesis"
                }
            ],
            "property_based_tests": [
                {
                    "file": "tests/auth/login.property.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_property",
                    "description": "Property tests for login",
                    "code": "...",
                    "setup_requirements": "Property test framework"
                }
            ],
            "acceptance_tests": []
        }
        
        # Tests missing required keywords
        missing_keyword_tests = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_success",
                    "description": "Test successful login",
                    "code": "def test_login_success():\n    assert auth.login('valid', 'correct') == True",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "security_tests": [
                {
                    "file": "tests/security/test_login_security.js", 
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_security", 
                    "description": "Test login security",
                    "code": "def test_login_security():\n    assert auth.login('invalid', 'wrong') == False",
                    "setup_requirements": "Security test environment"
                }
            ],
            "performance_tests": [
                {
                    "file": "tests/performance/test_auth_speed.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_speed",
                    "description": "Test API speed",
                    "code": "def test_api_speed():\n    start = time.time()\n    api.fetch_data()\n    end = time.time()\n    assert end - start < 0.1",
                    "setup_requirements": "Time measurement"
                }
            ],
            "integration_tests": [
                {
                    "file": "tests/api/client.test.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_client_fetch",
                    "description": "Test API client fetch",
                    "code": "def test_api_client_fetch():\n    response = client.fetch('/test')\n    assert response.status == 200",
                    "setup_requirements": "Mock server"
                }
            ],
            "property_based_tests": [],
            "acceptance_tests": []
        }
        
        # Tests missing suggested libraries
        missing_libraries_tests = {
            "unit_tests": [
                {
                    "file": "tests/auth/login.test.js",
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_login_unauthorized_access",
                    "description": "Test login rejects unauthorized access attempts",
                    "code": "def test_login_unauthorized_access():\n    # Test unauthorized access\n    assert auth.login('invalid', 'wrong') == False",
                    "setup_requirements": "Mock auth service"
                }
            ],
            "security_tests": [
                {
                    "file": "tests/security/test_injection.js", 
                    "implementation_file": "src/auth/login.js",
                    "test_name": "test_sql_injection_prevention", 
                    "description": "Test that SQL injection attempts are blocked",
                    "code": "def test_sql_injection_prevention():\n    # Try SQL injection\n    malicious_input = \"' OR 1=1 --\"\n    assert auth.login(malicious_input, 'any') == False",
                    "setup_requirements": "Security test environment"
                }
            ],
            "performance_tests": [
                {
                    "file": "tests/performance/test_auth_benchmark.js",
                    "implementation_file": "src/api/client.js",
                    "test_name": "test_api_benchmark",
                    "description": "Benchmark API performance",
                    "code": "def test_api_benchmark():\n    start = time.time()\n    api.fetch_data()\n    end = time.time()\n    assert end - start < 0.1",  # No pytest-benchmark
                    "setup_requirements": "Time measurement"
                }
            ],
            "integration_tests": [],
            "property_based_tests": [],
            "acceptance_tests": []
        }
    
        # Test valid case with required test characteristics
        is_valid, message, details = validate_test_coverage_against_risk(tests_with_characteristics, risk_assessment)
        self.assertTrue(is_valid)
        
        # Test missing critical file coverage
        is_valid, message, details = validate_test_coverage_against_risk(incomplete_tests, risk_assessment)
        self.assertFalse(is_valid)
        self.assertIn("src/api/client.js", details.get("uncovered_critical_files", []))
        
        # Test missing required test types
        is_valid, message, details = validate_test_coverage_against_risk(missing_test_types, risk_assessment)
        self.assertFalse(is_valid)
        self.assertTrue("property_based_tests" in message.lower() or "edge cases" in message.lower())
        
        # Test missing required keywords
        is_valid, message, details = validate_test_coverage_against_risk(missing_keyword_tests, risk_assessment)
        self.assertFalse(is_valid)
        self.assertTrue(len(details.get("missing_required_keywords", [])) > 0)
        self.assertIn("benchmark", details.get("missing_required_keywords", []))
        
        # Test missing suggested libraries
        is_valid, message, details = validate_test_coverage_against_risk(missing_libraries_tests, risk_assessment)
        self.assertFalse(is_valid)
        self.assertTrue(len(details.get("missing_suggested_libraries", [])) > 0)
        self.assertIn("pytest-benchmark", details.get("missing_suggested_libraries", []))

if __name__ == "__main__":
    unittest.main()
