import json

import pytest

from agent_s3.llm_utils import call_llm_via_supabase


class DummyResponse:
    def __init__(self, text: str) -> None:
        self.text = text

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
        "supabase_url": "http://supabase",
        "supabase_anon_key": "key",
        "supabase_function_name": "func",
    }

    with pytest.raises(ValueError) as exc:
        call_llm_via_supabase("hi", "tok", cfg)

    assert "{bad" in str(exc.value)
