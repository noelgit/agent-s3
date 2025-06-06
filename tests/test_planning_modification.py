from unittest.mock import MagicMock

from agent_s3.coordinator.orchestrator import WorkflowOrchestrator
from agent_s3.coordinator import Coordinator


def test_planning_workflow_regenerates_preplan(monkeypatch):
    # Build minimal coordinator without running __init__
    coord = object.__new__(Coordinator)
    coord.config = MagicMock()
    coord.config.config = {"context_management": {}}
    coord.router_agent = MagicMock()
    coord.progress_tracker = MagicMock()
    coord.scratchpad = MagicMock()
    coord.context_registry = MagicMock()
    coord.context_manager = None
    coord.feature_group_processor = MagicMock()
    coord.feature_group_processor.process_pre_planning_output.return_value = {
        "success": True,
        "feature_group_results": {"fg": {"consolidated_plan": {"group_name": "fg"}}},
    }
    coord.feature_group_processor.present_consolidated_plan_to_user.return_value = ("yes", None)

    registry = MagicMock()
    registry.get_tool.return_value = None
    orchestrator = WorkflowOrchestrator(coord, registry)
    coord.orchestrator = orchestrator
    orchestrator._create_github_issue_for_plan = MagicMock()

    pre_plan = {"original_request": "task", "feature_groups": []}
    new_plan = {"original_request": "task", "feature_groups": [{"group_name": "fg"}]}

    monkeypatch.setattr(
        "agent_s3.coordinator.orchestrator.pre_planning_workflow",
        lambda router, task, context=None, max_preplanning_attempts=2, allow_interactive_clarification=False, clarification_callback=None: (True, pre_plan),
    )

    regen_called = {}

    def mock_regen(router, original, text):
        regen_called["called"] = True
        assert original == pre_plan
        assert text == "add feature"
        return new_plan

    monkeypatch.setattr(
        "agent_s3.coordinator.orchestrator.regenerate_pre_planning_with_modifications",
        mock_regen,
    )

    monkeypatch.setattr(
        Coordinator,
        "_present_pre_planning_results_to_user",
        lambda self, results: ("modify", "add feature"),
    )

    class DummyChecker:
        def __init__(self, context_registry=None):
            pass

        def validate_plan(self, plan, original_plan=None):
            assert plan == new_plan
            assert original_plan == pre_plan
            return True, {}

    monkeypatch.setattr(
        "agent_s3.tools.static_plan_checker.StaticPlanChecker",
        DummyChecker,
    )

    plans = orchestrator._planning_workflow("task")
    assert regen_called.get("called") is True
    assert plans == [{"group_name": "fg"}]
