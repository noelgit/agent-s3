import builtins
from unittest.mock import MagicMock, patch

import pytest

from agent_s3.coordinator import Coordinator
from agent_s3.task_state_manager import PlanningState
from agent_s3.task_resumer import TaskResumer


@pytest.fixture
def simple_coordinator():
    with patch.object(Coordinator, "_initialize_core_components"), \
         patch.object(Coordinator, "_initialize_tools"), \
         patch.object(Coordinator, "_initialize_specialized_components"), \
         patch.object(Coordinator, "_initialize_communication"), \
         patch.object(Coordinator, "_finalize_initialization"):
        c = Coordinator.__new__(Coordinator)
        c.config = MagicMock()
        c.config.config = {
            "context_management": {},
            "max_attempts": 1,
        }
        c.scratchpad = MagicMock()
        c.progress_tracker = MagicMock()
        c.task_state_manager = MagicMock()
        c.task_state_manager.create_new_task_id.return_value = "task-1"
        c.orchestrator = MagicMock()
        c.current_task_id = None
        yield c


def test_run_task_saves_snapshots(simple_coordinator):
    simple_coordinator.orchestrator.run_task = MagicMock()
    simple_coordinator.run_task("feature")
    simple_coordinator.task_state_manager.create_new_task_id.assert_called_once()


def test_task_resumer_loads_snapshot(monkeypatch):
    coordinator = MagicMock()
    tsm = MagicMock()
    state = PlanningState("t1", "req", {}, {})
    tsm.get_active_tasks.return_value = [{"task_id": "t1", "phase": "planning", "request_text": "req"}]
    tsm.load_task_snapshot.return_value = state
    resumer = TaskResumer(coordinator, tsm, scratchpad=MagicMock(), progress_tracker=MagicMock())
    monkeypatch.setattr(builtins, "input", lambda *a: "yes")
    resumer.resume_task = MagicMock()
    success, _ = resumer.auto_resume_interrupted_task()
    assert success is True
    tsm.load_task_snapshot.assert_called_once_with("t1", "planning")
    resumer.resume_task.assert_called_once_with(state)
    assert coordinator.current_task_id == "t1"
