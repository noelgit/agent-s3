"""Unit tests for the current TestCritic implementation.

This module provides a minimal smoke test for the TestCritic class. The
previous tests for the old ``TestCriticRunner`` have been removed.
"""

import unittest
import pytest

import agent_s3.tools.test_critic.core as core
from agent_s3.tools.test_critic.core import TestCritic, TestVerdict


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


@pytest.fixture
def critic(monkeypatch):
    adapter = DummyAdapter()
    monkeypatch.setattr(core, "select_adapter", lambda workspace, lang_hint=None: adapter)

    class NoOpReporter:
        def __init__(self, workspace):
            self.workspace = workspace

        def write(self, results):
            pass

    monkeypatch.setattr(core, "Reporter", NoOpReporter)
    return core.TestCritic()


class TestCriticRunAnalysis:
    def test_collect_errors(self, critic, sample_workspace):
        result = critic.run_analysis(sample_workspace)
        assert result["details"]["collect_errors"] == []

    def test_smoke_run(self, critic, sample_workspace):
        result = critic.run_analysis(sample_workspace)
        assert result["details"]["smoke_passed"] is True

    def test_coverage_threshold(self, critic, sample_workspace):
        result = critic.run_analysis(sample_workspace)
        assert result["details"]["coverage_percent"] >= 80.0

    def test_mutation_threshold(self, critic, sample_workspace):
        result = critic.run_analysis(sample_workspace)
        assert result["details"]["mutation_score"] >= 70.0

    def test_full_verdict(self, critic, sample_workspace):
        result = critic.run_analysis(sample_workspace)
        assert result["verdict"] == TestVerdict.PASS


def test_run_analysis_returns_pass(critic, sample_workspace):
    """Test that ``run_analysis`` aggregates results correctly."""
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


if __name__ == "__main__":
    unittest.main()
