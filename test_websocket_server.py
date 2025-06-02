#!/usr/bin/env python3
"""Simple script to test the WebSocket server with authentication fix."""

import asyncio
import json
import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, '/Users/noelpatron/Documents/GitHub/agent-s3')

from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer
from agent_s3.communication.message_protocol import MessageBus

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_server():
    """Test the WebSocket server with authentication."""
    # Create message bus
    message_bus = MessageBus()
    
    # Create WebSocket server
    server = EnhancedWebSocketServer(
        message_bus=message_bus,
        host="localhost",
        port=8765,
        auth_token="test-token-123"
    )
    
    try:
        logger.info("Starting WebSocket server...")
        await server.start()
        logger.info("WebSocket server started successfully!")
        logger.info(f"Server running on ws://localhost:8765")
        logger.info(f"Auth token: test-token-123")
        
        # Keep the server running
        logger.info("Server is running. Press Ctrl+C to stop.")
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        await server.stop()
        logger.info("Server stopped.")
    except Exception as e:
        logger.error(f"Server error: {e}")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(test_server())
