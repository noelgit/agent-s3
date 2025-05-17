"""
SummaryRefiner: Refines summaries that fail validation, using feedback from validation metrics.
"""
import time

class SummaryRefiner:
    def __init__(self, validator, prompt_factory, config):
        self.validator = validator
        self.prompt_factory = prompt_factory
        self.config = config

    def refine(self, source, summary, language, task="summarize"):
        attempts = 0
        last_summary = summary
        while attempts < self.config.max_refinement_attempts:
            passed, metrics = self.validator.validate(source, last_summary, language)
            if passed:
                return last_summary, metrics
            # Generate refinement instructions
            feedback = self._generate_feedback(metrics)
            prompt = self.prompt_factory.get_prompt(language, source, task) + f"\n\nRefinement instructions: {feedback}"
            # Here, call the LLM with the new prompt (stubbed)
            last_summary = self._call_llm(prompt)
            attempts += 1
            time.sleep(2 ** attempts)  # Exponential backoff
        return last_summary, metrics

    def _generate_feedback(self, metrics):
        feedback = []
        if metrics.get('faithfulness', 1.0) < self.config.faithfulness_threshold:
            feedback.append("Increase faithfulness to the source.")
        if metrics.get('detail_preservation', 1.0) < self.config.detail_preservation_threshold:
            feedback.append("Preserve more key details from the source.")
        if metrics.get('structural_coherence', 1.0) < self.config.structural_coherence_threshold:
            feedback.append("Improve structural coherence.")
        return " ".join(feedback)

    def _call_llm(self, prompt):
        # TODO: Integrate with LLM API
        return "[Refined summary based on feedback]"
