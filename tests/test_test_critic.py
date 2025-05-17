"""Unit tests for the TestCritic class."""

import unittest
from unittest.mock import MagicMock
import pytest

import agent_s3.tools.test_critic.core as core
from agent_s3.tools.test_critic.core import TestVerdict


@pytest.fixture
def sample_workspace(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_example(): assert True")
    return tmp_path


class DummyAdapter:
    """Simple adapter returning predetermined results."""

    name = "dummy"

    def collect_only(self, workspace):
        return []

    def smoke_run(self, workspace):
        return True

    def coverage(self, workspace):
        return 85.0

    def mutation(self, workspace):
        return 75.0


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


if __name__ == "__main__":
    unittest.main()
