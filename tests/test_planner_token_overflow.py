import pytest
from unittest.mock import MagicMock, patch

from agent_s3.planner_json_enforced import _call_llm_with_retry


@patch('agent_s3.planner_json_enforced.TokenEstimator')
def test_call_llm_with_retry_adjusts_max_tokens(MockEstimator):
    estimator = MockEstimator.return_value
    estimator.estimate_tokens_for_text.side_effect = [100, 150]

    router = MagicMock()
    router.call_llm_by_role.return_value = 'ok'

    config = {'max_tokens': 500}
    _call_llm_with_retry(router, 'sys', 'user', config)

    assert router.call_llm_by_role.called
    used_config = router.call_llm_by_role.call_args.kwargs['config']
    assert used_config['max_tokens'] == 250


@patch('agent_s3.planner_json_enforced.TokenEstimator')
def test_call_llm_with_retry_handles_overflow(MockEstimator):
    estimator = MockEstimator.return_value
    estimator.estimate_tokens_for_text.side_effect = [300, 300]

    router = MagicMock()
    router.call_llm_by_role.return_value = 'ok'

    config = {'max_tokens': 500}
    _call_llm_with_retry(router, 'sys', 'user', config)

    used_config = router.call_llm_by_role.call_args.kwargs['config']
    assert used_config['max_tokens'] == 0
