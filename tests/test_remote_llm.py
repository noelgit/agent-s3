

from agent_s3.llm_utils import cached_call_llm
from agent_s3.config import ConfigModel

class DummyLLM:
    def __init__(self):
        self.calls = []

    def generate(self, params):
        self.calls.append(params)
        return "local"

def test_remote_llm_invocation(monkeypatch):
    cfg = ConfigModel(use_remote_llm=True, supabase_url="http://test", supabase_service_role_key="key")
    dummy = DummyLLM()
    called = {}

    def fake_remote(prompt, token, config, timeout=None):
        called["args"] = (prompt, token, config, timeout)
        return "remote"

    monkeypatch.setattr("agent_s3.llm_utils.call_llm_via_supabase", fake_remote)
    result = cached_call_llm("hi", dummy, config=cfg, github_token="tok")
    assert result == "remote"
    assert called["args"][0] == "hi"
    assert called["args"][1] == "tok"
    assert called["args"][2] == cfg
    assert not dummy.calls


def test_remote_llm_fallback(monkeypatch):
    cfg = ConfigModel(use_remote_llm=True, supabase_url="http://test", supabase_service_role_key="key")
    dummy = DummyLLM()

    def failing_remote(*_args, **_kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr("agent_s3.llm_utils.call_llm_via_supabase", failing_remote)
    result = cached_call_llm("hi", dummy, config=cfg, github_token="tok")
    assert result == "local"
    assert dummy.calls

