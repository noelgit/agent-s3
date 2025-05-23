"""
Tests for the Coordinator validation and debugging phases.

These tests focus on how the Coordinator validates code changes, handles test failures,
executes debugging workflows, and recovers from failures.
"""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import Section

# Test fixtures

@pytest.fixture
def mock_config():
    config = Config()
    config.config = {
        "max_attempts": 3,
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
         patch('agent_s3.coordinator.DatabaseManager'):
        
        coordinator = Coordinator(config=mock_config)
        
        # Mock required components for tests
        coordinator.test_runner_tool = MagicMock()
        coordinator.test_critic = MagicMock()
        coordinator.test_critic.run_analysis.return_value = {
            "verdict": None,
            "details": {"mutation_score": 80.0},
        }
        coordinator.database_manager = MagicMock()
        coordinator.database_manager.database_tool = MagicMock()
        coordinator.bash_tool = MagicMock()
        coordinator.scratchpad = MagicMock()
        coordinator.progress_tracker = MagicMock()
        coordinator.error_context_manager = MagicMock()
        coordinator.debugging_manager = MagicMock()
        coordinator.env_tool = MagicMock()
        
        yield coordinator

# Test _run_validation_phase method

def test_validation_phase_all_pass(coordinator):
    """Test validation phase with all validations passing."""
    # Set up mocks for successful validation
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(0, "No lint errors"), (0, "No type errors")]
    coordinator.run_tests = MagicMock(return_value={"success": True, "output": "All tests passed", "coverage": 80.0})
    
    # Execute
    result = coordinator._run_validation_phase()
    
    # Assert
    assert result["success"] is True  # Validation passed
    assert result["step"] is None  # No failing step
    assert result["lint_output"] == "No lint errors"
    assert result["type_output"] == "No type errors"
    assert result["test_output"] == "All tests passed"
    assert result["coverage"] == 80.0
    
    # Verify all validations were performed
    coordinator.database_manager.setup_database.assert_called()
    coordinator.database_manager.database_tool.get_schema_info.assert_called()
    assert coordinator.bash_tool.run_command.call_count == 2
    coordinator.run_tests.assert_called_once()

def test_validation_phase_database_failure(coordinator):
    """Test validation phase with database connection failure."""
    # Set up mocks for database validation failure
    coordinator.database_manager.setup_database.return_value = {
        "success": False, 
        "error": "Database connection failed"
    }
    
    # Execute
    result = coordinator._run_validation_phase()

    # Assert
    assert result["success"] is False  # Validation failed
    assert result["step"] == "database"  # Failing step
    assert result["test_output"] == "Database connection failed"  # Error info
    
    # Verify only database validation was performed
    coordinator.database_manager.setup_database.assert_called()
    coordinator.database_manager.database_tool.get_schema_info.assert_not_called()
    coordinator.bash_tool.run_command.assert_not_called()
    coordinator.run_tests.assert_not_called()

def test_validation_phase_lint_failure(coordinator):
    """Test validation phase with linting failure."""
    # Set up mocks for successful database validation but linting failure
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(1, "Lint errors found"), (0, "No type errors")]
    
    # Execute
    result = coordinator._run_validation_phase()

    # Assert
    assert result["success"] is False  # Validation failed
    assert result["step"] == "lint"  # Failing step
    assert result["lint_output"] == "Lint errors found"  # Error info
    
    # Verify validations were performed up to the failing point
    coordinator.database_manager.setup_database.assert_called()
    coordinator.database_manager.database_tool.get_schema_info.assert_called()
    coordinator.bash_tool.run_command.assert_called_once_with("flake8 .", timeout=120)
    coordinator.run_tests.assert_not_called()

def test_validation_phase_type_check_failure(coordinator):
    """Test validation phase with type checking failure."""
    # Set up mocks for successful database and lint validation but type check failure
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(0, "No lint errors"), (1, "Type errors found")]
    
    # Execute
    result = coordinator._run_validation_phase()

    # Assert
    assert result["success"] is False  # Validation failed
    assert result["step"] == "type_check"  # Failing step
    assert result["type_output"] == "Type errors found"  # Error info
    
    # Verify validations were performed up to the failing point
    coordinator.database_manager.setup_database.assert_called()
    coordinator.database_manager.database_tool.get_schema_info.assert_called()
    assert coordinator.bash_tool.run_command.call_count == 2
    coordinator.run_tests.assert_not_called()

def test_validation_phase_test_failure(coordinator):
    """Test validation phase with test execution failure."""
    # Set up mocks for successful db/lint/type validation but test failure
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(0, "No lint errors"), (0, "No type errors")]
    coordinator.run_tests = MagicMock(return_value={
        "success": False,
        "output": "Test failures detected",
        "coverage": 50.0,
    })
    
    # Execute
    result = coordinator._run_validation_phase()

    # Assert
    assert result["success"] is False  # Validation failed
    assert result["step"] == "tests"  # Failing step
    assert result["test_output"] == "Test failures detected"  # Error info
    assert result["coverage"] == 50.0
    
    # Verify all validations were performed up to the failing point
    coordinator.database_manager.setup_database.assert_called()
    coordinator.database_manager.database_tool.get_schema_info.assert_called()
    assert coordinator.bash_tool.run_command.call_count == 2
    coordinator.run_tests.assert_called_once()


def test_validation_phase_mutation_failure(coordinator):
    """Test validation fails when mutation score is below threshold."""
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(0, "No lint errors"), (0, "No type errors")]
    coordinator.run_tests = MagicMock(return_value={"success": True, "output": "All tests passed", "coverage": 80.0})
    coordinator.config.config["mutation_score_threshold"] = 75.0
    coordinator.test_critic.run_analysis.return_value = {
        "verdict": None,
        "details": {"mutation_score": 60.0},
    }

    result = coordinator._run_validation_phase()

    assert result["success"] is False
    assert result["step"] == "mutation"
    assert result["mutation_score"] == 60.0
    coordinator.test_critic.run_analysis.assert_called_once()


def test_validation_phase_invalid_threshold(coordinator):
    """Test invalid mutation_score_threshold defaults to 70.0."""
    coordinator.database_manager.setup_database.return_value = {"success": True}
    coordinator.bash_tool.run_command.side_effect = [(0, "No lint errors"), (0, "No type errors")]
    coordinator.run_tests = MagicMock(return_value={"success": True, "output": "All tests passed", "coverage": 80.0})
    coordinator.config.config["mutation_score_threshold"] = "invalid"
    coordinator.test_critic.run_analysis.return_value = {
        "verdict": None,
        "details": {"mutation_score": 60.0},
    }

    result = coordinator._run_validation_phase()

    assert result["success"] is False
    assert result["step"] == "mutation"
    assert result["mutation_score"] == 60.0
    coordinator.test_critic.run_analysis.assert_called_once()
    assert any(
        "Invalid mutation_score_threshold" in call.args[1]
        for call in coordinator.scratchpad.log.call_args_list
    )

def test_validation_phase_database_exception(coordinator):
    """Test validation phase with database validation exception."""
    # Set up mocks for database exception
    coordinator.database_manager.setup_database.side_effect = Exception("Database exception")

    # Execute
    result = coordinator._run_validation_phase()

    # Assert
    assert result["success"] is False  # Validation fails on exception
    assert result["step"] == "unknown_error"  # Unknown error step

    # Verify db validation was attempted and subsequent steps were skipped
    coordinator.database_manager.setup_database.assert_called()
    coordinator.bash_tool.run_command.assert_not_called()
    coordinator.run_tests.assert_not_called()

# Test run_tests method

def test_run_tests_success(coordinator):
    """Test run_tests method with successful test execution."""
    # Set up mocks
    coordinator.env_tool.activate_virtual_env.return_value = "source venv/bin/activate &&"
    coordinator.test_runner_tool.detect_runner.return_value = "pytest"
    coordinator.test_runner_tool.run_tests.return_value = (True, "All tests passed")
    coordinator.test_runner_tool.parse_coverage_report.return_value = 85.5
    
    # Mock path exists
    with patch('os.path.exists', return_value=True):
        # Execute
        result = coordinator.run_tests()
        
        # Assert
        assert result["success"] is True
        assert result["output"] == "All tests passed"
        assert result["coverage"] == 85.5
        coordinator.env_tool.activate_virtual_env.assert_called_once()
        coordinator.test_runner_tool.detect_runner.assert_called_once()
        coordinator.test_runner_tool.run_tests.assert_called_once()
        coordinator.test_runner_tool.parse_coverage_report.assert_called_once()

def test_run_tests_failure(coordinator):
    """Test run_tests method with test execution failure."""
    # Set up mocks
    coordinator.env_tool.activate_virtual_env.return_value = "source venv/bin/activate &&"
    coordinator.test_runner_tool.detect_runner.return_value = "pytest"
    coordinator.test_runner_tool.run_tests.return_value = (False, "Test failures detected")
    
    # Execute
    result = coordinator.run_tests()
    
    # Assert
    assert result["success"] is False
    assert result["output"] == "Test failures detected"
    assert result["coverage"] == 0.0  # Default when coverage can't be calculated
    coordinator.env_tool.activate_virtual_env.assert_called_once()
    coordinator.test_runner_tool.detect_runner.assert_called_once()
    coordinator.test_runner_tool.run_tests.assert_called_once()
    coordinator.test_runner_tool.parse_coverage_report.assert_not_called()

def test_run_tests_with_database_setup(coordinator):
    """Test run_tests method with database test setup."""
    # Configure database
    db_configs = {
        "main_db": {
            "type": "postgresql",
            "host": "localhost",
            "port": 5432,
            "database": "main_database",
            "username": "user"
        }
    }
    coordinator.config.config["databases"] = db_configs
    
    # Set up mocks
    coordinator.env_tool.activate_virtual_env.return_value = "source venv/bin/activate &&"
    coordinator.test_runner_tool.detect_runner.return_value = "pytest"
    coordinator.test_runner_tool.run_tests.return_value = (True, "All tests passed")
    coordinator.database_manager.setup_database.return_value = {"success": True}
    
    # Mock path exists
    with patch('os.path.exists', return_value=False):
        # Execute
        result = coordinator.run_tests()
        
        # Assert
        assert result["success"] is True
        assert result["output"] == "All tests passed"
        coordinator.env_tool.activate_virtual_env.assert_called_once()
        coordinator.database_manager.setup_database.assert_called()
        coordinator.test_runner_tool.run_tests.assert_called_once()

# Test debug_last_test method

def test_debug_last_test_success(coordinator):
    """Test debug_last_test method with successful debugging."""
    # Set up mocks
    coordinator.progress_tracker.get_latest_progress.return_value = {
        "output": "Test error: assert x == y failed"
    }
    coordinator.error_context_manager.collect_error_context.return_value = {
        "parsed_error": {
            "file_paths": ["path/to/file.py"],
            "line_numbers": [42]
        }
    }
    coordinator.error_context_manager.attempt_automated_recovery.return_value = (True, "Automated fix applied")
    coordinator.debugging_manager.handle_error.return_value = {
        "success": True,
        "description": "Debug successful"
    }
    coordinator.scratchpad.start_section = MagicMock()
    coordinator.scratchpad.end_section = MagicMock()
    
    # Execute
    result = coordinator.debug_last_test()
    
    # Assert
    assert result is None  # Successful debugging returns None
    coordinator.progress_tracker.get_latest_progress.assert_called_once()
    coordinator.error_context_manager.collect_error_context.assert_called_once()
    coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()
    coordinator.debugging_manager.handle_error.assert_not_called()  # Not called since automated fix worked
    coordinator.scratchpad.start_section.assert_called_once_with(Section.DEBUGGING, "Coordinator")
    coordinator.scratchpad.end_section.assert_called_once_with(Section.DEBUGGING)

def test_debug_last_test_advanced_debugging(coordinator):
    """Test debug_last_test method falling back to advanced debugging."""
    # Set up mocks
    coordinator.progress_tracker.get_latest_progress.return_value = {
        "output": "Test error: assert x == y failed"
    }
    coordinator.error_context_manager.collect_error_context.return_value = {
        "parsed_error": {
            "file_paths": ["path/to/file.py"],
            "line_numbers": [42]
        }
    }
    coordinator.error_context_manager.attempt_automated_recovery.return_value = (False, "Automation failed")
    coordinator.debugging_manager.handle_error.return_value = {
        "success": True,
        "description": "Advanced debugging fixed it"
    }
    coordinator.scratchpad.start_section = MagicMock()
    coordinator.scratchpad.end_section = MagicMock()
    
    # Execute
    result = coordinator.debug_last_test()
    
    # Assert
    assert result is None  # Successful debugging returns None
    coordinator.progress_tracker.get_latest_progress.assert_called_once()
    coordinator.error_context_manager.collect_error_context.assert_called_once()
    coordinator.error_context_manager.attempt_automated_recovery.assert_called_once()
    coordinator.debugging_manager.handle_error.assert_called_once()
    coordinator.scratchpad.start_section.assert_called_once_with(Section.DEBUGGING, "Coordinator")
    coordinator.scratchpad.end_section.assert_called_once_with(Section.DEBUGGING)

def test_debug_last_test_no_output(coordinator):
    """Test debug_last_test method with no test output available."""
    # Set up mocks
    coordinator.progress_tracker.get_latest_progress.return_value = None
    
    # Execute
    result = coordinator.debug_last_test()
    
    # Assert
    assert result is None  # No debugging needed
    coordinator.progress_tracker.get_latest_progress.assert_called_once()
    coordinator.error_context_manager.collect_error_context.assert_not_called()
    coordinator.error_context_manager.attempt_automated_recovery.assert_not_called()
    coordinator.debugging_manager.handle_error.assert_not_called()

def test_debug_last_test_exception(coordinator):
    """Test debug_last_test method with exception during debugging."""
    # Set up mocks
    coordinator.progress_tracker.get_latest_progress.return_value = {
        "output": "Test error: assert x == y failed"
    }
    coordinator.error_context_manager.collect_error_context.side_effect = Exception("Error context failed")
    
    # Execute
    result = coordinator.debug_last_test()
    
    # Assert
    assert "Error during finalization" in result  # Error message returned
    coordinator.progress_tracker.get_latest_progress.assert_called_once()
    coordinator.error_context_manager.collect_error_context.assert_called_once()
    coordinator.error_context_manager.attempt_automated_recovery.assert_not_called()
    coordinator.debugging_manager.handle_error.assert_not_called()
    coordinator.progress_tracker.update_progress.assert_called_with({
        "phase": "debug",
        "status": "failed",
        "error": "Error context failed",
        "timestamp": coordinator.progress_tracker.update_progress.call_args[0][0]["timestamp"]
    })
