import json
import os
import tempfile
from agent_s3 import user_config
from agent_s3.debugging_manager import DebuggingManager
from unittest.mock import MagicMock


def test_debugging_manager_respects_user_config(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    config = {
        "max_quick_fix_attempts": 5,
        "max_full_debug_attempts": 4,
        "max_restart_attempts": 3,
    }
    with open(tmp.name, "w", encoding="utf-8") as f:
        json.dump(config, f)

    monkeypatch.setattr(user_config, "CONFIG_PATH", tmp.name)

    coordinator = MagicMock()
    coordinator.llm = MagicMock()
    coordinator.file_tool = MagicMock()
    coordinator.code_generator = MagicMock()
    coordinator.error_context_manager = MagicMock()
    coordinator.config = MagicMock()
    scratchpad = MagicMock()

    dm = DebuggingManager(coordinator, scratchpad)
    assert dm.MAX_GENERATOR_ATTEMPTS == 5
    assert dm.MAX_DEBUGGER_ATTEMPTS == 4
    assert dm.MAX_RESTART_ATTEMPTS == 3

    os.unlink(tmp.name)
