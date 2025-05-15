import pytest
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig

def test_summary_validator_faithful():
    config = SummaryValidationConfig(faithfulness_threshold=0.5, detail_preservation_threshold=0.5, structural_coherence_threshold=0.5)
    validator = SummaryValidator(config)
    source = "def foo():\n    return 42"
    summary = "Function foo returns 42."
    valid, metrics = validator.validate(source, summary, language="python")
    assert valid
    assert metrics['faithfulness'] >= 0.5
    assert metrics['detail_preservation'] >= 0.5
    assert metrics['structural_coherence'] >= 0.5

def test_summary_validator_unfaithful():
    config = SummaryValidationConfig(faithfulness_threshold=0.9, detail_preservation_threshold=0.9, structural_coherence_threshold=0.9)
    validator = SummaryValidator(config)
    source = "def foo():\n    return 42"
    summary = "This function does something else."
    valid, metrics = validator.validate(source, summary, language="python")
    assert not valid
    assert metrics['faithfulness'] < 0.9
    assert metrics['detail_preservation'] < 0.9
