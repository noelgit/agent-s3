"""Base adapter class for test critic."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional


class Adapter(ABC):
    """Abstract base class for test framework adapters."""

    name = "base_adapter"

    @abstractmethod
    def detect(self, workspace: Path) -> bool:
        """Return True if this adapter can be used for the workspace."""

    @abstractmethod
    def collect_only(self, workspace: Path) -> List[str]:
        """Run a test collection to check for syntax errors."""

    @abstractmethod
    def smoke_run(self, workspace: Path) -> bool:
        """Run a smoke test to check if tests pass."""

    @abstractmethod
    def coverage(self, workspace: Path) -> Optional[float]:
        """Run code coverage analysis and return the coverage percentage."""

    @abstractmethod
    def mutation(self, workspace: Path) -> Optional[float]:
        """Run mutation testing and return the mutation score percentage."""
