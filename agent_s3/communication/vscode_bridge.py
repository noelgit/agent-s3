"""VS Code Bridge for Agent-S3.

This module handles communication between the Agent-S3 backend and VS Code.
It supports various communication methods including WebSocket, terminal output,
and direct file manipulation.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Callable

from .message_protocol import Message, MessageType, MessageBus
from .enhanced_websocket_server import EnhancedWebSocketServer

logger = logging.getLogger(__name__)

class VSCodeBridge:
    """Bridge for communication with VS Code extension."""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        websocket_port: int = 9000,
        auth_token: Optional[str] = None
    ):
        """Initialize the VS Code bridge.
        
        Args:
            message_bus: The message bus to use for routing messages
            websocket_port: The port to use for WebSocket communication
            auth_token: Authentication token for WebSocket
        """
        # Create message bus if not provided
        self.message_bus = message_bus or MessageBus()
        
        # Initialize WebSocket server
        self.websocket_server = EnhancedWebSocketServer(
            message_bus=self.message_bus,
            port=websocket_port,
            auth_token=auth_token
        )
        
        # Create connection file
        self._create_connection_file(websocket_port, auth_token)
        
        # Start WebSocket server
        asyncio.create_task(self.websocket_server.start())
        logger.info(f"VS Code bridge initialized with WebSocket on port {websocket_port}")
        
        # Register handlers for extension communication
        self._setup_message_handlers()
    
    def _create_connection_file(self, port: int, auth_token: Optional[str]) -> None:
        """Create a connection file for the VS Code extension to use.
        
        Args:
            port: The WebSocket port
            auth_token: The authentication token
        """
        connection_info = {
            "host": "localhost",
            "port": port,
            "auth_token": auth_token or "",
            "timestamp": int(time.time())
        }
        
        # Save to a file in the workspace root
        try:
            # Try to get workspace root
            workspace_root = os.getcwd()
            connection_file = os.path.join(workspace_root, ".agent_s3_ws_connection.json")
            
            with open(connection_file, "w") as f:
                json.dump(connection_info, f)
                
            logger.info(f"Created WebSocket connection file at {connection_file}")
        except Exception as e:
            logger.error(f"Failed to create WebSocket connection file: {e}")
    
    def _setup_message_handlers(self) -> None:
        """Set up handlers for extension messages."""
        # Register handlers for user responses from the extension
        self.message_bus.register_handler(MessageType.USER_RESPONSE, self._handle_user_response)
    
    def _handle_user_response(self, message: Message) -> None:
        """Handle user response messages from the extension.
        
        Args:
            message: The message from the extension
        """
        logger.info(f"Received user response: {message.content}")
        
        # Forward to any handlers registered for this response
        # Implemented by the agent
    
    def send_terminal_output(self, text: str, category: str = "output") -> None:
        """Send terminal output to the extension.
        
        Args:
            text: The terminal output text
            category: The output category (output, error, etc.)
        """
        self.message_bus.publish(Message(
            type=MessageType.TERMINAL_OUTPUT,
            content={
                "text": text,
                "category": category
            }
        ))
    
    def send_notification(self, title: str, text: str, level: str = "info") -> None:
        """Send a notification to the extension.
        
        Args:
            title: The notification title
            text: The notification text
            level: The notification level (info, warning, error)
        """
        self.message_bus.publish(Message(
            type=MessageType.NOTIFICATION,
            content={
                "title": title,
                "text": text,
                "level": level
            }
        ))
    
    def send_diff_display(self, files: List[Dict[str, Any]], summary: str) -> None:
        """Send a diff display to the extension.
        
        Args:
            files: The files to display in the diff
            summary: A summary of the changes
        """
        self.message_bus.publish(Message(
            type=MessageType.DIFF_DISPLAY,
            content={
                "files": files,
                "summary": summary
            }
        ))
    
    def request_approval(
        self,
        title: str,
        description: str,
        options: List[Dict[str, str]],
        timeout: Optional[int] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Request approval from the user for an action.
        
        Args:
            title: The approval request title
            description: The approval request description
            options: The options to present to the user
            timeout: Optional timeout in seconds
            callback: Optional callback to call with the selected option
            
        Returns:
            The request ID
        """
        request_id = f"approval-{time.time()}"
        
        self.message_bus.publish(Message(
            type=MessageType.APPROVAL_REQUEST,
            content={
                "title": title,
                "description": description,
                "options": options,
                "request_id": request_id,
                "timeout": timeout
            }
        ))
        
        return request_id
    
    def send_streaming_update(self, content: str, source: str = "agent") -> None:
        """Send a streaming update to the extension.
        
        This is a convenience method that handles the stream start, content, and end
        in a single call for simple messages.
        
        Args:
            content: The content to send
            source: The source of the message
        """
        stream_id = self.message_bus.publish_stream_start(source)
        self.message_bus.publish_stream_content(stream_id, content)
        self.message_bus.publish_stream_end(stream_id)
    
    def start_streaming(self, source: str = "agent") -> str:
        """Start a new content stream.
        
        Args:
            source: The source of the stream
            
        Returns:
            The stream ID
        """
        return self.message_bus.publish_stream_start(source)
    
    def add_to_stream(self, stream_id: str, content: str) -> None:
        """Add content to an active stream.
        
        Args:
            stream_id: The stream ID
            content: The content to add
        """
        self.message_bus.publish_stream_content(stream_id, content)
    
    def end_stream(self, stream_id: str) -> None:
        """End an active stream.
        
        Args:
            stream_id: The stream ID to end
        """
        self.message_bus.publish_stream_end(stream_id)
    
    def show_thinking_indicator(self, source: str = "agent") -> str:
        """Show a thinking indicator in the UI.
        
        Args:
            source: The source of the thinking action
            
        Returns:
            The stream ID
        """
        return self.message_bus.publish_thinking(source)
    
    def close(self) -> None:
        """Close the VS Code bridge."""
        if self.websocket_server:
            asyncio.create_task(self.websocket_server.stop())