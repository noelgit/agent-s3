"""
Message Protocol for Agent-S3 Communication System.

This module defines the message types and structures used for communication
between different components of the Agent-S3 system, particularly for 
workflow status broadcasting and UI communication.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional


class MessageType(Enum):
    """Enum defining the types of messages in the communication protocol."""
    
    # Workflow-related messages
    WORKFLOW_STATUS = auto()
    WORKFLOW_START = auto()
    WORKFLOW_PAUSE = auto()
    WORKFLOW_RESUME = auto()
    WORKFLOW_STOP = auto()
    WORKFLOW_COMPLETE = auto()
    WORKFLOW_ERROR = auto()
    
    # UI-related messages
    UI_UPDATE = auto()
    UI_NOTIFICATION = auto()
    UI_PROGRESS = auto()
    
    # Context-related messages
    CONTEXT_UPDATE = auto()
    CONTEXT_REFRESH = auto()
    
    # Chat-related messages
    CHAT_MESSAGE = auto()
    CHAT_STREAM_START = auto()
    CHAT_STREAM_CONTENT = auto()
    CHAT_STREAM_END = auto()
    
    # Terminal-related messages
    TERMINAL_OUTPUT = auto()
    COMMAND_RESULT = auto()
    
    # System messages
    SYSTEM_NOTIFICATION = auto()
    ERROR_NOTIFICATION = auto()
    STATUS_UPDATE = auto()


@dataclass
class Message:
    """
    Represents a message in the Agent-S3 communication protocol.
    
    This class encapsulates all the information needed to communicate
    between different components of the system.
    """
    
    type: MessageType
    content: Dict[str, Any]
    timestamp: Optional[float] = None
    message_id: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    priority: int = 1  # 1 = normal, 2 = high, 3 = critical
    
    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = time.time()
        
        if self.message_id is None:
            self.message_id = f"{self.type.name}_{int(self.timestamp * 1000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the message to a dictionary for serialization."""
        return {
            "type": self.type.name,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
            "source": self.source,
            "destination": self.destination,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Message:
        """Create a Message instance from a dictionary."""
        return cls(
            type=MessageType[data["type"]],
            content=data["content"],
            timestamp=data.get("timestamp"),
            message_id=data.get("message_id"),
            source=data.get("source"),
            destination=data.get("destination"),
            priority=data.get("priority", 1)
        )
    
    def is_urgent(self) -> bool:
        """Check if this message has high or critical priority."""
        return self.priority >= 2


class MessageBus:
    """
    Simple message bus for publishing and subscribing to messages.
    
    This provides a basic pub/sub mechanism for component communication.
    """
    
    def __init__(self):
        self._subscribers: Dict[MessageType, list] = {}
        self._message_history: list[Message] = []
        self._max_history = 1000
    
    def subscribe(self, message_type: MessageType, callback: callable) -> None:
        """Subscribe to a specific message type."""
        if message_type not in self._subscribers:
            self._subscribers[message_type] = []
        self._subscribers[message_type].append(callback)
    
    def unsubscribe(self, message_type: MessageType, callback: callable) -> None:
        """Unsubscribe from a specific message type."""
        if message_type in self._subscribers:
            try:
                self._subscribers[message_type].remove(callback)
            except ValueError:
                pass  # Callback wasn't subscribed
    
    def publish(self, message: Message) -> None:
        """Publish a message to all subscribers."""
        # Add to history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
        
        # Notify subscribers
        if message.type in self._subscribers:
            for callback in self._subscribers[message.type]:
                try:
                    callback(message)
                except Exception as e:
                    # Log error but don't stop other callbacks
                    print(f"Error in message callback: {e}")
    
    def get_history(self, message_type: Optional[MessageType] = None) -> list[Message]:
        """Get message history, optionally filtered by type."""
        if message_type is None:
            return self._message_history.copy()
        else:
            return [msg for msg in self._message_history if msg.type == message_type]


# Convenience functions for creating common message types

def create_workflow_status_message(
    status: str,
    workflow_id: str,
    can_pause: bool = False,
    can_resume: bool = False,
    can_stop: bool = False,
    current_phase: Optional[str] = None,
    message: str = "",
    **kwargs
) -> Message:
    """Create a workflow status message."""
    return Message(
        type=MessageType.WORKFLOW_STATUS,
        content={
            "status": status,
            "workflow_id": workflow_id,
            "can_pause": can_pause,
            "can_resume": can_resume,
            "can_stop": can_stop,
            "current_phase": current_phase,
            "message": message,
            **kwargs
        }
    )


def create_chat_message(
    text: str,
    source: str = "agent",
    stream_id: Optional[str] = None,
    **kwargs
) -> Message:
    """Create a chat message."""
    return Message(
        type=MessageType.CHAT_MESSAGE,
        content={
            "text": text,
            "source": source,
            "stream_id": stream_id,
            **kwargs
        }
    )


def create_terminal_output_message(
    text: str,
    **kwargs
) -> Message:
    """Create a terminal output message."""
    return Message(
        type=MessageType.TERMINAL_OUTPUT,
        content={
            "text": text,
            **kwargs
        }
    )


def create_error_notification_message(
    error: str,
    details: Optional[str] = None,
    **kwargs
) -> Message:
    """Create an error notification message."""
    return Message(
        type=MessageType.ERROR_NOTIFICATION,
        content={
            "error": error,
            "details": details,
            **kwargs
        }
    )
