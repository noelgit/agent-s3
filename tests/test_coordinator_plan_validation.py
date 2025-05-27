"""
Tests for the Coordinator plan validation functionality.

This includes validation of pre-planning data structure.
Note: Complexity checking and user confirmation flows have been moved to the orchestrator pattern.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.coordinator import Coordinator

class TestCoordinatorPlanValidation:
    """Test the plan validation functionality in Coordinator."""

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
             patch('agent_s3.coordinator.TaskResumer'), \
             patch('agent_s3.coordinator.DatabaseManager'):

            coordinator = Coordinator(config=mock_config)

            # Mock required components for tests
            coordinator.scratchpad = MagicMock()
            coordinator.progress_tracker = MagicMock()
            coordinator.router_agent = MagicMock()
            coordinator.prompt_moderator = MagicMock()
            coordinator.task_state_manager = MagicMock()
            coordinator.debugging_manager = MagicMock()
            coordinator.orchestrator = MagicMock()
            coordinator.orchestrator.run_task = MagicMock()

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

    def test_present_pre_planning_user_cancels_after_confirmation(self, coordinator):
        """Test that user can cancel after seeing pre-planning results."""
        # Create mock pre-planning data
        pre_planning_data = {
            "feature_groups": [
                {
                    "group_name": "Feature Group 1", 
                    "features": [{"name": "Feature 1", "files_affected": ["file1.py"]}]
                }
            ]
        }

        # Mock user saying no (which should cancel the operation)
        coordinator.prompt_moderator.ask_ternary_question.return_value = "no"

        # Execute
        user_choice, modified_data = coordinator._present_pre_planning_results_to_user(pre_planning_data)

        # Assert
        assert user_choice == "no"
        assert modified_data is None
        coordinator.prompt_moderator.ask_ternary_question.assert_called_once()


# DEPRECATED FUNCTIONALITY NOTICE:
# The following tests were removed as they tested deprecated functionality:
#
# - test_complexity_check_with_is_complex_flag
# - test_complexity_check_with_high_score  
# - test_complexity_check_user_chooses_modify
# - test_complexity_check_user_chooses_no
# - test_no_complexity_check_for_simple_task
# - test_complexity_check_immediately_after_validation
#
# These tests were testing the coordinator's direct handling of complexity checks
# and user confirmation flows, which have been moved to the orchestrator pattern.
# The coordinator now delegates these operations to the WorkflowOrchestrator.
#
# If you need to test complexity checking functionality, look at:
# - The WorkflowOrchestrator class methods directly
# - Integration tests for the current workflow system
# 
# Backup of original tests available at: tests/backups/test_coordinator_plan_validation.py.backup