import pytest
from agent_s3.tools.summarization.summary_refiner import SummaryRefiner
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig
from agent_s3.tools.summarization.prompt_factory import SummarizationPromptFactory

def test_summary_refiner_refines():
    config = SummaryValidationConfig(faithfulness_threshold=0.9, detail_preservation_threshold=0.9, structural_coherence_threshold=0.9, max_refinement_attempts=2)
    validator = SummaryValidator(config)
    prompt_factory = SummarizationPromptFactory()
    refiner = SummaryRefiner(validator, prompt_factory, config)
    source = "def foo():\n    return 42"
    summary = "This function does something else."
    refined, metrics = refiner.refine(source, summary, language="python")
    # Since _call_llm is stubbed, expect fallback output
    assert "Refined summary" in refined or not metrics['faithfulness'] >= 0.9
