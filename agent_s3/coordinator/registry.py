"""Registry for coordinator tools and managers."""
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class CoordinatorRegistry:
    """Track registered tools and managers for the coordinator."""
    config: Any
    github_token: str | None = None
    tools: Dict[str, Any] = field(default_factory=dict)
    managers: Dict[str, Any] = field(default_factory=dict)

    def register_tool(self, name: str, instance: Any) -> None:
        """Register a tool instance accessible by name."""
        self.tools[name] = instance

    def register_manager(self, name: str, instance: Any) -> None:
        """Register a manager instance accessible by name."""
        self.managers[name] = instance

    def get_tool(self, name: str) -> Any | None:
        """Return a previously registered tool."""
        return self.tools.get(name)

    def get_manager(self, name: str) -> Any | None:
        """Return a previously registered manager."""
        return self.managers.get(name)
