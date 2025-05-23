"""Tests for handling exceptions in Coordinator.run_task."""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config


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
        "context_management": {"enabled": False},
    }
    return config


@pytest.fixture
def coordinator(mock_config):
    with patch("agent_s3.coordinator.EnhancedScratchpadManager"), \
         patch("agent_s3.coordinator.ProgressTracker"), \
         patch("agent_s3.coordinator.FileTool"), \
         patch("agent_s3.coordinator.BashTool"), \
         patch("agent_s3.coordinator.GitTool"), \
         patch("agent_s3.coordinator.CodeAnalysisTool"), \
         patch("agent_s3.coordinator.TaskStateManager"), \
         patch("agent_s3.coordinator.TaskResumer"), \
         patch("agent_s3.coordinator.WorkspaceInitializer"), \
         patch("agent_s3.coordinator.DatabaseManager"):
        coord = Coordinator(config=mock_config)
        coord.pre_planner = MagicMock()
        coord.planner = MagicMock()
        coord.test_planner = MagicMock()
        coord.prompt_moderator = MagicMock()
        coord.scratchpad = MagicMock()
        coord.progress_tracker = MagicMock()
        coord.code_generator = MagicMock()
        coord.task_state_manager = MagicMock()
        coord.workspace_initializer = MagicMock()
        coord.design_manager = MagicMock()
        coord.implementation_manager = MagicMock()
        coord.deployment_manager = MagicMock()
        coord.file_tool = MagicMock()
        coord.error_context_manager = MagicMock()
        coord.debugging_manager = MagicMock()
        yield coord


def test_run_task_handles_exception(coordinator):
    """Coordinator.run_task should handle errors using the task text."""
    coordinator._planning_workflow = MagicMock(side_effect=RuntimeError("boom"))
    coordinator.error_handler.handle_exception = MagicMock()

    coordinator.run_task("Sample task")

    coordinator.error_handler.handle_exception.assert_called_once()
    call_kwargs = coordinator.error_handler.handle_exception.call_args.kwargs
    assert call_kwargs["inputs"]["request_text"] == "Sample task"
