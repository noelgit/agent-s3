"""Helper utilities for planning workflows."""
from typing import Any
from typing import Dict
from typing import Optional

from . import pre_planner_json_enforced

def generate_plan_via_workflow(
    coordinator: Any,
    task_description: str,
    context: Optional[Dict[str, Any]] = None,
    max_preplanning_attempts: int = 2,
) -> Dict[str, Any]:
    """Generate a consolidated plan via sequential pre-planning workflow.

    This helper runs ``pre_planning_workflow`` followed by
    ``FeatureGroupProcessor.process_pre_planning_output`` and returns
    a plan dictionary compatible with ``planner.generate_plan``.

    Args:
        coordinator: Coordinator instance providing ``router_agent`` and
            ``feature_group_processor``.
        task_description: Description of the task to plan.
        context: Optional context dictionary passed to the pre planner.
        max_preplanning_attempts: Maximum number of attempts for the pre-planning step.

    Returns:
        Dictionary with ``success`` flag and ``plan`` on success. On failure,
        ``error`` will describe the reason.
    """
    success, pre_plan = pre_planner_json_enforced.pre_planning_workflow(
        coordinator.router_agent,
        task_description,
        context=context,
        max_preplanning_attempts=max_preplanning_attempts,
    )
    if not success:
        return {"success": False, "error": "Pre-planning failed", "plan": None}

    fg_result = coordinator.feature_group_processor.process_pre_planning_output(
        pre_plan, task_description
    )
    if not fg_result.get("success"):
        return {
            "success": False,
            "error": fg_result.get("error", "Feature group processing failed"),
            "plan": None,
        }

    groups = fg_result.get("processed_groups", [])
    if not groups:
        return {"success": False, "error": "No processed plans returned", "plan": None}

    return {"success": True, "plan": groups[0]}
