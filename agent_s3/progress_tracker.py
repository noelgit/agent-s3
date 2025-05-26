"""Writes live progress updates to a rotating log file and broadcasts via WebSocket."""

import json
import os
import asyncio
import logging
import logging.handlers
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, ValidationError
from agent_s3.config import Config

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
    """Tracks progress by writing JSON lines to a rotating log file and via WebSocket."""

    def __init__(self, config, loop: Optional[asyncio.AbstractEventLoop] = None):
        # Use .jsonl extension for line-based JSON
        try:
            log_filename = config.config.get('log_files', {}).get('progress', 'progress_log.jsonl')
            if log_filename.endswith('.json'):
                log_filename = log_filename.replace('.json', '.jsonl')
        except (AttributeError, KeyError):
            # Default log filename if config is not properly structured
            log_filename = 'progress_log.jsonl'

        self.log_file_path = os.path.join(os.getcwd(), log_filename)
        self.websocket_server = None
        self.loop = loop # Store the event loop if provided

        # Setup rotating file logger
        self.logger = logging.getLogger('ProgressTracker')
        self.logger.setLevel(logging.INFO)
        # Prevent propagation to root logger if it has handlers
        self.logger.propagate = False

        # Remove existing handlers to avoid duplication if re-initialized
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        # Ensure log directory exists
        os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)

        # Rotate logs at 1MB, keep 3 backups
        handler = logging.handlers.RotatingFileHandler(
            self.log_file_path, maxBytes=1*1024*1024, backupCount=3, encoding='utf-8'
        )
        # Log only the message itself (which will be a JSON string)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)

        self.logger.addHandler(handler)

    def _stream_via_websocket(self, entry: "ProgressEntry") -> None:
        """Send a progress update through the configured WebSocket server."""
        if not self.websocket_server or not hasattr(self.websocket_server, "message_bus"):
            return

        if not self.loop:
            self.logger.warning(
                "WebSocket server is set but no event loop is available in ProgressTracker for streaming."
            )
            return

        try:
            entry_dict = entry.model_dump(mode="json")
            phase = entry_dict.get("phase", "unknown")
            status_enum = entry.status
            status_name = (
                status_enum.name.lower() if isinstance(status_enum, Enum) else str(status_enum).lower()
            )
            status = str(entry_dict.get("status", "unknown"))
            details = entry_dict.get("details", "")

            content = f"Phase: {phase} - Status: {status}"
            if details:
                content += f"\n{details}"

            def send_streaming_update() -> None:
                if status_name in ("started", "pending", "in_progress"):
                    self.websocket_server.message_bus.publish_thinking(
                        source=f"progress-{phase}", session_id=None
                    )

                stream_id = self.websocket_server.message_bus.publish_stream_start(
                    source=f"progress-{phase}", session_id=None
                )
                self.websocket_server.message_bus.publish_stream_content(
                    stream_id=stream_id, content=content, session_id=None
                )
                self.websocket_server.message_bus.publish_stream_end(
                    stream_id=stream_id, session_id=None
                )

            self.loop.call_soon_threadsafe(send_streaming_update)
        except Exception as e:  # pragma: no cover - best effort
            self.logger.error("Failed to stream progress update via WebSocket: %s", e)

    def set_websocket_server(
        self,
        websocket_server,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Set the WebSocket server and optionally the event loop."""

        self.websocket_server = websocket_server
        if loop:
            self.loop = loop
        elif self.websocket_server:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.logger.warning(
                    "Could not get running event loop for WebSocket."
                )
                self.loop = None


    def update_progress(self, entry_data: Dict[str, Any]) -> None:
        """Validate, log (append) a progress entry, and broadcast via WebSocket.

        Args:
            entry_data: The dictionary containing progress data.
        """
        try:
            # Validate and automatically add timestamp
            entry = ProgressEntry(**entry_data)
        except ValidationError as e:
            self.logger.error(
                "Invalid progress entry data: %s - Data: %s", e, entry_data
            )
            return # Don't log invalid entries

        # Log the validated entry as a JSON line
        try:
            log_line = entry.model_dump_json()
            self.logger.info(log_line)
        except Exception as e:
            # Log errors during the logging process itself
            self.logger.error("Failed to write progress log: %s", e)
            # Avoid crashing the application if logging fails

        # Stream via WebSocket if configured
        if self.websocket_server:
            self._stream_via_websocket(entry)

    def send_progress_indicator(
        self,
        title: str,
        percentage: float,
        steps: List[Dict[str, Any]],
        estimated_time_remaining: Optional[int] = None,
        cancelable: bool = True,
        pausable: bool = True,
        stoppable: bool = True
    ) -> None:
        """Send a progress indicator message with workflow control capabilities."""
        if not self.websocket_server or not hasattr(self.websocket_server, "message_bus"):
            return

        try:
            from .communication.message_protocol import Message, MessageType

            progress_msg = Message(
                type=MessageType.PROGRESS_INDICATOR,
                content={
                    "title": title,
                    "percentage": percentage,
                    "steps": steps,
                    "estimated_time_remaining": estimated_time_remaining,
                    "cancelable": cancelable,
                    "pausable": pausable,
                    "stoppable": stoppable
                }
            )

            self.websocket_server.message_bus.publish(progress_msg)
        except Exception as e:
            self.logger.error("Failed to send progress indicator: %s", e)


    def get_latest_progress(self) -> Dict[str, Any]:
        """Return the latest progress entry by reading the last line of the log file."""
        try:
            # Ensure the file exists before trying to open
            if not os.path.exists(self.log_file_path):
                return {}

            with open(self.log_file_path, 'rb') as f: # Open in binary mode for seeking
                # Seek to the end, then back up a bit to find the last line
                try:
                    f.seek(-2, os.SEEK_END) # Go to the second-to-last byte
                    while f.read(1) != b'\n': # Read backwards until newline
                        f.seek(-2, os.SEEK_CUR)
                        if f.tell() == 0: # Reached beginning of file
                            f.seek(0, os.SEEK_SET)
                            break
                except OSError: # Handle file smaller than buffer or empty file
                    f.seek(0, os.SEEK_SET)

                last_line = f.readline().decode('utf-8')
                if not last_line:
                    return {} # File might be empty or only contain newlines

            return json.loads(last_line) # Parse the last line as JSON
        except FileNotFoundError:
            self.logger.info("Progress log file not found: %s", self.log_file_path)
            return {}
        except json.JSONDecodeError:
            self.logger.error(
                "Failed to decode JSON from last line of %s", self.log_file_path
            )
            return {}
        except Exception as e:
            self.logger.error("Error reading latest progress: %s", e)
            return {}

    def get_all_progress(self) -> List[Dict[str, Any]]:
        """Return all progress entries by reading the log file line by line."""
        entries = []
        try:
            if not os.path.exists(self.log_file_path):
                return []
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        if line.strip(): # Avoid empty lines
                            entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        self.logger.warning(
                            "Skipping invalid JSON line in %s: %s",
                            self.log_file_path,
                            line.strip(),
                        )
            return entries
        except FileNotFoundError:
            self.logger.info("Progress log file not found: %s", self.log_file_path)
            return []
        except Exception as e:
            self.logger.error("Error reading all progress entries: %s", e)
            return [] # Return empty list on error

    def increment(self, metric: str, amount: int = 1) -> None:
        """Increment a named metric (e.g., cache hits) and log it."""
        try:
            # Log increment event
            self.logger.info("Metric increment: %s by %s", metric, amount)
        except Exception as e:
            self.logger.error("Failed to increment metric %s: %s", metric, e)

    def register_semantic_validation_phase(self) -> None:
        """
        Register the semantic validation phase in the progress tracker.

        This adds a semantic_validation phase to the tracked phases to provide visibility
        into the new validation step between planning phases.
        """
        self.logger.info(json.dumps({
            "phase": "semantic_validation",
            "status": "pending",
            "details": "Semantic validation between planning phases",
            "percentage": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }))

    def get_planning_phases(self) -> List[str]:
        """
        Get a list of all planning phases tracked by the progress tracker.

        Returns:
            List of planning phase names
        """
        return [
            "pre_planning",
            "architecture_review",
            "test_refinement",
            "test_implementation",
            "semantic_validation",  # New phase for validating consistency
            "implementation_planning",
            "code_generation"
        ]

# Create a default global progress_tracker instance

_default_config = Config()
try:
    _default_config.load()
except Exception:
    pass

progress_tracker = ProgressTracker(_default_config)
