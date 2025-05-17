"""
Tests for the Coordinator phase execution methods.

These tests focus specifically on the execution of individual phases
within the Coordinator's task execution flow, with a focus on error handling,
graceful degradation, and appropriate output formatting.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import LogLevel

# Test fixtures

@pytest.fixture
def mock_config():
    config = Config()
    config.config = {
        "complexity_threshold": 300.0,
        "max_attempts": 3,
        "max_plan_attempts": 2,
        "task_state_directory": "./task_snapshots",
        "sandbox_environment": True,
        "host_os_type": "linux",
        "context_management": {"enabled": False}
    }
    return config

@pytest.fixture
def coordinator(mock_config):
    with patch('agent_s3.coordinator.EnhancedScratchpadManager'), \
         patch('agent_s3.coordinator.ProgressTracker'), \
         patch('agent_s3.coordinator.FileTool'), \
         patch('agent_s3.coordinator.BashTool'), \
         patch('agent_s3.coordinator.GitTool'), \
         patch('agent_s3.coordinator.CodeAnalysisTool'), \
         patch('agent_s3.coordinator.TaskStateManager'), \
         patch('agent_s3.coordinator.TaskResumer'), \
         patch('agent_s3.coordinator.WorkspaceInitializer'):
        
        coordinator = Coordinator(config=mock_config)
        
        # Mock required components for tests
        coordinator.pre_planner = MagicMock()
        coordinator.planner = MagicMock()
        coordinator.test_planner = MagicMock()
        coordinator.prompt_moderator = MagicMock()
        coordinator.scratchpad = MagicMock()
        coordinator.progress_tracker = MagicMock()
        coordinator.code_generator = MagicMock()
        coordinator.task_state_manager = MagicMock()
        coordinator.workspace_initializer = MagicMock()
        coordinator.design_manager = MagicMock()
        coordinator.implementation_manager = MagicMock()
        coordinator.deployment_manager = MagicMock()
        coordinator.file_tool = MagicMock()
        coordinator.error_context_manager = MagicMock()
        coordinator.debugging_manager = MagicMock()
        
        yield coordinator

# Test initialize_workspace method

def test_initialize_workspace_success(coordinator):
    """Test successful workspace initialization."""
    # Set up mocks
    coordinator.workspace_initializer.initialize_workspace.return_value = True
    coordinator.workspace_initializer.workspace_path = MagicMock()
    coordinator.workspace_initializer.github_dir = MagicMock()
    coordinator.workspace_initializer.validation_failure_reason = None
    
    # Mock Path operations
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.stat', return_value=MagicMock(st_size=100, st_ctime=12345678)):
        
        # Execute
        result = coordinator.initialize_workspace()
        
        # Assert
        assert result["success"] is True
        assert result["is_workspace_valid"] is True
        assert "created_files" in result
        assert len(result["errors"]) == 0
        coordinator.workspace_initializer.initialize_workspace.assert_called_once()

def test_initialize_workspace_permission_error(coordinator):
    """Test workspace initialization with permission error."""
    # Set up mock to raise permission error
    coordinator.workspace_initializer.workspace_path = MagicMock()
    coordinator.workspace_initializer.github_dir = MagicMock()
    
    # Mock Path operations to simulate permission error
    with patch('pathlib.Path.touch', side_effect=PermissionError("Permission denied")):
        
        # Execute
        result = coordinator.initialize_workspace()
        
        # Assert
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert result["errors"][0]["type"] == "permission"
        coordinator.workspace_initializer.initialize_workspace.assert_not_called()
        coordinator.scratchpad.log.assert_any_call("Coordinator", 
                                                  result["errors"][0]["message"], 
                                                  level=LogLevel.ERROR)

def test_initialize_workspace_partial_success(coordinator):
    """Test workspace initialization with successful execution but validation failure."""
    # Set up mocks for partial success
    coordinator.workspace_initializer.initialize_workspace.return_value = False
    coordinator.workspace_initializer.workspace_path = MagicMock()
    coordinator.workspace_initializer.github_dir = MagicMock()
    coordinator.workspace_initializer.validation_failure_reason = "README.md not found"
    
    # Mock Path operations
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.stat', return_value=MagicMock(st_size=100, st_ctime=12345678)), \
         patch('pathlib.Path.touch'), \
         patch('pathlib.Path.unlink'):
        
        # Execute
        result = coordinator.initialize_workspace()
        
        # Assert
        assert result["success"] is True  # Overall success
        assert result["is_workspace_valid"] is False  # But workspace not valid
        assert "validation_failure_reason" in result
        assert result["validation_failure_reason"] == "README.md not found"
        coordinator.workspace_initializer.initialize_workspace.assert_called_once()

def test_initialize_workspace_exception(coordinator):
    """Test workspace initialization with unhandled exception."""
    # Set up mocks to raise unhandled exception
    coordinator.workspace_initializer.initialize_workspace.side_effect = Exception("Unexpected error")
    coordinator.workspace_initializer.workspace_path = MagicMock()
    coordinator.workspace_initializer.github_dir = MagicMock()
    
    # Mock Path operations
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.touch'), \
         patch('pathlib.Path.unlink'):
        
        # Execute
        result = coordinator.initialize_workspace()
        
        # Assert
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert result["errors"][0]["type"] == "exception"
        coordinator.workspace_initializer.initialize_workspace.assert_called_once()

# Test _execute_pre_planning_phase method

def test_pre_planning_phase_normal_flow(coordinator):
    """Test normal flow of pre-planning phase."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
    coordinator.pre_planner.estimate_complexity.return_value = 150.0
    coordinator.prompt_moderator.ask_binary_question.return_value = False  # Don't switch to design
    
    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature X")
    
    # Assert
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["switch_workflow"] is False
    assert len(result["impacted_files"]) == 2
    assert result["complexity_score"] == 150.0
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once()

def test_pre_planning_phase_high_complexity(coordinator):
    """Test pre-planning phase with high complexity leading to workflow switch."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py", "file3.py", "file4.py"]
    coordinator.pre_planner.estimate_complexity.return_value = 400.0  # Above threshold
    coordinator.prompt_moderator.ask_binary_question.return_value = True  # Switch to design
    
    # Execute
    result = coordinator._execute_pre_planning_phase("Refactor module Y")
    
    # Assert
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["switch_workflow"] is True
    assert result["workflow"] == "design"
    assert len(result["impacted_files"]) == 4
    assert result["complexity_score"] == 400.0
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once()
    coordinator.prompt_moderator.ask_binary_question.assert_called_once()

def test_pre_planning_file_collection_error(coordinator):
    """Test pre-planning phase with file collection error."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.side_effect = Exception("File collection error")
    coordinator.pre_planner.estimate_complexity.return_value = 100.0  # Will use empty list
    
    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature Z")
    
    # Assert
    assert result["success"] is True  # Still succeeds with fallback
    assert result["status"] == "completed"
    assert "file_collection_error" in result
    assert result["impacted_files"] == []
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once_with([])

def test_pre_planning_complexity_estimation_error(coordinator):
    """Test pre-planning phase with complexity estimation error."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
    coordinator.pre_planner.estimate_complexity.side_effect = Exception("Complexity estimation error")
    
    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature W")
    
    # Assert
    assert result["success"] is True  # Still succeeds with fallback
    assert result["status"] == "completed"
    assert "complexity_error" in result
    assert result["complexity_estimated"] is False
    assert result["complexity_score"] == 250  # Default value
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once()

def test_pre_planning_prompt_error(coordinator):
    """Test pre-planning phase with prompt error."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
    coordinator.pre_planner.estimate_complexity.return_value = 400.0  # Above threshold
    coordinator.prompt_moderator.ask_binary_question.side_effect = Exception("Prompt error")
    
    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature V")
    
    # Assert
    assert result["success"] is True  # Still succeeds
    assert result["status"] == "completed"
    assert result["switch_workflow"] is False  # Default to not switching
    assert "prompt_error" in result
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once()
    coordinator.prompt_moderator.ask_binary_question.assert_called_once()

def test_pre_planning_complete_failure(coordinator):
    """Test pre-planning phase with complete failure."""
    # Set up mocks for complete failure
    coordinator.pre_planner.collect_impacted_files.side_effect = Exception("Critical error")
    coordinator.pre_planner.estimate_complexity.side_effect = Exception("Should not be called")
    
    # Make sure the error propagates to the top level
    with patch('traceback.format_exc', return_value="Mock traceback"):
        # Execute
        result = coordinator._execute_pre_planning_phase("Invalid query")
        
        # Assert
        assert result["success"] is False
        assert result["status"] == "error"
        assert "error" in result
        assert "error_context" in result
        assert result["error_context"]["error_type"] == "Exception"
        coordinator.pre_planner.collect_impacted_files.assert_called_once()
        coordinator.pre_planner.estimate_complexity.assert_not_called()
        coordinator.progress_tracker.update_progress.assert_any_call({
            "phase": "pre_planning", 
            "status": "error",
            "error": result["error"]
        })

def test_pre_planning_phase_updated_requirements(coordinator):
    """Test pre-planning phase with updated test requirements."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
    coordinator.pre_planner.estimate_complexity.return_value = 200.0
    coordinator.pre_planner.get_test_requirements.return_value = {
        "unit": ["Test case 1"],
        "integration": ["Integration test 1"],
        "property_based": ["Property-based test 1"],
        "acceptance": [
            {
                "given": "Condition",
                "when": "Action",
                "then": "Result"
            }
        ],
        "approval_baseline": ["Baseline test"]
    }

    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature X")

    # Assert
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["test_requirements"]["approval_baseline"] == ["Baseline test"]
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.estimate_complexity.assert_called_once()
    coordinator.pre_planner.get_test_requirements.assert_called_once()

def test_pre_planning_phase_updated_complexity(coordinator):
    """Test pre-planning phase with updated complexity scoring."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py", "file3.py"]
    coordinator.pre_planner.assess_complexity.return_value = {
        "score": 55,
        "is_complex": True
    }
    coordinator.prompt_moderator.ask_binary_question.return_value = True  # Switch to design

    # Execute
    result = coordinator._execute_pre_planning_phase("Add feature X")

    # Assert
    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["switch_workflow"] is True
    assert result["workflow"] == "design"
    assert result["complexity_score"] == 55
    coordinator.pre_planner.collect_impacted_files.assert_called_once()
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_phase_with_caching(coordinator):
    """Test pre-planning phase with caching applied."""
    # Set up mocks
    coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
    coordinator.pre_planner.assess_complexity.return_value = {
        "score": 55,
        "is_complex": True
    }
    coordinator.prompt_moderator.ask_binary_question.return_value = True  # Switch to design

    # Execute twice to test caching
    result1 = coordinator._execute_pre_planning_phase("Add feature X")
    result2 = coordinator._execute_pre_planning_phase("Add feature X")

    # Assert
    assert result1["success"] is True
    assert result2["success"] is True
    assert result1 == result2  # Cached result should be identical
    coordinator.pre_planner.collect_impacted_files.assert_called_once()  # Cached result used
    coordinator.pre_planner.assess_complexity.assert_called_once()

# Test consolidated workflow through feature_group_processor

def test_feature_group_processor_consolidated_workflow(coordinator):
    """Test the consolidated workflow through feature_group_processor."""
    # Add feature_group_processor mock
    coordinator.feature_group_processor = MagicMock()
    
    # Setup sample pre-planning data
    pre_planning_data = {
        "feature_groups": [
            {
                "group_name": "Authentication", 
                "features": [
                    {"name": "Login", "files_affected": ["auth.py"]}
                ]
            }
        ]
    }
    
    # Mock the process_pre_planning_output method
    coordinator.feature_group_processor.process_pre_planning_output.return_value = {
        "success": True,
        "feature_group_results": {
            "feature_group_0": {
                "success": True,
                "feature_group": pre_planning_data["feature_groups"][0],
                "consolidated_plan": {
                    "architecture_review": {"logical_gaps": []},
                    "implementation_plan": {"auth.py": [{"function": "login()"}]},
                    "tests": {"unit_tests": [{"test_name": "test_login"}]}
                }
            }
        }
    }
    
    # Mock present_consolidated_plan_to_user to return user approval
    coordinator.feature_group_processor.present_consolidated_plan_to_user.return_value = ("yes", None)
    
    # Execute run_task
    coordinator.run_task("Implement authentication feature")
    
    # Assert
    coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()
    coordinator.feature_group_processor.present_consolidated_plan_to_user.assert_called_once()
    coordinator.progress_tracker.update_progress.assert_any_call({"phase": "feature_group_processing", "status": "completed"})

def test_feature_group_processor_with_user_modifications(coordinator):
    """Test the consolidated workflow with user modifications."""
    # Add feature_group_processor mock
    coordinator.feature_group_processor = MagicMock()
    
    # Setup sample pre-planning data
    pre_planning_data = {
        "feature_groups": [
            {
                "group_name": "Authentication", 
                "features": [
                    {"name": "Login", "files_affected": ["auth.py"]}
                ]
            }
        ]
    }
    
    # Mock the process_pre_planning_output method
    coordinator.feature_group_processor.process_pre_planning_output.return_value = {
        "success": True,
        "feature_group_results": {
            "feature_group_0": {
                "success": True,
                "feature_group": pre_planning_data["feature_groups"][0],
                "consolidated_plan": {
                    "architecture_review": {"logical_gaps": []},
                    "implementation_plan": {"auth.py": [{"function": "login()"}]},
                    "tests": {"unit_tests": [{"test_name": "test_login"}]}
                }
            }
        }
    }
    
    # Mock present_consolidated_plan_to_user to return user modifications
    coordinator.feature_group_processor.present_consolidated_plan_to_user.return_value = ("modify", "Add two-factor authentication")
    
    # Mock update_plan_with_modifications
    coordinator.feature_group_processor.update_plan_with_modifications.return_value = {
        "architecture_review": {
            "logical_gaps": [],
            "additional_considerations": ["USER MODIFICATION: Add two-factor authentication"]
        },
        "implementation_plan": {"auth.py": [{"function": "login()"}, {"function": "two_factor_auth()"}]},
        "tests": {"unit_tests": [{"test_name": "test_login"}]}
    }
    
    # Execute run_task
    coordinator.run_task("Implement authentication feature")
    
    # Assert
    coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()
    coordinator.feature_group_processor.present_consolidated_plan_to_user.assert_called_once()
    coordinator.feature_group_processor.update_plan_with_modifications.assert_called_once_with(
        coordinator.feature_group_processor.process_pre_planning_output.return_value["feature_group_results"]["feature_group_0"]["consolidated_plan"],
        "Add two-factor authentication"
    )
    coordinator.progress_tracker.update_progress.assert_any_call({"phase": "feature_group_processing", "status": "completed"})

def test_feature_group_processor_error_handling(coordinator):
    """Test error handling in the consolidated workflow."""
    # Add feature_group_processor mock
    coordinator.feature_group_processor = MagicMock()
    
    # Mock the process_pre_planning_output method to return an error
    coordinator.feature_group_processor.process_pre_planning_output.return_value = {
        "success": False,
        "error": "Failed to process feature groups",
        "feature_group_results": {}
    }
    
    # Add debugging_manager mock for recovery plan generation
    coordinator.debugging_manager.generate_recovery_plan.return_value = {
        "description": "Retry with simplified feature groups"
    }
    
    # Execute run_task
    coordinator.run_task("Implement feature with error")
    
    # Assert
    coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()
    coordinator.debugging_manager.generate_recovery_plan.assert_called_once()
    coordinator.scratchpad.log.assert_any_call(
        "Coordinator", 
        "Feature group processing failed: Failed to process feature groups", 
        level=LogLevel.ERROR
    )
