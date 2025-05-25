"""Utility helpers for compression strategies."""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)


def hash_content(content: str) -> str:
    """Return a SHA-256 hex digest for ``content``."""
    return hashlib.sha256(content.encode()).hexdigest()

