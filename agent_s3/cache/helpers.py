"""
Helpers for semantic cache read/write and vLLM KV reuse.
"""
import time
try:
    import torch
    Tensor = torch.Tensor
except Exception:  # pragma: no cover - torch optional for tests
    torch = None

    class Tensor:  # type: ignore
        """Fallback tensor type used when torch is unavailable."""

        def __init__(self, *_, **__):
            self.nbytes = 0

from gptcache import cache
from .prefix import prefix_hash
from .kv_store import kv_store


def read_cache(prompt: str, llm):
    res = cache.get(prompt)
    if res:
        return res  # semantic hit
    pfx = prefix_hash(prompt)
    if pfx in kv_store:
        llm.attach_kv(kv_store[pfx])  # vLLM API for prefix reuse
        return None  # must still call LLM
    return None


def write_cache(prompt: str, answer: str, kv_tensor: Tensor):
    meta = {
        "prefix": prefix_hash(prompt),
        "hits": 1,
        "kv_size": kv_tensor.nbytes,
        "is_leaf": True,
        "last": time.time(),
    }
    kv_store[meta["prefix"]] = kv_tensor
    cache.set(prompt, answer, meta)
