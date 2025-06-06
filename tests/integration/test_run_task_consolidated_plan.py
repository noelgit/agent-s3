from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.json_utils import validate_json_against_schema


# Sample data for mocking
PRE_PLAN_DATA = {
    "feature_groups": [
        {
            "group_name": "Auth",
            "group_description": "Authentication features",
            "features": [
                {
                    "name": "Login",
                    "files_affected": ["auth.py"],
                    "system_design": {}
                }
            ],
            "risk_assessment": {},
            "dependencies": {}
        }
    ]
}

ARCH_REVIEW = {"architecture_review": {"logical_gaps": []}, "discussion": "ok"}
REFINED_TESTS = {"refined_test_requirements": {}, "discussion": "tests"}
TEST_IMPL = {
    "tests": {"unit_tests": []},
    "test_strategy_implementation": {},
    "discussion": "impl"
}
IMPL_PLAN = {
    "implementation_plan": {"auth.py": [{"function": "login()"}]},
    "discussion": "plan"
}
SEM_VALID = {
    "validation_results": {
        "coherence_score": 1.0,
        "technical_consistency_score": 1.0,
        "critical_issues": []
    }
}

SCHEMA = {
    "plan_id": str,
    "group_name": str,
    "group_description": str,
    "architecture_review": dict,
    "implementation_plan": dict,
    "tests": dict,
    "discussion": str,
    "task_description": str,
    "dependencies": dict,
    "risk_assessment": dict,
    "success": bool,
    "timestamp": str,
}


def test_run_task_with_mocked_llm(monkeypatch):
    """Integration test for Coordinator.run_task producing a consolidated plan."""
    # Patch heavy initialization to no-op
    monkeypatch.setattr(Coordinator, "_initialize_tools", lambda self: None)
    monkeypatch.setattr(Coordinator, "_initialize_specialized_components", lambda self: None)

    with patch('agent_s3.coordinator.EnhancedScratchpadManager') as MockScratchpad, \
         patch('agent_s3.coordinator.ProgressTracker') as MockTracker, \
         patch('agent_s3.coordinator.TaskStateManager') as MockTSM, \
         patch('agent_s3.coordinator.CommandProcessor'):
        MockScratchpad.return_value = MagicMock()
        MockTracker.return_value = MagicMock()
        MockTSM.return_value = MagicMock(create_new_task_id=MagicMock(return_value="1"))

        coordinator = Coordinator()

    # Manually set required components
    coordinator.scratchpad = MagicMock()
    coordinator.progress_tracker = MagicMock()
    coordinator.router_agent = MagicMock()
    coordinator.prompt_moderator = MagicMock()
    coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"
    coordinator.test_critic = MagicMock(critique_tests=lambda tests, risk: {})

    # FeatureGroupProcessor instance using the coordinator
    from agent_s3.feature_group_processor import FeatureGroupProcessor
    fg_processor = FeatureGroupProcessor(coordinator)
    coordinator.feature_group_processor = fg_processor

    # Patch LLM-calling functions
    monkeypatch.setattr(
        'agent_s3.pre_planner_json_enforced.pre_planning_workflow',
        lambda router, task, context=None, max_attempts=2: (True, PRE_PLAN_DATA)
    )
    monkeypatch.setattr(
        'agent_s3.tools.plan_validator.validate_pre_plan',
        lambda data, repo_root=None, context_registry=None: (True, {})
    )
    monkeypatch.setattr(
        'agent_s3.planner_json_enforced.generate_architecture_review',
        lambda router, fg, task_description, context=None: ARCH_REVIEW
    )
    monkeypatch.setattr(
        'agent_s3.planner_json_enforced.generate_refined_test_specifications',
        lambda router, fg, arch, task_description, context=None: REFINED_TESTS
    )
    monkeypatch.setattr(
        'agent_s3.planner_json_enforced.generate_test_implementations',
        lambda router, specs, sys_design, task_description, context=None: TEST_IMPL
    )
    monkeypatch.setattr(
        'agent_s3.planner_json_enforced.generate_implementation_plan',
        lambda router, sys_design, arch, tests, task_description, context=None: IMPL_PLAN
    )
    monkeypatch.setattr(
        'agent_s3.planner_json_enforced.validate_planning_semantic_coherence',
        lambda router, arch, specs, impls, impl_plan, task_description, context=None: SEM_VALID
    )

    presented_plans = []

    def present_plan(plan):
        presented_plans.append(plan)
        # Simulate user approval
        return coordinator.prompt_moderator.ask_ternary_question("Proceed?"), None

    monkeypatch.setattr(fg_processor, 'present_consolidated_plan_to_user', present_plan)

    # Patch subsequent phases to keep run_task short
    monkeypatch.setattr(coordinator, '_apply_changes_and_manage_dependencies', lambda changes: True)
    monkeypatch.setattr(coordinator, '_run_validation_phase', lambda: {"success": True})
    monkeypatch.setattr(coordinator, '_finalize_task', lambda changes: None)
    monkeypatch.setattr(coordinator.code_generator if hasattr(coordinator, 'code_generator') else coordinator, 'generate_code', lambda plan, tech_stack=None: {})
    monkeypatch.setattr(coordinator, 'debugging_manager', MagicMock(handle_error=lambda **kw: {"success": True, "changes": {}}))

    # Execute the run_task workflow
    coordinator.run_task("Implement auth")

    # Ensure a plan was presented and user decision requested
    assert presented_plans, "No consolidated plan was presented"
    coordinator.prompt_moderator.ask_ternary_question.assert_called()

    # Validate the presented consolidated plan against schema
    is_valid, errors = validate_json_against_schema(presented_plans[0], SCHEMA)
    assert is_valid, f"Plan failed schema validation: {errors}"
