"""Simple file cache utilities."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=256)
def read_file_cached(path: str) -> str:
    """Read a text file from disk with LRU caching."""
    file_path = Path(path)
    if not file_path.is_file():
        return ""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""
