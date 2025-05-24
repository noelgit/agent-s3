"""Logging utilities for sanitizing sensitive information."""
import re

# Pre-compiled regex to find Authorization headers with tokens
_AUTH_HEADER_RE = re.compile(
    r'(?i)("?authorization"?\s*[:=]\s*"?(?:bearer|token)\s*)([^"\s]+)("?)'
)


def strip_sensitive_headers(message: str) -> str:
    """Redact Authorization header values in a log message.

    This prevents accidental exposure of secrets when logging exceptions
    that include HTTP headers.
    """
    return _AUTH_HEADER_RE.sub(lambda m: m.group(1) + "[REDACTED]" + m.group(3), message)
