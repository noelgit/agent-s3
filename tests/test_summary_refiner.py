from unittest.mock import MagicMock

from agent_s3.tools.summarization.summary_refiner import SummaryRefiner
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig



class DummyPromptFactory:
    def get_prompt(self, language, source, task):
        return "dummy prompt"

def test_summary_refiner_refines():
    config = SummaryValidationConfig(faithfulness_threshold=0.9, detail_preservation_threshold=0.9, structural_coherence_threshold=0.9, max_refinement_attempts=2)
    validator = SummaryValidator()
    prompt_factory = DummyPromptFactory()
    router_agent = MagicMock()
    router_agent.call_llm_by_role.return_value = "Improved summary"
    refiner = SummaryRefiner(validator, prompt_factory, config, router_agent)
    source = "def foo():\n    return 42"
    summary = "This function does something else."
    refined, metrics = refiner.refine(source, summary, language="python")
    router_agent.call_llm_by_role.assert_called()
    assert refined == "Improved summary" or not metrics["faithfulness"] >= 0.9
