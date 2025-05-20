import sys
import types
from unittest.mock import MagicMock


# Provide a minimal 'requests' stub for the module under test
requests_stub = types.ModuleType("requests")
class HTTPError(Exception):
    def __init__(self, response=None):
        super().__init__("HTTP error")
        self.response = response
class RequestException(Exception):
    pass
requests_stub.HTTPError = HTTPError
requests_stub.RequestException = RequestException
requests_stub.post = lambda *a, **k: None
sys.modules.setdefault("requests", requests_stub)

# ruff: noqa: E402
from agent_s3.llm_utils import call_llm_via_supabase, requests as llm_requests

class DummyConfig:
    supabase_url = "https://example.supabase.co"
    supabase_service_key = "service-key"
    llm_max_retries = 2
    llm_initial_backoff = 0
    llm_backoff_factor = 1
    llm_default_timeout = 5

def test_call_llm_via_supabase_success(monkeypatch):
    dummy_resp = MagicMock()
    dummy_resp.json.return_value = {"result": "ok"}
    dummy_resp.raise_for_status.return_value = None

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url.endswith("/functions/v1/llm")
        return dummy_resp

    monkeypatch.setattr("agent_s3.llm_utils.create_client", lambda u, k: object())
    monkeypatch.setattr(llm_requests, "post", fake_post)

    result = call_llm_via_supabase({"prompt": "hi"}, DummyConfig())
    assert result == {"result": "ok"}

def test_call_llm_via_supabase_retry(monkeypatch):
    attempts = {"count": 0}
    err = HTTPError(types.SimpleNamespace(status_code=500))

    def fake_post(url, json=None, headers=None, timeout=None):
        attempts["count"] += 1
        resp = MagicMock()
        if attempts["count"] == 1:
            resp.raise_for_status.side_effect = err
        else:
            resp.raise_for_status.return_value = None
            resp.json.return_value = {"ok": True}
        return resp

    monkeypatch.setattr("agent_s3.llm_utils.create_client", lambda u, k: object())
    monkeypatch.setattr(llm_requests, "post", fake_post)

    result = call_llm_via_supabase({"prompt": "hi"}, DummyConfig())
    assert attempts["count"] == 2
    assert result == {"ok": True}
