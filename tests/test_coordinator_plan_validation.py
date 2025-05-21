"""
Tests for the Coordinator plan validation functionality.

This includes validation of pre-planning data, complexity warnings,
and user confirmation flows.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.enhanced_scratchpad_manager import LogLevel


class TestCoordinatorPlanValidation:
    """Test the plan validation and complexity checks in Coordinator."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = MagicMock()
        config.config = {
            "complexity_threshold": 7,
            "max_attempts": 2,
            "sandbox_environment": True
        }
        return config

    @pytest.fixture
    def coordinator(self, mock_config):
        """Create a mocked coordinator with required components."""
        with patch('agent_s3.coordinator.EnhancedScratchpadManager'), \
             patch('agent_s3.coordinator.ProgressTracker'), \
             patch('agent_s3.coordinator.TaskStateManager'), \
             patch('agent_s3.coordinator.FileTool'), \
             patch('agent_s3.coordinator.GitTool'), \
             patch('agent_s3.coordinator.BashTool'), \
             patch('agent_s3.coordinator.TaskResumer'):
        
            coordinator = Coordinator(config=mock_config)
            
            # Mock required components for tests
            coordinator.scratchpad = MagicMock()
            coordinator.progress_tracker = MagicMock()
            coordinator.router_agent = MagicMock()
            coordinator.prompt_moderator = MagicMock()
            coordinator.feature_group_processor = MagicMock()
            coordinator.task_state_manager = MagicMock()
            coordinator.debugging_manager = MagicMock()
            
            yield coordinator

    def test_validate_pre_planning_data_valid(self, coordinator):
        """Test validation of valid pre-planning data."""
        # Create valid pre-planning data
        valid_data = {
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "group_description": "Description",
                    "features": [
                        {
                            "name": "Feature 1",
                            "files_affected": ["file1.py"]
                        }
                    ]
                }
            ]
        }
        
        # Execute validation
        result = coordinator._validate_pre_planning_data(valid_data)
        
        # Assert
        assert result is True
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator", 
            "Validating pre-planning data structure..."
        )

    def test_validate_pre_planning_data_invalid_type(self, coordinator):
        """Test validation of pre-planning data with invalid type."""
        # Create invalid pre-planning data (not a dictionary)
        invalid_data = ["This", "is", "not", "a", "dictionary"]
        
        # Execute validation and verify exception is raised
        with pytest.raises(ValueError) as excinfo:
            coordinator._validate_pre_planning_data(invalid_data)
        
        # Assert error message
        assert "Pre-planning data must be a dictionary" in str(excinfo.value)

    def test_validate_pre_planning_data_missing_feature_groups(self, coordinator):
        """Test validation of pre-planning data with missing feature groups."""
        # Create invalid pre-planning data (missing feature_groups)
        invalid_data = {
            "status": "completed",
            "complexity_score": 50
        }
        
        # Execute validation and verify exception is raised
        with pytest.raises(ValueError) as excinfo:
            coordinator._validate_pre_planning_data(invalid_data)
        
        # Assert error message
        assert "missing feature_groups" in str(excinfo.value)

    def test_validate_pre_planning_data_empty_feature_groups(self, coordinator):
        """Test validation of pre-planning data with empty feature groups."""
        # Create invalid pre-planning data (empty feature_groups)
        invalid_data = {
            "feature_groups": []
        }
        
        # Execute validation and verify exception is raised
        with pytest.raises(ValueError) as excinfo:
            coordinator._validate_pre_planning_data(invalid_data)
        
        # Assert error message
        assert "feature_groups is empty" in str(excinfo.value)

    def test_complexity_check_with_is_complex_flag(self, coordinator):
        """Test that the is_complex flag triggers a user confirmation."""
        # Create complex task data with is_complex flag
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 5.0,  # Below threshold but is_complex is True
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Configure mocks
        coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"  # User proceeds
        coordinator._present_pre_planning_results_to_user.return_value = ("yes", None)
        
        # Mock call_pre_planner_with_enforced_json
        with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                 return_value=(True, complex_task_data)):
            
            # Execute run_task
            coordinator.run_task("Implement feature")
        
        # Verify complexity warning was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "Task assessed as complex (Score: 5.0)"
        )
        
        # Verify user was asked for confirmation
        coordinator.prompt_moderator.ask_ternary_question.assert_any_call(
            "How would you like to proceed?"
        )
        
        # Verify feature group processing was called
        coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()

    def test_complexity_check_with_high_score(self, coordinator):
        """Test that a high complexity score triggers a user confirmation."""
        # Create task data with high complexity score
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": False,  # Not marked as complex
            "complexity_score": 8.5,  # Above threshold
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Configure mocks
        coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"  # User proceeds
        coordinator._present_pre_planning_results_to_user.return_value = ("yes", None)
        
        # Mock call_pre_planner_with_enforced_json
        with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                 return_value=(True, complex_task_data)):
            
            # Execute run_task
            coordinator.run_task("Implement feature")
        
        # Verify complexity warning was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "Task assessed as complex (Score: 8.5)"
        )
        
        # Verify user was asked for confirmation
        coordinator.prompt_moderator.ask_ternary_question.assert_any_call(
            "How would you like to proceed?"
        )
        
        # Verify feature group processing was called
        coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()

    def test_complexity_check_user_chooses_modify(self, coordinator):
        """Test that a complex task is terminated when the user chooses 'modify'."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 9.0,
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Configure mocks
        coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"  # User chooses to modify
        
        # Mock call_pre_planner_with_enforced_json
        with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                 return_value=(True, complex_task_data)):
            
            # Execute run_task
            coordinator.run_task("Implement feature")
        
        # Verify complexity warning was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "Task assessed as complex (Score: 9.0)"
        )
        
        # Verify user was asked for confirmation
        coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with(
            "How would you like to proceed?"
        )
        
        # Verify user's decision to modify was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "User chose to refine the request."
        )
        
        # Verify feature group processing was NOT called
        coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()

    def test_complexity_check_user_chooses_no(self, coordinator):
        """Test that a complex task is terminated when the user chooses 'no'."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 9.5,
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Configure mocks
        coordinator.prompt_moderator.ask_ternary_question.return_value = "no"  # User chooses to cancel
        
        # Mock call_pre_planner_with_enforced_json
        with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                 return_value=(True, complex_task_data)):
            
            # Execute run_task
            coordinator.run_task("Implement feature")
        
        # Verify complexity warning was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "Task assessed as complex (Score: 9.5)"
        )
        
        # Verify user was asked for confirmation
        coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with(
            "How would you like to proceed?"
        )
        
        # Verify user's decision to cancel was logged
        coordinator.scratchpad.log.assert_any_call(
            "Coordinator",
            "User cancelled the complex task."
        )
        
        # Verify feature group processing was NOT called
        coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()

    def test_no_complexity_check_for_simple_task(self, coordinator):
        """Test that no complexity check is performed for simple tasks."""
        # Create simple task data
        simple_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": False,
            "complexity_score": 3.0,  # Below threshold
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Configure mocks
        coordinator._present_pre_planning_results_to_user.return_value = ("yes", None)
        
        # Mock call_pre_planner_with_enforced_json
        with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                 return_value=(True, simple_task_data)):
            
            # Execute run_task
            coordinator.run_task("Implement simple feature")
        
        # Verify no complexity confirmation was requested
        coordinator.prompt_moderator.ask_ternary_question.assert_not_called()
        
        # Verify feature group processing was called
        coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()

    def test_complexity_check_immediately_after_validation(self, coordinator):
        """Test that complexity check happens right after validation, before user handoff."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 8.5,
            "feature_groups": [
                {
                    "group_name": "Feature Group 1",
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }
        
        # Mock Plan Validator
        with patch('agent_s3.tools.plan_validator.validate_pre_plan', return_value=(True, [])):
            # Mock call_pre_planner_with_enforced_json
            with patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json', 
                    return_value=(True, complex_task_data)):
                
                # Configure user to cancel
                coordinator.prompt_moderator.ask_ternary_question.return_value = "no"  # User cancels
                
                # Execute run_task
                coordinator.run_task("Implement complex feature to cancel early")
                
                # Verify complexity check happens before presenting results to user
                complexity_log_call = None
                present_results_call = None
                
                # Find relevant method call indices in the scratchpad.log mock calls
                for i, call in enumerate(coordinator.scratchpad.log.mock_calls):
                    if "Task assessed as complex" in str(call):
                        complexity_log_call = i
                    if "Pre-planning complete" in str(call):
                        present_results_call = i
                
                # Assert that complexity check happened and happened before user handoff
                assert complexity_log_call is not None
                assert present_results_call is None or complexity_log_call < present_results_call
                
                # Verify feature group processing was NOT called
                coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()


