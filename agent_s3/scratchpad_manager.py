"""Manages logging of detailed internal chain-of-thought to scratchpad.txt."""

import os
from datetime import datetime
from typing import Optional

from agent_s3.config import Config


class ScratchpadManager:
    """Manages the scratchpad log file for Agent-S3."""

    def __init__(self, config: Config):
        """Initialize the scratchpad manager.
        
        Args:
            config: The loaded configuration
        """
        self.config = config
        self.log_file = os.path.join(os.getcwd(), config.config['log_files']['scratchpad'])

    def log(self, role: str, message: str) -> None:
        """Append a log entry to scratchpad.txt."""
        ts = datetime.utcnow().isoformat() + "Z"
        entry = f"[{role} • {ts}] {message}\n"
        # Rotate if log file exceeds 1MB
        if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > 1_000_000:
            os.rename(self.log_file, self.log_file + ".1")
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
