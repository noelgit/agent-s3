import pytest

from agent_s3.security_utils import strip_sensitive_headers


def test_strip_sensitive_headers_removes_tokens():
    msg = "Error: Authorization: Bearer SECRET123 X-Api-Key: key456"
    sanitized = strip_sensitive_headers(msg)
    assert "SECRET123" not in sanitized
    assert "key456" not in sanitized
    assert "Authorization: <redacted>" in sanitized
    assert "X-Api-Key: <redacted>" in sanitized

