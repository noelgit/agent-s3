import logging
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

logger = logging.getLogger(__name__)

class ContextSizeMonitor:
    """Monitors context size and token usage with configurable thresholds."""

    def __init__(self, token_analyzer, max_tokens: int = 16000):
        self.token_analyzer = token_analyzer
        self.max_tokens = max_tokens
        self.current_usage = 0
        self.section_usage: Dict[str, int] = {}
        self.history: List[Tuple[float, int]] = []
        self.alert_thresholds = [0.7, 0.8, 0.9]
        self._exceeded_thresholds: Set[float] = set()

    def update(self, context: Dict[str, Any]) -> None:
        self.current_usage = self.token_analyzer.get_total_token_count(context)
        self.history.append((time.time(), self.current_usage))
        if len(self.history) > 100:
            self.history = self.history[-100:]
        for section_key, value in context.items():
            if isinstance(value, dict):
                section_tokens = 0
                for k, v in value.items():
                    if isinstance(v, str):
                        section_tokens += self.token_analyzer.get_token_count(v)
                self.section_usage[section_key] = section_tokens
            elif isinstance(value, str):
                self.section_usage[section_key] = self.token_analyzer.get_token_count(value)
        self._check_thresholds()

    def _check_thresholds(self) -> None:
        usage_ratio = self.current_usage / self.max_tokens
        for threshold in self.alert_thresholds:
            if usage_ratio >= threshold and threshold not in self._exceeded_thresholds:
                logger.warning(
                    f"Context size alert: {int(threshold * 100)}% of token budget used "
                    f"({self.current_usage}/{self.max_tokens} tokens)"
                )
                self._exceeded_thresholds.add(threshold)
            elif usage_ratio < threshold and threshold in self._exceeded_thresholds:
                self._exceeded_thresholds.remove(threshold)

    def get_section_breakdown(self) -> Dict[str, Dict[str, Any]]:
        total = max(1, self.current_usage)
        result = {}
        for section, tokens in self.section_usage.items():
            result[section] = {
                "tokens": tokens,
                "percentage": (tokens / total) * 100,
                "is_large": tokens > (self.max_tokens * 0.2),
            }
        return result

    def get_growth_rate(self) -> float:
        if len(self.history) < 2:
            return 0.0
        points = min(5, len(self.history))
        recent = self.history[-points:]
        if recent[-1][0] == recent[0][0]:
            return 0.0
        rate = (recent[-1][1] - recent[0][1]) / (recent[-1][0] - recent[0][0])
        return rate

    def estimate_time_to_threshold(self, threshold_ratio: float = 0.9) -> Optional[float]:
        growth_rate = self.get_growth_rate()
        if growth_rate <= 0:
            return None
        threshold_tokens = self.max_tokens * threshold_ratio
        tokens_remaining = threshold_tokens - self.current_usage
        if tokens_remaining <= 0:
            return 0
        return tokens_remaining / growth_rate
