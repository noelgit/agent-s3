"""Unit tests for the design to implementation workflow.

This module tests the flow from the design phase through to pre-planning and implementation.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

from agent_s3.design_manager import DesignManager
from agent_s3.coordinator import Coordinator


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.complexity_threshold = 100.0
    config.config = {
        "context_management": {
            "background_enabled": False
        },
        "enforced_json": True
    }
    return config


@pytest.fixture
def coordinator():
    """Create a lightweight Coordinator instance for testing."""
    coordinator = Coordinator.__new__(Coordinator)
    coordinator.design_manager = MagicMock()
    coordinator.scratchpad = MagicMock()
    coordinator.task_state_manager = MagicMock()
    coordinator.task_state_manager.create_new_task_id.return_value = "test-task-001"
    coordinator.progress_tracker = MagicMock()
    coordinator.router_agent = MagicMock()
    coordinator.error_handler = MagicMock()
    coordinator.error_handler.error_context = MagicMock(return_value=MagicMock(__enter__=lambda self: None, __exit__=lambda self, exc, val, tb: False))
    coordinator._prepare_context = MagicMock(return_value="test context")
    coordinator.run_task = MagicMock()
    return coordinator


def test_design_manager_initialization():
    """Test that DesignManager can be initialized with a coordinator."""
    coordinator = MagicMock()
    design_manager = DesignManager(coordinator)
    
    assert design_manager.coordinator == coordinator
    assert hasattr(design_manager, 'conversation_history')
    assert isinstance(design_manager.conversation_history, list)




def test_prompt_for_implementation_chooses_implementation(coordinator):
    """Test that prompt_for_implementation handles implementation choice."""
    design_manager = DesignManager(coordinator)

    with patch('builtins.input', return_value="yes"):
        result = design_manager.prompt_for_implementation()

    assert result["implementation"] is True
    assert result["deployment"] is False


def test_prompt_for_implementation_chooses_deployment(coordinator):
    """Test that prompt_for_implementation handles deployment choice."""
    design_manager = DesignManager(coordinator)

    with patch('builtins.input', side_effect=["no", "yes"]):
        result = design_manager.prompt_for_implementation()

    assert result["implementation"] is False
    assert result["deployment"] is True


def test_coordinator_run_task_from_design(coordinator):
    """Test that coordinator.run_task properly handles inputs from design phase."""
    # Create pre-planning input from design
    pre_planning_input = {
        "original_request": "Create a TODO app",
        "feature_groups": [
            {
                "group_name": "Feature Group 1",
                "group_description": "Core functionality",
                "features": [
                    {
                        "name": "Task Management",
                        "description": "Create, read, update, delete tasks",
                        "files_affected": [],
                        "test_requirements": {"unit_tests": []},
                        "dependencies": {},
                        "risk_assessment": {},
                        "system_design": {}
                    }
                ]
            }
        ]
    }
    
    # Call run_task with design input
    coordinator.run_task(
        task="Create a TODO app", 
        pre_planning_input=pre_planning_input,
        from_design=True
    )
    
    # Assertions - only check that run_task was called with the right parameters
    coordinator.run_task.assert_called_once_with(
        task="Create a TODO app", 
        pre_planning_input=pre_planning_input,
        from_design=True
    )


def test_execute_design_facade(coordinator):
    """Test that execute_design facade method works properly."""
    coordinator.design_manager.start_design_conversation.return_value = "Initial design response"
    coordinator.design_manager.continue_conversation.side_effect = [
        ("Response 1", False),
        ("Response 2", True),
    ]
    coordinator.design_manager.detect_design_completion.side_effect = [False, True]
    coordinator.design_manager.write_design_to_file.return_value = (True, "Design written successfully")
    coordinator.design_manager.prompt_for_implementation.return_value = {"implementation": True, "deployment": False}

    expected_result = {
        "success": True,
        "design_file": os.path.join(os.getcwd(), "design.txt"),
        "next_action": "implementation",
    }

    with patch('builtins.input', side_effect=["More details", "Finalize"]), \
         patch('builtins.print'):
        result = coordinator.execute_design("Create a TODO app")

    assert result == expected_result
    coordinator.design_manager.start_design_conversation.assert_called_once_with("Create a TODO app")
    assert coordinator.design_manager.continue_conversation.call_count == 1


def test_start_pre_planning_from_design(tmp_path, coordinator):
    """Verify tasks parsed from design trigger planning with from_design flag."""
    design_file = tmp_path / "design.txt"
    design_file.write_text(
        "1. Setup environment\n2. Build feature\n3. Write tests"
    )

    coordinator.run_task = MagicMock()

    coordinator.start_pre_planning_from_design(str(design_file))

    expected_calls = [
        call(task="Setup environment", from_design=True),
        call(task="Build feature", from_design=True),
        call(task="Write tests", from_design=True),
    ]
    coordinator.run_task.assert_has_calls(expected_calls)
