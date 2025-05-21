"""Utilities for generating summarization prompts.

This module provides language-specific prompt templates for summarizing code
units. It is intentionally lightweight for the unit tests in this repository.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SummarizationPromptGenerator:
    """Generate prompts for summarizing code units."""

    template: str = (
        "Summarize the following {language} {unit_type} named {unit_name}. "
        "The summary should be concise and capture the intent of the code.\n"
        "Code to summarize:\n{code}"
    )

    def get_unit_prompt(self, unit_type: str, unit_name: str, language: str, code: str) -> str:
        """Return a prompt for summarizing a code unit.

        Args:
            unit_type: The type of code unit (e.g. ``function`` or ``class``).
            unit_name: The name of the unit.
            language: Programming language of the code.
            code: The code snippet to summarize.
        """
        return self.template.format(
            unit_type=unit_type,
            unit_name=unit_name,
            language=language,
            code=code,
        )
