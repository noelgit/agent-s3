import agent_s3.tools.summarization.summary_validator as summary_validator
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig

def test_summary_validator_faithful(monkeypatch):
    def fake_metrics(*_args, **_kwargs):
        return {
            "faithfulness": 1.0,
            "detail_preservation": 1.0,
            "structural_coherence": 1.0,
            "overall": 1.0,
        }

    monkeypatch.setattr(summary_validator, "compute_overall_quality", fake_metrics)
    config = SummaryValidationConfig(
        faithfulness_threshold=0.5,
        detail_preservation_threshold=0.5,
        structural_coherence_threshold=0.5,
    )
    validator = SummaryValidator(config)
    source = "def foo():\n    return 42"
    summary = "Function foo returns 42."
    result = validator.validate(source, summary, language="python")
    assert result["passed"]
    assert result["metrics"]["faithfulness"] >= 0.5
    assert result["metrics"]["detail_preservation"] >= 0.5
    assert result["metrics"]["structural_coherence"] >= 0.5

def test_summary_validator_unfaithful(monkeypatch):
    def fake_metrics(*_args, **_kwargs):
        return {
            "faithfulness": 0.1,
            "detail_preservation": 0.1,
            "structural_coherence": 0.1,
            "overall": 0.1,
        }

    monkeypatch.setattr(summary_validator, "compute_overall_quality", fake_metrics)
    config = SummaryValidationConfig(
        faithfulness_threshold=0.9,
        detail_preservation_threshold=0.9,
        structural_coherence_threshold=0.9,
    )
    validator = SummaryValidator(config)
    source = "def foo():\n    return 42"
    summary = "This function does something else."
    result = validator.validate(source, summary, language="python")
    assert not result["passed"]
    assert result["metrics"]["faithfulness"] < 0.9
    assert result["metrics"]["detail_preservation"] < 0.9


def test_summary_validator_with_dict_config(monkeypatch):
    def fake_metrics(*_args, **_kwargs):
        return {
            "faithfulness": 1.0,
            "detail_preservation": 1.0,
            "structural_coherence": 1.0,
            "overall": 1.0,
        }

    monkeypatch.setattr(summary_validator, "compute_overall_quality", fake_metrics)
    config = {
        "min_faithfulness": 0.5,
        "min_detail_preservation": 0.5,
        "min_structural_coherence": 0.5,
        "min_overall_quality": 0.5,
    }
    validator = SummaryValidator(config)
    source = "def bar():\n    return 7"
    summary = "Function bar returns 7."
    result = validator.validate(source, summary, language="python")
    assert result["passed"]
    assert result["metrics"]["faithfulness"] >= 0.5
    assert result["metrics"]["detail_preservation"] >= 0.5
    assert result["metrics"]["structural_coherence"] >= 0.5
