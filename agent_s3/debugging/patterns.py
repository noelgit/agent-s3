"""Utilities for categorizing and comparing errors."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List

from agent_s3.tools.error_pattern_learner import ErrorPatternLearner

from .models import ErrorCategory, ErrorContext


class ErrorPatternMatcher:
    """Handle pattern-based error categorization."""

    def __init__(self) -> None:
        self.error_patterns: Dict[ErrorCategory, List[str]] = self._initialize_error_patterns()
        self.pattern_learner = ErrorPatternLearner()
        self.logger = logging.getLogger(__name__)

    def _initialize_error_patterns(self) -> Dict[ErrorCategory, List[str]]:
        """Return the default regex patterns for categorizing errors."""
        return {
            ErrorCategory.SYNTAX: [
                r"SyntaxError",
                r"IndentationError",
                r"unexpected token",
                r"invalid syntax",
                r"unexpected indent",
                r"expected an indented block",
            ],
            ErrorCategory.TYPE: [
                r"TypeError",
                r"unsupported operand type",
                r"not subscriptable",
                r"has no attribute",
                r"not a function",
                r"expected .* to be a",
                r"can't convert .* to",
            ],
            ErrorCategory.IMPORT: [
                r"ImportError",
                r"ModuleNotFoundError",
                r"No module named",
                r"cannot import name",
                r"cannot find module",
            ],
            ErrorCategory.ATTRIBUTE: [
                r"AttributeError",
                r"has no attribute",
                r"object has no attribute",
            ],
            ErrorCategory.NAME: [
                r"NameError",
                r"name .* is not defined",
                r"undefined variable",
                r"ReferenceError",
            ],
            ErrorCategory.INDEX: [
                r"IndexError",
                r"out of range",
                r"list index out of range",
                r"array index out of bounds",
            ],
            ErrorCategory.VALUE: [
                r"ValueError",
                r"invalid literal",
                r"could not convert",
                r"invalid value",
                r"value .* is not a valid",
            ],
            ErrorCategory.RUNTIME: [
                r"RuntimeError",
                r"RecursionError",
                r"maximum recursion depth exceeded",
                r"stack overflow",
            ],
            ErrorCategory.MEMORY: [
                r"MemoryError",
                r"out of memory",
                r"memory allocation failed",
                r"cannot allocate",
            ],
            ErrorCategory.PERMISSION: [
                r"PermissionError",
                r"Permission denied",
                r"Access is denied",
                r"not permitted",
            ],
            ErrorCategory.ASSERTION: [
                r"AssertionError",
                r"Assertion failed",
                r"Expected .* but got",
            ],
            ErrorCategory.NETWORK: [
                r"ConnectionError",
                r"ConnectionRefusedError",
                r"ConnectionResetError",
                r"TimeoutError",
                r"Connection refused",
                r"Network is unreachable",
                r"Connection timed out",
            ],
            ErrorCategory.DATABASE: [
                r"DatabaseError",
                r"OperationalError",
                r"IntegrityError",
                r"database is locked",
                r"constraint failed",
                r"syntax error in SQL",
                r"no such table",
            ],
        }

    def categorize_error(self, error_message: str, traceback_text: str) -> ErrorCategory:
        """Categorize an error using regex patterns and the learned model."""
        combined_text = f"{error_message}\n{traceback_text}".lower()
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern.lower(), combined_text):
                    return category

        prediction = self.pattern_learner.predict(error_message)
        if prediction and prediction in ErrorCategory.__members__:
            return ErrorCategory[prediction]
        return ErrorCategory.UNKNOWN

    def update_learning(self, message: str, category: ErrorCategory) -> None:
        """Update the machine-learning model."""
        try:
            self.pattern_learner.update(message, category.name)
        except Exception:  # pragma: no cover - defensive
            self.logger.debug("Pattern learner update failed")

    @staticmethod
    def text_similarity(text1: str, text2: str) -> float:
        """Calculate similarity between two strings."""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1, text2).ratio()

    def is_similar_error(self, error1: ErrorContext, error2: ErrorContext) -> bool:
        """Return True if two errors are similar enough to be treated the same."""
        if error1.category != error2.category:
            return False
        if error1.file_path != error2.file_path:
            return False
        if error1.line_number is not None and error2.line_number is not None:
            if abs(error1.line_number - error2.line_number) > 5:
                return False
        similarity = self.text_similarity(error1.message, error2.message)
        return similarity > 0.7
