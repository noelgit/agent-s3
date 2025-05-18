"""Error Pattern Learner for ML-based prediction.

This module provides a lightweight naive Bayes implementation to learn
error message patterns and predict their categories. Patterns are stored
per-user under ``~/.agent_s3/error_patterns.json`` so they can be shared
across projects.
"""

from __future__ import annotations

import json
import os
import math
from collections import Counter, defaultdict
from typing import Dict, List

# Path to shared pattern database
PATTERN_DB_PATH = os.path.expanduser("~/.agent_s3/error_patterns.json")


class ErrorPatternLearner:
    """Learn error patterns and predict categories using naive Bayes."""

    def __init__(self) -> None:
        self.category_counts: Counter[str] = Counter()
        self.word_category_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        self._load()

    def _load(self) -> None:
        if os.path.exists(PATTERN_DB_PATH):
            try:
                with open(PATTERN_DB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.category_counts.update(data.get("category_counts", {}))
                for cat, counts in data.get("word_category_counts", {}).items():
                    self.word_category_counts[cat].update(counts)
            except Exception:
                # Corrupted file, ignore
                pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(PATTERN_DB_PATH), exist_ok=True)
        data = {
            "category_counts": self.category_counts,
            "word_category_counts": self.word_category_counts,
        }
        # Convert Counters to regular dicts for JSON serialization
        serializable = {
            "category_counts": dict(self.category_counts),
            "word_category_counts": {
                cat: dict(cnt) for cat, cnt in self.word_category_counts.items()
            },
        }
        with open(PATTERN_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f)

    def update(self, message: str, category: str) -> None:
        tokens = self._tokenize(message)
        if not tokens:
            return
        self.category_counts[category] += 1
        for token in tokens:
            self.word_category_counts[category][token] += 1
        self._save()

    def predict(self, message: str) -> str | None:
        tokens = self._tokenize(message)
        if not tokens or not self.category_counts:
            return None

        total_categories = sum(self.category_counts.values())
        best_cat = None
        best_log_prob = -math.inf

        for category, cat_count in self.category_counts.items():
            # Prior probability
            log_prob = math.log(cat_count / total_categories)
            word_counts = self.word_category_counts[category]
            total_words = sum(word_counts.values())
            for token in tokens:
                count = word_counts.get(token, 0)
                # Laplace smoothing
                log_prob += math.log((count + 1) / (total_words + len(word_counts)))
            if log_prob > best_log_prob:
                best_log_prob = log_prob
                best_cat = category
        return best_cat

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w.lower() for w in text.split() if w.isalpha()]
