import requests
import sys
import types

# Provide a minimal progress_tracker to satisfy llm_utils import
sys.modules.setdefault(
    "agent_s3.progress_tracker",
    types.SimpleNamespace(progress_tracker=lambda *a, **k: None),
)

from agent_s3.llm_utils import call_llm_with_retry  # noqa: E402




def test_call_llm_with_retry_fallback_executes():
    class DummyLLM:
        def __init__(self):
            self.calls = []

        def generate(self, prompt_data):
            self.calls.append(prompt_data)
            # Return success only when the fallback prefix is present
            prompt = prompt_data.get("prompt", "")
            if prompt.startswith("Previous attempt failed"):
                return {"response": "ok"}
            raise requests.exceptions.Timeout("fail")

    class DummyScratchpad:
        def log(self, *_args, **_kwargs):
            pass

    client = DummyLLM()
    scratch = DummyScratchpad()
    config = {
        "llm_default_timeout": 0,
        "llm_max_retries": 1,
        "llm_initial_backoff": 0,
        "llm_backoff_factor": 1,
        "llm_fallback_strategy": "retry_simplified",
    }
    prompt_data = {"prompt": "hello"}

    result = call_llm_with_retry(client, "generate", prompt_data, config, scratch, "hello")

    assert result["success"] is True
    assert result.get("used_fallback") is True
    assert len(client.calls) == 2
