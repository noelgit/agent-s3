"""Unit tests for the static plan validator.

Tests the validation functions for Pre-Planner outputs.
"""

import tempfile
import pytest
from unittest.mock import patch

from agent_s3.tools.plan_validator import (
    validate_pre_plan,
    validate_schema,
    validate_identifier_hygiene,
    validate_path_validity,
    validate_token_budget,
    validate_duplicate_symbols,
    validate_reserved_prefixes,
    validate_stub_test_coherence,
    validate_complexity_sanity,
    write_junit_report,
    create_github_annotations
)


class TestPlanValidator:
    """Test class for plan validator module."""
    
    @pytest.fixture
    def valid_plan_data(self):
        """Fixture providing valid plan data for testing."""
        return {
            "original_request": "Implement user authentication",
            "feature_groups": [
                {
                    "group_name": "Authentication",
                    "group_description": "User authentication features",
                    "features": [
                        {
                            "name": "User Login",
                            "description": "Implement user login functionality",
                            "files_affected": ["auth.py", "login.py", "templates/login.html"],
                            "est_tokens": 1500,
                            "complexity_enum": 0,
                            "test_requirements": {
                                "unit": ["Test password validation"],
                                "integration": ["Test login flow"],
                                "property_based": ["Test with varied inputs"],
                                "acceptance": [
                                    {
                                        "given": "A user with valid credentials",
                                        "when": "The user submits login form",
                                        "then": "The user is authenticated and redirected"
                                    }
                                ]
                            },
                            "dependencies": {
                                "internal": ["user_model"],
                                "external": ["passlib"],
                                "feature_dependencies": []
                            },
                            "risk_assessment": {
                                "critical_files": ["auth.py"],
                                "potential_regressions": ["Authentication bypass"],
                                "backward_compatibility_concerns": ["API changes"],
                                "mitigation_strategies": ["Extensive testing"]
                            },
                            "system_design": """
                            def authenticate_user(username: str, password: str) -> bool:
                                \"\"\"Authenticate a user with username and password.
                                
                                Args:
                                    username: The username to check
                                    password: The password to validate
                                    
                                Returns:
                                    True if authentication succeeds, False otherwise
                                \"\"\"
                                # Test-specific function
                                user = get_user_by_username(username)
                                if not user:
                                    return False
                                return verify_password(password, user.password_hash)
                            """
                        }
                    ]
                }
            ]
        }
    
    @pytest.fixture
    def invalid_plan_data(self):
        """Fixture providing invalid plan data for testing."""
        return {
            "original_request": "Implement user authentication",
            "feature_groups": [
                {
                    "group_name": "Authentication",
                    "group_description": "User authentication features",
                    "features": [
                        {
                            "name": "User Login",
                            "description": "Implement user login functionality",
                            "files_affected": ["/absolute/path/auth.py"],  # Invalid absolute path
                            "est_tokens": 3000,  # Too high for trivial complexity
                            "complexity_enum": 0,
                            "test_requirements": {
                                "unit": ["Test password validation"],
                                "integration": ["Test login flow"],
                                "property_based": ["Test with varied inputs"],
                                "acceptance": [
                                    {
                                        "given": "A user with valid credentials",
                                        "when": "The user submits login form",
                                        "then": "The user is authenticated and redirected"
                                    }
                                ]
                            },
                            "dependencies": {
                                "internal": ["user_model"],
                                "external": ["passlib"],
                                "feature_dependencies": []
                            },
                            "risk_assessment": {
                                "critical_files": ["auth.py"],
                                "potential_regressions": ["Authentication bypass"],
                                "backward_compatibility_concerns": ["API changes"],
                                "mitigation_strategies": ["Extensive testing"]
                            },
                            "system_design": """
                            def for(username: str, password: str) -> bool:
                                \"\"\"Invalid function name (Python keyword).\"\"\"
                                return True
                                
                            def authenticate_user(username: str, password: str) -> bool:
                                \"\"\"This will conflict with a duplicate name below\"\"\"
                                return True
                                
                            def authenticate_user(email: str, password: str) -> bool:
                                \"\"\"Duplicate function name\"\"\"
                                return True
                                
                            # Missing test coverage for this function
                            def reset_password(user_id: int, new_password: str) -> bool:
                                return True
                                
                            # Environment variable with reserved name
                            os.environ.get("PATH")
                                
                            # Environment variable with lowercase start (invalid)
                            os.getenv("dbPassword")
                            """
                        }
                    ]
                },
                {
                    "group_name": "Authentication",  # Duplicate group name
                    "group_description": "Duplicate group",
                    "features": []
                }
            ]
        }

    def test_validate_schema_valid(self, valid_plan_data):
        """Test schema validation with valid data."""
        errors = validate_schema(valid_plan_data)
        assert len(errors) == 0
    
    def test_validate_schema_invalid(self):
        """Test schema validation with invalid data."""
        # Missing required fields
        invalid_data = {
            "feature_groups": []
        }
        errors = validate_schema(invalid_data)
        assert len(errors) > 0
        assert any("Missing required field 'original_request'" in error for error in errors)
        
        # Invalid types
        invalid_data = {
            "original_request": 123,  # Should be string
            "feature_groups": "not a list"  # Should be list
        }
        errors = validate_schema(invalid_data)
        assert len(errors) > 0
        assert any("must be a string" in error for error in errors)
        assert any("must be a list" in error for error in errors)
    
    def test_validate_identifier_hygiene_valid(self, valid_plan_data):
        """Test identifier hygiene validation with valid data."""
        errors = validate_identifier_hygiene(valid_plan_data)
        assert len(errors) == 0
    
    def test_validate_identifier_hygiene_invalid(self, invalid_plan_data):
        """Test identifier hygiene validation with invalid data."""
        errors = validate_identifier_hygiene(invalid_plan_data)
        assert len(errors) > 0
        assert any("Duplicate feature group name" in error for error in errors)
        assert any("is a reserved Python keyword" in error for error in errors)
        assert any("Duplicate function/class name" in error for error in errors)
    
    @patch('glob.glob')
    def test_validate_path_validity(self, mock_glob, valid_plan_data):
        """Test path validity validation."""
        # Mock successful glob match
        mock_glob.return_value = ["auth.py"]
        
        # Valid paths
        errors = validate_path_validity(valid_plan_data, "/repo/root")
        assert len(errors) == 0
        
        # Invalid absolute path
        invalid_data = {
            "feature_groups": [
                {
                    "features": [
                        {
                            "files_affected": ["/absolute/path/file.py"]
                        }
                    ]
                }
            ]
        }
        errors = validate_path_validity(invalid_data, "/repo/root")
        assert len(errors) > 0
        assert any("Absolute path not allowed" in error for error in errors)
    
    def test_validate_token_budget_valid(self, valid_plan_data):
        """Test token budget validation with valid data."""
        errors = validate_token_budget(valid_plan_data)
        assert len(errors) == 0
    
    def test_validate_token_budget_invalid(self, invalid_plan_data):
        """Test token budget validation with invalid data."""
        errors = validate_token_budget(invalid_plan_data)
        assert len(errors) > 0
        assert any("exceeds token budget" in error for error in errors)
        
        # Global budget exceeded
        high_tokens = {
            "feature_groups": [
                {
                    "features": [
                        {"est_tokens": 50000, "complexity_enum": 3},
                        {"est_tokens": 60000, "complexity_enum": 3}
                    ]
                }
            ],
            "token_budget": 100000
        }
        errors = validate_token_budget(high_tokens)
        assert len(errors) > 0
        assert any("exceeds global budget" in error for error in errors)
    
    def test_validate_duplicate_symbols(self, invalid_plan_data):
        """Test duplicate symbols validation."""
        errors = validate_duplicate_symbols(invalid_plan_data)
        assert len(errors) > 0
        assert any("is defined in multiple features" in error for error in errors)
    
    def test_validate_reserved_prefixes(self, invalid_plan_data):
        """Test reserved prefixes validation."""
        errors = validate_reserved_prefixes(invalid_plan_data)
        assert len(errors) > 0
        assert any("is a system-reserved name" in error for error in errors)
        assert any("should start with an uppercase letter" in error for error in errors)
    
    def test_validate_stub_test_coherence(self, invalid_plan_data):
        """Test stub/test coherence validation."""
        errors = validate_stub_test_coherence(invalid_plan_data)
        assert len(errors) > 0
        assert any("has no corresponding tests" in error for error in errors)
    
    def test_validate_complexity_sanity(self, invalid_plan_data):
        """Test complexity sanity validation."""
        errors = validate_complexity_sanity(invalid_plan_data)
        assert len(errors) > 0
        assert any("marked as trivial but has" in error for error in errors)
    
    def test_write_junit_report(self):
        """Test writing JUnit XML report."""
        with tempfile.NamedTemporaryFile(suffix='.xml') as tmp:
            errors = ["Error 1", "Error 2"]
            result = write_junit_report(errors, tmp.name)
            assert result is True
            
            # Read the file and check if it contains the errors
            with open(tmp.name, 'r') as f:
                content = f.read()
                assert "Error 1" in content
                assert "Error 2" in content
    
    def test_create_github_annotations(self):
        """Test creating GitHub annotations."""
        errors = [
            "Error in file app.py",
            "Warning: function name invalid"
        ]
        
        annotations = create_github_annotations(errors)
        assert len(annotations) == 2
        
        # Check annotation properties
        assert annotations[0]["annotation_level"] == "failure"
        
        # Warning level for errors containing "warning"
        assert annotations[1]["annotation_level"] == "warning"
        
        # Extract file path from error
        assert "app.py" in str(annotations[0].get("path", ""))
    
    def test_validate_pre_plan_valid(self, valid_plan_data):
        """Test the main validate_pre_plan function with valid data."""
        with patch('agent_s3.tools.plan_validator.validate_path_validity', return_value=[]):
            is_valid, validation_results = validate_pre_plan(valid_plan_data)
            assert is_valid is True
            assert validation_results.get("critical_count", 0) == 0
    
    def test_validate_pre_plan_invalid(self, invalid_plan_data):
        """Test the main validate_pre_plan function with invalid data."""
        is_valid, validation_results = validate_pre_plan(invalid_plan_data)
        assert is_valid is False
        
        # Check that we have critical errors
        critical_errors = validation_results.get("critical", [])
        assert len(critical_errors) > 0
        
        # Check that the summary counts match
        assert validation_results.get("summary", {}).get("critical_count", 0) == len(critical_errors)


