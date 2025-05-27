import pytest
from agent_s3.tools.context_management.token_budget import TokenEstimator


@pytest.fixture
def sample_context():
    return {
        "metadata": {"task_id": "test-123"},
        "code_context": {"app.py": "def main():\n    return True"},
        "framework_structures": {"models": ["User"]},
    }


def test_estimate_tokens_language_modifier():
    estimator = TokenEstimator()
    python_code = "def hello():\n    return True"
    py_tokens = estimator.estimate_tokens_for_text(python_code, "python")
    js_tokens = estimator.estimate_tokens_for_text(python_code, "javascript")
    assert js_tokens >= py_tokens


def test_estimate_tokens_for_file(tmp_path):
    estimator = TokenEstimator()
    test_file = tmp_path / "hello.py"
    content = "print('hi')\n"
    test_file.write_text(content)
    assert estimator.estimate_tokens_for_file(str(test_file)) == estimator.estimate_tokens_for_text(content, "python")


def test_estimate_tokens_for_context(sample_context):
    estimator = TokenEstimator()
    estimates = estimator.estimate_tokens_for_context(sample_context)
    assert "total" in estimates
    code_total = estimates["code_context"]["total"]
    expected = code_total + estimates["metadata"] + estimates["framework_structures"]
    assert estimates["total"] == expected
