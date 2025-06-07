from unittest.mock import MagicMock, patch

from agent_s3.implementation_manager import ImplementationManager
from agent_s3.task_state_manager import TaskStateManager, PlanningState


def test_implementation_manager_uses_error_handler(tmp_path):
    handler = MagicMock()
    manager = ImplementationManager(coordinator=None, error_handler=handler)
    manager.progress_file = str(tmp_path / "progress.json")

    with patch("builtins.open", side_effect=IOError("boom")), patch(
        "os.path.exists", return_value=True
    ):
        result = manager._load_progress_tracker()

    assert result is None
    handler.handle_exception.assert_called_once()


def test_task_state_manager_uses_error_handler(tmp_path):
    handler = MagicMock()
    manager = TaskStateManager(base_dir=str(tmp_path), error_handler=handler)
    state = PlanningState("t1", "req", {}, {})
    state.phase = "planning"

    with patch("builtins.open", side_effect=IOError("boom")):
        success = manager.save_task_snapshot(state)

    assert not success
    handler.handle_exception.assert_called_once()
