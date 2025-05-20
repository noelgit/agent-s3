"""Tests for the Supabase-based LLM invocation helper."""

from agent_s3.llm_utils import call_llm_via_supabase

class DummyResponse:
    def __init__(self, data):
        self._data = data
    def json(self):
        return self._data

class DummyFunctions:
    def __init__(self):
        self.invoked = False
        self.args = None
        self.kwargs = None
    def invoke(self, *args, **kwargs):
        self.invoked = True
        self.args = args
        self.kwargs = kwargs
        return DummyResponse({"response": "ok"})

class DummyClient:
    def __init__(self):
        self.functions = DummyFunctions()

def fake_create_client(url, key):
    assert url == "https://example.com"
    assert key == "servicekey"
    return DummyClient()

def test_call_llm_via_supabase(monkeypatch):
    monkeypatch.setattr("agent_s3.llm_utils.create_client", fake_create_client)
    result = call_llm_via_supabase(
        "hello",
        "gh",
        {
            "supabase_url": "https://example.com",
            "supabase_service_role_key": "servicekey",
            "supabase_function_name": "llm-func",
        },
        timeout=5.0,
    )
    assert result == "ok"
