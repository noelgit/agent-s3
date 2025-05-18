"""Tests for the CommandProcessor component."""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.command_processor import CommandProcessor

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
        coordinator.planner = MagicMock()
        coordinator.planner.generate_plan = MagicMock(return_value="Test plan content")
        coordinator.workspace_initializer = MagicMock()
        coordinator.workspace_initializer.initialize_workspace = MagicMock(return_value=True)
        coordinator.workspace_initializer.execute_personas_command = MagicMock(return_value="Personas created")
        coordinator.workspace_initializer.execute_guidelines_command = MagicMock(return_value="Guidelines created")
        coordinator.bash_tool = MagicMock()
        coordinator.bash_tool.run_command = MagicMock(return_value=(0, "Command output"))

        # New coordinator facade methods used by additional command tests
        coordinator.execute_design = MagicMock(return_value={
            "success": True,
            "design_file": "design.txt",
            "next_action": None,
        })
        coordinator.execute_implementation = MagicMock(return_value={
            "success": True,
            "message": "Implementation completed",
        })
        coordinator.execute_continue = MagicMock(return_value={
            "success": True,
            "message": "Continuation completed",
        })
        coordinator.execute_deployment = MagicMock(return_value={
            "success": True,
            "message": "Deployment completed",
        })
        coordinator.implementation_manager = MagicMock()
        coordinator.implementation_manager.continue_implementation = MagicMock(return_value={
            "success": True,
            "next_pending": None,
        })
        coordinator.deployment_manager = MagicMock()

        return coordinator
    
    @pytest.fixture
    def command_processor(self, mock_coordinator):
        """Create a CommandProcessor instance with a mock coordinator."""
        return CommandProcessor(mock_coordinator)
    
    def test_process_command_with_unknown_command(self, command_processor):
        """Test process_command with an unknown command."""
        # Exercise
        result = command_processor.process_command("unknown_command")
        
        # Verify
        assert "Unknown command" in result
    
    def test_process_command_with_error(self, command_processor, mock_coordinator):
        """Test process_command handles errors."""
        # Setup
        mock_coordinator.workspace_initializer.initialize_workspace.side_effect = Exception("Test error")
        
        # Exercise
        result = command_processor.process_command("init")
        
        # Verify
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
        result = command_processor.execute_init_command("")
        
        # Verify
        mock_coordinator.workspace_initializer.initialize_workspace.assert_called_once()
        assert "Workspace initialized successfully" in result
    
    @patch('pathlib.Path.open')
    @patch('pathlib.Path.exists')
    def test_execute_plan_command(self, mock_exists, mock_open, command_processor, mock_coordinator):
        """Test execute_plan_command."""
        # Setup
        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Exercise
        result = command_processor.execute_plan_command("Create a new feature")
        
        # Verify
        mock_coordinator.planner.generate_plan.assert_called_with("Create a new feature")
        mock_coordinator.progress_tracker.update_progress.assert_called()
        mock_file.write.assert_called_with("Test plan content")
        assert "Plan generated and saved" in result
    
    def test_execute_plan_command_with_empty_args(self, command_processor):
        """Test execute_plan_command with empty args."""
        # Exercise
        result = command_processor.execute_plan_command("")
        
        # Verify
        assert "Please provide a plan description" in result
    
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_execute_generate_command(self, mock_read_text, mock_exists, command_processor, mock_coordinator):
        """Test execute_generate_command."""
        # Setup
        mock_exists.return_value = True
        mock_read_text.return_value = "Test plan content"
        mock_coordinator.execute_generate = MagicMock()
        
        # Exercise
        command_processor.execute_generate_command("")

        # Verify
        mock_coordinator.execute_generate.assert_called_once()
        mock_coordinator.progress_tracker.update_progress.assert_called()
    
    @patch('pathlib.Path.exists')
    def test_execute_generate_command_no_plan(self, mock_exists, command_processor):
        """Test execute_generate_command with no plan file."""
        # Setup
        mock_exists.return_value = False
        
        # Exercise
        result = command_processor.execute_generate_command("")
        
        # Verify
        assert "plan.txt not found" in result
    
    def test_execute_test_command(self, command_processor, mock_coordinator):
        """Test execute_test_command."""
        # Exercise
        result = command_processor.execute_test_command("")
        
        # Verify
        mock_coordinator.bash_tool.run_command.assert_called()
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert "Tests completed" in result
    
    def test_execute_debug_command(self, command_processor, mock_coordinator):
        """Test execute_debug_command."""
        # Setup
        mock_coordinator.debug_last_test = MagicMock()
        
        # Exercise
        result = command_processor.execute_debug_command("")
        
        # Verify
        mock_coordinator.debug_last_test.assert_called_once()
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert "Debugging completed" in result
    
    def test_execute_terminal_command(self, command_processor, mock_coordinator):
        """Test execute_terminal_command."""
        # Exercise
        result = command_processor.execute_terminal_command("ls -la")
        
        # Verify
        mock_coordinator.bash_tool.run_command.assert_called_with("ls -la", timeout=120)
        mock_coordinator.progress_tracker.update_progress.assert_called()
        assert "Command executed" in result
    
    def test_execute_terminal_command_empty_args(self, command_processor):
        """Test execute_terminal_command with empty args."""
        # Exercise
        result = command_processor.execute_terminal_command("")
        
        # Verify
        assert "Please provide a terminal command" in result
    
    def test_execute_personas_command(self, command_processor, mock_coordinator):
        """Test execute_personas_command."""
        # Exercise
        result = command_processor.execute_personas_command("")
        
        # Verify
        mock_coordinator.workspace_initializer.execute_personas_command.assert_called_once()
        assert "Personas created" in result
    
    def test_execute_guidelines_command(self, command_processor, mock_coordinator):
        """Test execute_guidelines_command."""
        # Exercise
        result = command_processor.execute_guidelines_command("")
        
        # Verify
        mock_coordinator.workspace_initializer.execute_guidelines_command.assert_called_once()
        assert "Guidelines created" in result
    
    def test_execute_help_command_general(self, command_processor):
        """Test execute_help_command with no specific command."""
        # Exercise
        result = command_processor.execute_help_command("")
        
        # Verify
        assert "Available commands" in result
        assert "/init:" in result
        assert "/plan" in result
        assert "/generate" in result
    
    def test_execute_help_command_specific(self, command_processor):
        """Test execute_help_command with a specific command."""
        # Exercise
        result = command_processor.execute_help_command("init")

        # Verify
        assert "/init:" in result
        assert "Initialize workspace" in result

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.read_text')
    def test_generate_command_fallback_to_process_change_request(self, mock_read_text, mock_exists, command_processor, mock_coordinator):
        """Ensure generate command uses process_change_request when execute_generate is unavailable."""
        mock_exists.return_value = True
        mock_read_text.return_value = "Plan"
        if hasattr(mock_coordinator, 'execute_generate'):
            delattr(mock_coordinator, 'execute_generate')
        mock_coordinator.process_change_request = MagicMock()

        command_processor.execute_generate_command("")

        mock_coordinator.process_change_request.assert_called_once_with("Plan", skip_planning=True)

    def test_execute_request_command(self, command_processor, mock_coordinator):
        """Test execute_request_command routes to process_change_request."""
        result = command_processor.execute_request_command("Add feature")
        mock_coordinator.process_change_request.assert_called_once_with("Add feature")
        assert result == ""

    @patch.object(CommandProcessor, "execute_implement_command", return_value="Implementation triggered")
    def test_execute_design_command_auto_implementation(self, mock_impl, command_processor, mock_coordinator):
        """Design command triggers implementation when coordinator requests it."""
        mock_coordinator.execute_design.return_value = {
            "success": True,
            "design_file": "design.txt",
            "next_action": "implementation",
        }

        result = command_processor.execute_design_command("Build app")

        mock_coordinator.execute_design.assert_called_once_with("Build app")
        mock_impl.assert_called_once_with("")
        assert "Implementation triggered" in result

    def test_execute_design_command_cancelled(self, command_processor, mock_coordinator):
        """Design command handles user cancellation."""
        mock_coordinator.execute_design.return_value = {"success": False, "cancelled": True}

        result = command_processor.execute_design_command("Build app")

        assert result == "Design process cancelled by user."

    def test_execute_design_command_error(self, command_processor, mock_coordinator):
        """Design command handles design errors."""
        mock_coordinator.execute_design.return_value = {"success": False, "error": "Validation failed"}

        result = command_processor.execute_design_command("Build app")

        assert "Design process failed: Validation failed" == result

    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_implement_command_success(self, mock_exists, command_processor, mock_coordinator):
        """Implement command runs successfully."""
        mock_coordinator.execute_implementation.return_value = {"success": True, "message": "Impl done"}

        result = command_processor.execute_implement_command("")

        mock_coordinator.execute_implementation.assert_called_once_with("design.txt")
        assert result == "Impl done"

    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_implement_command_failure(self, mock_exists, command_processor, mock_coordinator):
        """Implement command surfaces failure message."""
        mock_coordinator.execute_implementation.return_value = {"success": False, "error": "Oops"}

        result = command_processor.execute_implement_command("")

        assert result == "Implementation failed: Oops"

    @patch('pathlib.Path.exists', return_value=False)
    def test_execute_implement_command_missing_design(self, mock_exists, command_processor):
        """Implement command validates design file presence."""
        result = command_processor.execute_implement_command("")

        assert "design.txt not found" in result

    def test_execute_continue_command_success(self, command_processor, mock_coordinator):
        """Continue command formats next task message."""
        mock_coordinator.execute_continue.return_value = {
            "success": True,
            "task_completed": "task1",
            "next_task": "task2",
        }

        result = command_processor.execute_continue_command("implementation")

        mock_coordinator.execute_continue.assert_called_once_with("implementation")
        assert result == "Task task1 completed. Next task: task2"

    def test_execute_continue_command_failure(self, command_processor, mock_coordinator):
        """Continue command surfaces errors."""
        mock_coordinator.execute_continue.return_value = {"success": False, "error": "No tasks"}

        result = command_processor.execute_continue_command("implementation")

        assert result == "Continuation failed: No tasks"

    def test_execute_continue_command_fallback(self, command_processor, mock_coordinator):
        """Continue command falls back to implementation manager when facade missing."""
        if hasattr(mock_coordinator, "execute_continue"):
            delattr(mock_coordinator, "execute_continue")
        mock_coordinator.implementation_manager.continue_implementation.return_value = {"success": True, "next_pending": None}

        result = command_processor.execute_continue_command("implementation")

        mock_coordinator.implementation_manager.continue_implementation.assert_called_once()
        assert result == "All implementation tasks completed."

    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_deploy_command_success(self, mock_exists, command_processor, mock_coordinator):
        """Deploy command returns deployment output."""
        mock_coordinator.execute_deployment.return_value = {
            "success": True,
            "message": "Deployment succeeded",
            "access_url": "http://localhost",
        }

        result = command_processor.execute_deploy_command("design.txt")

        mock_coordinator.execute_deployment.assert_called_once_with("design.txt")
        assert "Deployment succeeded" in result
        assert "http://localhost" in result

    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_deploy_command_failure(self, mock_exists, command_processor, mock_coordinator):
        """Deploy command surfaces deployment errors."""
        mock_coordinator.execute_deployment.return_value = {"success": False, "error": "Bad deploy"}

        result = command_processor.execute_deploy_command("design.txt")

        assert result == "Deployment failed: Bad deploy"

    @patch('pathlib.Path.exists', return_value=True)
    def test_execute_deploy_command_cancelled(self, mock_exists, command_processor, mock_coordinator):
        """Deploy command handles user cancellation."""
        mock_coordinator.execute_deployment.return_value = {"success": False, "cancelled": True}

        result = command_processor.execute_deploy_command("design.txt")

        assert result == "Deployment process cancelled by user."

    @patch('pathlib.Path.exists', return_value=False)
    def test_execute_deploy_command_missing_design(self, mock_exists, command_processor):
        """Deploy command validates design file presence."""
        result = command_processor.execute_deploy_command("design.txt")

        assert "design.txt not found" in result
