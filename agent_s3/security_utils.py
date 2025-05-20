"""Security-related utility functions for Agent-S3."""

import re

SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "token",
    "openai-api-key",
}


def strip_sensitive_headers(message: str) -> str:
    """Remove sensitive header values from a log or error message."""
    if not message:
        return message

    pattern = re.compile(r"(?i)(" + "|".join(map(re.escape, SENSITIVE_HEADERS)) + r")\s*:\s*[^\s\n]+")

    def _replacer(match: re.Match[str]) -> str:
        header = match.group(1)
        return f"{header}: <redacted>"

    return pattern.sub(_replacer, message)
