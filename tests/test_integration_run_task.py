"""
Integration test for Coordinator.run_task simulating a simple feature request.
"""
import pytest
from unittest.mock import MagicMock, patch
from agent_s3.coordinator import Coordinator

def test_run_task_simple(monkeypatch):
    # Patch all external effects
    monkeypatch.setattr("agent_s3.coordinator.PrePlanningManager.collect_impacted_files", lambda self, req: ["agent_s3/cli.py"])
    monkeypatch.setattr("agent_s3.coordinator.PrePlanningManager.estimate_complexity", lambda self, files: 10.0)
    monkeypatch.setattr("agent_s3.coordinator.PrePlanningManager.identify_arch_implications", lambda self, files: {})
    monkeypatch.setattr("agent_s3.coordinator.Planner.create_plan", lambda self, req: "# Plan\nDo X\n")
    monkeypatch.setattr("agent_s3.coordinator.PromptModerator.present_plan", lambda self, plan, summary: (True, plan))
    monkeypatch.setattr("agent_s3.coordinator.Planner.generate_prompt", lambda self: "Prompt")
    monkeypatch.setattr("agent_s3.coordinator.CodeGenerator.generate_code", lambda self: "print('hello world')")
    monkeypatch.setattr("agent_s3.coordinator.Coordinator.execute_code", lambda self: "Execution result")
    monkeypatch.setattr("agent_s3.coordinator.ProgressTracker.update_progress", lambda self, *a, **kw: None)
    monkeypatch.setattr("agent_s3.coordinator.ScratchpadManager.log", lambda self, *a, **kw: None)
    c = Coordinator()
    c.run_task("Add a hello world print statement")
    # If no exception, test passes
