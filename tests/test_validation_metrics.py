from unittest.mock import patch

from agent_s3.tools.summarization import validation_metrics as vm


def test_embedding_caching():
    vm._embedding_cache.clear()
    with patch("agent_s3.tools.summarization.validation_metrics.get_embedding", return_value=[1.0, 0.0]) as mock_get:
        vm.compute_faithfulness("source text", "summary text")
        assert mock_get.call_count == 2
        vm.compute_faithfulness("source text", "summary text")
        # second call should not invoke get_embedding again
        assert mock_get.call_count == 2
        assert set(vm._embedding_cache.keys()) == {"source text", "summary text"}

