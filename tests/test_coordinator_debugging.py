"""
Unit tests for the debugging integration in the Coordinator class.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.coordinator import Coordinator
from agent_s3.debugging_manager import DebuggingManager
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
from agent_s3.enhanced_scratchpad_manager import LogLevel
from agent_s3.enhanced_scratchpad_manager import Section

@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = MagicMock()
    config.config = {
        "version": "test-version",
        "log_files": {
            "development": "log/dev.log",
            "scratchpad": "log/scratchpad.log"
        },
        "sandbox_environment": False,
        "github_token": "mock-token",
        "host_os_type": "linux"
    }
    config.get_log_file_path.return_value = "log/dev.log"
    return config


@pytest.fixture
def mock_file_tool():
    """Create a mock file tool for testing."""
    file_tool = MagicMock()
    file_tool.read_file.return_value = "def test_function():\n    return x"  # Example content
    return file_tool


@pytest.fixture
def mock_bash_tool():
    """Create a mock bash tool for testing."""
    bash_tool = MagicMock()
    bash_tool.run_command.return_value = (0, "Success")
    return bash_tool


@pytest.fixture
def mock_coordinator(mock_config, mock_file_tool, mock_bash_tool):
    """Create a mock coordinator with minimal components for testing."""
    # Patch initialization to avoid creating actual components
    with patch('agent_s3.coordinator.EnhancedScratchpadManager'), \
         patch('agent_s3.coordinator.DebuggingManager'), \
         patch('agent_s3.coordinator.RouterAgent'), \
         patch('agent_s3.coordinator.ProgressTracker'), \
         patch('agent_s3.coordinator.ErrorContextManager'), \
         patch('agent_s3.coordinator.TaskStateManager'), \
         patch('agent_s3.coordinator.DatabaseManager'), \
         patch('agent_s3.coordinator.BashTool', return_value=mock_bash_tool), \
         patch('agent_s3.coordinator.FileTool', return_value=mock_file_tool), \
         patch('agent_s3.coordinator.os.path.join', return_value="task_snapshots"):

        coordinator = Coordinator(config=mock_config)

        # Keep reference to the mocks that should have been set during initialization
        coordinator.router_agent = MagicMock()
        coordinator.llm = coordinator.router_agent
        coordinator.progress_tracker = MagicMock()
        coordinator.task_state_manager = MagicMock()
        coordinator.error_context_manager = MagicMock()

        # Create real scratchpad and debugging manager for integration
        coordinator.scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        coordinator.debugging_manager = MagicMock(spec=DebuggingManager)

        # Add other required attributes
        coordinator.planner = MagicMock()
        coordinator.code_generator = MagicMock()
        coordinator.code_analysis_tool = MagicMock()

        yield coordinator


class TestCoordinatorDebuggingIntegration:
    """Test the integration of the debugging system in the Coordinator class."""

    def test_debug_last_test_with_no_output(self, mock_coordinator):
        """Test debug_last_test with no output available."""
        # Mock progress tracker to return None for latest progress
        mock_coordinator.progress_tracker.get_latest_progress.return_value = None

        # Call debug_last_test
        mock_coordinator.debug_last_test()

        # Verify section not started (no debugging attempted)
        mock_coordinator.scratchpad.start_section.assert_not_called()

    def test_debug_last_test_basic_recovery(self, mock_coordinator):
        """Test debug_last_test with successful basic recovery."""
        # Set up mocks
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Test error message"
        }
        mock_coordinator.error_context_manager.collect_error_context.return_value = {
            "parsed_error": {
                "file_paths": ["/test/file.py"],
                "line_numbers": [10]
            }
        }
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (
            True, "Successfully fixed issue"
        )

        # Call debug_last_test
        mock_coordinator.debug_last_test()

        # Verify scratchpad sections
        mock_coordinator.scratchpad.start_section.assert_called_with(Section.DEBUGGING, "Coordinator")

        # Verify error context was collected
        mock_coordinator.error_context_manager.collect_error_context.assert_called_with(
            error_message="Test error message"
        )

        # Verify automated recovery was attempted
        mock_coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()

        # Verify debugging manager was not called (since basic recovery succeeded)
        mock_coordinator.debugging_manager.handle_error.assert_not_called()

        # Verify section was ended
        mock_coordinator.scratchpad.end_section.assert_called_with(Section.DEBUGGING)

        # Verify progress was updated
        mock_coordinator.progress_tracker.update_progress.assert_called()

    def test_debug_last_test_advanced_debugging(self, mock_coordinator):
        """Test debug_last_test with advanced debugging."""
        # Set up mocks
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Test error message"
        }
        mock_coordinator.error_context_manager.collect_error_context.return_value = {
            "parsed_error": {
                "file_paths": ["/test/file.py"],
                "line_numbers": [10]
            }
        }
        # Make basic recovery fail
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (
            False, "No automated recovery possible"
        )

        # Set up debugging manager response
        mock_coordinator.debugging_manager.handle_error.return_value = {
            "success": True,
            "description": "Fixed with advanced debugging",
            "changes": {"/test/file.py": "def test_function():\n    return 5"}
        }

        # Call debug_last_test
        mock_coordinator.debug_last_test()

        # Verify advanced debugging was attempted
        mock_coordinator.debugging_manager.handle_error.assert_called_with(
            error_message="Test error message",
            traceback_text="Test error message",
            file_path="/test/file.py",
            line_number=10
        )

        # Verify debugging success was logged
        success_log_call = False
        for call in mock_coordinator.scratchpad.log.call_args_list:
            args, kwargs = call
            if kwargs.get("message", "").startswith("Advanced debugging completed"):
                if kwargs.get("level") == LogLevel.INFO:  # Success log should be INFO level
                    success_log_call = True
                    break

        assert success_log_call, "Debugging success was not logged correctly"

        # Verify progress was updated
        mock_coordinator.progress_tracker.update_progress.assert_called()

    def test_debug_last_test_failed_debugging(self, mock_coordinator):
        """Test debug_last_test with failed advanced debugging."""
        # Set up mocks
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Complex error message"
        }
        mock_coordinator.error_context_manager.collect_error_context.return_value = {
            "parsed_error": {
                "file_paths": ["/test/file.py"],
                "line_numbers": [10]
            }
        }
        # Make basic recovery fail
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (
            False, "No automated recovery possible"
        )

        # Set up debugging manager to fail
        mock_coordinator.debugging_manager.handle_error.return_value = {
            "success": False,
            "description": "Failed to fix with advanced debugging",
            "changes": {}
        }

        # Call debug_last_test
        mock_coordinator.debug_last_test()

        # Verify advanced debugging was attempted
        mock_coordinator.debugging_manager.handle_error.assert_called_once()

        # Verify debugging failure was logged
        failure_log_call = False
        for call in mock_coordinator.scratchpad.log.call_args_list:
            args, kwargs = call
            if kwargs.get("message", "").startswith("Advanced debugging completed"):
                if kwargs.get("level") == LogLevel.WARNING:  # Failure log should be WARNING level
                    failure_log_call = True
                    break

        assert failure_log_call, "Debugging failure was not logged correctly"

        # Verify progress was updated
        mock_coordinator.progress_tracker.update_progress.assert_called()

    def test_shutdown_closes_scratchpad(self, mock_coordinator):
        """Test shutdown method properly closes enhanced scratchpad."""
        # Mock the close method on scratchpad
        mock_coordinator.scratchpad.close = MagicMock()

        # Call shutdown
        mock_coordinator.shutdown()

        # Verify close was called
        mock_coordinator.scratchpad.close.assert_called_once()

        # Verify log message
        mock_coordinator.scratchpad.log.assert_any_call("Coordinator", "Shutting down Agent-S3 coordinator...")
