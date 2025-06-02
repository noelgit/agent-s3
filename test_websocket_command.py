#!/usr/bin/env python3
"""Test WebSocket command flow to verify /help works"""

import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_help_command():
    """Test sending /help command via WebSocket"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            # First authenticate
            auth_message = {
                "type": "authentication",
                "content": {
                    "token": "test-token-123"
                }
            }
            await websocket.send(json.dumps(auth_message))
            auth_response = await websocket.recv()
            logger.info(f"Auth response: {auth_response}")
            
            # Send help command
            help_message = {
                "type": "command",
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": "test-help-123"
                }
            }
            
            logger.info(f"Sending help command: {json.dumps(help_message)}")
            await websocket.send(json.dumps(help_message))
            
            # Wait for response
            logger.info("Waiting for response...")
            response = await websocket.recv()
            logger.info(f"Received response: {response}")
            
            # Parse and analyze response
            response_data = json.loads(response)
            logger.info(f"Response type: {response_data.get('type')}")
            logger.info(f"Response content: {response_data.get('content')}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_help_command())