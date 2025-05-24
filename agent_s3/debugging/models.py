"""Data models for debugging components."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional


class ErrorCategory(Enum):
    """Categories of errors for specialized handling."""

    SYNTAX = auto()
    TYPE = auto()
    IMPORT = auto()
    ATTRIBUTE = auto()
    NAME = auto()
    INDEX = auto()
    VALUE = auto()
    RUNTIME = auto()
    MEMORY = auto()
    PERMISSION = auto()
    ASSERTION = auto()
    NETWORK = auto()
    DATABASE = auto()
    UNKNOWN = auto()


class DebuggingPhase(Enum):
    """Phases of the debugging process."""

    ANALYSIS = auto()
    QUICK_FIX = auto()
    FULL_DEBUG = auto()
    STRATEGIC_RESTART = auto()


class RestartStrategy(Enum):
    """Strategies for strategic restart."""

    REGENERATE_CODE = auto()
    REDESIGN_PLAN = auto()
    MODIFY_REQUEST = auto()


@dataclass
class ErrorContext:
    """Context information about an error for debugging."""

    message: str
    traceback: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    code_snippet: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now().isoformat())
    attempt_number: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary representation."""
        result = asdict(self)
        result["category"] = self.category.name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorContext":
        """Create an instance from a dictionary."""
        category_name = data.get("category", "UNKNOWN")
        category = ErrorCategory[category_name] if category_name in ErrorCategory.__members__ else ErrorCategory.UNKNOWN
        return cls(
            message=data.get("message", ""),
            traceback=data.get("traceback", ""),
            category=category,
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            function_name=data.get("function_name"),
            code_snippet=data.get("code_snippet"),
            variables=data.get("variables", {}),
            occurred_at=data.get("occurred_at", datetime.now().isoformat()),
            attempt_number=data.get("attempt_number", 1),
            metadata=data.get("metadata", {}),
        )

    def get_summary(self) -> str:
        """Return a concise summary of the error."""
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f" at line {self.line_number}"
        return f"{self.category.name} error{location}: {self.message}"


@dataclass
class DebugAttempt:
    """Record of a debugging attempt."""

    error_context: ErrorContext
    phase: DebuggingPhase
    fix_description: str
    code_changes: Dict[str, str]
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary representation."""
        result = asdict(self)
        result["error_context"] = self.error_context.to_dict()
        result["phase"] = self.phase.name
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DebugAttempt":
        """Create an instance from a dictionary."""
        error_data = data.get("error_context", {})
        error_context = ErrorContext.from_dict(error_data)
        phase_name = data.get("phase", "ANALYSIS")
        phase = DebuggingPhase[phase_name] if phase_name in DebuggingPhase.__members__ else DebuggingPhase.ANALYSIS
        return cls(
            error_context=error_context,
            phase=phase,
            fix_description=data.get("fix_description", ""),
            code_changes=data.get("code_changes", {}),
            success=data.get("success", False),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            duration_seconds=data.get("duration_seconds", 0.0),
            reasoning=data.get("reasoning", ""),
            metadata=data.get("metadata", {}),
        )
