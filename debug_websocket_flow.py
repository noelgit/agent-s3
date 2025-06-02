#!/usr/bin/env python3
"""Debug the exact WebSocket message flow"""

import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_help_command():
    """Test sending /help command and trace the response"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("Connected to WebSocket server")
            
            # First authenticate
            auth_message = {
                "type": "authentication",
                "content": {
                    "token": "agent-s3-dev-token"
                }
            }
            await websocket.send(json.dumps(auth_message))
            auth_response = await websocket.recv()
            logger.info(f"Auth response: {auth_response}")
            
            # Send help command exactly like VS Code extension does
            help_message = {
                "type": "command",
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": "test-help-debug"
                }
            }
            
            logger.info(f"Sending help command: {json.dumps(help_message)}")
            await websocket.send(json.dumps(help_message))
            
            # Wait for ALL responses
            logger.info("Waiting for ALL responses...")
            timeout = 10
            responses = []
            
            try:
                while timeout > 0:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    responses.append(response)
                    logger.info(f"Response {len(responses)}: {response}")
                    
                    # Parse and check if it's a command result
                    try:
                        parsed = json.loads(response)
                        if parsed.get("type") == "command_result":
                            logger.info("✅ FOUND COMMAND_RESULT!")
                            logger.info(f"Content: {parsed.get('content')}")
                            break
                        elif parsed.get("type") == "batch":
                            logger.info("📦 FOUND BATCH MESSAGE!")
                            for msg in parsed.get("messages", []):
                                logger.info(f"Batch item: {msg}")
                                if msg.get("type") == "command_result":
                                    logger.info("✅ FOUND COMMAND_RESULT IN BATCH!")
                                    logger.info(f"Content: {msg.get('content')}")
                    except:
                        pass
                    
                    timeout -= 1
            except asyncio.TimeoutError:
                logger.info("No more responses received")
            
            logger.info(f"Total responses received: {len(responses)}")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_help_command())