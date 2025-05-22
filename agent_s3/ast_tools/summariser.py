"""
LLM-based summarization for code units and file-level merging.
"""

from typing import Any, Dict, List

from agent_s3.tools.summarization.prompt_factory import SummarizationPromptFactory
from agent_s3.tools.summarization.summary_validator import SummaryValidator
from agent_s3.tools.summarization.validation_config import SummaryValidationConfig
from agent_s3.tools.summarization.refinement_manager import SummaryRefinementManager

prompt_factory = SummarizationPromptFactory()
validator = SummaryValidator(SummaryValidationConfig())

def summarise_unit(code_unit: Dict[str, Any], router_agent: Any, config: Dict[str, Any] | None = None) -> str:
    """
    Summarize a code unit with validation and refinement.
    """
    code_text = code_unit.get('text', '')
    language = code_unit.get('language', None)
    if not code_text.strip():
        return ""
    system_prompt = (
        f"You are an expert at summarizing {language or 'code'}. "
        f"Create a concise summary of the following code unit ({code_unit.get('type', 'unit')}). "
        "Focus on functionality, purpose, parameters, return values, and key logic. "
        "Be factually accurate and preserve all critical technical details."
    )
    user_prompt = (
        f"Summarize this {language or 'code'} {code_unit.get('type', 'unit')}:\n\n"
        f"---CODE START---\n{code_text}\n---CODE END---"
    )
    summary = router_agent.call_llm_by_role(
        role="summarizer",
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )
    validation_result = validator.validate(code_text, summary, language)
    if not validation_result["passed"]:
        refinement_manager = SummaryRefinementManager(router_agent)
        refinement_result = refinement_manager.refine_summary(
            source=code_text,
            summary=summary,
            validation_result=validation_result,
            language=language
        )
        summary = refinement_result["summary"]
    return summary

def merge_summaries(summaries: List[str], language: str, router_agent: Any) -> str:
    """
    Merge multiple summaries with validation.
    """
    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]
    system_prompt = (
        f"You are an expert at merging and consolidating {language or 'code'} summaries. "
        "Create a cohesive, unified summary from the individual component summaries provided. "
        "Maintain factual accuracy and eliminate redundancy while preserving all critical details."
    )
    user_prompt = (
        f"Merge these {language or 'code'} summaries into a cohesive single summary:\n\n"
        f"---SUMMARY START---\n{chr(10)+'---'+chr(10).join(summaries)}\n---SUMMARY END---\n"
        "Provide a unified summary that accurately represents all components."
    )
    merged = router_agent.call_llm_by_role(
        role="summarizer",
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )
    # No validation here as we don't have the original source; rely on validated inputs
    return merged
