import json
from pathlib import Path
from agent_s3.task_state_manager import (
    TaskStateManager,
    ExecutionState,
    CURRENT_STATE_VERSION,
)


def test_state_version_default():
    state = ExecutionState("task1", [], 0, {})
    assert state.to_dict()["state_version"] == CURRENT_STATE_VERSION


def test_load_snapshot_migrates_old_version(tmp_path: Path):
    manager = TaskStateManager(str(tmp_path))
    task_dir = tmp_path / "task1"
    task_dir.mkdir()
    data = {
        "task_id": "task1",
        "timestamp": "2024-01-01T00:00:00",
        "phase": "execution",
        "changes": [],
        "iteration": 0,
        "test_results": {},
    }
    (task_dir / "execution.json").write_text(json.dumps(data))

    state = manager.load_task_snapshot("task1", "execution")
    assert state is not None
    assert state.state_version == CURRENT_STATE_VERSION

