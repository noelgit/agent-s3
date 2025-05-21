"""Summarization prompt generator utilities."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SummarizationPromptGenerator:
    """Generate consistent prompts for summarizing code units and larger content."""

    system_template: str = (
        "You are an expert software engineer summarizer. Provide concise yet"
        " accurate summaries."
    )

    def create_system_prompt(self, language: Optional[str] = None) -> str:
        """Return a system prompt for the summarizer."""
        if language:
            return f"{self.system_template} The code is written in {language}."
        return self.system_template

    def create_user_prompt(self, content: str, language: Optional[str] = None) -> str:
        """Return a user prompt instructing the model to summarize the content."""
        lang_part = f" in {language}" if language else ""
        return f"Summarize the following code{lang_part}:\n{content}"

    def get_unit_prompt(
        self, unit_type: str, unit_name: str, language: str, code: str
    ) -> str:
        """Return a prompt for summarizing a specific code unit."""
        header = f"Summarize the {language} {unit_type} `{unit_name}`."
        return f"{header}\nCode to summarize:\n{code}"
