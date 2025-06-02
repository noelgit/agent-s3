#!/usr/bin/env python3
"""
Test WebSocket on port 8080 with Python client
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def server_handler(websocket):
    """WebSocket server handler"""
    logger.info(f"✅ Client connected from {websocket.remote_address}")
    
    try:
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": "Connected to test server on port 8080"
        }))
        
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"📥 Received: {data}")
            
            response = {
                "type": "response",
                "echo": data,
                "status": "success"
            }
            await websocket.send(json.dumps(response))
            
    except Exception as e:
        logger.error(f"Handler error: {e}")

async def test_client():
    """Test client connection"""
    logger.info("🔌 Testing client connection to port 8080...")
    
    try:
        async with websockets.connect("ws://127.0.0.1:8080") as websocket:
            logger.info("✅ Client connected successfully!")
            
            # Send test message
            test_msg = {"type": "test", "message": "Hello from client"}
            await websocket.send(json.dumps(test_msg))
            logger.info("📤 Sent test message")
            
            # Receive response
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"📥 Received response: {data}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Client connection failed: {e}")
        return False

async def main():
    """Run server and client test"""
    # Start server
    logger.info("🚀 Starting WebSocket server on port 8080...")
    server = await websockets.serve(server_handler, "127.0.0.1", 8080)
    logger.info("✅ Server started")
    
    # Test client connection
    await asyncio.sleep(0.5)  # Let server settle
    success = await test_client()
    
    if success:
        logger.info("🎉 SUCCESS: Port 8080 works perfectly!")
        logger.info("💡 The issue is likely port 8765 being blocked or reserved")
    else:
        logger.info("❌ FAILED: Even port 8080 doesn't work")
    
    # Clean up
    server.close()
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())