import numpy as np

import agent_s3.tools.summarization.validation_metrics as vm

def test_compute_faithfulness_caching(monkeypatch):
    calls = []

    def fake_get_embedding(text):
        calls.append(text)
        return [1.0, 0.0]

    monkeypatch.setattr(vm, "get_embedding", fake_get_embedding)
    vm._embedding_cache.clear()
    vm.compute_faithfulness("foo", "bar")
    vm.compute_faithfulness("foo", "bar")
    assert calls == ["foo", "bar"]


def test_compute_faithfulness_similarity(monkeypatch):
    monkeypatch.setattr(vm, "get_embedding", lambda _text: [1.0, 1.0])
    vm._embedding_cache.clear()
    result = vm.compute_faithfulness("same", "same")
    assert np.isclose(result, 1.0)
