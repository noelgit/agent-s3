#!/usr/bin/env python3
"""Test /help command via WebSocket"""

import asyncio
import websockets
import json

async def test_help_command():
    """Test sending /help command to the Agent-S3 WebSocket server"""
    try:
        # Connect to the WebSocket server
        uri = "ws://localhost:8765"
        print(f"Connecting to {uri}...")
        
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Send authentication message
            auth_message = {
                "type": "authenticate",
                "content": {"token": "agent-s3-dev-token"}
            }
            await websocket.send(json.dumps(auth_message))
            print("Sent authentication message")
            
            # Wait for auth response
            auth_response = await websocket.recv()
            print(f"Auth response: {auth_response}")
            
            # Send /help command
            help_command = {
                "type": "command",
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": "test-help-123"
                }
            }
            await websocket.send(json.dumps(help_command))
            print("Sent /help command")
            
            # Wait for response
            response = await websocket.recv()
            print(f"Help response: {response}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_help_command())