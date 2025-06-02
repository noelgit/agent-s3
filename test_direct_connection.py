#!/usr/bin/env python3
"""Test direct connection to 0.0.0.0:8765"""

import asyncio
import websockets
import json

async def test_connection():
    """Test connection to different addresses"""
    addresses = [
        "ws://0.0.0.0:8765",
        "ws://127.0.0.1:8765", 
        "ws://localhost:8765"
    ]
    
    for addr in addresses:
        try:
            print(f"Trying {addr}...")
            async with websockets.connect(addr) as websocket:
                print(f"✅ Connected to {addr}!")
                
                # Send auth message
                auth_msg = {
                    "type": "authenticate",
                    "content": {"token": "agent-s3-dev-token"}
                }
                await websocket.send(json.dumps(auth_msg))
                response = await websocket.recv()
                print(f"Auth response: {response[:100]}...")
                break
                
        except Exception as e:
            print(f"❌ Failed to connect to {addr}: {e}")
    
if __name__ == "__main__":
    asyncio.run(test_connection())