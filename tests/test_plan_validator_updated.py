"""
Plan validator test module for Agent-S3.
Tests the functionality of the plan validator component.
"""
import os
import json
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.tools.plan_validator.validator import PlanValidator

class TestPlanValidator:
    """Test suite for the PlanValidator class."""
    
    def setup_method(self):
        """Setup before each test method."""
        self.validator = PlanValidator()
        
        # Sample valid plan
        self.valid_plan = {
            "plan": {
                "architecture_review": {
                    "description": "Overall system architecture for user authentication",
                    "components": [
                        {
                            "name": "AuthService",
                            "responsibilities": ["User authentication", "Token validation"],
                            "interfaces": ["login(credentials)", "validateToken(token)"]
                        }
                    ],
                    "data_flow": "Client -> AuthService -> Database",
                    "security_considerations": ["Use HTTPS", "Hash passwords"]
                },
                "implementation_plan": {
                    "steps": [
                        {
                            "id": "step1",
                            "description": "Create AuthService class",
                            "file_path": "src/auth/AuthService.js",
                            "estimated_time": "2 hours"
                        }
                    ]
                },
                "testing_strategy": {
                    "unit_tests": ["Test login success", "Test login failure"],
                    "integration_tests": ["Test auth flow end-to-end"]
                }
            }
        }
        
        # Sample invalid plan (missing required sections)
        self.invalid_plan = {
            "plan": {
                "architecture_review": {
                    "description": "Overall system architecture for user authentication"
                }
            }
        }
    
    def test_validate_plan_structure_valid(self):
        """Test plan structure validation with a valid plan."""
        result, errors = self.validator.validate_plan_structure(self.valid_plan)
        assert result is True
        assert not errors
    
    def test_validate_plan_structure_invalid(self):
        """Test plan structure validation with an invalid plan."""
        result, errors = self.validator.validate_plan_structure(self.invalid_plan)
        assert result is False
        assert any("missing required section" in error.lower() for error in errors)
    
    def test_validate_implementation_steps(self):
        """Test validation of implementation steps."""
        steps = self.valid_plan["plan"]["implementation_plan"]["steps"]
        result, errors = self.validator.validate_implementation_steps(steps)
        assert result is True
        assert not errors
        
        # Test with invalid steps (missing id)
        invalid_steps = [{"description": "Create class", "file_path": "src/auth.js"}]
        result, errors = self.validator.validate_implementation_steps(invalid_steps)
        assert result is False
        assert any("missing required field" in error.lower() for error in errors)
    
    def test_validate_architecture_review(self):
        """Test validation of architecture review section."""
        arch_review = self.valid_plan["plan"]["architecture_review"]
        result, errors = self.validator.validate_architecture_review(arch_review)
        assert result is True
        assert not errors
        
        # Test with invalid architecture review (missing components)
        invalid_arch = {"description": "Authentication system"}
        result, errors = self.validator.validate_architecture_review(invalid_arch)
        assert result is False
        assert any("components" in error.lower() for error in errors)
    
    def test_validate_testing_strategy(self):
        """Test validation of testing strategy section."""
        testing = self.valid_plan["plan"]["testing_strategy"]
        result, errors = self.validator.validate_testing_strategy(testing)
        assert result is True
        assert not errors
        
        # Test with invalid testing strategy (empty tests)
        invalid_testing = {"unit_tests": [], "integration_tests": []}
        result, errors = self.validator.validate_testing_strategy(invalid_testing)
        assert result is False
        assert any("no tests specified" in error.lower() for error in errors)
    
    @patch('agent_s3.tools.plan_validator.validator.PlanValidator.validate_plan_structure')
    @patch('agent_s3.tools.plan_validator.validator.PlanValidator.validate_implementation_steps')
    @patch('agent_s3.tools.plan_validator.validator.PlanValidator.validate_architecture_review')
    @patch('agent_s3.tools.plan_validator.validator.PlanValidator.validate_testing_strategy')
    def test_validate_full_plan(self, mock_test, mock_arch, mock_impl, mock_struct):
        """Test the full plan validation process with mocks."""
        # All validations pass
        mock_struct.return_value = (True, [])
        mock_impl.return_value = (True, [])
        mock_arch.return_value = (True, [])
        mock_test.return_value = (True, [])
        
        result, errors = self.validator.validate_full_plan(self.valid_plan)
        assert result is True
        assert not errors
        
        # One validation fails
        mock_struct.return_value = (True, [])
        mock_impl.return_value = (False, ["Invalid step"])
        mock_arch.return_value = (True, [])
        mock_test.return_value = (True, [])
        
        result, errors = self.validator.validate_full_plan(self.valid_plan)
        assert result is False
        assert "Invalid step" in errors
