"""Base classes for compression strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from .utils import logger


class CompressionStrategy(ABC):
    """Abstract base class for context compression strategies."""

    @abstractmethod
    def compress(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Compress the given context."""

    @abstractmethod
    def decompress(self, compressed_context: Dict[str, Any]) -> Dict[str, Any]:
        """Decompress a previously compressed context."""

