"""Tests for the enhanced WebSocket server implementation."""

import unittest
import asyncio
import json
import tempfile
import os
import time
from unittest.mock import MagicMock, patch, AsyncMock, call

from agent_s3.communication.message_protocol import Message, MessageType, MessageBus
from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer


class TestEnhancedWebSocketServer(unittest.TestCase):
    """Test suite for the EnhancedWebSocketServer class."""

    def setUp(self):
        """Set up the test environment."""
        self.message_bus = MessageBus()
        self.test_port = 9876  # Use a different port from the default

        # Create a temporary directory for connection file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)

        # Create server with mock event loop for testing
        self.server = EnhancedWebSocketServer(
            message_bus=self.message_bus,
            host="localhost",
            port=self.test_port,
            auth_token="test-token",
            heartbeat_interval=1  # Shorter interval for testing
        )

    def tearDown(self):
        """Clean up the test environment."""
        # Restore original working directory
        os.chdir(self.original_cwd)
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test server initialization."""
        # Check basic properties
        self.assertEqual(self.server.host, "localhost")
        self.assertEqual(self.server.port, self.test_port)
        self.assertEqual(self.server.auth_token, "test-token")
        self.assertEqual(self.server.heartbeat_interval, 1)

        # Check message bus and queue
        self.assertIs(self.server.message_bus, self.message_bus)
        self.assertIsNotNone(self.server.message_queue)

        # Check initial state
        self.assertFalse(self.server.running)
        self.assertEqual(len(self.server.clients), 0)
        self.assertEqual(len(self.server.authenticated_clients), 0)

        # Check handlers are registered
        message_types = [
            MessageType.TERMINAL_OUTPUT,
            MessageType.APPROVAL_REQUEST,
            MessageType.DIFF_DISPLAY,
            MessageType.LOG_OUTPUT,
            MessageType.DEBATE_CONTENT,
            MessageType.PROGRESS_UPDATE,
            MessageType.ERROR_NOTIFICATION,
            MessageType.INTERACTIVE_DIFF,
            MessageType.INTERACTIVE_APPROVAL,
            MessageType.DEBATE_VISUALIZATION,
            MessageType.PROGRESS_INDICATOR,
            MessageType.CHAT_MESSAGE,
            MessageType.CODE_SNIPPET,
            MessageType.FILE_TREE,
            MessageType.TASK_BREAKDOWN
        ]

        for message_type in message_types:
            self.assertIn(message_type.value, self.message_bus.handlers)

    @patch("websockets.serve", new_callable=AsyncMock)
    @patch("asyncio.create_task")
    async def test_start(self, mock_create_task, mock_serve):
        """Test starting the WebSocket server."""
        # Mock the socket object to simulate port assignment
        mock_socket = MagicMock()
        mock_socket.family = socket.AF_INET
        mock_socket.getsockname.return_value = ("localhost", self.test_port)

        # Mock the server's sockets attribute
        mock_server = MagicMock()
        mock_server.sockets = [mock_socket]
        mock_serve.return_value = mock_server

        # Start server
        await self.server.start()

        # Check server is running
        self.assertTrue(self.server.running)

        # Check connection file was created
        self.assertTrue(os.path.exists(self.server.connection_file))

        # Read connection file
        with open(self.server.connection_file, "r") as f:
            connection_info = json.load(f)

        self.assertEqual(connection_info["host"], "localhost")
        self.assertEqual(connection_info["port"], self.test_port)
        self.assertEqual(connection_info["auth_token"], "test-token")
        self.assertEqual(connection_info["protocol"], "ws")

        # Check tasks were created
        expected_task_count = 4  # heartbeat, queue processor, expiry cleaner, metrics logger
        self.assertEqual(mock_create_task.call_count, expected_task_count)

        mock_serve.assert_awaited_once_with(
            self.server._handle_client,
            self.server.host,
            self.server.port,
            ping_interval=self.server.heartbeat_interval,
            ping_timeout=self.server.heartbeat_interval * 2,
            max_size=self.server.max_message_size,
        )

    @patch("asyncio.gather", new_callable=AsyncMock)
    async def test_stop(self, mock_gather):
        """Test stopping the WebSocket server."""
        # Setup running server
        self.server.running = True
        self.server.server = MagicMock()
        self.server.server.close = MagicMock()
        self.server.server.wait_closed = AsyncMock()

        # Create mock tasks
        self.server.heartbeat_task = AsyncMock()
        self.server.heartbeat_task.cancel = MagicMock()
        self.server.queue_processor_task = AsyncMock()
        self.server.queue_processor_task.cancel = MagicMock()
        self.server.expiry_cleaner_task = AsyncMock()
        self.server.expiry_cleaner_task.cancel = MagicMock()
        self.server.metrics_logger_task = AsyncMock()
        self.server.metrics_logger_task.cancel = MagicMock()

        # Create mock clients
        client1 = MagicMock()
        client1.close = AsyncMock()
        client2 = MagicMock()
        client2.close = AsyncMock()
        self.server.clients = {"client1": client1, "client2": client2}

        # Create connection file for testing removal
        with open(self.server.connection_file, "w") as f:
            f.write("{}")

        # Stop server
        await self.server.stop()

        # Check server is stopped
        self.assertFalse(self.server.running)

        # Check tasks were cancelled
        self.server.heartbeat_task.cancel.assert_called_once()
        self.server.queue_processor_task.cancel.assert_called_once()
        self.server.expiry_cleaner_task.cancel.assert_called_once()
        self.server.metrics_logger_task.cancel.assert_called_once()

        # Check client connections were closed
        mock_gather.assert_called_once()

        # Check server was closed
        self.server.server.close.assert_called_once()
        self.server.server.wait_closed.assert_awaited_once()

        # Check connection file was removed
        self.assertFalse(os.path.exists(self.server.connection_file))

    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        # Initialize client counter
        client_id = "test-client"
        self.server.client_message_counters[client_id] = {
            "count": 0,
            "last_reset": time.time() - 2,  # 2 seconds ago
            "batch": []
        }

        # First check should reset counter due to elapsed time
        self.assertTrue(self.server._check_rate_limit(client_id))
        self.assertEqual(self.server.client_message_counters[client_id]["count"], 1)

        # Make requests up to the limit
        for _ in range(self.server.rate_limits["messages_per_second"] - 1):
            self.assertTrue(self.server._check_rate_limit(client_id))

        # One more request should hit the limit
        self.assertFalse(self.server._check_rate_limit(client_id))

    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("json.dumps")
    async def test_message_batching(self, mock_dumps, mock_sleep):
        """Test message batching."""
        # Setup client and counter
        client_id = "test-client"
        mock_client = MagicMock()
        mock_client.send = AsyncMock()
        self.server.clients = {client_id: mock_client}

        self.server.client_message_counters[client_id] = {
            "count": 0,
            "last_reset": time.time(),
            "batch": []
        }

        # Create test messages
        message1 = Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 1"})
        message2 = Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 2"})

        # Send first message
        await self.server.send_message(client_id, message1)

        # Check message was added to batch
        self.assertEqual(len(self.server.client_message_counters[client_id]["batch"]), 1)

        # Send second message without triggering batch send
        await self.server.send_message(client_id, message2)

        # Check both messages in batch
        self.assertEqual(len(self.server.client_message_counters[client_id]["batch"]), 2)

        # Manually trigger batch send
        mock_dumps.return_value = "{}"  # Mock JSON serialization
        await self.server._send_batch(client_id)

        # Check batch was sent and cleared
        mock_client.send.assert_called_once()
        self.assertEqual(len(self.server.client_message_counters[client_id]["batch"]), 0)

        # Verify batch format in the send call
        args, _ = mock_dumps.call_args
        batch_data = args[0]
        self.assertEqual(batch_data["type"], "batch")
        self.assertEqual(len(batch_data["messages"]), 2)

    @patch("agent_s3.communication.enhanced_websocket_server.logger.error")
    async def test_client_message_handling(self, mock_logger_error):
        """Test client message handling code paths."""
        # Setup mocks
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()

        # First test authentication
        mock_websocket.recv = AsyncMock(return_value=json.dumps({
            "type": "authenticate",
            "content": {"token": "test-token"}
        }))

        # Create a connection handler task
        handler_task = asyncio.create_task(
            self.server._handle_client(mock_websocket, "/")
        )

        # Wait a short time for the connection setup
        await asyncio.sleep(0.1)

        # Cancel the task since we're not actually running a WebSocket server
        handler_task.cancel()

        # There should be one client in authenticated_clients
        self.assertEqual(len(self.server.authenticated_clients), 1)

        # Check connection established message was sent
        mock_websocket.send.assert_called()

        # Extract the message to validate it
        send_args, _ = mock_websocket.send.call_args_list[0]
        connection_message = json.loads(send_args[0])
        self.assertEqual(connection_message["type"], "connection_established")

        # Reset mocks for testing error handling
        mock_websocket.reset_mock()
        mock_websocket.recv.side_effect = json.JSONDecodeError("Invalid JSON", "{", 0)

        # Create a connection handler task for error testing
        handler_task = asyncio.create_task(
            self.server._handle_client(mock_websocket, "/")
        )

        # Wait a short time for the error to be processed
        await asyncio.sleep(0.1)

        # Cancel the task
        handler_task.cancel()

        # Error should have been logged
        mock_logger_error.assert_called()

        # Error message should have been sent
        mock_websocket.send.assert_called()
        send_args, _ = mock_websocket.send.call_args
        error_message = json.loads(send_args[0])
        self.assertEqual(error_message["type"], "error_notification")

    @patch("agent_s3.communication.enhanced_websocket_server.logger.error")
    async def test_oversized_message_rejected(self, mock_logger_error):
        """Messages over the size limit should be rejected."""
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()

        # Authentication handshake
        mock_websocket.recv = AsyncMock(return_value=json.dumps({
            "type": "authenticate",
            "content": {"token": "test-token"}
        }))

        async def message_gen():
            yield "x" * (self.server.max_message_size + 1)

        mock_websocket.__aiter__.return_value = message_gen()

        handler_task = asyncio.create_task(
            self.server._handle_client(mock_websocket, "/")
        )

        await asyncio.sleep(0.1)
        handler_task.cancel()

        mock_websocket.send.assert_called()
        send_args, _ = mock_websocket.send.call_args_list[-1]
        sent_msg = json.loads(send_args[0])
        self.assertEqual(sent_msg["type"], "error_notification")

    @patch("agent_s3.communication.enhanced_websocket_server.logger.error")
    async def test_custom_limit_oversized_message_rejected(self, mock_logger_error):
        """Custom max_message_size should reject larger messages."""
        small_server = EnhancedWebSocketServer(
            message_bus=self.message_bus,
            host="localhost",
            port=self.test_port,
            auth_token="test-token",
            heartbeat_interval=1,
            max_message_size=10,
        )

        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()

        mock_websocket.recv = AsyncMock(
            return_value=json.dumps({"type": "authenticate", "content": {"token": "test-token"}})
        )

        async def message_gen():
            yield "x" * 11

        mock_websocket.__aiter__.return_value = message_gen()

        handler_task = asyncio.create_task(
            small_server._handle_client(mock_websocket, "/")
        )

        await asyncio.sleep(0.1)
        handler_task.cancel()

        mock_websocket.send.assert_called()
        send_args, _ = mock_websocket.send.call_args_list[-1]
        sent_msg = json.loads(send_args[0])
        self.assertEqual(sent_msg["type"], "error_notification")

    @patch("asyncio.create_task")
    async def test_message_handlers(self, mock_create_task):
        """Test message handlers broadcast messages correctly."""
        # Test each handler
        test_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Test"})

        self.server._handle_terminal_output(test_message)
        mock_create_task.assert_called_with(self.server.broadcast_message(test_message))

        mock_create_task.reset_mock()
        test_message = Message(MessageType.APPROVAL_REQUEST,
                               {"text": "Approve?", "options": ["yes", "no"], "request_id": "1"})
        self.server._handle_approval_request(test_message)
        mock_create_task.assert_called_with(self.server.broadcast_message(test_message))

        # Test one of the new enhanced handlers
        mock_create_task.reset_mock()
        test_message = Message(MessageType.INTERACTIVE_DIFF,
                               {"files": [], "summary": "Test diff", "request_id": "1"})
        self.server._handle_interactive_diff(test_message)
        mock_create_task.assert_called_with(self.server.broadcast_message(test_message))

    @patch("asyncio.create_task")
    async def test_queue_message_for_disconnected_client(self, mock_create_task):
        """Test queuing messages for disconnected clients."""
        client_id = "disconnected-client"
        self.server.authenticated_clients.add(client_id)

        # Queue message for the client
        test_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Test"})
        queued = await self.server._queue_message(client_id, test_message)

        self.assertTrue(queued)
        self.assertIn(client_id, self.server.client_queues)
        self.assertEqual(len(self.server.client_queues[client_id]), 1)
        self.assertEqual(self.server.client_queues[client_id][0], test_message)

        # Queue too many messages
        for i in range(self.server.max_queue_size):
            message = Message(MessageType.TERMINAL_OUTPUT, {"text": f"Test {i}"})
            await self.server._queue_message(client_id, message)

        # Next message should fail
        overflow_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Overflow"})
        queued = await self.server._queue_message(client_id, overflow_message)
        self.assertFalse(queued)

    async def test_send_queued_messages(self):
        """Test sending queued messages to a reconnected client."""
        old_id = "old-client"
        new_id = "new-client"

        # Setup mock client
        mock_client = MagicMock()
        mock_client.send = AsyncMock()
        self.server.clients = {new_id: mock_client}

        # Queue messages for the old client
        queued_messages = [
            Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 1"}),
            Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 2"})
        ]
        self.server.client_queues[old_id] = queued_messages.copy()

        # Send queued messages
        with patch.object(self.server, "send_message", AsyncMock(return_value=True)) as mock_send:
            count = await self.server._send_queued_messages(old_id, new_id)

            self.assertEqual(count, 2)
            self.assertEqual(mock_send.call_count, 2)
            mock_send.assert_has_calls([
                call(new_id, queued_messages[0]),
                call(new_id, queued_messages[1])
            ])
            self.assertEqual(len(self.server.client_queues[old_id]), 0)


if __name__ == "__main__":
    # Import socket module for patching
    import socket
    unittest.main()
