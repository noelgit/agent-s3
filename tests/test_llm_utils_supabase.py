"""Unit tests for the Supabase LLM utility functions."""

from typing import Any, Dict

import pytest

from agent_s3.llm_utils import call_llm_via_supabase

class DummyResponse:
    """Simplistic response object used for mocking."""

    def __init__(self, json_data: Dict[str, Any] | None = None, text: str = "", status_code: int = 200) -> None:
        self._json = json_data or {}
        self.text = text
        self.status_code = status_code

    def json(self) -> Dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 300):
            raise Exception("Error")


def test_missing_config_raises_value_error():
    with pytest.raises(ValueError):
        call_llm_via_supabase('prompt', 'token', {})


def test_call_llm_via_supabase(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == 'https://example.supabase.co/edge'
        assert json == {'prompt': 'hello'}
        assert headers['X-GitHub-Token'] == 'gh-token'
        return DummyResponse({'response': 'hi'})

    monkeypatch.setattr('agent_s3.llm_utils.requests.post', fake_post)

    result = call_llm_via_supabase(
        'hello',
        'gh-token',
        {
            'supabase_url': 'https://example.supabase.co/edge',
            'supabase_service_role_key': 'key',
            'llm_default_timeout': 10,
        },
    )

    assert result == 'hi'


def test_openai_style_response(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        return DummyResponse({'choices': [{'text': 'openai text'}]})

    monkeypatch.setattr('agent_s3.llm_utils.requests.post', fake_post)

    result = call_llm_via_supabase(
        'hello',
        'gh-token',
        {
            'supabase_url': 'https://example.supabase.co/edge',
            'supabase_service_role_key': 'key',
        },
    )

    assert result == 'openai text'
