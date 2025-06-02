#!/usr/bin/env python3
"""Debug script to test WebSocket command handling"""

import asyncio
import json
import time
from agent_s3.coordinator import Coordinator
from agent_s3.config import Config
from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer
from agent_s3.communication.message_protocol import Message, MessageType

async def test_websocket_command():
    """Test sending a command through WebSocket"""
    
    # Create coordinator
    config = Config()
    config.config = {
        'WEBSOCKET_HOST': 'localhost',
        'WEBSOCKET_PORT': 8766,  # Use different port to avoid conflicts
        'WEBSOCKET_AUTH_TOKEN': 'test-token'
    }
    
    # Initialize coordinator (this will set up websocket server)
    coordinator = Coordinator(config, github_token=None)
    
    # Wait a moment for server to start
    await asyncio.sleep(1)
    
    # Verify coordinator reference is set
    print(f"WebSocket server coordinator reference: {coordinator.websocket_server.coordinator}")
    print(f"Coordinator has command_processor: {hasattr(coordinator, 'command_processor')}")
    
    # Test command processing directly through message bus
    command_message = Message(
        type=MessageType.COMMAND,
        content={
            "command": "/help",
            "args": "",
            "request_id": "test-123"
        }
    )
    
    print(f"Publishing command message: {command_message.to_dict()}")
    
    # Publish the message to the bus (this should trigger _handle_command)
    coordinator.websocket_server.message_bus.publish(command_message)
    
    # Wait for processing
    await asyncio.sleep(2)
    
    # Shutdown
    coordinator.websocket_server.stop_sync()

if __name__ == "__main__":
    asyncio.run(test_websocket_command())