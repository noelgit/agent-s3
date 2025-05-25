"""Utilities for loading per-user Agent-S3 configuration."""
import json
import os
from typing import Any
from typing import Dict

CONFIG_PATH = os.path.expanduser("~/.agent_s3/user_config.json")


def load_user_config() -> Dict[str, Any]:
    """Load user configuration from ``~/.agent_s3/user_config.json``."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
