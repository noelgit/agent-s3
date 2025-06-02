#!/usr/bin/env python3
"""Test connection to Agent-S3 server on port 8080"""

import asyncio
import websockets
import json

async def test_agent_s3_connection():
    """Test connection to Agent-S3 server on port 8080"""
    print("🧪 Testing Agent-S3 server on port 8080...")
    
    try:
        # Connect to Agent-S3 server
        async with websockets.connect("ws://127.0.0.1:8080") as websocket:
            print("✅ Connected to Agent-S3 server!")
            
            # Send authentication
            auth_msg = {
                "type": "authenticate",
                "content": {"token": "agent-s3-dev-token"}
            }
            await websocket.send(json.dumps(auth_msg))
            print("📤 Sent authentication")
            
            # Wait for auth response
            auth_response = await websocket.recv()
            print(f"📥 Auth response: {auth_response[:100]}...")
            
            # Send /help command
            help_cmd = {
                "type": "command",
                "content": {
                    "command": "/help",
                    "args": "",
                    "request_id": "test-help-8080"
                }
            }
            await websocket.send(json.dumps(help_cmd))
            print("📤 Sent /help command")
            
            # Wait for response
            help_response = await websocket.recv()
            help_data = json.loads(help_response)
            
            if help_data.get("type") == "batch":
                for msg in help_data.get("messages", []):
                    if msg.get("type") == "command_result":
                        print("✅ Received /help command result!")
                        print(f"📄 Help preview: {msg['content']['result'][:100]}...")
                        return True
            
            print("❌ Unexpected response format")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_agent_s3_connection())
    if success:
        print("\n🎉 SUCCESS: Agent-S3 server works perfectly on port 8080!")
        print("💡 VS Code extension should now be able to connect!")
    else:
        print("\n❌ FAILED: Agent-S3 server connection issues persist")