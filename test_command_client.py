#!/usr/bin/env python3
"""Test client to verify command processing in Agent-S3 WebSocket server."""

import asyncio
import json
import websockets
import uuid
import sys

async def test_command_processing():
    """Test command processing via WebSocket connection."""
    uri = "ws://localhost:8765"
    
    try:
        print(f"Connecting to {uri}...")
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Receive connection acknowledgment
            ack_message = await websocket.recv()
            ack_data = json.loads(ack_message)
            print(f"Received acknowledgment: {ack_data}")
            
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
            
            print(f"Sending command: {command_message}")
            await websocket.send(json.dumps(command_message))
            
            # Wait for response
            print("Waiting for command result...")
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response_data = json.loads(response)
            print(f"Received response: {response_data}")
            
            # Test another command: /config
            command_message2 = {
                "id": str(uuid.uuid4()),
                "type": "command", 
                "content": {
                    "command": "/config",
                    "args": "",
                    "request_id": str(uuid.uuid4())
                },
                "timestamp": "2025-06-01T12:00:00Z"
            }
            
            print(f"Sending second command: {command_message2}")
            await websocket.send(json.dumps(command_message2))
            
            # Wait for second response
            print("Waiting for second command result...")
            response2 = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            response2_data = json.loads(response2)
            print(f"Received second response: {response2_data}")
            
    except websockets.ConnectionClosed:
        print("Connection closed by server")
    except asyncio.TimeoutError:
        print("Timeout waiting for response")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Custom command from command line
        command = sys.argv[1]
        args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        
        async def test_custom_command():
            uri = "ws://localhost:8765"
            try:
                async with websockets.connect(uri) as websocket:
                    # Receive connection acknowledgment
                    ack_message = await websocket.recv()
                    ack_data = json.loads(ack_message)
                    print(f"Connected: {ack_data['content']['client_id']}")
                    
                    # Send custom command
                    command_message = {
                        "id": str(uuid.uuid4()),
                        "type": "command",
                        "content": {
                            "command": command,
                            "args": args,
                            "request_id": str(uuid.uuid4())
                        },
                        "timestamp": "2025-06-01T12:00:00Z"
                    }
                    
                    print(f"Sending: {command} {args}")
                    await websocket.send(json.dumps(command_message))
                    
                    # Wait for response
                    response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                    response_data = json.loads(response)
                    
                    if response_data['content'].get('success'):
                        print("Success!")
                        print(response_data['content']['result'])
                    else:
                        print("Error:")
                        print(response_data['content']['error'])
                        
            except Exception as e:
                print(f"Error: {e}")
                
        asyncio.run(test_custom_command())
    else:
        asyncio.run(test_command_processing())
