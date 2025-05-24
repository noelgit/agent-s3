"""Test the agent's ability to handle multi-step workflow tasks.

These tests verify that the system can:
1. Break down complex tasks into appropriate steps
2. Execute steps in the correct sequence
3. Track state between steps
4. Adapt to changing circumstances during execution
"""

import os
import sys
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.coordinator import Coordinator
from system_tests.mock_llm import MockLLMResponses


@pytest.fixture
def mock_coordinator(workspace, test_config, scratchpad):
    """Create a coordinator with mocked components for testing multi-step workflows."""
    # Create a coordinator with the test config
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)

    # Mock the LLM clients
    coordinator.llm = MagicMock()

    # Configure the mocks to return realistic responses
    def mock_create_plan(task, *args, **kwargs):
        # Generate a mock plan based on the task
        plan_dict = MockLLMResponses.create_plan_response(task)
        return json.dumps(plan_dict)

    def mock_generate_code(task, plan, *args, **kwargs):
        # Parse the plan from string to dict
        if isinstance(plan, str):
            try:
                plan_dict = json.loads(plan)
            except json.JSONDecodeError:
                # If the plan is not valid JSON, create a minimal dict
                plan_dict = {"test_specifications": []}
        else:
            plan_dict = plan

        # Generate mock code based on the task and plan
        return {"code": MockLLMResponses.generate_code_response(task, plan_dict)}

    # Patch the methods that make LLM calls
    coordinator.planner.create_plan = MagicMock(side_effect=mock_create_plan)
    coordinator.code_generator.generate_code = MagicMock(side_effect=mock_generate_code)

    # Mock environment for each test
    os.environ["TESTING_MULTI_STEP"] = "1"

    # Make run_tests always succeed in tests
    coordinator.run_tests = MagicMock(return_value={"success": True, "output": "All tests passed", "coverage": 95.0})

    # Mock bash tool to avoid actually running commands
    coordinator.bash_tool.run_command = MagicMock(return_value=(0, "Command executed successfully"))

    return coordinator


def test_feature_implementation_workflow(mock_coordinator):
    """Test a complete workflow for implementing a new feature with multiple steps."""
    # Define a complex task that requires multiple steps
    task = "Add a new user authentication system with login, logout, and password reset features"

    # Generate a unique task ID
    task_id = str(uuid.uuid4())

    # Configure the mock to track steps
    executed_steps = []
    original_execute_single_step = mock_coordinator._execute_single_step if hasattr(mock_coordinator, '_execute_single_step') else None

    def mock_execute_single_step(step_description, context=None):
        executed_steps.append(step_description)
        result = {"status": "completed", "step": step_description}
        return result

    # Patch the method for executing single steps
    if hasattr(mock_coordinator, '_execute_single_step'):
        mock_coordinator._execute_single_step = MagicMock(side_effect=mock_execute_single_step)

    # Execute the task
    result = mock_coordinator.execute_task(task)

    # Verify task execution
    assert result["success"] is True
    assert result["task_id"] is not None
    assert "phases" in result

    # Verify planning phase
    assert "planning" in result["phases"]
    assert result["phases"]["planning"]["success"] is True
    assert "plan" in result["phases"]["planning"]

    # Verify implementation phase
    assert "implementation" in result["phases"]
    assert result["phases"]["implementation"]["success"] is True

    # Verify that all required files were generated
    if "changes" in result:
        changes = result["changes"]

        # Should have at least one implementation file and one test file
        has_auth_implementation = any("auth" in file for file in changes.keys())
        has_test_file = any("test" in file for file in changes.keys())

        assert has_auth_implementation is True
        assert has_test_file is True

    # If we tracked steps, verify they were executed in the correct order
    if hasattr(mock_coordinator, '_execute_single_step'):
        # Should have at least planning, implementation, and testing steps
        assert any("plan" in step.lower() for step in executed_steps)
        assert any("implement" in step.lower() or "creat" in step.lower() or "add" in step.lower()
                 for step in executed_steps)
        assert any("test" in step.lower() for step in executed_steps)


def test_step_dependency_handling(mock_coordinator):
    """Test that the agent handles step dependencies correctly."""
    # Define a task with dependent steps
    task = "Create a data pipeline with ingestion, transformation, and export stages"

    # Generate step result sequences to test dependency handling
    # Each step will depend on the previous one's output

    # Track intermediate results
    intermediate_results = {}

    def mock_execute_single_step(step_description, context=None):
        if "ingestion" in step_description.lower():
            # First step creates output for next step
            intermediate_results["ingestion_output"] = {
                "data_source": "mock_source",
                "schema": {"id": "int", "name": "string", "value": "float"}
            }
            return {
                "status": "completed",
                "step": step_description,
                "output": intermediate_results["ingestion_output"]
            }
        elif "transformation" in step_description.lower():
            # Second step uses output from first step
            assert context is not None
            assert "ingestion_output" in intermediate_results

            # Verify second step uses first step's output
            if context:
                assert context.get("data_source") == "mock_source"

            # Generate output for third step
            intermediate_results["transformation_output"] = {
                "transformed_schema": {"id": "int", "name": "string", "normalized_value": "float"}
            }
            return {
                "status": "completed",
                "step": step_description,
                "output": intermediate_results["transformation_output"]
            }
        elif "export" in step_description.lower():
            # Third step uses output from second step
            assert context is not None
            assert "transformation_output" in intermediate_results

            # Verify third step uses second step's output
            if context:
                assert "transformed_schema" in context

            return {
                "status": "completed",
                "step": step_description,
                "output": {"export_status": "success", "records_processed": 100}
            }
        else:
            return {"status": "completed", "step": step_description}

    # Patch the method for executing single steps
    if hasattr(mock_coordinator, '_execute_single_step'):
        mock_coordinator._execute_single_step = MagicMock(side_effect=mock_execute_single_step)

    # Execute the task
    result = mock_coordinator.execute_task(task)

    # Verify task execution
    assert result["success"] is True

    # Verify that all intermediate results were created and used
    assert "ingestion_output" in intermediate_results
    assert "transformation_output" in intermediate_results


def test_error_recovery_and_continuation(mock_coordinator):
    """Test that the system can recover from errors and continue execution."""
    # Define a task that will have recoverable errors
    task = "Create a data validation system with parser, validator, and formatter components"

    # Track execution state
    execution_state = {
        "attempts": {},
        "current_step": None
    }

    def mock_execute_single_step(step_description, context=None):
        execution_state["current_step"] = step_description

        # Track attempts for this step
        if step_description not in execution_state["attempts"]:
            execution_state["attempts"][step_description] = 1
        else:
            execution_state["attempts"][step_description] += 1

        # Make parser component fail on first attempt
        if "parser" in step_description.lower() and execution_state["attempts"][step_description] == 1:
            return {
                "status": "failed",
                "step": step_description,
                "error": "Failed to implement parser component: TypeError: invalid arguments",
                "recoverable": True
            }
        # Make validator component fail on first and second attempts
        elif "validator" in step_description.lower() and execution_state["attempts"][step_description] <= 2:
            return {
                "status": "failed",
                "step": step_description,
                "error": "Failed to implement validator component: SyntaxError: invalid syntax",
                "recoverable": True
            }
        else:
            # All other steps (and retries) succeed
            return {"status": "completed", "step": step_description}

    # Patch the method for executing single steps
    if hasattr(mock_coordinator, '_execute_single_step'):
        mock_coordinator._execute_single_step = MagicMock(side_effect=mock_execute_single_step)

    # Execute the task
    result = mock_coordinator.execute_task(task)

    # Verify task execution
    assert result["success"] is True

    # Verify that there were retries for the failed steps
    if execution_state["attempts"]:
        parser_step = next((s for s in execution_state["attempts"].keys() if "parser" in s.lower()), None)
        validator_step = next((s for s in execution_state["attempts"].keys() if "validator" in s.lower()), None)

        if parser_step:
            assert execution_state["attempts"][parser_step] > 1
        if validator_step:
            assert execution_state["attempts"][validator_step] > 2


def test_adaptive_planning(mock_coordinator):
    """Test that the system can adapt the plan based on discoveries during execution."""
    # Define a task that requires adaptive planning
    task = "Implement a configuration manager with auto-reloading capabilities"

    # Track execution state
    execution_state = {
        "plan": None,
        "plan_modified": False,
        "steps_executed": []
    }

    # Original planning method
    original_create_plan = mock_coordinator.planner.create_plan

    def mock_create_plan_with_discovery(task_desc, *args, **kwargs):
        # Create the initial plan
        initial_plan = original_create_plan(task_desc, *args, **kwargs)
        execution_state["plan"] = initial_plan
        return initial_plan

    # Mock step execution to simulate a discovery
    def mock_execute_single_step(step_description, context=None):
        execution_state["steps_executed"].append(step_description)

        # If this is the implementation step, simulate discovering a dependency
        if any(term in step_description.lower() for term in ["implement", "create", "add"]):
            # We've discovered we need file system watching capabilities
            if not execution_state["plan_modified"]:
                # Update the plan to include the new discovery
                plan_dict = json.loads(execution_state["plan"])
                plan_dict["plan"].append("Add file system watching capability for auto-reloading")
                execution_state["plan"] = json.dumps(plan_dict)
                execution_state["plan_modified"] = True

                # Simulate updating the plan
                mock_coordinator.planner.create_plan = MagicMock(return_value=execution_state["plan"])

                # Indicate that the plan was modified
                return {
                    "status": "modified_plan",
                    "step": step_description,
                    "modification": "Added file system watching capability requirement",
                    "needs_replanning": True
                }

        # All other steps succeed normally
        return {"status": "completed", "step": step_description}

    # Patch the relevant methods
    mock_coordinator.planner.create_plan = MagicMock(side_effect=mock_create_plan_with_discovery)
    if hasattr(mock_coordinator, '_execute_single_step'):
        mock_coordinator._execute_single_step = MagicMock(side_effect=mock_execute_single_step)

    # Execute the task
    result = mock_coordinator.execute_task(task)

    # Verify task execution
    assert result["success"] is True

    # Verify that the plan was modified and new steps were executed
    assert execution_state["plan_modified"] is True

    # Should have executed steps related to file system watching
    has_file_watching_step = any("file" in step.lower() and "watch" in step.lower()
                               for step in execution_state["steps_executed"])

    # If the step execution is properly mocked, we should see the file watching step
    if execution_state["steps_executed"]:
        assert has_file_watching_step is True
