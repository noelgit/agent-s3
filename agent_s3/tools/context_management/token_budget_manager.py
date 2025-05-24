"""Wrapper around :class:`TokenBudgetAnalyzer` with helper utilities."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .token_budget import TokenBudgetAnalyzer


class TokenBudgetManager:
    """Simplify token budget operations."""

    def __init__(self, analyzer: TokenBudgetAnalyzer) -> None:
        self.analyzer = analyzer

    def allocate(
        self,
        context: Dict[str, Any],
        task_type: Optional[str] = None,
        task_keywords: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        return self.analyzer.allocate_tokens(
            context,
            task_type=task_type,
            task_keywords=task_keywords,
            force_optimization=False,
        )
