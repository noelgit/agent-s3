"""Workflow helpers for implementation and debugging phases."""

from typing import Any, Dict, Tuple, List


class ImplementationWorkflow:
    """Execute code generation, validation and debugging for approved plans."""

    def __init__(self, coordinator: "Coordinator") -> None:
        self.coordinator = coordinator

    def execute(self, plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run implementation loop for the provided plans."""
        return self.coordinator._implementation_workflow(plans)
