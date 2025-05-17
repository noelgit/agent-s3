"""
SummaryCache: LRU cache for validated summaries, with content-hash based invalidation.
"""
import hashlib
from collections import OrderedDict

class SummaryCache:
    def __init__(self, max_size=128):
        self.cache = OrderedDict()
        self.max_size = max_size

    def _hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get(self, content):
        key = self._hash(content)
        return self.cache.get(key)

    def set(self, content, summary):
        key = self._hash(content)
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = summary
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
