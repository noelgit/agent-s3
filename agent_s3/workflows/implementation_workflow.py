"""Workflow helpers for implementation and debugging phases."""

from __future__ import annotations
from typing import Any, Dict, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from agent_s3.coordinator import Coordinator


class ImplementationWorkflow:
    """Execute code generation, validation and debugging for approved plans."""

    def __init__(self, coordinator: Coordinator) -> None:
        self.coordinator = coordinator

    def execute(self, plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run implementation loop for the provided plans."""
        return self.coordinator._implementation_workflow(plans)
