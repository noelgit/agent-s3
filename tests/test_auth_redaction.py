from agent_s3 import auth


def test_token_redacted_on_exception(monkeypatch, capsys):
    token = "abc123"

    def fake_get(*args, **kwargs):
        raise Exception(f"401 Unauthorized: Authorization: token {token}")

    monkeypatch.setattr(auth.requests, "get", fake_get)

    auth._validate_token_and_check_org(token, "org")
    captured = capsys.readouterr()
    assert token not in captured.out
