import agent_s3


def test_redact_sensitive_headers():
    headers = {
        "Authorization": "token secret",
        "Content-Type": "application/json",
        "Cookie": "sessionid=abc",
    }
    redacted = agent_s3.redact_sensitive_headers(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Cookie"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"


def test_redact_auth_headers():
    message = 'Error: Authorization: bearer secret-token'
    sanitized = agent_s3.redact_auth_headers(message)
    assert "secret-token" not in sanitized

