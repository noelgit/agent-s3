import os
import tempfile
import unittest
from unittest.mock import MagicMock

from agent_s3.config import Config
from agent_s3.progress_tracker import ProgressTracker
from agent_s3.progress_tracker import Status

class TestProgressTrackerWebSocket(unittest.TestCase):
    """Tests for progress streaming via WebSocket."""

    def test_in_progress_triggers_thinking(self):
        """Phases with status IN_PROGRESS should emit thinking indicators."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            original_cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                tracker = ProgressTracker(Config())
                message_bus = MagicMock()
                websocket_server = MagicMock(message_bus=message_bus)
                tracker.set_websocket_server(websocket_server, loop=MagicMock())
                # Immediately execute scheduled callbacks
                tracker.loop.call_soon_threadsafe = lambda fn: fn()

                tracker.update_progress({
                    "phase": "demo",
                    "status": Status.IN_PROGRESS,
                    "details": "processing"
                })

                message_bus.publish_thinking.assert_called_once_with(
                    source="progress-demo",
                    session_id=None
                )
                message_bus.publish_stream_start.assert_called_once()
                message_bus.publish_stream_content.assert_called_once()
                message_bus.publish_stream_end.assert_called_once()
            finally:
                os.chdir(original_cwd)
