"""Security utility helpers.

This module provides password hashing and validation helpers built
around ``bcrypt``. These helpers should be used anywhere the
application needs to store or compare passwords to ensure that strong
hashing algorithms are consistently applied.
"""

from typing import Tuple
import re
import bcrypt

PATTERNS = {
    "length": r".{8,}",
    "uppercase": r"[A-Z]",
    "lowercase": r"[a-z]",
    "digit": r"\d",
    "special": r"[!@#$%^&*(),.?\":{}|<>]",
}


def hash_password(password: str) -> str:
    """Return a bcrypt hash for the given password."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    plain_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength using simple heuristic rules."""
    if not re.search(PATTERNS["length"], password):
        return False, "Password must be at least 8 characters long"
    if not re.search(PATTERNS["uppercase"], password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(PATTERNS["lowercase"], password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(PATTERNS["digit"], password):
        return False, "Password must contain at least one digit"
    if not re.search(PATTERNS["special"], password):
        return False, "Password must contain at least one special character"
    return True, "Password is valid"
