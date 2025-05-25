"""
SummaryRefiner: Refines summaries that fail validation, using feedback from validation metrics.
"""
import time

class SummaryRefiner:
    def __init__(self, validator, prompt_factory, config, router_agent):
        self.validator = validator
        self.prompt_factory = prompt_factory
        self.config = config
        self.router_agent = router_agent

    def refine(self, source, summary, language, task="summarize"):
        attempts = 0
        last_summary = summary
        while attempts < self.config.max_refinement_attempts:
            validation = self.validator.validate(source, last_summary, language)
            if validation["passed"]:
                return last_summary, validation["metrics"]
            # Generate refinement instructions
            feedback = self._generate_feedback(validation["metrics"])
            prompt = self.prompt_factory.get_prompt(language, source, task) + f"\n\nRefinement instructions: {feedback}"
            # Here, call the LLM with the new prompt (stubbed)
            last_summary = self._call_llm(prompt)
            attempts += 1
            time.sleep(2 ** attempts)  # Exponential backoff
        return last_summary, validation.get("metrics", {})

    def _generate_feedback(self, metrics):
        feedback = []
        if metrics.get('faithfulness', 1.0) < self.config.faithfulness_threshold:
            feedback.append("Increase faithfulness to the source.")
        if metrics.get('detail_preservation', 1.0) < self.config.detail_preservation_threshold:
            feedback.append("Preserve more key details from the source.")
        if metrics.get('structural_coherence', 1.0) < self.config.structural_coherence_threshold:
            feedback.append("Improve structural coherence.")
        return " ".join(feedback)

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM via ``router_agent`` and return the response.

        Parameters
        ----------
        prompt : str
            The user prompt containing the source code and refinement
            instructions.

        Returns
        -------
        str
            The LLM generated summary or an empty string if the call fails.
        """
        try:
            response = self.router_agent.call_llm_by_role(
                role="summarizer",
                system_prompt=(
                    "You refine code summaries based on validation feedback. "
                    "Return only the improved summary."
                ),
                user_prompt=prompt,
            )
            return response or ""
        except Exception:
            # In case of API failure, return empty string to allow retry logic
            return ""
