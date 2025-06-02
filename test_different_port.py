#!/usr/bin/env python3
"""
Test WebSocket server on different ports to isolate port-specific issues
"""

import asyncio
import websockets
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simple_handler(websocket, path):
    """Simple WebSocket handler"""
    logger.info(f"✅ Client connected: {websocket.remote_address}")
    
    # Send welcome
    await websocket.send(json.dumps({"status": "connected", "port": "test"}))
    
    # Echo messages
    async for message in websocket:
        await websocket.send(f"Echo: {message}")

async def test_port(port):
    """Test WebSocket server on specific port"""
    logger.info(f"🧪 Testing port {port}")
    
    try:
        server = await websockets.serve(simple_handler, "127.0.0.1", port)
        logger.info(f"✅ Server started on 127.0.0.1:{port}")
        
        # Wait a bit for connections
        await asyncio.sleep(2)
        server.close()
        await server.wait_closed()
        
        return True
    except Exception as e:
        logger.error(f"❌ Port {port} failed: {e}")
        return False

async def main():
    """Test different ports"""
    test_ports = [8080, 3000, 9000, 8888, 7777]
    
    for port in test_ports:
        success = await test_port(port)
        if success:
            logger.info(f"🎉 Port {port} works! Let's test client connection...")
            
            # Test client connection
            import subprocess
            try:
                # Start server again
                server = await websockets.serve(simple_handler, "127.0.0.1", port)
                
                # Test with node client
                client_code = f"""
const WebSocket = require('ws');
const ws = new WebSocket('ws://127.0.0.1:{port}');
ws.on('open', () => {{
    console.log('✅ Client connected to port {port}');
    ws.send('test message');
}});
ws.on('message', (data) => {{
    console.log('📥 Received:', data.toString());
    ws.close();
}});
ws.on('error', (err) => {{
    console.log('❌ Error:', err.message);
}});
"""
                
                with open('/tmp/test_client.js', 'w') as f:
                    f.write(client_code)
                
                # Run client test
                result = subprocess.run(['node', '/tmp/test_client.js'], 
                                      capture_output=True, text=True, timeout=5)
                
                logger.info(f"Client test result: {result.stdout}")
                if result.stderr:
                    logger.error(f"Client test error: {result.stderr}")
                
                server.close()
                await server.wait_closed()
                break
                
            except Exception as e:
                logger.error(f"Client test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())