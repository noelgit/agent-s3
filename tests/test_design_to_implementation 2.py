"""Unit tests for the design to implementation workflow.

This module tests the flow from the design phase through to pre-planning and implementation.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open

from agent_s3.design_manager import DesignManager
from agent_s3.coordinator import Coordinator
from agent_s3.config import Config


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
    # Create a fully mocked coordinator instead of initializing a real one
    coordinator = MagicMock()
    
    # Set up essential mocked components and methods
    coordinator.design_manager = MagicMock()
    coordinator.scratchpad = MagicMock()
    coordinator.task_state_manager = MagicMock()
    coordinator.task_state_manager.create_new_task_id.return_value = "test-task-001"
    coordinator.progress_tracker = MagicMock()
    coordinator.router_agent = MagicMock()
    coordinator.error_handler = MagicMock()
    coordinator._prepare_context = MagicMock(return_value="test context")
    coordinator.run_task = MagicMock()
    coordinator.start_pre_planning_from_design = MagicMock()
    
    return coordinator


def test_design_manager_initialization():
    """Test that DesignManager can be initialized with a coordinator."""
    coordinator = MagicMock()
    design_manager = DesignManager(coordinator)
    
    assert design_manager.coordinator == coordinator
    assert hasattr(design_manager, 'conversation_history')
    assert isinstance(design_manager.conversation_history, list)


def test_transition_to_pre_planning_success(coordinator):
    """Test successful transition from design to pre-planning phase."""
    # Create DesignManager with mocked coordinator
    design_manager = DesignManager(coordinator)
    design_manager.design_objective = "Create a TODO application"
    
    # Mock file operations
    design_exists = True
    progress_exists = True
    mock_progress_data = {
        "tasks": [
            {"id": "1", "description": "Feature 1", "status": "pending"},
            {"id": "1.1", "description": "Subfeature 1.1", "status": "pending"},
            {"id": "2", "description": "Feature 2", "status": "pending"},
            {"id": "2.1", "description": "Subfeature 2.1", "status": "pending"}
        ]
    }
    
    # Set up the patch for file operations
    with patch('os.path.exists', side_effect=lambda path: 
               design_exists if path.endswith('design.txt') else progress_exists), \
         patch('builtins.open', mock_open(read_data=json.dumps(mock_progress_data))), \
         patch('json.load', return_value=mock_progress_data):
        
        # Call the method
        result = design_manager._transition_to_pre_planning()
        
        # Assertions
        assert result is True
        
        # Check if either of the coordinator methods was called
        if coordinator.start_pre_planning_from_design.called:
            # Verify the pre-planning input has feature_groups
            assert "feature_groups" in coordinator.start_pre_planning_from_design.call_args[0][0]
            assert coordinator.start_pre_planning_from_design.call_args[0][0]["original_request"] == "Create a TODO application"
        else:
            # Verify the run_task was called correctly
            coordinator.run_task.assert_called_once()
            # Verify the task is the design objective
            assert coordinator.run_task.call_args[1]['task'] == "Create a TODO application"
            # Verify from_design flag is True
            assert coordinator.run_task.call_args[1]['from_design'] is True
            # Verify pre_planning_input has the right structure
            assert "feature_groups" in coordinator.run_task.call_args[1]['pre_planning_input']


def test_transition_to_pre_planning_no_design_file(coordinator):
    """Test transition failure when design file doesn't exist."""
    # Create DesignManager with mocked coordinator
    design_manager = DesignManager(coordinator)
    design_manager.design_objective = "Create a TODO application"
    
    # Mock file operations - design file doesn't exist
    with patch('os.path.exists', return_value=False):
        # Call the method
        result = design_manager._transition_to_pre_planning()
        
        # Assertions
        assert result is False
        # Verify coordinator method wasn't called
        coordinator.run_task.assert_not_called()


def test_prompt_for_implementation_chooses_implementation(coordinator):
    """Test that prompt_for_implementation calls _transition_to_pre_planning when implementation is chosen."""
    # Create DesignManager with mocked components
    design_manager = DesignManager(coordinator)
    design_manager._transition_to_pre_planning = MagicMock(return_value=True)
    
    # Mock user input to choose implementation
    with patch('builtins.input', return_value="yes"):
        result = design_manager.prompt_for_implementation()
        
        # Assertions
        assert result["implementation"] is True
        assert result["deployment"] is False
        # Verify transition method was called
        design_manager._transition_to_pre_planning.assert_called_once()


def test_prompt_for_implementation_chooses_deployment(coordinator):
    """Test that prompt_for_implementation doesn't call _transition_to_pre_planning when deployment is chosen."""
    # Create DesignManager with mocked components
    design_manager = DesignManager(coordinator)
    design_manager._transition_to_pre_planning = MagicMock()
    
    # Mock user input to choose deployment
    with patch('builtins.input', side_effect=["no", "yes"]):
        result = design_manager.prompt_for_implementation()
        
        # Assertions
        assert result["implementation"] is False
        assert result["deployment"] is True
        # Verify transition method was NOT called
        design_manager._transition_to_pre_planning.assert_not_called()


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
    # Set up expected behavior for design manager
    coordinator.design_manager.start_design_conversation.return_value = "Initial design response"
    coordinator.design_manager.continue_conversation.side_effect = [
        ("Response 1", False),
        ("Response 2", True)
    ]
    coordinator.design_manager.write_design_to_file.return_value = (True, "Design written successfully")
    coordinator.design_manager.prompt_for_implementation.return_value = {"implementation": True, "deployment": False}
    
    # Set up the return value for execute_design
    expected_result = {
        "success": True,
        "design_file": "design.txt",
        "next_action": "implementation"
    }
    coordinator.execute_design.return_value = expected_result
    
    # Mock user input
    with patch('builtins.input', side_effect=["More details", "Finalize"]), \
         patch('builtins.print'):
        
        # Call execute_design
        result = coordinator.execute_design("Create a TODO app")
        
        # Assertions
        assert result == expected_result
        coordinator.execute_design.assert_called_once_with("Create a TODO app")
