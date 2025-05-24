"""Unit tests for the current TestCritic implementation.

This module provides a minimal smoke test for the TestCritic class. The
previous tests for the old ``TestCriticRunner`` have been removed.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.tools.test_critic.core import TestCritic
from agent_s3.tools.test_critic.core import TestVerdict

@pytest.fixture
def sample_workspace(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_example(): assert True")
    return tmp_path


class DummyAdapter:
    """Simple adapter returning deterministic results for testing."""

    name = "dummy"

    def detect(self, workspace):
        return True

    def collect_only(self, workspace):
        return []

    def smoke_run(self, workspace):
        return True

    def coverage(self, workspace):
        return 85.0

    def mutation(self, workspace):
        return 72.0


def test_run_analysis_returns_pass(sample_workspace):
    """Test that ``run_analysis`` aggregates results correctly."""
    with patch(
        "agent_s3.tools.test_critic.core.select_adapter", return_value=DummyAdapter()
    ), patch("agent_s3.tools.test_critic.core.Reporter") as mock_reporter:
        mock_reporter.return_value.write = MagicMock()
        critic = TestCritic()
        result = critic.run_analysis(sample_workspace)

    assert result["verdict"] == TestVerdict.PASS
    details = result["details"]
    assert details == {
        "collect_errors": [],
        "smoke_passed": True,
        "coverage_percent": 85.0,
        "mutation_score": 72.0,
    }


def test_analyze_test_file_detects_unit_tests():
    """Ensure static analysis recognises unit tests with assertions."""
    critic = TestCritic()
    code = """\
import pytest


def test_example():
    assert 1 == 1
"""
    result = critic.analyze_test_file("test_example.py", code)
    assert result["verdict"] == TestVerdict.PASS
    assert "unit" in result["test_types"]
    assert result["test_count"] == 1
    assert result["assertion_count"] >= 1
