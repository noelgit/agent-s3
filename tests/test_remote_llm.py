from agent_s3.config import ConfigModel
from agent_s3.llm_utils import cached_call_llm
import types

class DummyLLM:
    def __init__(self):
        self.calls = []

    def generate(self, params):
        self.calls.append(params)
        return "local"

def test_cached_call_llm_local_only(monkeypatch):
    cfg = ConfigModel(use_remote_llm=True)
    dummy = DummyLLM()
    monkeypatch.setattr(
        "agent_s3.cache.helpers.cache",
        types.SimpleNamespace(get=lambda *_args, **_kw: None, set=lambda *_a, **_k: None),
    )
    result = cached_call_llm("hi", dummy, config=cfg.model_dump(), github_token="tok")
    assert result == "local"
    assert dummy.calls

