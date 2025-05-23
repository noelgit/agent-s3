"""
Tests for the Coordinator phase execution methods.

These tests focus specifically on the execution of individual phases
within the Coordinator's task execution flow, with a focus on error handling,
graceful degradation, and appropriate output formatting.
"""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import LogLevel
from agent_s3.pre_planner_json_enforced import integrate_with_coordinator

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
         patch('agent_s3.coordinator.WorkspaceInitializer'), \
         patch('agent_s3.coordinator.DatabaseManager'):
        
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
        coordinator.router_agent = MagicMock()
        
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

# Test pre-planning integration

def test_pre_planning_phase_normal_flow(coordinator):
    """Test normal flow of pre-planning phase using the new workflow."""
    coordinator.pre_planner.assess_complexity.return_value = {
        "score": 150.0,
        "is_complex": False,
    }
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Add feature X", "feature_groups": [], "complexity_score": 150.0},
        )

        result = integrate_with_coordinator(coordinator, "Add feature X")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["is_complex"] is False
    assert result["complexity_score"] == 150.0
    mock_call.assert_called_once_with(coordinator.router_agent, "Add feature X")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_phase_high_complexity(coordinator):
    """Test pre-planning phase identifies complex tasks."""
    coordinator.pre_planner.assess_complexity.return_value = {
        "score": 400.0,
        "is_complex": True,
    }
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Refactor module Y", "feature_groups": [], "complexity_score": 400.0},
        )

        result = integrate_with_coordinator(coordinator, "Refactor module Y")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["is_complex"] is True
    assert result["complexity_score"] == 400.0
    mock_call.assert_called_once_with(coordinator.router_agent, "Refactor module Y")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_assess_complexity_error(coordinator):
    """Test assess_complexity errors are handled gracefully."""
    coordinator.pre_planner.assess_complexity.side_effect = Exception("complexity error")
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Add feature Z", "feature_groups": [], "complexity_score": 0},
        )

        result = integrate_with_coordinator(coordinator, "Add feature Z")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["is_complex"] is False
    mock_call.assert_called_once_with(coordinator.router_agent, "Add feature Z")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_complexity_estimation_error(coordinator):
    """Test that invalid complexity assessment does not raise."""
    coordinator.pre_planner.assess_complexity.side_effect = Exception("boom")
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Add feature W", "feature_groups": [], "complexity_score": None},
        )

        result = integrate_with_coordinator(coordinator, "Add feature W")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["complexity_score"] is None
    assert result["is_complex"] is False
    mock_call.assert_called_once_with(coordinator.router_agent, "Add feature W")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_prompt_error(coordinator):
    """Test errors from the pre-planner are surfaced."""
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json",
        side_effect=Exception("Prompt error"),
    ):
        with pytest.raises(Exception):
            integrate_with_coordinator(coordinator, "Add feature V")

def test_pre_planning_complete_failure(coordinator):
    """Test that failures bubble up when JSON validation fails."""
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json",
        return_value=(False, {}),
    ):
        with pytest.raises(Exception):
            integrate_with_coordinator(coordinator, "Invalid query")

def test_pre_planning_phase_updated_requirements(coordinator):
    """Test pre-planning returns updated test requirements."""
    coordinator.pre_planner.assess_complexity.return_value = {"score": 200.0, "is_complex": False}
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {
                "original_request": "Add feature X",
                "feature_groups": [],
                "test_requirements": {"approval_baseline": ["Baseline test"]},
                "complexity_score": 200.0,
            },
        )

        result = integrate_with_coordinator(coordinator, "Add feature X")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["test_requirements"]["approval_baseline"] == ["Baseline test"]
    mock_call.assert_called_once_with(coordinator.router_agent, "Add feature X")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_phase_updated_complexity(coordinator):
    """Test updated complexity scoring is returned."""
    coordinator.pre_planner.assess_complexity.return_value = {"score": 55, "is_complex": True}
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Add feature X", "feature_groups": [], "complexity_score": 55},
        )

        result = integrate_with_coordinator(coordinator, "Add feature X")

    assert result["success"] is True
    assert result["status"] == "completed"
    assert result["is_complex"] is True
    assert result["complexity_score"] == 55
    mock_call.assert_called_once_with(coordinator.router_agent, "Add feature X")
    coordinator.pre_planner.assess_complexity.assert_called_once()

def test_pre_planning_phase_with_caching(coordinator):
    """Test pre-planning phase with caching applied."""
    coordinator.pre_planner.assess_complexity.return_value = {"score": 55, "is_complex": True}
    with patch(
        "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
    ) as mock_call:
        mock_call.return_value = (
            True,
            {"original_request": "Add feature X", "feature_groups": [], "complexity_score": 55},
        )

        result1 = integrate_with_coordinator(coordinator, "Add feature X")
        result2 = integrate_with_coordinator(coordinator, "Add feature X")

    assert result1 == result2
    assert mock_call.call_count == 2
    coordinator.pre_planner.assess_complexity.assert_called()

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

def test_implementation_retry_requests_user_guidance(coordinator):
    coordinator.config.config["max_attempts"] = 1
    plan = {"plan_id": "1", "group_name": "auth"}

    coordinator.code_generator.generate_code.return_value = {"auth.py": "code"}
    coordinator._apply_changes_and_manage_dependencies = MagicMock(return_value=True)
    coordinator._run_validation_phase.side_effect = [
        {
            "success": False,
            "step": "lint",
            "lint_output": "fail",
            "type_output": None,
            "test_output": None,
            "coverage": None,
        },
        {
            "success": True,
            "step": None,
            "lint_output": "No lint errors",
            "type_output": "No type errors",
            "test_output": "All checks passed",
            "coverage": None,
        },
    ]
    coordinator.debugging_manager.handle_error.return_value = {"success": False}
    coordinator.prompt_moderator.request_debugging_guidance.return_value = "Fix plan"
    coordinator.feature_group_processor.update_plan_with_modifications.return_value = plan

    changes, success = coordinator._implementation_workflow([plan])

    coordinator.prompt_moderator.request_debugging_guidance.assert_called_once_with("auth", 1)
    coordinator.feature_group_processor.update_plan_with_modifications.assert_called_once_with(plan, "Fix plan")
    assert success is True


def test_implementation_multiple_plans_processed_sequentially(coordinator):
    """Ensure multiple approved plans are executed sequentially."""
    plan1 = {"plan_id": "1", "group_name": "auth"}
    plan2 = {"plan_id": "2", "group_name": "billing"}

    coordinator.code_generator.generate_code.side_effect = [
        {"auth.py": "code1"},
        {"billing.py": "code2"},
    ]
    coordinator._apply_changes_and_manage_dependencies.return_value = True
    coordinator._run_validation_phase.side_effect = [
        {"success": True, "step": None},
        {"success": True, "step": None},
    ]

    changes, success = coordinator._implementation_workflow([plan1, plan2])

    assert coordinator._run_validation_phase.call_count == 2
    assert changes == {"auth.py": "code1", "billing.py": "code2"}
    assert success is True
