import time
import pytest
from agent_s3.tools.semantic_cache import SemanticCache

class DummyClient:
    """Dummy embedding client returning constant embeddings"""
    def __init__(self, config=None):
        pass
    def generate_embedding(self, text):
        # Return a fixed embedding vector normalized for simplicity
        return [1.0] * SemanticCache.get_instance().embedding_dim

@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    # Create a fresh cache directory for each test
    cache_dir = tmp_path / "semantic_cache"
    cache_dir.mkdir()
    monkeypatch.setenv('SEMANTIC_CACHE_DIR', str(cache_dir))
    # Reset singleton
    SemanticCache._instance = None

    yield

    # Clean up
    SemanticCache._instance = None


def test_set_and_get_cache_hit():
    cache = SemanticCache.get_instance({'semantic_cache_ttl': 10})
    cache.embedding_client = None  # Disable semantic search
    prompt = {'prompt': 'hello'}
    response = {'data': 'world'}

    assert cache.get(prompt) is None  # Miss initially
    cache.set(prompt, response)
    assert cache.get(prompt) == response

    stats = cache.get_cache_stats()
    assert stats['hits'] == 1
    assert stats['misses'] == 0
    assert stats['semantic_hits'] == 0


def test_ttl_expiry():
    cache = SemanticCache.get_instance({'semantic_cache_ttl': 1})
    cache.embedding_client = None
    prompt = {'prompt': 'expire'}
    response = {'result': True}
    cache.set(prompt, response)

    # Immediately accessible
    assert cache.get(prompt) == response
    time.sleep(1.1)
    # Should expire
    assert cache.get(prompt) is None


def test_eviction_lru():
    # Set max entries to 3 for testing eviction
    cache = SemanticCache.get_instance({'semantic_cache_max_entries': 3, 'semantic_cache_ttl': 100})
    cache.embedding_client = None
    # Add 5 entries
    for i in range(5):
        cache.set({'prompt': str(i)}, {'val': i})
    # Should have evicted to <= max entries
    assert len(cache.mem_cache) <= 3

    # Check ordering: oldest entries removed
    keys = list(cache.mem_cache.keys())
    # The last few inserted should remain
    assert all(k in [cache.get_cache_key({'prompt': str(i)}) for i in range(2,5)] for k in keys)


def test_cache_miss_and_hit(monkeypatch):
    cache = SemanticCache.get_instance()
    prompt = {'prompt': 'hello', 'model': 'test'}
    # Ensure miss
    assert cache.get(prompt) is None
    # Set a response
    cache.set(prompt, {'res': 123})
    # Hit
    result = cache.get(prompt)
    assert result == {'res': 123}
    stats = cache.get_cache_stats()
    assert stats['misses'] == 1
    assert stats['hits'] == 1


def test_ttl_expiry():
    cache = SemanticCache.get_instance()
    prompt = {'prompt': 'bye', 'model': 'test'}
    cache.set(prompt, {'res': 'expire'})
    time.sleep(1.1)
    # Should expire
    assert cache.get(prompt) is None


def test_eviction_lru():
    cache = SemanticCache.get_instance()
    # Fill beyond max entries to trigger eviction (max 3)
    for i in range(5):
        cache.set({'prompt': f'p{i}', 'model': 'test'}, i)
    # After eviction, only <=3 entries remain
    stats = cache.get_cache_stats()
    entries = cache.mem_cache
    assert len(entries) <= cache.max_cache_entries


@pytest.mark.parametrize('count', [0, 1])
def test_semantic_search_no_embedding(monkeypatch, count):
    cache = SemanticCache.get_instance()
    # Monkeypatch embedding client to None to disable semantic
    cache.embedding_client = None
    cache.index = None
    prompt = {'prompt': f'q{count}', 'model': 'test'}
    cache.set(prompt, {'val': count})
    # Only exact get works
    assert cache.get(prompt) == {'val': count}
