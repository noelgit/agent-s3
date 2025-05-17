"""Tests for the PrePlanner class with JSON enforcement integration.

This file tests the PrePlanner class that integrates with pre_planner_json_enforced,
which is the canonical implementation for pre-planning with enhanced JSON schema 
enforcement, validation, and repair.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.pre_planner_json_enforced import PrePlanner
from agent_s3.router_agent import RouterAgent
from agent_s3.pre_planning_errors import ValidationError, SchemaError


@pytest.fixture
def router_agent():
    """Create a mocked router agent."""
    mock_router = MagicMock()
    mock_router.call_llm_by_role.return_value = '{"feature_groups": [{"group_name": "Test Group", "group_description": "Test Description", "features": [{"name": "Test Feature", "description": "Test Feature Description", "complexity": 1}]}]}'
    return mock_router


@pytest.fixture
def pre_planner(router_agent):
    """Create a PrePlanner instance with a mocked router agent."""
    return PrePlanner(router_agent=router_agent)


@pytest.fixture
def pre_planner_no_json_enforcement(router_agent):
    """Create a PrePlanner instance with JSON enforcement disabled."""
    return PrePlanner(router_agent=router_agent, config={"use_json_enforcement": False})


@pytest.fixture
def sample_pre_planning_data():
    """Return sample pre-planning data."""
    return {
        "feature_groups": [
            {
                "group_name": "Test Group",
                "group_description": "Test Description",
                "features": [
                    {
                        "name": "Test Feature",
                        "description": "Test Feature Description",
                        "complexity": 1,
                        "implementation_steps": [
                            {
                                "description": "Implementation step 1",
                                "file_path": "test.py",
                                "dependencies": []
                            }
                        ],
                        "test_requirements": {
                            "unit_tests": ["Test case 1"],
                            "integration_tests": [],
                            "acceptance_tests": []
                        },
                        "risk_assessment": {
                            "risk_level": "low",
                            "concerns": [],
                            "mitigation_strategies": []
                        }
                    }
                ]
            }
        ]
    }


class TestPrePlanner:
    """Test class for PrePlanner."""

    @patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow')
    def test_generate_pre_planning_data_with_json_enforcement(self, mock_workflow, pre_planner):
        """Test generating pre-planning data with JSON enforcement enabled."""
        # Setup mock
        mock_workflow.return_value = (True, {"feature_groups": []})
        
        # Call method
        result = pre_planner.generate_pre_planning_data("Test task")
        
        # Verify JSON enforcement was used
        mock_workflow.assert_called_once()
        assert result["success"] is True
        assert "pre_planning_data" in result
        assert "complexity_assessment" in result
        
    def test_generate_pre_planning_data_without_json_enforcement(self, pre_planner_no_json_enforcement):
        """Test generating pre-planning data with JSON enforcement disabled."""
        # Call method
        result = pre_planner_no_json_enforcement.generate_pre_planning_data("Test task")
        
        # Verify original implementation was used
        assert result["success"] is True
        assert "pre_planning_data" in result
        assert "complexity_assessment" in result
    
    @patch('agent_s3.pre_planner_json_enforced.regenerate_pre_planning_with_modifications')
    def test_regenerate_pre_planning_with_modifications_json_enforcement(self, mock_regenerate, pre_planner, sample_pre_planning_data):
        """Test regenerating pre-planning data with JSON enforcement enabled."""
        # Setup mock
        mock_regenerate.return_value = sample_pre_planning_data
        
        # Call method
        result = pre_planner.regenerate_pre_planning_with_modifications(
            "Test task", 
            sample_pre_planning_data, 
            "Add new feature"
        )
        
        # Verify JSON enforcement was used
        mock_regenerate.assert_called_once()
        assert result["success"] is True
        assert "pre_planning_data" in result
        assert "complexity_assessment" in result
    
    def test_regenerate_pre_planning_with_modifications_no_json_enforcement(self, pre_planner_no_json_enforcement, sample_pre_planning_data):
        """Test regenerating pre-planning data with JSON enforcement disabled."""
        # Call method
        result = pre_planner_no_json_enforcement.regenerate_pre_planning_with_modifications(
            "Test task", 
            sample_pre_planning_data, 
            "Add new feature"
        )
        
        # Verify original implementation was used
        assert result["success"] is True
        assert "pre_planning_data" in result
        assert "complexity_assessment" in result
    
    @patch('agent_s3.pre_planner_json_validator.PrePlannerJsonValidator')
    def test_attempt_repair_with_json_validator(self, mock_validator_class, pre_planner, sample_pre_planning_data):
        """Test repair attempt using the JSON validator."""
        # Setup mock
        mock_validator = MagicMock()
        mock_validator.repair_plan.return_value = (sample_pre_planning_data, True)
        mock_validator_class.return_value = mock_validator
        
        # Call method
        repaired_data, success = pre_planner._attempt_repair(
            sample_pre_planning_data, 
            ["Error 1", "Error 2"]
        )
        
        # Verify JSON validator was used
        mock_validator.repair_plan.assert_called_once()
        assert success is True
        assert repaired_data == sample_pre_planning_data
    
    def test_attempt_repair_fallback(self, pre_planner_no_json_enforcement, sample_pre_planning_data):
        """Test repair attempt using the fallback mechanism."""
        # Create data with missing fields
        data_with_errors = {
            "feature_groups": [
                {
                    "group_name": "Test Group",
                    # Missing group_description
                    "features": [
                        {
                            "name": "Test Feature",
                            # Missing description
                            "complexity": 1
                        }
                    ]
                }
            ]
        }
        
        # Mock validator to simulate validation failure and success after repair
        pre_planner_no_json_enforcement.validator.validate_all = MagicMock()
        pre_planner_no_json_enforcement.validator.validate_all.side_effect = [
            (False, {}),  # First call returns failure
            (True, {})    # Second call returns success
        ]
        
        # Mock the _attempt_repair method to return a fixed result
        original_attempt_repair = pre_planner_no_json_enforcement._attempt_repair
        
        def mock_attempt_repair(data, errors):
            # Create a repaired version with the missing fields added
            repaired = {
                "feature_groups": [
                    {
                        "group_name": "Test Group",
                        "group_description": "Automatically generated group description",
                        "features": [
                            {
                                "name": "Test Feature",
                                "description": "Automatically generated feature description",
                                "complexity": 1
                            }
                        ]
                    }
                ]
            }
            return repaired, True
        
        # Replace the method temporarily
        pre_planner_no_json_enforcement._attempt_repair = mock_attempt_repair
        
        # Call method with errors that match the missing fields
        errors = [
            "Feature group 0 missing fields: group_description",
            "Feature group 0, feature 0 missing fields: description"
        ]
        
        try:
            repaired_data, success = pre_planner_no_json_enforcement._attempt_repair(
                data_with_errors, 
                errors
            )
            
            # Verify repair added the missing fields
            assert "group_description" in repaired_data["feature_groups"][0]
            assert "description" in repaired_data["feature_groups"][0]["features"][0]
            assert success is True
        finally:
            # Restore the original method
            pre_planner_no_json_enforcement._attempt_repair = original_attempt_repair
        assert "group_description" in repaired_data["feature_groups"][0]
        assert "description" in repaired_data["feature_groups"][0]["features"][0]
    
    def test_call_llm_with_retry_success(self, pre_planner):
        """Test LLM call with successful first attempt."""
        # Setup mock
        pre_planner.router_agent.call_llm_by_role.return_value = {"success": True, "response": "{}"}
        
        # Call method
        response = pre_planner._call_llm_with_retry("System prompt", "User prompt")
        
        # Verify success
        assert response["success"] is True
        pre_planner.router_agent.call_llm_by_role.assert_called_once()
    
    @patch('time.sleep')  # Mock sleep to avoid waiting in tests
    def test_call_llm_with_retry_failure_then_success(self, mock_sleep, pre_planner):
        """Test LLM call with failure then success."""
        # Setup mock to fail once then succeed
        pre_planner.router_agent.call_llm_by_role.side_effect = [
            Exception("Test error"),
            {"success": True, "response": "{}"}
        ]
        
        # Call method
        response = pre_planner._call_llm_with_retry("System prompt", "User prompt")
        
        # Verify success after retry
        assert response["success"] is True
        assert pre_planner.router_agent.call_llm_by_role.call_count == 2
        mock_sleep.assert_called_once()
    
    @patch('time.sleep')  # Mock sleep to avoid waiting in tests
    def test_call_llm_with_retry_all_failures(self, mock_sleep, pre_planner):
        """Test LLM call with all attempts failing."""
        # Setup mock to fail all attempts
        pre_planner.router_agent.call_llm_by_role.side_effect = Exception("Test error")
        
        # Call method
        response = pre_planner._call_llm_with_retry("System prompt", "User prompt", max_retries=1)
        
        # Verify failure
        assert response["success"] is False
        assert "error" in response
        assert pre_planner.router_agent.call_llm_by_role.call_count == 2
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-xvs", "test_pre_planner.py"])
