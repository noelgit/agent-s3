"""
Tests for the Coordinator phase execution methods.

These tests focus specifically on the execution of individual phases
within the Coordinator's task execution flow, with a focus on error handling,
graceful degradation, and appropriate output formatting.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
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
         patch('agent_s3.coordinator.WorkspaceInitializer'), \
         patch('agent_s3.coordinator.DatabaseManager'), \
         patch('agent_s3.coordinator.ContextManager'):

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
        coordinator.orchestrator = MagicMock()
        coordinator.orchestrator.run_task = MagicMock()

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
    coordinator.workspace_initializer.initialize_workspace.side_effect = PermissionError("Permission denied")

    # Execute
    result = coordinator.initialize_workspace()

    # Assert
    assert result["success"] is False
    assert len(result["errors"]) > 0
    assert result["errors"][0]["type"] == "permission"
    coordinator.workspace_initializer.initialize_workspace.assert_called_once()
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

# NOTE: Pre-planning, feature group processor, and implementation phase tests
# have been removed as they test deprecated functionality that has been moved
# to the orchestrator pattern. The current coordinator delegates these operations
# to the orchestrator via run_task(), execute_implementation(), etc.
#
# The remaining functionality should be tested through:
# - Orchestrator tests (tests/test_orchestrator_*.py)
# - Integration tests using the public coordinator API (run_task, execute_implementation, etc.)
# - End-to-end workflow tests