"""Tests for the VSCodeBridge class."""
import threading
import time
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer
from agent_s3.communication.message_protocol import Message
from agent_s3.communication.message_protocol import MessageBus
from agent_s3.communication.message_protocol import MessageType
from agent_s3.communication.vscode_bridge import VSCodeBridge
from agent_s3.communication.vscode_bridge import VSCodeBridgeConfig

class TestVSCodeBridgeConfig(unittest.TestCase):
    """Test the VSCodeBridgeConfig class."""

    def test_default_config(self):
        """Test default configuration."""
        config = VSCodeBridgeConfig()

        # Check default values
        self.assertFalse(config.enabled)
        self.assertTrue(config.prefer_ui)
        self.assertTrue(config.show_terminal_output)
        self.assertTrue(config.interactive_prompts)
        self.assertTrue(config.fallback_to_terminal)
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, 9000)
        self.assertIsNone(config.auth_token)
        self.assertEqual(config.heartbeat_interval, 15)

        # Check UI components
        self.assertTrue(config.ui_components["approval_requests"])
        self.assertTrue(config.ui_components["diff_viewer"])
        self.assertTrue(config.ui_components["progress_indicators"])
        self.assertTrue(config.ui_components["debate_visualization"])
        self.assertTrue(config.ui_components["chat_interface"])
        self.assertFalse(config.ui_components["file_explorer"])
        self.assertTrue(config.ui_components["terminal_output"])

    def test_custom_config(self):
        """Test custom configuration."""
        custom_config = {
            "enabled": True,
            "prefer_ui": False,
            "show_terminal_output": False,
            "interactive_prompts": False,
            "host": "test-host",
            "port": 8000,
            "auth_token": "test-token",
            "heartbeat_interval": 30,
            "debug_mode": True,
            "ui_components": {
                "approval_requests": False,
                "file_explorer": True
            }
        }

        config = VSCodeBridgeConfig(custom_config)

        # Check custom values
        self.assertTrue(config.enabled)
        self.assertFalse(config.prefer_ui)
        self.assertFalse(config.show_terminal_output)
        self.assertFalse(config.interactive_prompts)
        self.assertEqual(config.host, "test-host")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.auth_token, "test-token")
        self.assertEqual(config.heartbeat_interval, 30)
        self.assertTrue(config.debug_mode)

        # Check overridden UI components
        self.assertFalse(config.ui_components["approval_requests"])
        self.assertTrue(config.ui_components["file_explorer"])

        # Check unchanged UI components
        self.assertTrue(config.ui_components["diff_viewer"])  # Default preserved


class TestVSCodeBridge(unittest.TestCase):
    """Test the VSCodeBridge class."""

    def setUp(self):
        """Set up the test environment."""
        # Create test config
        self.config = VSCodeBridgeConfig({
            "enabled": True,
            "port": 9876,
            "auth_token": "test-token"
        })

        # Create message bus
        self.message_bus = MessageBus()

        # Create mock WebSocket server
        self.mock_websocket_server = MagicMock(spec=EnhancedWebSocketServer)
        self.mock_websocket_server.message_bus = self.message_bus
        self.mock_websocket_server.start_in_thread.return_value = MagicMock()

        # Create VSCodeBridge
        self.bridge = VSCodeBridge(
            config=self.config,
            message_bus=self.message_bus,
            websocket_server=self.mock_websocket_server
        )

    def test_initialization(self):
        """Test bridge initialization."""
        # Check configuration
        self.assertEqual(self.bridge.config, self.config)

        # Check message bus and WebSocket server
        self.assertEqual(self.bridge.message_bus, self.message_bus)
        self.assertEqual(self.bridge.websocket_server, self.mock_websocket_server)

        # Check initial state
        self.assertFalse(self.bridge.connection_active)
        self.assertIsNone(self.bridge.server_thread)

        # Check metrics
        self.assertEqual(self.bridge.metrics["messages_sent"], 0)
        self.assertEqual(self.bridge.metrics["messages_received"], 0)
        self.assertEqual(self.bridge.metrics["approvals_requested"], 0)

        # Check handler registration
        self.assertIn(MessageType.USER_RESPONSE.value, self.message_bus.handlers)

    def test_initialize(self):
        """Test bridge initialization method."""
        # Test successful initialization
        result = self.bridge.initialize()

        self.assertTrue(result)
        self.assertTrue(self.bridge.connection_active)
        self.assertIsNotNone(self.bridge.server_thread)
        self.mock_websocket_server.start_in_thread.assert_called_once()

        # Verify metrics updated
        self.assertEqual(self.bridge.metrics["connection_attempts"], 1)
        self.assertEqual(self.bridge.metrics["successful_connections"], 1)

        # Test with disabled config
        self.bridge.config.enabled = False
        self.bridge.connection_active = False

        result = self.bridge.initialize()
        self.assertFalse(result)
        self.assertFalse(self.bridge.connection_active)

    def test_shutdown(self):
        """Test bridge shutdown."""
        # Setup running bridge
        self.bridge.connection_active = True
        self.bridge.running = True
        self.bridge.queue_worker_thread = MagicMock()
        self.bridge.queue_worker_thread.is_alive.return_value = True

        # Shutdown
        self.bridge.shutdown()

        # Verify shutdown
        self.assertFalse(self.bridge.connection_active)
        self.assertFalse(self.bridge.running)
        self.mock_websocket_server.stop_from_main_thread.assert_called_once()

        # Test when not active
        self.mock_websocket_server.reset_mock()
        self.bridge.shutdown()
        self.mock_websocket_server.stop_from_main_thread.assert_not_called()

    def test_process_message(self):
        """Test message processing."""
        # Setup active bridge
        self.bridge.connection_active = True

        # Process a message
        test_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Test"})
        self.bridge._process_message(test_message)

        # Verify message was published
        # Extract the handler for the message type and check if it was called
        next(iter(self.message_bus.handlers[MessageType.TERMINAL_OUTPUT.value]))

        # Since the handler is a method of the bridge, we need to check the metrics
        self.assertEqual(self.bridge.metrics["messages_sent"], 1)

        # Test when not active
        self.bridge.connection_active = False

        # Reset metrics
        self.bridge.metrics["messages_sent"] = 0

        # Process a message
        self.bridge._process_message(test_message)

        # Verify message was not published
        self.assertEqual(self.bridge.metrics["messages_sent"], 0)

    def test_handle_user_response(self):
        """Test handling user responses."""
        # Setup bridge
        request_id = "test-request-id"
        self.bridge.response_events[request_id] = threading.Event()
        self.bridge.active_requests[request_id] = {
            "type": "approval",
            "timestamp": time.time(),
            "text": "Approve?",
            "options": ["yes", "no"]
        }

        # Create response message
        response_message = Message(
            MessageType.USER_RESPONSE,
            {
                "request_id": request_id,
                "response": "yes"
            }
        )

        # Handle response
        self.bridge._handle_user_response(response_message)

        # Verify response was recorded
        self.assertTrue(self.bridge.response_events[request_id].is_set())
        self.assertIn(request_id, self.bridge.response_data)
        self.assertEqual(self.bridge.metrics["approvals_granted"], 1)
        self.assertEqual(self.bridge.metrics["messages_received"], 1)

        # Test with unknown request ID
        unknown_message = Message(
            MessageType.USER_RESPONSE,
            {"request_id": "unknown-id", "response": "yes"}
        )

        # Reset metrics
        self.bridge.metrics["messages_received"] = 0

        # Handle unknown response
        self.bridge._handle_user_response(unknown_message)

        # Verify no response was recorded
        self.assertEqual(self.bridge.metrics["messages_received"], 0)

    @patch("builtins.print")
    def test_send_terminal_output(self, mock_print):
        """Test sending terminal output."""
        # Setup active bridge
        self.bridge.connection_active = True

        # Send terminal output
        test_text = "Hello, world!"
        self.bridge.send_terminal_output(test_text)

        # Verify print was called
        mock_print.assert_called_once_with(test_text)

        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)

        # Get the message from the queue
        message = self.bridge.message_queue.get()

        # Verify message properties
        self.assertEqual(message.type, MessageType.TERMINAL_OUTPUT)
        self.assertEqual(message.content["text"], test_text)

        # Test with inactive bridge
        self.bridge.connection_active = False
        mock_print.reset_mock()

        # Send terminal output
        self.bridge.send_terminal_output(test_text)

        # Verify print was still called but no message was queued
        mock_print.assert_called_once_with(test_text)
        self.assertEqual(self.bridge.message_queue.qsize(), 0)

    def test_send_approval_request(self):
        """Test sending approval requests."""
        # Setup active bridge
        self.bridge.connection_active = True

        # Send approval request
        text = "Do you approve?"
        options = ["yes", "no", "maybe"]

        wait_fn = self.bridge.send_approval_request(text, options)

        # Verify function was returned
        self.assertIsNotNone(wait_fn)

        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)

        # Get the message from the queue
        message = self.bridge.message_queue.get()

        # Verify message properties
        self.assertEqual(message.type, MessageType.INTERACTIVE_APPROVAL)
        self.assertEqual(message.content["description"], text)
        self.assertEqual(len(message.content["options"]), 3)
        self.assertEqual(message.content["options"][0]["id"], "yes")

        # Verify metrics
        self.assertEqual(self.bridge.metrics["approvals_requested"], 1)

        # Test with inactive bridge
        self.bridge.connection_active = False

        # Send approval request
        wait_fn = self.bridge.send_approval_request(text, options)

        # Verify no function was returned
        self.assertIsNone(wait_fn)

    def test_send_diff_display(self):
        """Test sending diff displays."""
        # Setup active bridge
        self.bridge.connection_active = True

        # Send diff display
        text = "diff --git a/file.txt b/file.txt"
        files = [{"filename": "file.txt", "content": text, "is_new": False}]

        wait_fn = self.bridge.send_diff_display(text, files)

        # Verify function was returned
        self.assertIsNotNone(wait_fn)

        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)

        # Get the message from the queue
        message = self.bridge.message_queue.get()

        # Verify message properties
        self.assertEqual(message.type, MessageType.DIFF_DISPLAY)
        self.assertEqual(message.content["text"], text)
        self.assertEqual(message.content["files"], files)

        # Test with enhanced diff (before/after content)
        enhanced_files = [{
            "filename": "file.txt",
            "before": "old content",
            "after": "new content",
            "is_new": False
        }]

        wait_fn = self.bridge.send_diff_display(text, enhanced_files, interactive=True)

        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)

        # Get the message from the queue
        message = self.bridge.message_queue.get()

        # Verify message properties
        self.assertEqual(message.type, MessageType.INTERACTIVE_DIFF)
        self.assertEqual(message.content["files"][0]["before"], "old content")
        self.assertEqual(message.content["files"][0]["after"], "new content")

        # Test with inactive bridge
        self.bridge.connection_active = False

        # Send diff display
        wait_fn = self.bridge.send_diff_display(text, files)

        # Verify no function was returned
        self.assertIsNone(wait_fn)

    def test_extract_before_after(self):
        """Test extracting before/after content from diff."""
        # Test new file
        new_file_diff = """diff --git a/new_file.txt b/new_file.txt
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/new_file.txt
@@ -0,0 +1,3 @@
+Line 1
+Line 2
+Line 3"""

        before, after = self.bridge._extract_before_after(new_file_diff)

        self.assertEqual(before, "")
        self.assertEqual(after, "Line 1\nLine 2\nLine 3")

        # Test modified file
        modified_file_diff = """diff --git a/file.txt b/file.txt
index abcdef..1234567 100644
--- a/file.txt
+++ b/file.txt
@@ -1,3 +1,4 @@
 Line 1
-Line 2
+Line 2 modified
+Line 3 added
 Line 4"""

        before, after = self.bridge._extract_before_after(modified_file_diff)

        self.assertEqual(before, "Line 1\nLine 2\nLine 4")
        self.assertEqual(after, "Line 1\nLine 2 modified\nLine 3 added\nLine 4")

    def test_compute_diff_stats(self):
        """Test computing diff statistics."""
        files = [
            {
                "filename": "file1.txt",
                "before": "Line 1\nLine 2\nLine 3",
                "after": "Line 1\nLine 2 modified\nLine 3\nLine 4",
                "is_new": False
            },
            {
                "filename": "file2.txt",
                "before": "",
                "after": "Line 1\nLine 2",
                "is_new": True
            }
        ]

        stats = self.bridge._compute_diff_stats(files)

        self.assertEqual(stats["files_changed"], 2)
        self.assertTrue(stats["insertions"] >= 3)  # At least 3 insertions
        self.assertTrue(stats["deletions"] >= 1)   # At least 1 deletion

    def test_get_metrics(self):
        """Test getting bridge metrics."""
        # Setup metrics
        self.bridge.metrics = {
            "messages_sent": 10,
            "messages_received": 5,
            "errors": 2,
            "approvals_requested": 3,
            "approvals_granted": 2,
            "approvals_denied": 1,
            "connection_attempts": 1,
            "successful_connections": 1,
            "reconnects": 0
        }

        # Get metrics
        metrics = self.bridge.get_metrics()

        # Verify metrics
        self.assertEqual(metrics["messages_sent"], 10)
        self.assertEqual(metrics["messages_received"], 5)
        self.assertEqual(metrics["errors"], 2)
        self.assertEqual(metrics["approvals_requested"], 3)
        self.assertEqual(metrics["approvals_granted"], 2)
        self.assertEqual(metrics["approvals_denied"], 1)

        # Test with message bus metrics
        self.message_bus.get_metrics = MagicMock(return_value={
            "messages_published": 15,
            "messages_handled": 12,
            "handler_errors": 1
        })

        # Get combined metrics
        metrics = self.bridge.get_metrics()

        # Verify combined metrics
        self.assertEqual(metrics["messages_sent"], 10)
        self.assertEqual(metrics["message_bus_messages_published"], 15)
        self.assertEqual(metrics["message_bus_messages_handled"], 12)
        self.assertEqual(metrics["message_bus_handler_errors"], 1)

    def test_reset_metrics(self):
        """Test resetting bridge metrics."""
        # Setup metrics
        self.bridge.metrics = {
            "messages_sent": 10,
            "messages_received": 5,
            "errors": 2,
            "approvals_requested": 3,
            "approvals_granted": 2,
            "approvals_denied": 1,
            "connection_attempts": 1,
            "successful_connections": 1,
            "reconnects": 0
        }

        # Mock message bus reset method
        self.message_bus.reset_metrics = MagicMock()

        # Reset metrics
        self.bridge.reset_metrics()

        # Verify metrics reset
        self.assertEqual(self.bridge.metrics["messages_sent"], 0)
        self.assertEqual(self.bridge.metrics["messages_received"], 0)
        self.assertEqual(self.bridge.metrics["errors"], 0)
        self.assertEqual(self.bridge.metrics["approvals_requested"], 0)
        self.assertEqual(self.bridge.metrics["approvals_granted"], 0)
        self.assertEqual(self.bridge.metrics["approvals_denied"], 0)

        # Connection metrics should be preserved
        self.assertEqual(self.bridge.metrics["connection_attempts"], 1)
        self.assertEqual(self.bridge.metrics["successful_connections"], 1)
        self.assertEqual(self.bridge.metrics["reconnects"], 0)

        # Verify message bus metrics were reset
        self.message_bus.reset_metrics.assert_called_once()


if __name__ == "__main__":
    unittest.main()
