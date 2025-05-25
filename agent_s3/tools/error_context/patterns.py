"""Pattern recognition helpers for debugging errors."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple


def parse_error(error_message: str, stack_trace: str | None = None) -> Dict[str, Any]:
    """Parse an error message and optional stack trace."""
    info = {
        "type": None,
        "message": error_message,
        "message_pattern": None,
        "file_paths": [],
        "line_numbers": [],
        "function_names": [],
        "modules": [],
    }

    error_type_match = re.search(r"([A-Za-z]+Error|Exception):", error_message)
    if error_type_match:
        info["type"] = error_type_match.group(1)

    if error_message:
        pattern = re.sub(r"\'[^\']+\'", "'VALUE'", error_message)
        pattern = re.sub(r'"[^"]+"', '"VALUE"', pattern)
        pattern = re.sub(r"\d+", "NUM", pattern)
        info["message_pattern"] = pattern

    if stack_trace:
        file_paths = re.findall(r'File \"([^\"]+)\"', stack_trace)
        info["file_paths"] = file_paths

        line_numbers = re.findall(r'line (\d+)', stack_trace)
        info["line_numbers"] = [int(num) for num in line_numbers]

        func_matches = re.findall(r'in ([A-Za-z_][A-Za-z0-9_]*)', stack_trace)
        info["function_names"] = func_matches

        if file_paths:
            modules = []
            for path in file_paths:
                if path.endswith('.py'):
                    modules.append(os.path.basename(path)[:-3])
            info["modules"] = modules

    return info


def calculate_pattern_similarity(pattern1: str, pattern2: str) -> float:
    """Return a Jaccard similarity score between two patterns."""
    if not pattern1 or not pattern2:
        return 0.0

    words1 = set(pattern1.lower().split())
    words2 = set(pattern2.lower().split())
    if not words1 or not words2:
        return 0.0

    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    if union == 0:
        return 0.0

    similarity = intersection / union
    if abs(len(pattern1) - len(pattern2)) / max(len(pattern1), len(pattern2)) < 0.2:
        similarity *= 1.2

    return min(1.0, similarity)


def find_similar_error_pattern(error_info: Dict[str, Any], patterns: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
    """Search cached patterns for a similar error."""
    if not error_info or not patterns:
        return None, 0.0

    error_type = error_info.get("type")
    message_pattern = error_info.get("message_pattern")
    if not error_type or not message_pattern:
        return None, 0.0

    best_match = None
    best_score = 0.0
    for pattern in patterns:
        if pattern.get("type") != error_type:
            continue
        pattern_msg = pattern.get("message_pattern", "")
        if not pattern_msg:
            continue
        score = calculate_pattern_similarity(message_pattern, pattern_msg)
        if score > best_score:
            best_score = score
            best_match = pattern

    return best_match, best_score


def create_error_fingerprint(error_info: Dict[str, Any]) -> str:
    """Create a fingerprint string for an error."""
    error_type = error_info.get("type", "unknown")
    msg_pattern = error_info.get("message_pattern", "")
    if not msg_pattern:
        return f"{error_type}:generic"
    shortened = msg_pattern[:100]
    return f"{error_type}:{shortened}"


def detect_error_type(error_info: Dict[str, Any]) -> str:
    """Categorize an error into a generalized type."""
    error_type = "unknown"
    error_msg = error_info.get("message", "").lower()
    error_class = error_info.get("type", "").lower()

    if "syntaxerror" in error_class or "syntax error" in error_msg:
        error_type = "syntax"
    elif "typeerror" in error_class or "type error" in error_msg:
        error_type = "type"
    elif "importerror" in error_class or "modulenotfounderror" in error_class:
        error_type = "import"
    elif "attributeerror" in error_class:
        error_type = "attribute"
    elif "nameerror" in error_class:
        error_type = "name"
    elif "indexerror" in error_class or "keyerror" in error_class:
        error_type = "index"
    elif "valueerror" in error_class:
        error_type = "value"
    elif "runtimeerror" in error_class:
        error_type = "runtime"
    elif "memoryerror" in error_class:
        error_type = "memory"
    elif "permissionerror" in error_class or "oserror" in error_class:
        error_type = "permission"
    elif "assertionerror" in error_class:
        error_type = "assertion"
    elif any(x in error_msg for x in ["http", "network", "connection", "timeout"]):
        error_type = "network"
    elif any(x in error_msg for x in ["sql", "database", "db"]):
        error_type = "database"

    return error_type
