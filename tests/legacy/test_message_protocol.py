"""Tests for message protocol and message bus architecture."""
import unittest
from unittest.mock import MagicMock

from agent_s3.communication.message_protocol import Message
from agent_s3.communication.message_protocol import MessageBus
from agent_s3.communication.message_protocol import MessageQueue
from agent_s3.communication.message_protocol import MessageType

    Message, MessageType, MessageBus, MessageQueue
)


class TestMessage(unittest.TestCase):
    """Test the Message class."""

    def test_message_initialization(self):
        """Test message initialization with various parameters."""
        # Test with minimal arguments - disabling schema validation
        message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Hello, world!"}, schema_validation=False)
        self.assertEqual(message.type, MessageType.TERMINAL_OUTPUT)
        self.assertEqual(message.content, {"text": "Hello, world!"})
        self.assertIsNotNone(message.id)
        self.assertIsNotNone(message.timestamp)

        # Test with custom ID and timestamp - add required fields for schema
        custom_id = "test-id-123"
        custom_timestamp = "2025-01-01T12:00:00"
        message = Message(
            MessageType.APPROVAL_REQUEST,
            {"text": "Approve?", "options": ["yes", "no"], "request_id": "req-123"},
            id=custom_id,
            timestamp=custom_timestamp
        )
        self.assertEqual(message.id, custom_id)
        self.assertEqual(message.timestamp, custom_timestamp)

        # Test with string message type - disabling schema validation
        message = Message("terminal_output", {"text": "Hello, world!"}, schema_validation=False)
        self.assertEqual(message.type, MessageType.TERMINAL_OUTPUT)

    def test_to_dict(self):
        """Test message serialization to dictionary."""
        message = Message(
            MessageType.DIFF_DISPLAY,
            {
                "text": "Diff content",
                "files": [{"filename": "test.py", "content": "test content"}],
                "request_id": "diff-req-123"
            },
            id="diff-123",
            timestamp="2025-01-01T12:00:00"
        )
        message_dict = message.to_dict()

        self.assertEqual(message_dict["id"], "diff-123")
        self.assertEqual(message_dict["type"], "diff_display")
        self.assertEqual(message_dict["content"]["text"], "Diff content")
        self.assertEqual(message_dict["timestamp"], "2025-01-01T12:00:00")

    def test_from_dict(self):
        """Test message deserialization from dictionary."""
        message_dict = {
            "id": "approval-123",
            "type": "approval_request",
            "content": {"text": "Approve this?", "options": ["yes", "no"], "request_id": "req-123"},
            "timestamp": "2025-01-01T12:00:00"
        }

        message = Message.from_dict(message_dict)

        self.assertEqual(message.id, "approval-123")
        self.assertEqual(message.type, MessageType.APPROVAL_REQUEST)
        self.assertEqual(message.content["text"], "Approve this?")
        self.assertEqual(message.timestamp, "2025-01-01T12:00:00")

    def test_schema_validation(self):
        """Test message schema validation."""
        # Test valid message against schema
        valid_message = Message(
            MessageType.APPROVAL_REQUEST,
            {
                "text": "Approve this?",
                "options": ["yes", "no"],
                "request_id": "req-123"
            },
            schema_validation=True
        )
        self.assertEqual(valid_message.type, MessageType.APPROVAL_REQUEST)

        # Test invalid message against schema (missing required field)
        with self.assertRaises(ValueError):
            Message(
                MessageType.APPROVAL_REQUEST,
                {"text": "Approve this?"},  # Missing required 'options' and 'request_id'
                schema_validation=True
            )

        # Test disabling schema validation
        message = Message(
            MessageType.APPROVAL_REQUEST,
            {"text": "Approve this?"},  # Missing required fields
            schema_validation=False
        )
        self.assertEqual(message.type, MessageType.APPROVAL_REQUEST)


class TestMessageBus(unittest.TestCase):
    """Test the MessageBus class."""

    def setUp(self):
        """Set up for each test."""
        self.message_bus = MessageBus()
        self.received_messages = []

    def test_register_handler(self):
        """Test registering message handlers."""
        def handler(msg):
            self.received_messages.append(msg)

        # Register handler for terminal output
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, handler)

        # Verify handler was registered
        self.assertIn(MessageType.TERMINAL_OUTPUT.value, self.message_bus.handlers)
        self.assertEqual(len(self.message_bus.handlers[MessageType.TERMINAL_OUTPUT.value]), 1)

        # Register another handler for the same message type
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, lambda msg: None)
        self.assertEqual(len(self.message_bus.handlers[MessageType.TERMINAL_OUTPUT.value]), 2)

        # Register handler with string message type
        self.message_bus.register_handler("approval_request", handler)
        self.assertIn(MessageType.APPROVAL_REQUEST.value, self.message_bus.handlers)

    def test_unregister_handler(self):
        """Test unregistering message handlers."""
        def handler1(msg):
            self.received_messages.append(1)

        def handler2(msg):
            self.received_messages.append(2)

        # Register handlers
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, handler1)
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, handler2)

        # Verify both handlers are registered
        self.assertEqual(len(self.message_bus.handlers[MessageType.TERMINAL_OUTPUT.value]), 2)

        # Unregister first handler
        result = self.message_bus.unregister_handler(MessageType.TERMINAL_OUTPUT, handler1)
        self.assertTrue(result)
        self.assertEqual(len(self.message_bus.handlers[MessageType.TERMINAL_OUTPUT.value]), 1)

        # Attempt to unregister non-existent handler
        result = self.message_bus.unregister_handler(MessageType.TERMINAL_OUTPUT, lambda msg: None)
        self.assertFalse(result)

        # Attempt to unregister from non-existent message type
        result = self.message_bus.unregister_handler(MessageType.USER_INPUT, handler1)
        self.assertFalse(result)

    def test_publish(self):
        """Test publishing messages to the bus."""
        # Setup handlers
        terminal_handler = MagicMock()
        approval_handler = MagicMock()

        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, terminal_handler)
        self.message_bus.register_handler(MessageType.APPROVAL_REQUEST, approval_handler)

        # Publish terminal message
        terminal_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Hello"})
        result = self.message_bus.publish(terminal_message)

        self.assertTrue(result)
        terminal_handler.assert_called_once_with(terminal_message)
        approval_handler.assert_not_called()

        # Publish approval message
        approval_message = Message(MessageType.APPROVAL_REQUEST,
                                   {"text": "Approve?", "options": ["yes", "no"], "request_id": "1"})
        result = self.message_bus.publish(approval_message)

        self.assertTrue(result)
        terminal_handler.assert_called_once()  # Still only called once
        approval_handler.assert_called_once_with(approval_message)

        # Publish message with no handlers
        log_message = Message(MessageType.LOG_OUTPUT, {"text": "Log"})
        result = self.message_bus.publish(log_message)

        self.assertFalse(result)  # No handlers processed the message

    def test_client_subscription(self):
        """Test client subscription to message types."""
        # Setup client handler
        client_handler = MagicMock()

        # Subscribe client to message type
        self.message_bus.subscribe_client("client1", MessageType.TERMINAL_OUTPUT, client_handler)

        # Verify subscription
        self.assertIn(MessageType.TERMINAL_OUTPUT.value, self.message_bus.topic_subscribers)
        self.assertIn("client1", self.message_bus.topic_subscribers[MessageType.TERMINAL_OUTPUT.value])
        self.assertIn("client1", self.message_bus.client_handlers)

        # Publish message
        terminal_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Hello"})
        result = self.message_bus.publish(terminal_message)

        self.assertTrue(result)
        client_handler.assert_called_once_with(terminal_message)

        # Subscribe another client
        client2_handler = MagicMock()
        self.message_bus.subscribe_client("client2", MessageType.TERMINAL_OUTPUT, client2_handler)

        # Publish another message
        terminal_message2 = Message(MessageType.TERMINAL_OUTPUT, {"text": "World"})
        self.message_bus.publish(terminal_message2)

        client_handler.assert_called_with(terminal_message2)
        client2_handler.assert_called_once_with(terminal_message2)

    def test_client_unsubscription(self):
        """Test client unsubscription from message types."""
        # Setup client handlers
        client1_handler = MagicMock()
        client2_handler = MagicMock()

        # Subscribe clients to different message types
        self.message_bus.subscribe_client("client1", MessageType.TERMINAL_OUTPUT, client1_handler)
        self.message_bus.subscribe_client("client1", MessageType.APPROVAL_REQUEST, client1_handler)
        self.message_bus.subscribe_client("client2", MessageType.TERMINAL_OUTPUT, client2_handler)

        # Unsubscribe client1 from terminal output
        self.message_bus.unsubscribe_client("client1", MessageType.TERMINAL_OUTPUT)

        # Verify client1 is still subscribed to approval requests
        self.assertNotIn("client1", self.message_bus.topic_subscribers[MessageType.TERMINAL_OUTPUT.value])
        self.assertIn("client1", self.message_bus.topic_subscribers[MessageType.APPROVAL_REQUEST.value])
        self.assertIn("client1", self.message_bus.client_handlers)

        # Unsubscribe client1 from all
        self.message_bus.unsubscribe_client("client1")

        # Verify client1 is completely unsubscribed
        self.assertNotIn("client1", self.message_bus.topic_subscribers[MessageType.APPROVAL_REQUEST.value])
        self.assertNotIn("client1", self.message_bus.client_handlers)

        # Publish messages
        terminal_message = Message(MessageType.TERMINAL_OUTPUT, {"text": "Hello"})
        self.message_bus.publish(terminal_message)

        client1_handler.assert_not_called()
        client2_handler.assert_called_once_with(terminal_message)

    def test_metrics(self):
        """Test message bus metrics tracking."""
        # Setup handlers
        terminal_handler = MagicMock()
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, terminal_handler)

        # Initial metrics
        metrics = self.message_bus.get_metrics()
        self.assertEqual(metrics["messages_published"], 0)
        self.assertEqual(metrics["messages_handled"], 0)
        self.assertEqual(metrics["handler_errors"], 0)

        # Publish message
        self.message_bus.publish(Message(MessageType.TERMINAL_OUTPUT, {"text": "Hello"}))

        # Updated metrics
        metrics = self.message_bus.get_metrics()
        self.assertEqual(metrics["messages_published"], 1)
        self.assertEqual(metrics["messages_handled"], 1)

        # Test handler error
        terminal_handler.side_effect = Exception("Test error")
        self.message_bus.publish(Message(MessageType.TERMINAL_OUTPUT, {"text": "Error"}))

        metrics = self.message_bus.get_metrics()
        self.assertEqual(metrics["messages_published"], 2)
        self.assertEqual(metrics["handler_errors"], 1)

        # Reset metrics
        self.message_bus.reset_metrics()
        metrics = self.message_bus.get_metrics()
        self.assertEqual(metrics["messages_published"], 0)
        self.assertEqual(metrics["messages_handled"], 0)
        self.assertEqual(metrics["handler_errors"], 0)


class TestMessageQueue(unittest.TestCase):
    """Test the MessageQueue class."""

    def setUp(self):
        """Set up for each test."""
        self.message_queue = MessageQueue(max_size=5)

    def test_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations."""
        # Create test messages
        message1 = Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 1"})
        message2 = Message(MessageType.TERMINAL_OUTPUT, {"text": "Message 2"})

        # Enqueue messages
        self.message_queue.enqueue(message1)
        self.message_queue.enqueue(message2)

        # Check queue state
        self.assertEqual(self.message_queue.size(), 2)
        self.assertFalse(self.message_queue.is_empty())

        # Peek at first message
        peek_message = self.message_queue.peek()
        self.assertEqual(peek_message.content["text"], "Message 1")
        self.assertEqual(self.message_queue.size(), 2)  # Size unchanged after peek

        # Dequeue messages
        dequeue_message1 = self.message_queue.dequeue()
        self.assertEqual(dequeue_message1.content["text"], "Message 1")
        self.assertEqual(self.message_queue.size(), 1)

        dequeue_message2 = self.message_queue.dequeue()
        self.assertEqual(dequeue_message2.content["text"], "Message 2")
        self.assertEqual(self.message_queue.size(), 0)
        self.assertTrue(self.message_queue.is_empty())

        # Dequeue from empty queue
        empty_message = self.message_queue.dequeue()
        self.assertIsNone(empty_message)

    def test_max_size(self):
        """Test queue max size enforcement."""
        # Fill queue to max size
        for i in range(5):
            result = self.message_queue.enqueue(
                Message(MessageType.TERMINAL_OUTPUT, {"text": f"Message {i}"})
            )
            self.assertTrue(result)

        # Attempt to enqueue one more message
        result = self.message_queue.enqueue(
            Message(MessageType.TERMINAL_OUTPUT, {"text": "Overflow"})
        )
        self.assertFalse(result)  # Enqueue should fail
        self.assertEqual(self.message_queue.size(), 5)

    def test_metrics(self):
        """Test queue metrics tracking."""
        # Initial metrics
        metrics = self.message_queue.get_metrics()
        self.assertEqual(metrics["enqueued"], 0)
        self.assertEqual(metrics["dequeued"], 0)
        self.assertEqual(metrics["dropped"], 0)
        self.assertEqual(metrics["max_queue_length"], 0)

        # Enqueue messages
        for i in range(3):
            self.message_queue.enqueue(
                Message(MessageType.TERMINAL_OUTPUT, {"text": f"Message {i}"})
            )

        # Check metrics after enqueue
        metrics = self.message_queue.get_metrics()
        self.assertEqual(metrics["enqueued"], 3)
        self.assertEqual(metrics["max_queue_length"], 3)

        # Dequeue a message
        self.message_queue.dequeue()

        # Check metrics after dequeue
        metrics = self.message_queue.get_metrics()
        self.assertEqual(metrics["enqueued"], 3)
        self.assertEqual(metrics["dequeued"], 1)
        self.assertEqual(metrics["max_queue_length"], 3)

        # Fill queue and trigger overflow
        for i in range(4):
            self.message_queue.enqueue(
                Message(MessageType.TERMINAL_OUTPUT, {"text": f"More {i}"})
            )

        # Check metrics after overflow
        metrics = self.message_queue.get_metrics()
        self.assertEqual(metrics["dropped"], 1)

        # Clear queue
        self.message_queue.clear()
        self.assertEqual(self.message_queue.size(), 0)

        # Metrics should be preserved except max_queue_length
        metrics = self.message_queue.get_metrics()
        self.assertEqual(metrics["enqueued"], 3+3)  # Still counts total enqueued
        self.assertEqual(metrics["dequeued"], 1)    # Still counts total dequeued
        self.assertEqual(metrics["dropped"], 1)     # Still counts total dropped
        self.assertEqual(metrics["max_queue_length"], 0)  # Reset


if __name__ == "__main__":
    unittest.main()
