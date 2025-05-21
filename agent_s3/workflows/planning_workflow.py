"""Workflow helpers for task planning phases."""

from __future__ import annotations
from typing import Any, Dict, List
from agent_s3.coordinator import Coordinator


class PlanningWorkflow:
    """Handle pre-planning, validation and plan consolidation for a task."""

    def __init__(self, coordinator: Coordinator) -> None:
        self.coordinator = coordinator

    def execute(self, task: str, pre_planning_input: Dict[str, Any] | None = None, from_design: bool = False) -> List[Dict[str, Any]]:
        """Run the planning workflow and return approved consolidated plans."""
        return self.coordinator._planning_workflow(task, pre_planning_input, from_design)
