import os
from cryptography.fernet import Fernet

from agent_s3.auth import save_token, load_token, TOKEN_ENCRYPTION_KEY_ENV, TOKEN_FILE


def test_load_token_encrypted(tmp_path, monkeypatch):
    token_data = {"access_token": "abc123"}
    key = Fernet.generate_key()
    monkeypatch.setenv(TOKEN_ENCRYPTION_KEY_ENV, key.decode())
    token_path = tmp_path / "token.json"
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))
    save_token(token_data)

    loaded = load_token()
    assert loaded == token_data


def test_load_token_missing_key(tmp_path, monkeypatch):
    token_data = {"access_token": "abc123"}
    key = Fernet.generate_key()
    token_path = tmp_path / "token.json"
    monkeypatch.setenv(TOKEN_ENCRYPTION_KEY_ENV, key.decode())
    monkeypatch.setattr("agent_s3.auth.TOKEN_FILE", str(token_path))
    save_token(token_data)

    monkeypatch.delenv(TOKEN_ENCRYPTION_KEY_ENV, raising=False)
    assert load_token() is None

