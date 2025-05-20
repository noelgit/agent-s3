"""Unit tests for :mod:`agent_s3.security_utils`."""

import re
from agent_s3.security_utils import hash_password, verify_password, validate_password


def test_hash_and_verify_password():
    password = "Valid123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)


def test_validate_password_strong():
    valid, _ = validate_password("Valid123!")
    assert valid


def test_validate_password_weak():
    valid, reason = validate_password("weak")
    assert not valid
    assert re.search("at least 8 characters", reason)
