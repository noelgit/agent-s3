from collections import OrderedDict
from collections import defaultdict
import json
import logging
import threading
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

logger = logging.getLogger(__name__)

class ContentPruningManager:
    """Manages LRU tracking and prioritized pruning of context elements."""

    def __init__(self, token_analyzer):
        self.token_analyzer = token_analyzer
        self._access_history: Dict[str, List[float]] = defaultdict(list)
        self._access_counts: Dict[str, int] = defaultdict(int)
        self._importance_overrides: Dict[str, float] = {}
        self._critical_paths: Set[str] = set()
        self._lru_cache = OrderedDict()
        self._max_history_per_key = 10
        self.recency_weight = 0.5
        self.frequency_weight = 0.3
        self.importance_weight = 0.2
        # Thread safety lock for atomic operations
        self._data_lock = threading.Lock()

    def record_access(self, key_path: str) -> None:
        timestamp = time.time()
        with self._data_lock:
            history = self._access_history[key_path]
            history.append(timestamp)
            if len(history) > self._max_history_per_key:
                history.pop(0)
            self._access_counts[key_path] += 1
            self._lru_cache[key_path] = timestamp
            if len(self._lru_cache) > 1000:
                self._lru_cache.popitem(last=False)

    def set_importance(self, key_path: str, importance: float) -> None:
        with self._data_lock:
            self._importance_overrides[key_path] = max(0.0, min(1.0, importance))

    def mark_as_critical(self, key_path: str) -> None:
        with self._data_lock:
            self._critical_paths.add(key_path)

    def _calculate_value_score(self, key_path: str) -> float:
        if key_path in self._critical_paths:
            return 1.0
        if key_path in self._importance_overrides:
            return self._importance_overrides[key_path]
        recency_score = 0.0
        if key_path in self._lru_cache:
            most_recent = self._lru_cache[key_path]
            time_since = time.time() - most_recent
            recency_score = max(0.0, min(1.0, 1.0 - (time_since / (24 * 60 * 60))))
        freq_score = 0.0
        if self._access_counts:
            max_count = max(self._access_counts.values())
            if max_count > 0:
                freq_score = self._access_counts.get(key_path, 0) / max_count
        importance_score = 0.5
        return (
            recency_score * self.recency_weight
            + freq_score * self.frequency_weight
            + importance_score * self.importance_weight
        )

    def identify_pruning_candidates(
        self,
        context: Dict[str, Any],
        current_tokens: int,
        target_tokens: int,
    ) -> List[Tuple[str, float, int]]:
        if current_tokens <= target_tokens:
            return []
        candidates: List[Tuple[str, int]] = []
        self._collect_pruneable_elements(context, "", candidates)
        for i, (key_path, token_count) in enumerate(candidates):
            value_score = self._calculate_value_score(key_path)
            candidates[i] = (key_path, value_score, token_count)
        return sorted(candidates, key=lambda x: (x[1], -x[2]))

    def _collect_pruneable_elements(
        self, context: Dict[str, Any], prefix: str, result: List[Tuple[str, int]]
    ) -> None:
        if not isinstance(context, dict):
            return
        for key, value in context.items():
            current_path = f"{prefix}.{key}" if prefix else key
            if current_path in self._critical_paths:
                continue
            if isinstance(value, str):
                token_count = self.token_analyzer.get_token_count(value)
                if token_count > 0:
                    result.append((current_path, token_count))
            elif isinstance(value, dict):
                total_tokens = self.token_analyzer.get_token_count(json.dumps(value))
                if total_tokens > 0:
                    result.append((current_path, total_tokens))
                self._collect_pruneable_elements(value, current_path, result)
