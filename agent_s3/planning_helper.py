"""Helper utilities for planning workflows."""

from typing import Any
from typing import Dict

from . import pre_planner_json_enforced


def generate_plan_via_workflow(
    coordinator: Any,
    task_description: str,
) -> Dict[str, Any]:
    """Generate a consolidated plan via JSON enforced pre-planning workflow.

    This helper runs ``call_pre_planner_with_enforced_json`` followed by
    ``FeatureGroupProcessor.process_pre_planning_output`` and returns
    a plan dictionary compatible with ``planner.generate_plan``.

    Args:
        coordinator: Coordinator instance providing ``router_agent`` and
            ``feature_group_processor``.
        task_description: Description of the task to plan.

    Returns:
        Dictionary with ``success`` flag and ``plan`` on success. On failure,
        ``error`` will describe the reason.
    """
    # Use enhanced context management if available
    context = None
    try:
        # Use consolidated context manager directly (context_bridge removed)
        if hasattr(coordinator, "context_manager") and coordinator.context_manager:
            # Use consolidated context manager with planning-specific gathering
            context = coordinator.context_manager.gather_context(
                task_description=task_description,
                task_type="planning",
                max_tokens=coordinator.config.config.get("context_management", {}).get(
                    "max_tokens_for_planning", 4000
                ),
            )
            if hasattr(coordinator, "scratchpad"):
                coordinator.scratchpad.log(
                    "PlanningHelper", "Retrieved consolidated context", level="debug"
                )
    except Exception as e:
        # Log warning but continue without context
        if hasattr(coordinator, "scratchpad"):
            coordinator.scratchpad.log(
                "PlanningHelper", f"Failed to retrieve context: {e}", level="warning"
            )

    success, pre_plan = pre_planner_json_enforced.call_pre_planner_with_enforced_json(
        coordinator.router_agent,
        task_description,
        context,
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
