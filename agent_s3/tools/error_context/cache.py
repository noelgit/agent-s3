"""Utilities for caching recognized error patterns."""

from __future__ import annotations

import time
from typing import Any, Dict, List


def update_error_patterns(error_patterns: List[Dict[str, Any]], error_info: Dict[str, Any], context: Dict[str, Any]) -> None:
    """Update the error pattern cache with a new entry."""
    if error_patterns is None:
        return

    pattern = {
        "type": error_info.get("type"),
        "message_pattern": error_info.get("message_pattern"),
        "context": {"error_type": context.get("error_type")},
        "solutions": context.get("recovery_suggestions", []),
        "frequency": 1,
        "last_seen": time.time(),
    }

    similar_found = False
    for existing in error_patterns:
        if (
            existing.get("type") == pattern["type"]
            and existing.get("message_pattern") == pattern["message_pattern"]
        ):
            existing["frequency"] += 1
            existing["last_seen"] = pattern["last_seen"]
            existing["solutions"] = list(set(existing["solutions"] + pattern["solutions"]))
            similar_found = True
            break

    if not similar_found:
        error_patterns.append(pattern)

    prune_error_patterns(error_patterns)


def prune_error_patterns(error_patterns: List[Dict[str, Any]], *, retention_period: float | None = None) -> None:
    """Remove outdated or infrequent error patterns from the cache."""
    if not error_patterns:
        return

    current_time = time.time()
    if retention_period is None:
        retention_period = 7 * 24 * 60 * 60  # one week

    error_patterns[:] = [
        p
        for p in error_patterns
        if current_time - p.get("last_seen", 0) <= retention_period or p.get("frequency", 0) > 5
    ]
