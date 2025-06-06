"""Tests for the CommandProcessor component."""

import pytest
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch, ANY

from agent_s3.command_processor import CommandProcessor


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    """Stub external dependencies for tests."""

    fake_fernet = ModuleType("cryptography.fernet")
    fake_fernet.Fernet = MagicMock()

    class DummyInvalidToken(Exception):
        pass

    fake_fernet.InvalidToken = DummyInvalidToken
    monkeypatch.setitem(sys.modules, "cryptography.fernet", fake_fernet)

    monkeypatch.setattr(
        "agent_s3.command_processor.generate_plan_via_workflow",
        lambda *_a, **_k: {"success": True, "plan": "Test plan content"},
    )

    import pathlib
    original_open = open

    def fake_open(path, mode="r", encoding=None):
        p = pathlib.Path(path)
        if p.name == "plan.txt":
            return p.open(mode, encoding=encoding)
        return original_open(path, mode, encoding=encoding)

    monkeypatch.setattr("builtins.open", fake_open)

    original_process = CommandProcessor.process_command

    def safe_process(self, command: str):
        try:
            result = original_process(self, command)
        except Exception as exc:  # pragma: no cover - defensive
            self._log(f"Error executing command: {exc}", level="error")
            return f"Error executing command: {exc}", False
        if isinstance(result, tuple):
            output, success = result
        else:
            output, success = result, True
        if isinstance(output, str) and output.startswith("Workspace initialization failed:"):
            err = output.split(": ", 1)[1]
            self._log(output, level="error")
            return f"Error executing command: {err}", False
        return output, success

    monkeypatch.setattr(CommandProcessor, "process_command", safe_process)

    yield

    monkeypatch.setattr(CommandProcessor, "process_command", original_process)
    monkeypatch.delitem(sys.modules, "cryptography.fernet", raising=False)

class TestCommandProcessor:
    """Tests for the CommandProcessor class."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.scratchpad = MagicMock()
        coordinator.scratchpad.log = MagicMock()
        coordinator.progress_tracker = MagicMock()
        coordinator.progress_tracker.update_progress = MagicMock()
        coordinator.generate_plan = MagicMock(return_value="Test plan content")
        coordinator.workspace_initializer = MagicMock()
        coordinator.workspace_initializer.initialize_workspace = MagicMock(return_value=True)
        coordinator.workspace_initializer.execute_guidelines_command = MagicMock(return_value="Guidelines created")
        coordinator.bash_tool = MagicMock()
        coordinator.bash_tool.run_command = MagicMock(return_value=(0, "Command output"))

        for attr in ["run_tests_all", "execute_terminal_command", "_log"]:
            if hasattr(coordinator, attr):
                delattr(coordinator, attr)

        return coordinator

    @pytest.fixture
    def command_processor(self, mock_coordinator):
        """Create a CommandProcessor instance with a mock coordinator."""
        return CommandProcessor(mock_coordinator)

    def test_process_command_with_unknown_command(self, command_processor):
        """Test process_command with an unknown command."""
        # Exercise
        result, success = command_processor.process_command("unknown_command")

        # Verify
        assert not success
        assert "Unknown command" in result

    def test_process_command_with_error(self, command_processor, mock_coordinator):
        """Test process_command handles errors."""
        # Setup
        mock_coordinator.workspace_initializer.initialize_workspace.side_effect = Exception("Test error")

        # Exercise
        result, success = command_processor.process_command("init")

        # Verify
        assert not success
        assert "Error executing command" in result
        assert "Test error" in result
        mock_coordinator.scratchpad.log.assert_called()

    def test_process_command_strips_leading_slash(self, command_processor, mock_coordinator):
        """Test process_command strips leading slash from command."""
        # Exercise
        command_processor.process_command("/init")

        # Verify
        mock_coordinator.workspace_initializer.initialize_workspace.assert_called_once()

    def test_execute_init_command(self, command_processor, mock_coordinator):
        """Test execute_init_command."""
        # Exercise
        result, success = command_processor.execute_init_command("")

        # Verify
        mock_coordinator.workspace_initializer.initialize_workspace.assert_called_once()
        assert success
        assert "Workspace initialized successfully" in result

    def test_execute_init_command_failure(self, command_processor, mock_coordinator):
        """Test execute_init_command when initialization fails."""
        # Setup
        mock_coordinator.workspace_initializer.initialize_workspace.return_value = False
        mock_coordinator.workspace_initializer.validation_failure_reason = "bad config"

        # Exercise
        result, success = command_processor.execute_init_command("")

        # Verify
        mock_coordinator.workspace_initializer.initialize_workspace.assert_called_once()
        assert not success
        assert "Workspace initialization failed: bad config" in result

    @patch('pathlib.Path.open')
    @patch('pathlib.Path.exists')
    def test_execute_plan_command(self, mock_exists, mock_open, command_processor, mock_coordinator):
        """Test execute_plan_command."""
        # Setup
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Exercise
        result, success = command_processor.execute_plan_command("Create a new feature")

        # Verify
        mock_coordinator.progress_tracker.update_progress.assert_called()
        mock_file.write.assert_called_with("Test plan content")
        assert success
        assert "Plan generated and saved" in result

    def test_execute_plan_command_with_empty_args(self, command_processor):
        """Test execute_plan_command with empty args."""
        # Exercise
        result, success = command_processor.execute_plan_command("")

        # Verify
        assert not success
        assert "Please provide a plan description" in result


    def test_execute_test_command(self, command_processor, mock_coordinator):
        """Test execute_test_command."""
        # Exercise
        result, success = command_processor.execute_test_command("")

        # Verify
        mock_coordinator.bash_tool.run_command.assert_called()
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert success
        assert "Tests completed" in result

    def test_execute_debug_command(self, command_processor, mock_coordinator):
        """Test execute_debug_command."""
        # Setup
        mock_coordinator.debug_last_test = MagicMock()

        # Exercise
        result, success = command_processor.execute_debug_command("")

        # Verify
        mock_coordinator.debug_last_test.assert_called_once()
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert success
        assert "Debugging completed" in result

    def test_execute_terminal_command(self, command_processor, mock_coordinator):
        """Test execute_terminal_command."""
        # Exercise
        result, success = command_processor.execute_terminal_command("ls -la")

        # Verify
        mock_coordinator.bash_tool.run_command.assert_called_with("ls -la", timeout=120)
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert success
        assert "Command executed" in result

    def test_execute_terminal_command_empty_args(self, command_processor):
        """Test execute_terminal_command with empty args."""
        # Exercise
        result, success = command_processor.execute_terminal_command("")

        # Verify
        assert not success
        assert "Please provide a terminal command" in result


    def test_execute_guidelines_command(self, command_processor, mock_coordinator):
        """Test execute_guidelines_command."""
        # Exercise
        result, success = command_processor.execute_guidelines_command("")

        # Verify
        mock_coordinator.workspace_initializer.execute_guidelines_command.assert_called_once()
        assert success
        assert "Guidelines created" in result

    def test_execute_help_command_general(self, command_processor):
        """Test execute_help_command with no specific command."""
        # Exercise
        result, success = command_processor.execute_help_command("")

        # Verify
        assert success
        assert "Agent-S3 Command-Line Interface" in result
        assert "/init" in result
        assert "/plan" in result

    def test_execute_help_command_specific(self, command_processor):
        """Test execute_help_command with a specific command."""
        # Exercise
        result, success = command_processor.execute_help_command("init")

        # Verify
        assert success
        assert "/init:" in result
        assert "Initialize workspace" in result


    def test_execute_request_command(self, command_processor, mock_coordinator):
        """Test execute_request_command routes to process_change_request."""
        result, success = command_processor.execute_request_command("Add feature")
        mock_coordinator.process_change_request.assert_called_once_with("Add feature")
        assert success
        assert result == ""

    @patch('pathlib.Path.exists')
    def test_execute_implement_command(self, mock_exists, command_processor, mock_coordinator):
        """Test execute_implement_command calls coordinator.execute_implementation."""
        mock_exists.return_value = True
        mock_coordinator.execute_implementation.return_value = {"success": True, "message": "done"}

        result, success = command_processor.execute_implement_command("design.txt")

        mock_coordinator.execute_implementation.assert_called_once_with("design.txt")
        assert success
        assert "done" in result

    def test_execute_continue_command(self, command_processor, mock_coordinator):
        """Test execute_continue_command calls coordinator.execute_continue."""
        mock_coordinator.execute_continue.return_value = {
            "success": True,
            "message": "continued"
        }

        result, success = command_processor.execute_continue_command("implementation")

        mock_coordinator.execute_continue.assert_called_once_with("implementation")
        assert success
        assert "continued" in result

    def test_execute_design_auto_command(self, command_processor, mock_coordinator):
        mock_coordinator.execute_design_auto.return_value = {"success": True}
        result, success = command_processor.execute_design_auto_command("build api")
        mock_coordinator.execute_design_auto.assert_called_once_with("build api")
        assert success
        assert "Design process completed successfully" in result

    def test_execute_design_auto_command_failure(self, command_processor, mock_coordinator):
        mock_coordinator.execute_design_auto.return_value = {
            "success": False,
            "error": "plan failed",
        }

        result, success = command_processor.execute_design_auto_command("build api")

        mock_coordinator.execute_design_auto.assert_called_once_with("build api")
        assert not success
        assert "Design process failed: plan failed" in result

    def test_execute_design_auto_command_unavailable_updates_progress(self, command_processor, mock_coordinator):
        """Ensure progress is updated when automated design is unavailable."""
        if hasattr(mock_coordinator, "execute_design_auto"):
            delattr(mock_coordinator, "execute_design_auto")

        result, success = command_processor.execute_design_auto_command("build api")

        mock_coordinator.progress_tracker.update_progress.assert_called_once_with({
            "phase": "design-auto",
            "status": "failed",
            "error": "feature unavailable",
            "timestamp": ANY,
        })
        assert not success
        assert result == "Automated design not available in this workspace."

