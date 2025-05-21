"""Core message protocol definitions used for IDE communication."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Union


class MessageType(Enum):
    """Supported message types for IDE communication."""

    TERMINAL_OUTPUT = "terminal_output"
    APPROVAL_REQUEST = "approval_request"
    DIFF_DISPLAY = "diff_display"
    LOG_OUTPUT = "log_output"
    USER_INPUT = "user_input"
    USER_RESPONSE = "user_response"
    INTERACTIVE_APPROVAL = "interactive_approval"
    INTERACTIVE_DIFF = "interactive_diff"
    DEBATE_CONTENT = "debate_content"
    PROGRESS_UPDATE = "progress_update"
    ERROR_NOTIFICATION = "error_notification"
    DEBATE_VISUALIZATION = "debate_visualization"
    PROGRESS_INDICATOR = "progress_indicator"
    CHAT_MESSAGE = "chat_message"
    CODE_SNIPPET = "code_snippet"
    FILE_TREE = "file_tree"
    TASK_BREAKDOWN = "task_breakdown"


class OutputCategory(Enum):
    """Categories for output streams."""

    STDOUT = "stdout"
    STDERR = "stderr"


@dataclass
class Message:
    """Represents a message exchanged with the IDE."""

    type: MessageType
    content: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __init__(
        self,
        message_type: Union[MessageType, str],
        content: Dict[str, Any],
        *,
        id: Optional[str] = None,
        timestamp: Optional[str] = None,
        schema_validation: bool = True,
    ) -> None:
        if isinstance(message_type, str):
            message_type = MessageType(message_type)
        self.type = message_type
        self.content = content
        self.id = id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.utcnow().isoformat()
        if schema_validation:
            self._validate()

    # Basic validation for tests
    def _validate(self) -> None:
        if self.type == MessageType.APPROVAL_REQUEST:
            required = {"text", "options", "request_id"}
            if not required.issubset(self.content):
                raise ValueError("Invalid approval request content")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(data["type"], data.get("content", {}), id=data.get("id"), timestamp=data.get("timestamp"))


class MessageBus:
    """Simple in-memory message bus for event dispatch."""

    def __init__(self) -> None:
        self.handlers: Dict[str, List[Callable[[Message], None]]] = {}
        self.topic_subscribers: Dict[str, List[str]] = {}
        self.client_handlers: Dict[str, Callable[[Message], None]] = {}
        self.metrics = {
            "messages_published": 0,
            "messages_handled": 0,
            "handler_errors": 0,
        }

    def register_handler(self, message_type: Union[MessageType, str], handler: Callable[[Message], None]) -> None:
        key = message_type.value if isinstance(message_type, MessageType) else message_type
        self.handlers.setdefault(key, []).append(handler)

    def unregister_handler(self, message_type: Union[MessageType, str], handler: Callable[[Message], None]) -> bool:
        key = message_type.value if isinstance(message_type, MessageType) else message_type
        if key not in self.handlers or handler not in self.handlers[key]:
            return False
        self.handlers[key].remove(handler)
        return True

    def publish(self, message: Message) -> bool:
        key = message.type.value
        handled = False
        if key in self.handlers:
            for handler in list(self.handlers[key]):
                try:
                    handler(message)
                    self.metrics["messages_handled"] += 1
                    handled = True
                except Exception:
                    self.metrics["handler_errors"] += 1
        self.metrics["messages_published"] += 1
        return handled

    def subscribe_client(self, client_id: str, message_type: Union[MessageType, str], handler: Callable[[Message], None]) -> None:
        key = message_type.value if isinstance(message_type, MessageType) else message_type
        self.topic_subscribers.setdefault(key, []).append(client_id)
        self.client_handlers[client_id] = handler

    def unsubscribe_client(self, client_id: str, message_type: Optional[Union[MessageType, str]] = None) -> bool:
        removed = False
        if message_type is None:
            if client_id in self.client_handlers:
                del self.client_handlers[client_id]
                removed = True
            for subscribers in self.topic_subscribers.values():
                if client_id in subscribers:
                    subscribers.remove(client_id)
                    removed = True
        else:
            key = message_type.value if isinstance(message_type, MessageType) else message_type
            if key in self.topic_subscribers and client_id in self.topic_subscribers[key]:
                self.topic_subscribers[key].remove(client_id)
                removed = True
        return removed

    def get_metrics(self) -> Dict[str, int]:
        return dict(self.metrics)

    def reset_metrics(self) -> None:
        for key in self.metrics:
            self.metrics[key] = 0


class MessageQueue:
    """FIFO queue with simple metrics."""

    def __init__(self, max_size: int = 100) -> None:
        self.queue: "Queue[Message]" = Queue()
        self.max_size = max_size
        self.metrics = {
            "enqueued": 0,
            "dequeued": 0,
            "dropped": 0,
            "max_queue_length": 0,
        }

    def enqueue(self, message: Message) -> bool:
        if self.queue.qsize() >= self.max_size:
            self.metrics["dropped"] += 1
            return False
        self.queue.put(message)
        self.metrics["enqueued"] += 1
        if self.queue.qsize() > self.metrics["max_queue_length"]:
            self.metrics["max_queue_length"] = self.queue.qsize()
        return True

    def dequeue(self) -> Optional[Message]:
        if self.queue.empty():
            return None
        self.metrics["dequeued"] += 1
        return self.queue.get()

    def peek(self) -> Optional[Message]:
        if self.queue.empty():
            return None
        # Access the underlying deque directly to avoid modifying queue state
        return self.queue.queue[0]

    def size(self) -> int:
        return self.queue.qsize()

    def is_empty(self) -> bool:
        return self.queue.empty()

    def clear(self) -> None:
        while not self.queue.empty():
            self.queue.get()
        self.metrics["max_queue_length"] = 0

    def get_metrics(self) -> Dict[str, int]:
        return dict(self.metrics)
