import json

import pytest

from agent_s3.llm_utils import call_llm_via_supabase


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def json(self) -> dict:
        raise json.JSONDecodeError("error", self.text, 0)


class DummyFunctions:
    def __init__(self) -> None:
        pass

    def invoke(self, *args, **kwargs):
        import requests  # delayed import for patching

        return requests.post("http://example.com")


class DummyClient:
    def __init__(self) -> None:
        self.functions = DummyFunctions()


# fake create_client to avoid network

def fake_create_client(url: str, key: str) -> DummyClient:
    return DummyClient()


def test_invalid_json_snippet(monkeypatch):
    monkeypatch.setattr("agent_s3.llm_utils.create_client", fake_create_client)

    def fake_post(*_args, **_kwargs):
        return DummyResponse("{bad")

    monkeypatch.setattr("requests.post", fake_post)

    cfg = {
        "supabase_url": "https://supabase",
        "supabase_service_role_key": "key",
        "supabase_function_name": "func",
    }

    with pytest.raises(ValueError) as exc:
        call_llm_via_supabase("hi", "tok", cfg)

    assert "{bad" in str(exc.value)


def test_invalid_request_body(monkeypatch):
    """Error is raised for a payload that cannot be JSON serialized."""
    def dummy_client(*_args, **_kwargs):
        raise AssertionError("client should not be created for invalid payload")

    monkeypatch.setattr("agent_s3.llm_utils.create_client", dummy_client)

    cfg = {
        "supabase_url": "https://supabase",
        "supabase_service_role_key": "key",
        "supabase_function_name": "func",
    }

    with pytest.raises(ValueError):
        call_llm_via_supabase(object(), "tok", cfg)


def test_invalid_supabase_url_scheme(monkeypatch):
    cfg = {
        "supabase_url": "http://supabase",
        "supabase_service_role_key": "key",
        "supabase_function_name": "func",
    }

    with pytest.raises(ValueError):
        call_llm_via_supabase("hi", "tok", cfg)
