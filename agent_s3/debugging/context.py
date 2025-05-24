"""Functions for building error context information."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .models import ErrorContext
from .patterns import ErrorPatternMatcher


logger = logging.getLogger(__name__)


def process_test_failure_data(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract structured information from test failure metadata."""
    if not metadata:
        return {}

    if metadata.get("failed_step") == "tests":
        info = metadata.get("failure_info")
        if isinstance(info, list) and info:
            return info[0]
        if isinstance(info, dict):
            return info

    test_failure_fields = {
        "test_name",
        "test_file",
        "test_class",
        "line_number",
        "expected",
        "actual",
        "assertion",
        "traceback",
        "failure_category",
        "possible_bad_test",
        "variables",
    }
    extracted: Dict[str, Any] = {}
    for field in test_failure_fields:
        if field in metadata:
            extracted[field] = metadata[field]
    return extracted


def create_error_context(
    matcher: ErrorPatternMatcher,
    error_message: str,
    traceback_text: str,
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    function_name: Optional[str] = None,
    code_snippet: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    error_context_manager: Any | None = None,
) -> ErrorContext:
    """Create an :class:`ErrorContext` with enriched information."""
    category = matcher.categorize_error(error_message, traceback_text)

    if not code_snippet and error_context_manager and file_path and line_number:
        try:
            context = error_context_manager.get_context_for_error(file_path, line_number, error_message)
            if context:
                code_snippet = context.get("code_snippet")
                if not variables:
                    variables = context.get("variables", {})
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Error getting additional context: %s", exc)

    error_ctx = ErrorContext(
        message=error_message,
        traceback=traceback_text,
        category=category,
        file_path=file_path,
        line_number=line_number,
        function_name=function_name,
        code_snippet=code_snippet,
        variables=variables or {},
        metadata=metadata or {},
    )
    matcher.update_learning(error_message, error_ctx.category)
    return error_ctx
