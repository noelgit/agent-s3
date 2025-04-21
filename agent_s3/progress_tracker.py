"""Writes live progress updates to progress_log.json and outputs status to the terminal."""

import json
import os
from datetime import datetime


class ProgressTracker:
    """Tracks progress by appending entries to progress_log.json."""

    def __init__(self, config):
        self.log_file = os.path.join(os.getcwd(), config.config['log_files']['progress'])

    def update_progress(self, entry: dict) -> None:
        """Append a progress entry with timestamp."""
        ts = datetime.utcnow().isoformat() + "Z"
        entry.setdefault('timestamp', ts)
        try:
            data = []
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    data = json.load(f) or []
            data.append(entry)
            with open(self.log_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            # In case of error, create a new log file
            with open(self.log_file, 'w') as f:
                json.dump([entry], f, indent=2)

    def get_latest_progress(self) -> dict:
        """Return the latest progress entry."""
        try:
            with open(self.log_file, 'r') as f:
                data = json.load(f) or []
            return data[-1] if data else {}
        except Exception:
            return {}
