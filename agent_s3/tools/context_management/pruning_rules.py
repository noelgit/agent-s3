"""Utilities for pruning and compressing context data."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

from .compression import CompressionManager
from .content_pruning_manager import ContentPruningManager
from .context_size_monitor import ContextSizeMonitor
from .token_budget import TokenBudgetAnalyzer

logger = logging.getLogger(__name__)


class ContextPruner:
    """Apply pruning rules to maintain context within a token budget."""

    def __init__(
        self,
        token_budget: TokenBudgetAnalyzer,
        size_monitor: ContextSizeMonitor,
        pruning_manager: ContentPruningManager,
        compressor: CompressionManager,
    ) -> None:
        self.token_budget = token_budget
        self.size_monitor = size_monitor
        self.pruning_manager = pruning_manager
        self.compressor = compressor

    def optimize(self, context: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Return an optimized copy of ``context`` respecting the given ``config``."""
        if not context:
            return context
        ctx = copy.deepcopy(context)
        self.size_monitor.update(ctx)
        current = self.size_monitor.current_usage
        target = config.get("CONTEXT_BACKGROUND_OPT_TARGET_TOKENS", 16000)
        allocation = self.token_budget.allocate_tokens(
            ctx,
            task_type=None,
            task_keywords=None,
            force_optimization=False,
        )
        ctx = allocation.get("optimized_context", ctx)
        importance = allocation.get("importance_scores", {})
        self.size_monitor.update(ctx)
        current = self.size_monitor.current_usage
        for section, value in importance.items():
            if isinstance(value, dict):
                for item, score in value.items():
                    self.pruning_manager.set_importance(f"{section}.{item}", score)
            elif isinstance(value, (float, int)):
                self.pruning_manager.set_importance(section, value)
        if current > target:
            candidates = self.pruning_manager.identify_pruning_candidates(ctx, current, target)
            to_prune = current - target
            pruned = 0
            for path, score, tokens in candidates:
                if pruned >= to_prune:
                    break
                if score > 0.7:
                    continue
                self._delete_key(ctx, path)
                pruned += tokens
        return self._compress(ctx)

    def _delete_key(self, context: Dict[str, Any], key_path: str) -> None:
        keys = key_path.split(".")
        if len(keys) == 1:
            context.pop(keys[0], None)
            return
        current = context
        for key in keys[:-1]:
            current = current.get(key)
            if not isinstance(current, dict):
                return
        current.pop(keys[-1], None)

    def _compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        compressed: Dict[str, Any] = {}
        for key, value in context.items():
            if isinstance(value, str) and len(value) > 1000:
                compressed[key] = self.compressor.compress_text(value)
            else:
                compressed[key] = value
        return compressed
