"""
Unit tests for the debugging integration in the Coordinator class.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.coordinator import Coordinator
from agent_s3.debugging_manager import DebuggingManager
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager

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
        "host_os_type": "linux",
        "task_state_directory": "./task_snapshots",
        "max_attempts": 3,
        "context_management": {"enabled": False}
    }
    config.get_log_file_path.return_value = "log/dev.log"
    return config


@pytest.fixture
def mock_file_tool():
    """Create a mock file tool."""
    file_tool = MagicMock()
    file_tool.read_file.return_value = "Mock file content"
    file_tool.write_file.return_value = True
    return file_tool


@pytest.fixture
def mock_bash_tool():
    """Create a mock bash tool."""
    bash_tool = MagicMock()
    bash_tool.run_command.return_value = (0, "Success")
    return bash_tool


@pytest.fixture
def mock_coordinator(mock_config):
    """Create a fully mocked coordinator for testing debugging functionality."""
    
    # Create patches for actual coordinator imports only
    patches = [
        # Core component patches (from coordinator imports)
        patch('agent_s3.coordinator.EnhancedScratchpadManager'),
        patch('agent_s3.coordinator.ImplementationManager'),
        patch('agent_s3.coordinator.FeatureGroupProcessor'),
        patch('agent_s3.coordinator.FileHistoryAnalyzer'),
        patch('agent_s3.coordinator.Planner'),
        patch('agent_s3.coordinator.ProgressTracker'),
        patch('agent_s3.coordinator.PromptModerator'),
        patch('agent_s3.coordinator.RouterAgent'),
        patch('agent_s3.coordinator.DesignManager'),
        patch('agent_s3.coordinator.TaskResumer'),
        patch('agent_s3.coordinator.TaskStateManager'),
        patch('agent_s3.coordinator.TechStackDetector'),
        patch('agent_s3.coordinator.WorkspaceInitializer'),
        # Tool patches (from coordinator imports)
        patch('agent_s3.coordinator.ASTTool'),
        patch('agent_s3.coordinator.BashTool'),
        patch('agent_s3.coordinator.CodeAnalysisTool'),
        patch('agent_s3.coordinator.ContextManager'),
        patch('agent_s3.coordinator.ContextRegistry'),
        patch('agent_s3.coordinator.DatabaseTool'),
        patch('agent_s3.coordinator.DatabaseManager'),
        patch('agent_s3.coordinator.EmbeddingClient'),
        patch('agent_s3.coordinator.EnvTool'),
        patch('agent_s3.coordinator.ErrorContextManager'),
        patch('agent_s3.coordinator.FileTool'),
        patch('agent_s3.coordinator.GitTool'),
        patch('agent_s3.coordinator.TerminalExecutor'),
        patch('agent_s3.coordinator.MemoryManager'),
        patch('agent_s3.coordinator.TestCritic'),
        patch('agent_s3.coordinator.TestFrameworks'),
        patch('agent_s3.coordinator.TestRunnerTool'),
        patch('agent_s3.coordinator.PlanningWorkflow'),
        patch('agent_s3.coordinator.ImplementationWorkflow'),
        patch('agent_s3.coordinator.DebuggingManager'),
        patch('agent_s3.coordinator.CodeGenerator'),
        patch('agent_s3.coordinator.CoordinatorRegistry'),
        # Patch the lazy orchestrator import
        patch('agent_s3.coordinator.orchestrator.WorkflowOrchestrator'),
        # Patch file operations that cause issues
        patch('agent_s3.tools.memory_manager.Path.exists', return_value=False),
        patch('agent_s3.router_agent._load_llm_config', return_value={}),
        patch('builtins.open', create=True),
    ]
    
    # Start all patches
    mocks = []
    for p in patches:
        mocks.append(p.start())
    
    try:
        # Create coordinator with all dependencies mocked
        coordinator = Coordinator(config=mock_config)
        
        # Manually set up all required attributes that tests expect
        coordinator.scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        coordinator.progress_tracker = MagicMock()
        coordinator.file_tool = MagicMock()
        coordinator.bash_tool = MagicMock()
        coordinator.git_tool = MagicMock()
        coordinator.code_analysis_tool = MagicMock()
        coordinator.task_state_manager = MagicMock()
        coordinator.database_manager = MagicMock()
        coordinator.debugging_manager = MagicMock(spec=DebuggingManager)
        coordinator.error_context_manager = MagicMock()
        coordinator.memory_manager = MagicMock()
        coordinator.prompt_moderator = MagicMock()
        coordinator.test_runner_tool = MagicMock()
        coordinator.test_critic = MagicMock()
        coordinator.env_tool = MagicMock()
        coordinator.tech_stack_detector = MagicMock()
        coordinator.orchestrator = MagicMock()
        coordinator.design_manager = MagicMock()
        coordinator.implementation_manager = MagicMock()
        coordinator.deployment_manager = MagicMock()
        coordinator.router_agent = MagicMock()
        coordinator.llm = coordinator.router_agent
        coordinator.embedding_client = MagicMock()
        coordinator.coordinator_config = MagicMock()
        
        # Set up common mock returns for debugging tests
        coordinator.progress_tracker.get_latest_progress.return_value = None
        coordinator.error_context_manager.collect_error_context.return_value = {
            "parsed_error": {
                "file_paths": ["test.py"],
                "line_numbers": [42]
            }
        }
        coordinator.error_context_manager.attempt_automated_recovery.return_value = (False, "No auto-fix")
        coordinator.debugging_manager.handle_error.return_value = {
            "success": True,
            "description": "Debug successful"
        }
        
        yield coordinator
        
    finally:
        # Stop all patches
        for mock in mocks:
            mock.stop()


class TestCoordinatorDebuggingIntegration:
    """Test the debugging integration functionality of the Coordinator."""

    def test_debug_last_test_with_no_output(self, mock_coordinator):
        """Test debug_last_test when no progress output is available."""
        # Set up: no latest progress available
        mock_coordinator.progress_tracker.get_latest_progress.return_value = None

        # Execute
        result = mock_coordinator.debug_last_test()

        # Assert
        assert result is None
        mock_coordinator.progress_tracker.get_latest_progress.assert_called_once()
        # Should not attempt any error context collection
        mock_coordinator.error_context_manager.collect_error_context.assert_not_called()

    def test_debug_last_test_basic_recovery(self, mock_coordinator):
        """Test debug_last_test with successful automated recovery."""
        # Set up: progress with error available
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Test failed: assert x == y"
        }
        
        # Set up: automated recovery succeeds
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (True, "Fixed automatically")

        # Execute
        result = mock_coordinator.debug_last_test()

        # Assert
        assert result is None  # Successful debugging returns None
        mock_coordinator.progress_tracker.get_latest_progress.assert_called_once()
        mock_coordinator.error_context_manager.collect_error_context.assert_called_once()
        mock_coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()
        # Should not need advanced debugging
        mock_coordinator.debugging_manager.handle_error.assert_not_called()

    def test_debug_last_test_advanced_debugging(self, mock_coordinator):
        """Test debug_last_test falling back to advanced debugging."""
        # Set up: progress with error available
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Complex test failure"
        }
        
        # Set up: automated recovery fails, advanced debugging succeeds
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (False, "Auto-fix failed")
        mock_coordinator.debugging_manager.handle_error.return_value = {
            "success": True,
            "description": "Advanced debugging successful"
        }

        # Execute
        result = mock_coordinator.debug_last_test()

        # Assert
        assert result is None  # Successful debugging returns None
        mock_coordinator.progress_tracker.get_latest_progress.assert_called_once()
        mock_coordinator.error_context_manager.collect_error_context.assert_called_once()
        mock_coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()
        mock_coordinator.debugging_manager.handle_error.assert_called_once()

    def test_debug_last_test_failed_debugging(self, mock_coordinator):
        """Test debug_last_test when all debugging attempts fail."""
        # Set up: progress with error available
        mock_coordinator.progress_tracker.get_latest_progress.return_value = {
            "output": "Unfixable test failure"
        }
        
        # Set up: both automated and advanced debugging fail
        mock_coordinator.error_context_manager.attempt_automated_recovery.return_value = (False, "Auto-fix failed")
        mock_coordinator.debugging_manager.handle_error.return_value = {
            "success": False,
            "description": "Could not resolve error"
        }

        # Execute
        result = mock_coordinator.debug_last_test()

        # Assert
        assert result is None  # Even failed debugging returns None (logs the failure)
        mock_coordinator.progress_tracker.get_latest_progress.assert_called_once()
        mock_coordinator.error_context_manager.collect_error_context.assert_called_once()
        mock_coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()
        mock_coordinator.debugging_manager.handle_error.assert_called_once()

    def test_shutdown_closes_scratchpad(self, mock_coordinator):
        """Test that coordinator shutdown properly closes the scratchpad."""
        # Execute
        mock_coordinator.shutdown()

        # Assert
        mock_coordinator.scratchpad.close.assert_called_once()