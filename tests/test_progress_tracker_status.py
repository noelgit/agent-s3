from agent_s3.progress_tracker import ProgressTracker, Status

class DummyConfig:
    def __init__(self, log_file: str):
        self.config = {"log_files": {"progress": log_file}}

def make_tracker(tmp_path):
    cfg = DummyConfig(str(tmp_path / "progress.jsonl"))
    tracker = ProgressTracker(cfg)
    return tracker

def test_update_progress_with_string_status(tmp_path):
    tracker = make_tracker(tmp_path)
    captured = {}

    def fake_log_entry(entry):
        captured['entry'] = entry
        return True

    tracker.log_entry = fake_log_entry
    assert tracker.update_progress({"phase": "phase", "status": "completed"})
    assert captured['entry'].status == Status.COMPLETED.value

def test_update_progress_with_int_status(tmp_path):
    tracker = make_tracker(tmp_path)
    captured = {}

    def fake_log_entry(entry):
        captured['entry'] = entry
        return True

    tracker.log_entry = fake_log_entry
    assert tracker.update_progress({"phase": "phase", "status": Status.FAILED.value})
    assert captured['entry'].status == Status.FAILED.value


def test_update_progress_with_invalid_status(tmp_path):
    tracker = make_tracker(tmp_path)
    captured = {}

    def fake_log_entry(entry):
        captured['entry'] = entry
        return True

    tracker.log_entry = fake_log_entry
    assert tracker.update_progress({"phase": "phase", "status": 999})
    assert captured['entry'].status == Status.IN_PROGRESS.value
