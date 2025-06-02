"""Message Protocol for Agent-S3 UI Flow.

This module defines the message protocol used for communication between
the Agent-S3 backend and the VS Code extension's WebView UI.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable, Set
import logging
import jsonschema
from jsonschema import validate
import asyncio

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Enumeration of message types for the message bus."""

    # General message types
    TERMINAL_OUTPUT = "terminal_output"
    APPROVAL_REQUEST = "approval_request"
    DIFF_DISPLAY = "diff_display"
    LOG_OUTPUT = "log_output"
    PROGRESS_UPDATE = "progress_update"
    USER_RESPONSE = "user_response"
    ERROR_NOTIFICATION = "error_notification"

    # Connection management
    CONNECTION_ESTABLISHED = "connection_established"
    AUTHENTICATE = "authenticate"
    AUTHENTICATION_RESULT = "authentication_result"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_RESPONSE = "heartbeat_response"
    SERVER_HEARTBEAT = "server_heartbeat"
    RECONNECT = "reconnect"
    RECONNECTION_RESULT = "reconnection_result"

    # Streaming message types
    THINKING = "thinking"
    THINKING_INDICATOR = "thinking_indicator"
    STREAM_START = "stream_start"
    STREAM_CONTENT = "stream_content"
    STREAM_END = "stream_end"
    STREAM_INTERACTIVE = "stream_interactive"

    # UI-specific messages
    NOTIFICATION = "notification"
    COMMAND = "command"
    COMMAND_RESULT = "command_result"
    USER_INPUT = "user_input"
    UI_STATE_UPDATE = "ui_state_update"

    # Enhanced message types for interactive UI
    INTERACTIVE_DIFF = "interactive_diff"
    INTERACTIVE_APPROVAL = "interactive_approval"
    PROGRESS_INDICATOR = "progress_indicator"
    PROGRESS_RESPONSE = "progress_response"
    CHAT_MESSAGE = "chat_message"
    CODE_SNIPPET = "code_snippet"
    FILE_TREE = "file_tree"
    TASK_BREAKDOWN = "task_breakdown"

    # Workflow control messages
    WORKFLOW_CONTROL = "workflow_control"
    WORKFLOW_STATUS = "workflow_status"


class OutputCategory(Enum):
    """Categories for terminal output classification."""

    GENERAL = "general"
    APPROVAL_PROMPT = "approval_prompt"
    DIFF_CONTENT = "diff_content"
    LOG_MESSAGE = "log_message"
    PROGRESS_INFO = "progress_info"
    ERROR_MESSAGE = "error_message"
    CODE_SNIPPET = "code_snippet"


# Message schemas for validation
MESSAGE_SCHEMAS = {
    MessageType.TERMINAL_OUTPUT.value: {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "category": {"type": "string"}
        }
    },
    MessageType.APPROVAL_REQUEST.value: {
        "type": "object",
        "required": ["text", "options", "request_id"],
        "properties": {
            "text": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "request_id": {"type": "string"},
            "timeout": {"type": "number"}
        }
    },
    MessageType.DIFF_DISPLAY.value: {
        "type": "object",
        "required": ["text", "files", "request_id"],
        "properties": {
            "text": {"type": "string"},
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["filename", "content"],
                    "properties": {
                        "filename": {"type": "string"},
                        "content": {"type": "string"},
                        "is_new": {"type": "boolean"}
                    }
                }
            },
            "request_id": {"type": "string"}
        }
    },
    MessageType.INTERACTIVE_DIFF.value: {
        "type": "object",
        "required": ["files", "summary", "request_id"],
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["filename", "before", "after"],
                    "properties": {
                        "filename": {"type": "string"},
                        "before": {"type": "string"},
                        "after": {"type": "string"},
                        "is_new": {"type": "boolean"},
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["line", "type"],
                                "properties": {
                                    "line": {"type": "number"},
                                    "type": {"type": "string", "enum": ["added", "removed", "modified"]},
                                    "content": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            },
            "summary": {"type": "string"},
            "stats": {
                "type": "object",
                "properties": {
                    "files_changed": {"type": "number"},
                    "insertions": {"type": "number"},
                    "deletions": {"type": "number"}
                }
            },
            "request_id": {"type": "string"}
        }
    },
    MessageType.INTERACTIVE_APPROVAL.value: {
        "type": "object",
        "required": ["title", "description", "options", "request_id"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "options": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "label"],
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "shortcut": {"type": "string"},
                        "description": {"type": "string"}
                    }
                }
            },
            "timeout": {"type": "number"},
            "request_id": {"type": "string"}
        }
    },
    MessageType.PROGRESS_INDICATOR.value: {
        "type": "object",
        "required": ["title", "percentage"],
        "properties": {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "percentage": {"type": "number"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name", "status"],
                    "properties": {
                        "name": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "failed"]},
                        "percentage": {"type": "number"},
                        "message": {"type": "string"}
                    }
                }
            },
            "estimated_time_remaining": {"type": "number"},
            "started_at": {"type": "string"},
            "cancelable": {"type": "boolean"},
            "pausable": {"type": "boolean"},
            "stoppable": {"type": "boolean"}
        }
    },
    MessageType.PROGRESS_RESPONSE.value: {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string", "enum": ["cancel", "pause", "resume", "stop"]},
            "request_id": {"type": "string"}
        }
    },
    MessageType.WORKFLOW_CONTROL.value: {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string", "enum": ["pause", "resume", "stop", "cancel"]},
            "workflow_id": {"type": "string"},
            "reason": {"type": "string"}
        }
    },
    MessageType.WORKFLOW_STATUS.value: {
        "type": "object",
        "required": ["status"],
        "properties": {
            "status": {"type": "string", "enum": ["running", "paused", "stopped", "completed", "failed"]},
            "workflow_id": {"type": "string"},
            "can_pause": {"type": "boolean"},
            "can_resume": {"type": "boolean"},
            "can_stop": {"type": "boolean"},
            "current_phase": {"type": "string"},
            "message": {"type": "string"}
        }
    },
    MessageType.STREAM_INTERACTIVE.value: {
        "type": "object",
        "required": ["stream_id", "component"],
        "properties": {
            "stream_id": {"type": "string"},
            "component": {
                "type": "object",
                "required": ["type", "id"],
                "properties": {
                    "type": {"type": "string", "enum": ["button", "input"]},
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "action": {"type": "string"},
                    "placeholder": {"type": "string"}
                }
            }
        }
    },
    MessageType.COMMAND.value: {
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {"type": "string"},
            "args": {"type": "string"},
            "request_id": {"type": "string"}
        }
    },
    MessageType.COMMAND_RESULT.value: {
        "type": "object",
        "required": ["success"],
        "properties": {
            "request_id": {"type": "string"},
            "command": {"type": "string"},
            "result": {"type": "string"},
            "success": {"type": "boolean"},
            "error": {"type": "string"}
        }
    }
}


class Message:
    """Represents a message in the message bus."""

    def __init__(
        self,
        type: Union[MessageType, str],
        content: Dict[str, Any],
        id: Optional[str] = None,
        timestamp: Optional[str] = None,
        schema_validation: bool = True
    ):
        """Initialize a new message.

        Args:
            type: The message type
            content: The message content
            id: Optional message ID (generated if not provided)
            timestamp: Optional timestamp (generated if not provided)
            schema_validation: Whether to validate against schema
        """
        self.type = type if isinstance(type, MessageType) else MessageType(type)
        self.content = content
        self.id = id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now().isoformat()

        # Validate against schema if applicable
        if schema_validation and self.type.value in MESSAGE_SCHEMAS:
            try:
                validate(instance=content, schema=MESSAGE_SCHEMAS[self.type.value])
            except jsonschema.exceptions.ValidationError as e:
                logger.error("%s", f"Message schema validation failed: {e}")
                raise ValueError(
                    f"Message schema validation failed: {e}") from e

    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary for JSON serialization.

        Returns:
            Dictionary representation of the message
        """
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], schema_validation: bool = True) -> "Message":
        """Create a message from a dictionary.

        Args:
            data: Dictionary representation of the message
            schema_validation: Whether to validate against schema

        Returns:
            New Message instance
        """
        return cls(
            type=data["type"],
            content=data["content"],
            id=data.get("id"),
            timestamp=data.get("timestamp"),
            schema_validation=schema_validation
        )

    def __str__(self) -> str:
        """String representation of the message.

        Returns:
            String representation
        """
        return f"Message(type={self.type.value}, id={self.id})"


class MessageBus:
    """Central message bus for routing messages between components."""

    def __init__(self):
        """Initialize the message bus."""
        self.handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self.topic_subscribers: Dict[str, Set[str]] = {}
        self.client_handlers: Dict[str, Callable[[Message], None]] = {}
        self.metrics: Dict[str, int] = {
            "messages_published": 0,
            "messages_handled": 0,
            "handler_errors": 0
        }

    def register_handler(
        self,
        message_type: Union[MessageType, str],
        handler_fn: Callable[[Message], None],
    ) -> None:
        """Register a handler for a specific message type."""
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        if message_type.value not in self.handlers:
            self.handlers[message_type.value] = []

        self.handlers[message_type.value].append(handler_fn)
        logger.debug(
            "%s", f"Registered handler for message type: {message_type.value}"
        )

    def unregister_handler(
        self,
        message_type: Union[MessageType, str],
        handler_fn: Callable[[Message], None],
    ) -> bool:
        """Unregister a handler for a specific message type."""
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        if message_type.value in self.handlers:
            try:
                self.handlers[message_type.value].remove(handler_fn)
                return True
            except ValueError:
                return False
        return False

    def publish(self, message: Message) -> bool:
        """Publish a message to the bus.

        Args:
            message: The message to publish

        Returns:
            True if any handlers processed the message, False otherwise
        """
        message_type = message.type.value
        self.metrics["messages_published"] += 1

        handled = False
        if message_type in self.handlers:
            for handler in self.handlers[message_type]:
                try:
                    handler(message)
                    handled = True
                    self.metrics["messages_handled"] += 1
                except Exception as e:
                    self.metrics["handler_errors"] += 1
                    logger.error("%s", f"Error in message handler: {e}")

        # Also notify topic subscribers
        if message_type in self.topic_subscribers:
            for client_id in self.topic_subscribers[message_type]:
                if client_id in self.client_handlers:
                    try:
                        self.client_handlers[client_id](message)
                        handled = True
                    except Exception as e:
                        logger.error(
                            "%s", f"Error in client handler for {client_id}: {e}"
                        )

        return handled

    def subscribe_client(
        self,
        client_id: str,
        message_type: Union[MessageType, str],
        handler_fn: Callable[[Message], None],
    ) -> None:
        """Subscribe a client to a specific message type."""
        if isinstance(message_type, str):
            message_type = MessageType(message_type)

        if message_type.value not in self.topic_subscribers:
            self.topic_subscribers[message_type.value] = set()

        self.topic_subscribers[message_type.value].add(client_id)
        self.client_handlers[client_id] = handler_fn
        logger.debug(
            "%s", f"Client {client_id} subscribed to {message_type.value}"
        )

    def unsubscribe_client(
        self,
        client_id: str,
        message_type: Optional[Union[MessageType, str]] = None,
    ) -> None:
        """Unsubscribe a client from message types."""
        if message_type is not None:
            if isinstance(message_type, str):
                message_type = MessageType(message_type)

            if message_type.value in self.topic_subscribers:
                self.topic_subscribers[message_type.value].discard(client_id)
        else:
            # Unsubscribe from all topics
            for topic in self.topic_subscribers:
                self.topic_subscribers[topic].discard(client_id)

        # Remove client handler if no more subscriptions
        has_subscriptions = False
        for topic_subscribers in self.topic_subscribers.values():
            if client_id in topic_subscribers:
                has_subscriptions = True
                break

        if not has_subscriptions and client_id in self.client_handlers:
            del self.client_handlers[client_id]
            logger.debug("%s", f"Removed client handler for {client_id}")

    def get_metrics(self) -> Dict[str, int]:
        """Get message bus metrics.

        Returns:
            Dictionary of metrics
        """
        return self.metrics.copy()

    def reset_metrics(self):
        """Reset message bus metrics."""
        for key in self.metrics:
            self.metrics[key] = 0

    def publish_thinking(self, source: str, session_id: Optional[str] = None) -> str:
        """Publish a thinking indicator message to indicate the agent is processing.

        Args:
            source: The source of the thinking action
            session_id: Optional session ID to group related messages

        Returns:
            The stream ID that can be used for subsequent streaming messages
        """
        stream_id = str(uuid.uuid4())
        message = Message(
            type=MessageType.THINKING,
            content={
                "stream_id": stream_id,
                "source": source
            },
            session_id=session_id
        )
        self.publish(message)
        return stream_id

    def publish_stream_start(self, source: str, session_id: Optional[str] = None) -> str:
        """Start a new content stream.

        Args:
            source: The source of the stream
            session_id: Optional session ID to group related messages

        Returns:
            The stream ID that can be used for subsequent streaming messages
        """
        stream_id = str(uuid.uuid4())
        message = Message(
            type=MessageType.STREAM_START,
            content={
                "stream_id": stream_id,
                "source": source
            },
            session_id=session_id
        )
        self.publish(message)
        return stream_id

    def publish_stream_content(
        self,
        stream_id: str,
        content: str,
        session_id: Optional[str] = None,
    ) -> None:
        """Publish content to an existing stream."""
        message = Message(
            type=MessageType.STREAM_CONTENT,
            content={"stream_id": stream_id, "content": content},
            session_id=session_id,
        )
        self.publish(message)

    def publish_stream_end(self, stream_id: str, session_id: Optional[str] = None) -> None:
        """End a content stream.

        Args:
            stream_id: The stream ID to close
            session_id: Optional session ID to group related messages
        """
        message = Message(
            type=MessageType.STREAM_END,
            content={
                "stream_id": stream_id
            },
            session_id=session_id
        )
        self.publish(message)

    def publish_stream_interactive(
        self,
        stream_id: str,
        component: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """Publish an interactive component for a stream."""
        message = Message(
            type=MessageType.STREAM_INTERACTIVE,
            content={"stream_id": stream_id, "component": component},
            session_id=session_id,
        )
        self.publish(message)


class MessageQueue:
    """Queue for storing and processing messages asynchronously."""

    def __init__(self, max_size: int = 1000):
        """Initialize the message queue.

        Args:
            max_size: Maximum number of messages to store in the queue
        """
        self.queue: asyncio.Queue[Message] = asyncio.Queue(maxsize=max_size)
        self.max_size = max_size
        self.metrics = {
            "enqueued": 0,
            "dequeued": 0,
            "dropped": 0,
            "max_queue_length": 0
        }

    async def put(self, message: Message) -> bool:
        """Add a message to the queue.

        Args:
            message: The message to queue

        Returns:
            True if message was queued, False if queue is full and message was dropped.
        """
        try:
            await asyncio.wait_for(self.queue.put(message), timeout=0.1)
            self.metrics["enqueued"] += 1
            current_size = self.queue.qsize()
            if current_size > self.metrics["max_queue_length"]:
                self.metrics["max_queue_length"] = current_size
            return True
        except asyncio.QueueFull:
            logger.warning("Message queue is full. Message dropped.")
            self.metrics["dropped"] += 1
            return False
        except asyncio.TimeoutError:
            logger.warning("Message queue put timed out. Message dropped.")
            self.metrics["dropped"] += 1
            return False

    async def get(self) -> Optional[Message]:
        """Remove and return the next message from the queue.

        Returns:
            The next message, or None if queue is empty (though get() will wait)
        """
        message = await self.queue.get()
        self.metrics["dequeued"] += 1
        self.queue.task_done()  # Important for asyncio.Queue
        return message

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if the queue is empty, False otherwise
        """
        return self.queue.empty()

    def size(self) -> int:
        """Get the current size of the queue.

        Returns:
            Number of messages in the queue
        """
        return self.queue.qsize()

    def get_metrics(self) -> Dict[str, int]:
        """Get queue metrics.

        Returns:
            Dictionary of metrics
        """
        # Update max_queue_length one last time before returning, in case it wasn't updated by put
        current_size = self.queue.qsize()
        if current_size > self.metrics["max_queue_length"]:
            self.metrics["max_queue_length"] = current_size
        return self.metrics.copy()

    async def clear(self):
        """Clear the queue and reset metrics."""
        # Drain the queue
        while not self.queue.empty():
            try:
                await self.queue.get()
                self.queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception:  # nosec
                pass  # Ignore errors during clear

        for key in self.metrics:
            if key not in ["dropped", "enqueued", "dequeued"]:  # Preserve historical counts
                self.metrics[key] = 0
