"""Debugging support utilities and models."""

from .models import (
    ErrorCategory,
    DebuggingPhase,
    ErrorContext,
    DebugAttempt,
)
from .patterns import ErrorPatternMatcher
from .context import create_error_context, process_test_failure_data
from .response_parsers import (
    extract_code_from_response,
    extract_reasoning_from_response,
    extract_multi_file_fixes,
    extract_json_from_response
)
from .context_helpers import (
    get_related_files,
    get_project_root,
    is_safe_new_file,
    analyze_error_context
)
from .quick_fixes import execute_generator_quick_fix
from .full_debugging import execute_full_debugging
from .strategic_restart import execute_strategic_restart, RestartStrategy

__all__ = [
    "ErrorCategory",
    "DebuggingPhase",
    "RestartStrategy",
    "ErrorContext",
    "DebugAttempt",
    "ErrorPatternMatcher",
    "create_error_context",
    "process_test_failure_data",
    "extract_code_from_response",
    "extract_reasoning_from_response",
    "extract_multi_file_fixes",
    "extract_json_from_response",
    "get_related_files",
    "get_project_root",
    "is_safe_new_file",
    "analyze_error_context",
    "execute_generator_quick_fix",
    "execute_full_debugging",
    "execute_strategic_restart",
]
