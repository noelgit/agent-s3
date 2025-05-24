"""Unit tests for :func:`call_llm_via_supabase`.

These tests verify that the helper interacts correctly with a mocked
Supabase client and returns the expected response.
"""

from __future__ import annotations

from typing import Any
import json

import pytest

from agent_s3.llm_utils import call_llm_via_supabase

class DummyResponse:
    def __init__(self, data: dict[str, Any], status_code: int = 200, text: str | None = None)
         -> None:        self._data = data
        self.status_code = status_code
        self.text = text or json.dumps(data)

    def json(self) -> dict[str, Any]:
        return self._data

class DummyFunctions:
    def __init__(self) -> None:
        self.invoked = False
        self.args: tuple[Any, ...] | None = None
        self.kwargs: dict[str, Any] | None = None

    def invoke(self, *args: Any, **kwargs: Any) -> DummyResponse:
        self.invoked = True
        self.args = args
        self.kwargs = kwargs
        return DummyResponse({"response": "ok"})

class DummyClient:
    def __init__(self) -> None:
        self.functions: DummyFunctions = DummyFunctions()

def fake_create_client(url: str, key: str) -> DummyClient:
    assert url == "https://example.com"
    assert key == "servicekey"
    return DummyClient()

def test_call_llm_via_supabase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_s3.llm_utils.create_client", fake_create_client)

    def fake_post(url, **_kwargs):
        assert "example.com" in url
        return DummyResponse({"response": "ok"})

    monkeypatch.setattr("agent_s3.llm_utils.requests.post", fake_post)

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


def test_call_llm_via_supabase_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agent_s3.llm_utils.create_client", fake_create_client)

    def fake_post(url, **_kwargs):
        assert "example.com" in url
        return DummyResponse({"error": "bad"}, status_code=500, text="bad")

    monkeypatch.setattr("agent_s3.llm_utils.requests.post", fake_post)

    with pytest.raises(RuntimeError):
        call_llm_via_supabase(
            "hello",
            "gh",
            {
                "supabase_url": "https://example.com",
                "supabase_service_role_key": "servicekey",
                "supabase_function_name": "llm-func",
            },
            timeout=5.0,
        )
