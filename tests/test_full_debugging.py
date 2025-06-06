"""Tests for the full debugging execution logic."""

from unittest.mock import MagicMock

import agent_s3.debugging.full_debugging as full_debugging
from agent_s3.debugging import ErrorContext
from agent_s3.debugging.full_debugging import execute_full_debugging


def test_execute_full_debugging_skips_invalid_new_file(tmp_path, monkeypatch):
    """Ensure invalid new file paths are skipped and validation uses reference."""
    main_file = tmp_path / "main.py"
    main_file.write_text("print('hi')\n")

    error_ctx = ErrorContext(
        message="error",
        traceback="traceback",
        file_path=str(main_file),
    )

    file_tool = MagicMock()
    file_tool.read_file.return_value = (True, "print('hi')\n")
    file_tool.write_file = MagicMock()

    coordinator = MagicMock()
    coordinator.config.config = {}

    scratchpad = MagicMock()
    scratchpad.extract_cot_for_debugging.return_value = ""

    llm = MagicMock()

    monkeypatch.setattr(full_debugging, "cached_call_llm", lambda *a, **k: {"success": True, "response": "resp"})
    monkeypatch.setattr(full_debugging, "extract_multi_file_fixes", lambda *a, **k: {"/unsafe/out.py": "data"})
    monkeypatch.setattr(full_debugging, "extract_reasoning_from_response", lambda *a, **k: "reason")

    captured = {}

    def fake_is_safe(path: str, reference: str) -> bool:
        captured["args"] = (path, reference)
        return False

    monkeypatch.setattr(full_debugging, "is_safe_new_file", fake_is_safe)

    result = execute_full_debugging(
        error_context=error_ctx,
        file_tool=file_tool,
        coordinator=coordinator,
        scratchpad=scratchpad,
        logger=MagicMock(),
        llm=llm,
        debugger_attempts=1,
        create_full_debugging_prompt_func=lambda *a, **k: "prompt",
    )

    assert captured["args"] == ("/unsafe/out.py", str(main_file))
    file_tool.write_file.assert_not_called()
    assert "success" in result
