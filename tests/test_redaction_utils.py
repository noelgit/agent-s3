from agent_s3.security_utils import redact_sensitive_headers
from agent_s3.logging_utils import redact_auth_headers
from agent_s3 import strip_sensitive_headers


def test_redact_sensitive_headers():
    headers = {
        "Authorization": "token secret",
        "Content-Type": "text/plain",
        "Cookie": "sessionid=abc",
    }
    sanitized = redact_sensitive_headers(headers)
    assert sanitized["Authorization"] == "[REDACTED]"
    assert sanitized["Cookie"] == "[REDACTED]"
    assert sanitized["Content-Type"] == "text/plain"


def test_strip_sensitive_headers():
    headers = {
        "Authorization": "token secret",
        "Content-Type": "text/plain",
        "Cookie": "sessionid=abc",
    }
    sanitized = strip_sensitive_headers(headers)
    assert "Authorization" not in sanitized
    assert "Cookie" not in sanitized
    assert sanitized["Content-Type"] == "text/plain"


def test_redact_auth_headers():
    message = '401 Unauthorized: Authorization: token abc123'
    redacted = redact_auth_headers(message)
    assert "abc123" not in redacted
    assert "[REDACTED]" in redacted
