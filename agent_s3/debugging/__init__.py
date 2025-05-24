"""Debugging support utilities and models."""

from .models import (
    ErrorCategory,
    DebuggingPhase,
    RestartStrategy,
    ErrorContext,
    DebugAttempt,
)
from .patterns import ErrorPatternMatcher
from .context import create_error_context, process_test_failure_data

__all__ = [
    "ErrorCategory",
    "DebuggingPhase",
    "RestartStrategy",
    "ErrorContext",
    "DebugAttempt",
    "ErrorPatternMatcher",
    "create_error_context",
    "process_test_failure_data",
]
