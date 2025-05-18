"""
Integration test for Coordinator.run_task simulating a simple feature request.
"""
import pytest
from agent_s3.coordinator import Coordinator

# Minimal pre-planning result used for mocking
SIMPLE_PREPLAN = {
    "feature_groups": [
        {
            "group_name": "Misc",
            "group_description": "Simple group",
            "features": [
                {
                    "name": "PrintHello",
                    "description": "Add hello world",
                    "files_affected": ["agent_s3/cli.py"],
                    "test_requirements": {
                        "unit_tests": [],
                        "integration_tests": [],
                        "property_based_tests": [],
                        "acceptance_tests": [],
                        "test_strategy": {},
                    },
                    "dependencies": {
                        "internal": [],
                        "external": [],
                        "feature_dependencies": [],
                    },
                    "risk_assessment": {},
                    "system_design": {"code_elements": []},
                }
            ],
            "risk_assessment": {},
            "dependencies": {},
        }
    ],
    "complexity_score": 10.0,
}

def test_run_task_simple(monkeypatch):
    # Patch all external effects
    monkeypatch.setattr(
        "agent_s3.pre_planner_json_enforced.pre_planning_workflow",
        lambda router, task, context=None: (True, SIMPLE_PREPLAN),
    )
    monkeypatch.setattr(
        "agent_s3.pre_planner_json_enforced.regenerate_pre_planning_with_modifications",
        lambda router, results, mod: results,
    )
    monkeypatch.setattr(
        "agent_s3.tools.plan_validator.validate_pre_plan", lambda data, **_: (True, {})
    )
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
