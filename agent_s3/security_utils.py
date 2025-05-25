"""Security-related utility functions for Agent-S3."""
from typing import Dict
from typing import MutableMapping
import re

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


PROMPT_BREAK_PATTERN = re.compile(r"```")


def sanitize_prompt_text(text: str) -> str:
    """Return text safe for inclusion in LLM prompts.

    Escapes tokens that could prematurely close code blocks or otherwise
    disrupt the prompt. Currently this function escapes triple backticks.

    Args:
        text: Raw text to sanitize.

    Returns:
        Sanitized text safe for embedding in prompts.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return PROMPT_BREAK_PATTERN.sub("\`\`\`", text)


def redact_sensitive_headers(headers: MutableMapping[str, str]) -> Dict[str, str]:
    """Return a copy of ``headers`` with sensitive values redacted.

    This is useful when logging or debugging HTTP requests and responses.
    Only non-sensitive headers retain their original values. Sensitive
    headers are replaced with the string ``"[REDACTED]"``.

    Args:
        headers: Mapping of header names to values.

    Returns:
        A new dictionary with sensitive header values redacted.
    """
    sanitized: Dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADERS:
            sanitized[name] = "[REDACTED]"
        else:
            sanitized[name] = value
    return sanitized


def strip_sensitive_headers(headers: MutableMapping[str, str]) -> Dict[str, str]:
    """Return a copy of ``headers`` with sensitive entries removed.

    Args:
        headers: Mapping of header names to values.

    Returns:
        A new dictionary containing only non-sensitive headers.
    """
    sanitized: Dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() not in SENSITIVE_HEADERS:
            sanitized[name] = value
    return sanitized
