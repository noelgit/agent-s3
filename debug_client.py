#!/usr/bin/env python3
"""Debug client to see exact WebSocket responses."""

import asyncio
import json
import websockets
import uuid

async def debug_test():
    """Test command processing and show all responses."""
    uri = "ws://localhost:8765"
    
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Receive connection acknowledgment
            ack_message = await websocket.recv()
            ack_data = json.loads(ack_message)
            print(f"Received acknowledgment: {json.dumps(ack_data, indent=2)}")
            
            # Test command: /help
            command_message = {
                "id": str(uuid.uuid4()),
                "type": "command",
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": str(uuid.uuid4())
                },
                "timestamp": "2025-06-01T12:00:00Z"
            }
            
            print(f"Sending command: {json.dumps(command_message, indent=2)}")
            await websocket.send(json.dumps(command_message))
            
            # Wait for response with timeout
            print("Waiting for command result...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                response_data = json.loads(response)
                print(f"Received response: {json.dumps(response_data, indent=2)}")
            except asyncio.TimeoutError:
                print("Timeout waiting for response")
            except Exception as e:
                print(f"Error receiving response: {e}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_test())
