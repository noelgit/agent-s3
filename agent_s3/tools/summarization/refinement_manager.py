"""
SummaryRefinementManager: Manages the refinement of summaries based on validation feedback.
"""
from typing import Optional, Dict, Any
from agent_s3.tools.summarization.summary_validator import SummaryValidator

class SummaryRefinementManager:
    def __init__(self, router_agent):
        self.router_agent = router_agent
        self.validator = SummaryValidator()

    def refine_summary(self, source: str, summary: str, validation_result: Dict[str, Any],
         language: Optional[str] = None, max_attempts: int = 2) -> Dict[str, Any]:        if validation_result["passed"]:
            return {"summary": summary, "validation": validation_result, "attempts": 0}
        current_summary = summary
        current_validation = validation_result
        attempts = 0
        while not current_validation["passed"] and attempts < max_attempts:
            attempts += 1
            system_prompt = self._create_system_prompt(language)
            user_prompt = self._create_refinement_prompt(source, current_summary, current_validation, language)
            refined_summary = self.router_agent.call_llm_by_role(
                role="summarizer",
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            current_validation = self.validator.validate(source, refined_summary, language)
            current_summary = refined_summary
            if current_validation["passed"]:
                break
        return {"summary": current_summary, "validation": current_validation, "attempts": attempts}

    def _create_system_prompt(self, language: Optional[str]) -> str:
        lang_specific = f"You are summarizing {language} code. " if language else ""
        return f"You are an expert code summarizer. {lang_specific}Your task is to improve an existing summary based on feedback. Focus on accuracy, preserving important details, and maintaining the code's structural elements. Do not add information that isn't in the original code. Return only the improved summary without explanations."

    def _create_refinement_prompt(self, source: str, summary: str, validation: Dict[str, Any],
         language: Optional[str]) -> str:        issues = "\n- ".join([""] + validation["issues"])
        return f"""I need to improve this summary of the following {language or 'code'} source:

```{language or 'code'}
{source}
```
Current summary:
```
{summary}
```
The current summary has these issues:{issues}

Metrics:
- Faithfulness: {validation['metrics']['faithfulness']:.2f}
- Detail Preservation: {validation['metrics']['detail_preservation']:.2f}
- Structural Coherence: {validation['metrics']['structural_coherence']:.2f}
- Overall Quality: {validation['metrics']['overall']:.2f}

Please provide an improved summary that addresses these issues."""
