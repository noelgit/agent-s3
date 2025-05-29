from unittest.mock import patch

from agent_s3.llm_utils import cached_call_llm
from agent_s3.config import ConfigModel


class DummyLLM:
    def __init__(self):
        self.calls = []

    def generate(self, params):
        self.calls.append(params)
        return "local"


def test_cached_call_llm_local_only(monkeypatch):
    cfg = ConfigModel()
    dummy = DummyLLM()

    monkeypatch.setattr("agent_s3.llm_utils.cache", None, raising=False)

    with patch("agent_s3.llm_utils.read_cache", return_value=None) as read_cache, \
            patch("agent_s3.llm_utils.write_cache"):
        result = cached_call_llm("hi", dummy, config=cfg.model_dump())
        read_cache.assert_called_once_with("hi", dummy)

    assert result == "local"
    assert dummy.calls
