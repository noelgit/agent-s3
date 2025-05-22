import pytest

from agent_s3.design_manager import DesignManager


def test_detect_design_completion_case_insensitive():
    """Design completion detection should handle mixed-case indicators."""
    manager = DesignManager()
    manager.conversation_history = [
        {"role": "system", "content": "init"},
        {"role": "user", "content": "List features"},
        {"role": "assistant", "content": "feature 1: login system"},
        {"role": "user", "content": "Looks Good"},
    ]

    assert manager.detect_design_completion()
