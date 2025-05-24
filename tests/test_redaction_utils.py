from agent_s3.security_utils import redact_sensitive_headers
from agent_s3.logging_utils import redact_auth_headers


def test_redact_sensitive_headers():
    headers = {
        "Authorization": "token abc",
        "Content-Type": "application/json",
        "Cookie": "sessionid=1",
    }
    result = redact_sensitive_headers(headers)
    assert result["Authorization"] == "[REDACTED]"
    assert result["Cookie"] == "[REDACTED]"
    assert result["Content-Type"] == "application/json"


def test_redact_auth_headers():
    token = "abc123"
    msg = f"401 Unauthorized: Authorization: token {token}"
    redacted = redact_auth_headers(msg)
    assert token not in redacted
    assert "[REDACTED]" in redacted

