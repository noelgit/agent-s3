#!/usr/bin/env python3
"""Simple test to verify /help command works through WebSocket"""

import asyncio
import json
import websockets
import sys

async def test_help():
    """Test /help command end to end"""
    try:
        # Connect to the server
        print("Connecting to ws://localhost:8765...")
        async with websockets.connect("ws://localhost:8765") as websocket:
            print("✅ Connected!")
            
            # Authenticate (using correct message type)
            auth_msg = {"type": "authenticate", "content": {"token": "agent-s3-dev-token"}}
            await websocket.send(json.dumps(auth_msg))
            
            # Get auth response
            auth_response = await websocket.recv()
            print(f"Auth response: {auth_response}")
            
            # Send /help command
            help_msg = {
                "type": "command", 
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": "test123"
                }
            }
            print("Sending /help command...")
            await websocket.send(json.dumps(help_msg))
            
            # Wait for response
            print("Waiting for response...")
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"✅ Got response: {response}")
            
            # Parse and check
            parsed = json.loads(response)
            if parsed.get("type") == "command_result":
                result = parsed.get("content", {}).get("result", "")
                print(f"✅ SUCCESS! Help text: {result[:100]}...")
                return True
            else:
                print(f"❌ Wrong message type: {parsed.get('type')}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_help())
    sys.exit(0 if result else 1)