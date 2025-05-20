import pytest
from agent_s3.llm_utils import call_llm_via_supabase
from agent_s3.config import ConfigModel


def test_call_llm_via_supabase_includes_token(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers
        class Resp:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {'ok': True}
        return Resp()

    monkeypatch.setattr('requests.post', fake_post)
    config = ConfigModel(
        use_remote_llm=True,
        supabase_url='https://example.supabase.co',
        supabase_function='edge-llm',
        github_oauth_token='test-token',
        llm_default_timeout=5
    )
    payload = {'prompt': 'hi'}
    resp = call_llm_via_supabase(payload, config)
    assert resp.status_code == 200
    assert captured['headers']['Authorization'] == 'Bearer test-token'
    assert 'edge-llm' in captured['url']
