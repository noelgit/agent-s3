"""Unified context access layer with deduplication and monitoring."""

from __future__ import annotations

import json
from hashlib import sha1
from typing import Any, Dict, Set

from .context_manager import ContextManager
from .context_monitoring import get_context_monitor


class ContextAccessLayer:
    """Central interface for retrieving context snapshots."""

    def __init__(self, manager: ContextManager, enable_monitoring: bool = True) -> None:
        self.manager = manager
        self.enable_monitoring = enable_monitoring
        self.monitor = get_context_monitor() if enable_monitoring else None
        self._seen_hashes: Set[str] = set()

    def get_context(
        self, *, task_description: str, task_type: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Return a deduplicated context snapshot."""
        context = self.manager.gather_context(
            task_description=task_description,
            task_type=task_type,
            **kwargs,
        )
        context_hash = sha1(
            json.dumps(context, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if context_hash in self._seen_hashes:
            if self.monitor:
                self.monitor.log_event(
                    "cache_hit", source="access_layer", query=task_type
                )
            return context
        self._seen_hashes.add(context_hash)
        if self.monitor:
            self.monitor.log_event("retrieval", source="access_layer", query=task_type)
        return context
