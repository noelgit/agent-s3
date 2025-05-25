"""Utility helpers for diff and similarity comparisons."""

from difflib import SequenceMatcher
from typing import Iterable, Optional


def find_best_match(target: str, candidates: Iterable[str], threshold: float = 0.7) -> Optional[str]:
    """Return the candidate most similar to *target* above *threshold*.

    Args:
        target: String we are trying to match.
        candidates: Possible candidate strings.
        threshold: Minimum similarity ratio required for a match.

    Returns:
        The best matching candidate if one exceeds the threshold, else ``None``.
    """
    best_match: Optional[str] = None
    highest_similarity = 0.0
    for candidate in candidates:
        similarity = SequenceMatcher(None, target, candidate).ratio()
        if similarity > highest_similarity and similarity >= threshold:
            highest_similarity = similarity
            best_match = candidate
    return best_match
