"""Logging utilities for sanitizing sensitive information."""
import re

# Pre-compiled regex to find Authorization headers with tokens
_AUTH_HEADER_RE = re.compile(
    r'(?i)("?authorization"?\s*[:=]\s*"?(?:bearer|token)\s*)([^"\s]+)("?)'
)


def redact_auth_headers(message: str) -> str:
    """Redact Authorization header values in a log message.

    This prevents accidental exposure of secrets when logging exceptions
    that include HTTP headers.
    """
    return _AUTH_HEADER_RE.sub(lambda m: m.group(1) + "[REDACTED]" + m.group(3), message)


def strip_sensitive_headers(message: str) -> str:
    """Remove sensitive HTTP header values from a log message.

    This is primarily used when logging exceptions that may include request
    or response headers. It ensures tokens, cookies and similar credentials
    are not written to disk or stdout while still providing useful debugging
    context.

    Parameters
    ----------
    message:
        The original log message possibly containing sensitive header values.

    Returns
    -------
    str
        The sanitized message safe for logging.
    """
    from .security_utils import SENSITIVE_HEADERS

    sanitized = redact_auth_headers(message)
    for header in SENSITIVE_HEADERS:
        pattern = re.compile(fr"(?i)({header}\s*[:=]\s*)([^;\s]+)")
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized
