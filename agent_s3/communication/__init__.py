"""Communication package for Agent-S3 UI Flow.

This package contains modules for communication between the Agent-S3 backend
and the VS Code extension's WebView UI.
"""

from .message_protocol import (
    Message,
    MessageType,
    MessageBus,
    MessageQueue,
    OutputCategory
)
from .terminal_parser import TerminalOutputParser

__all__ = [
    'Message',
    'MessageType',
    'MessageBus',
    'MessageQueue',
    'OutputCategory',
    'TerminalOutputParser'
]
