"""Writes live progress updates to a rotating log file."""

import json
import os
import logging
import logging.handlers
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, ValidationError


class Status(Enum):
    """Represents the status of a task."""

    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    SKIPPED = auto()


class ProgressEntry(BaseModel):
    """Pydantic model for a progress entry."""

    phase: str
    status: Status
    details: Optional[str] = None
    percentage: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Allow enum serialization
    model_config = {
        "use_enum_values": True,
    }


class ProgressTracker:
    """Tracks progress by writing JSON lines to a rotating log file."""

    def __init__(self, config, loop: Optional = None):
        # Use .jsonl extension for line-based JSON
        try:
            log_filename = config.config.get("log_files", {}).get(
                "progress", "progress_log.jsonl"
            )
            if log_filename.endswith(".json"):
                log_filename = log_filename.replace(".json", ".jsonl")
        except (AttributeError, KeyError):
            # Default log filename if config is not properly structured
            log_filename = "progress_log.jsonl"

        self.log_file_path = os.path.join(os.getcwd(), log_filename)
        self.config = config

        # Setup logger for progress tracking
        self.logger = logging.getLogger(__name__)

        # Ensure the log directory exists
        os.makedirs(os.path.dirname(self.log_file_path) or ".", exist_ok=True)

    def update_progress(self, update: Dict[str, Any]) -> bool:
        """Backwards-compatible progress update using a dictionary.

        Args:
            update: Mapping with keys such as ``phase``, ``status``, ``details``,
                ``percentage`` and ``timestamp``.

        Returns:
            bool: True if the entry was logged successfully, False otherwise.
        """
        phase = str(update.get("phase", "unknown"))
        status_val = update.get("status", Status.PENDING)
        if isinstance(status_val, str):
            try:
                status = Status[status_val.upper()]
            except KeyError:
                status = Status.IN_PROGRESS
        elif isinstance(status_val, Status):
            status = status_val
        else:
            status = Status.IN_PROGRESS

        timestamp = update.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now(timezone.utc)

        entry = ProgressEntry(
            phase=phase,
            status=status,
            details=update.get("details") or update.get("message"),
            percentage=update.get("percentage"),
            timestamp=timestamp,
        )
        return self.log_entry(entry)

    def log_entry(self, entry: ProgressEntry) -> bool:
        """Validate, log (append) a progress entry.

        Args:
            entry: The progress entry to log

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate the entry using Pydantic
            validated_entry = ProgressEntry.model_validate(entry.model_dump())

            # Convert to JSON line and append to file
            json_line = validated_entry.model_dump_json()

            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json_line + "\n")

            # Also log to standard logger
            self.logger.info(
                f"Progress: {entry.phase} - {entry.status.name} - {entry.details or ''}"
            )

            return True

        except ValidationError as e:
            self.logger.error(f"Invalid progress entry: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to log progress entry: {e}")
            return False

    def log_progress(
        self,
        phase: str,
        status: Status,
        details: Optional[str] = None,
        percentage: Optional[int] = None,
    ) -> bool:
        """Log a progress update with the given parameters.

        Args:
            phase: The current phase/step
            status: The status of the phase
            details: Optional additional details
            percentage: Optional completion percentage (0-100)

        Returns:
            bool: True if successful, False otherwise
        """
        entry = ProgressEntry(
            phase=phase, status=status, details=details, percentage=percentage
        )
        return self.log_entry(entry)

    def send_progress_message(
        self, phase: str, description: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a progress message.

        Args:
            phase: Current phase
            description: Description of progress
            metadata: Optional metadata
        """
        # Log progress message
        progress_msg = {
            "type": "progress",
            "timestamp": datetime.now().isoformat(),
            "phase": phase,
            "description": description,
            "metadata": metadata or {},
        }

        try:
            self.logger.info(f"Progress: {phase} - {description}")

            # Also write to progress log file
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(progress_msg) + "\n")

        except Exception as e:
            self.logger.error("Failed to log progress message: %s", e)

    def get_latest_progress(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read the most recent progress entries from the log file.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of progress entries as dictionaries
        """
        entries = []
        try:
            if os.path.exists(self.log_file_path):
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # Get the last 'limit' lines
                recent_lines = lines[-limit:] if len(lines) > limit else lines

                for line in recent_lines:
                    try:
                        entry = json.loads(line.strip())
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            self.logger.error(f"Failed to read progress entries: {e}")

        return entries

    def clear_log(self) -> bool:
        """Clear the progress log file.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if os.path.exists(self.log_file_path):
                os.remove(self.log_file_path)
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear progress log: {e}")
            return False
