from typing import Any

import pytest

# Skip this module if cryptography isn't installed
pytest.importorskip("cryptography")
from cryptography.fernet import Fernet

from agent_s3.auth import TOKEN_ENCRYPTION_KEY_ENV
from agent_s3.auth import load_token
from agent_s3.auth import save_token

def test_load_token_encrypted(tmp_path, monkeypatch):
    token_data = {"access_token": "abc123"}
    key = Fernet.generate_key()
    monkeypatch.setenv(TOKEN_ENCRYPTION_KEY_ENV, key.decode())
    token_path = tmp_path / "token.json"
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))
    save_token(token_data)

    loaded = load_token()
    assert loaded == token_data


def test_save_token_requires_key(tmp_path, monkeypatch):
    token_data = {"access_token": "abc123"}
    token_path = tmp_path / "token.json"
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))
    monkeypatch.delenv(TOKEN_ENCRYPTION_KEY_ENV, raising=False)

    with pytest.raises(RuntimeError):
        save_token(token_data)
    assert not token_path.exists()


def test_load_token_missing_key(tmp_path, monkeypatch, capsys):
    token_data = {"access_token": "abc123"}
    key = Fernet.generate_key()
    token_path = tmp_path / "token.json"
    monkeypatch.setenv(TOKEN_ENCRYPTION_KEY_ENV, key.decode())
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))
    save_token(token_data)

    monkeypatch.delenv(TOKEN_ENCRYPTION_KEY_ENV, raising=False)
    assert load_token() is None
    captured = capsys.readouterr()
    assert "Encryption key not set" in captured.out


def test_save_token_encryption_failure(tmp_path, monkeypatch, capsys):
    token_data = {"access_token": "abc123"}
    key = Fernet.generate_key()
    token_path = tmp_path / "token.json"
    monkeypatch.setenv(TOKEN_ENCRYPTION_KEY_ENV, key.decode())
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))

    class BadFernet:
        def __init__(self, *a, **k):
            pass

        def encrypt(self, *_: Any) -> bytes:  # type: ignore[override]
            raise ValueError("boom Authorization: token abc123")

    monkeypatch.setattr("agent_s3.auth.Fernet", lambda *a, **k: BadFernet())
    with pytest.raises(RuntimeError):
        save_token(token_data)
    captured = capsys.readouterr()
    assert "abc123" not in captured.out
    assert "[REDACTED]" in captured.out
    assert not token_path.exists()

