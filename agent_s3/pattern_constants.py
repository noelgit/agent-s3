"""Centralized regex patterns for text matching."""
from __future__ import annotations

import re
from typing import List, Pattern

# Security-related keyword patterns
SECURITY_KEYWORDS: List[str] = [
    "auth",
    "login",
    "password",
    "credential",
    "token",
    "jwt",
    "encrypt",
    "decrypt",
    "permission",
    "role",
    "admin",
    "sensitive",
    "personal",
    "verify",
    "validate",
]

SECURITY_KEYWORD_PATTERNS: List[Pattern[str]] = [
    re.compile(keyword, re.IGNORECASE) for keyword in SECURITY_KEYWORDS
]

# Generic patterns used throughout the codebase
SECURITY_CONCERN_PATTERN: Pattern[str] = re.compile(r"security", re.IGNORECASE)
LANG_SPEC_EXTENSION_PATTERN: Pattern[str] = re.compile(r"\.")
ERROR_PATTERN: Pattern[str] = re.compile(r"error", re.IGNORECASE)
EXCEPTION_PATTERN: Pattern[str] = re.compile(r"exception", re.IGNORECASE)
START_DEPLOYMENT_PATTERN: Pattern[str] = re.compile(r"/start-deployment", re.IGNORECASE)
DEV_MODE_PATTERN: Pattern[str] = re.compile(r"dev(elopment)?", re.IGNORECASE)
DONT_RETRY_PATTERN: Pattern[str] = re.compile(r"don't retry", re.IGNORECASE)

