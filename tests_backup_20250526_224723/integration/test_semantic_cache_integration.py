import pytest
from functools import wraps

from agent_s3.llm_utils import call_llm_with_retry

# Simple in-memory cache for testing
_test_cache = {}

class DummyLLMClient:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt_data):
        self.calls += 1
        # Simulate LLM response based on prompt
        return {'output': prompt_data.get('prompt', '') + '_resp'}

class DummyScratchpad:
    def __init__(self):
        self.logs = []

    def log(self, category, message):
        self.logs.append((category, message))

def mock_cache(func):
    """Mock cache decorator that simulates semantic cache behavior."""
    @wraps(func)
    def wrapper(prompt_data, *args, **kwargs):
        # Create a simple key based on the prompt
        key = str(prompt_data.get('prompt', ''))

        # Check if in cache
        if key in _test_cache:
            # Return cached result with cached flag
            return {'response': _test_cache[key], 'cached': True}

        # Not in cache, call original function
        result = func(prompt_data, *args, **kwargs)

        # Store in cache
        _test_cache[key] = result

        # Return original result
        return result
    return wrapper

@pytest.fixture(autouse=True)
def clear_cache(tmp_path, monkeypatch):
    # Reset our test cache
    global _test_cache
    _test_cache = {}

    # Reset SemanticCache singleton
    from agent_s3.tools.semantic_cache import SemanticCache as _SC
    _SC._instance = None
    yield
    _SC._instance = None

@pytest.mark.parametrize('prompt_text', ['hello', 'world'])
def test_integration_cache_efficiency(prompt_text):
    client = DummyLLMClient()
    scratch = DummyScratchpad()
    # Configuration for llm_utils
    config = {
        'llm_default_timeout': 1.0,
        'llm_max_retries': 1,
        'llm_initial_backoff': 0,
        'llm_backoff_factor': 1,
        'llm_fallback_strategy': 'none'
    }
    prompt_data = {'prompt': prompt_text}

    # Apply our mock cache decorator to the generate method
    original_generate = client.generate
    client.generate = mock_cache(original_generate)

    # First call: cache miss, client.calls increments
    result1 = call_llm_with_retry(client, 'generate', prompt_data, config, scratch, prompt_text)
    assert result1['success'] is True
    assert not result1.get('cached', False)
    assert client.calls == 1

    # Second call: should hit cache, no new client invocation
    result2 = call_llm_with_retry(client, 'generate', prompt_data, config, scratch, prompt_text)
    assert result2['success'] is True
    assert result2.get('cached') is True
    assert client.calls == 1

    # Response content matches
    assert result2['response'] == result1['response']
