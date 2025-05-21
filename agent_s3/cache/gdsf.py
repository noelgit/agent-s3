"""
Prefix-aware Greedy-Dual-Size-Frequency (GDSF) eviction policy for GPTCache.
"""
import time
from gptcache.manager.eviction.base import BaseEvictionPolicy
from gptcache.manager.eviction import registry

class PrefixGDSF(BaseEvictionPolicy):
    def __init__(self):
        self.lambda_decay = 0.001

    def _score(self, m):
        freq  = m.get("hits", 1)
        size  = m.get("kv_size", 1)
        age   = time.time() - m.get("last", time.time())
        return (freq / size) - self.lambda_decay * age

    def evict(self, all_meta):
        leaves = [m for m in all_meta if m.get("is_leaf", True)]
        victim = min(leaves, key=self._score)
        return victim["uuid"]

# Register the policy at import time
registry.register("custom_gdsf", PrefixGDSF)
