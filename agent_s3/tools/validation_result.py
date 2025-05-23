"""Common validation result data structure used across validators."""
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ValidationResult:
    """Represents the result of a validation operation."""

    data: Any = None
    issues: List[Dict[str, Any]] = field(default_factory=list)
    needs_repair: bool = False
    metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when no issues require repair."""
        return not self.issues and not self.needs_repair
