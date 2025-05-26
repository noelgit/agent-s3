import pytest
from unittest.mock import MagicMock

from agent_s3.task_resumer import TaskResumer
from agent_s3.task_state_manager import ExecutionState


@pytest.fixture
def resumer():
    coordinator = MagicMock()
    coordinator._execute_changes_atomically = MagicMock()
    coordinator._run_tests_after_changes = MagicMock(return_value={})
    coordinator._analyze_test_results = MagicMock(return_value={})
    task_state_manager = MagicMock()
    return TaskResumer(
        coordinator,
        task_state_manager,
        scratchpad=MagicMock(),
        progress_tracker=MagicMock(),
    )


def _base_state(sub_state: str) -> ExecutionState:
    changes = [{"path": "file.py", "content": "print('hi')"}]
    state = ExecutionState("task1", changes, 1, {})
    state.sub_state = sub_state
    return state


def test_resume_execution_applying_changes(resumer):
    state = _base_state("APPLYING_CHANGES")
    state.pending_changes = [{"path": "pending.py", "content": ""}]
    state.applied_changes = [{"path": "done.py", "content": ""}]

    resumer._resume_execution_phase(state)

    resumer.coordinator._execute_changes_atomically.assert_called_once_with(
        state.pending_changes,
        1,
        already_applied=state.applied_changes,
    )


def test_resume_execution_running_tests(resumer):
    state = _base_state("RUNNING_TESTS")

    resumer._resume_execution_phase(state)

    resumer.coordinator._run_tests_after_changes.assert_called_once_with(
        state.changes, 1
    )


def test_resume_execution_analyzing_results(resumer):
    state = _base_state("ANALYZING_RESULTS")
    state.raw_test_output = "failed"

    resumer._resume_execution_phase(state)

    resumer.coordinator._analyze_test_results.assert_called_once_with(
        "failed",
        state.changes,
        1,
    )
