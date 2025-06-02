#!/usr/bin/env python3
"""
Minimal WebSocket server test to isolate connection issues
"""

import asyncio
import websockets
import json
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MinimalWebSocketServer:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()

    async def handle_client(self, websocket, path):
        """Handle a client connection - minimal implementation"""
        client_id = f"client_{len(self.clients) + 1}"
        self.clients.add(websocket)
        logger.info(f"✅ Client {client_id} connected from {websocket.remote_address}")
        
        try:
            # Send welcome message
            welcome = {
                "type": "connection_established",
                "content": {
                    "client_id": client_id,
                    "message": "Connected to minimal test server"
                }
            }
            await websocket.send(json.dumps(welcome))
            logger.info(f"📤 Sent welcome to {client_id}")
            
            # Listen for messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.info(f"📥 Received from {client_id}: {data}")
                    
                    # Echo back
                    response = {
                        "type": "echo",
                        "content": {
                            "original": data,
                            "message": f"Echo from server to {client_id}"
                        }
                    }
                    await websocket.send(json.dumps(response))
                    logger.info(f"📤 Sent echo to {client_id}")
                    
                except json.JSONDecodeError:
                    logger.error(f"❌ Invalid JSON from {client_id}")
                except Exception as e:
                    logger.error(f"❌ Error handling message from {client_id}: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"🔌 Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"❌ Error with {client_id}: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"🧹 Cleaned up {client_id}")

    async def start(self):
        """Start the minimal server"""
        logger.info(f"🚀 Starting minimal WebSocket server on {self.host}:{self.port}")
        
        try:
            # Try different binding configurations
            server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10
            )
            logger.info(f"✅ Server started successfully")
            logger.info(f"🔗 Listening on ws://{self.host}:{self.port}")
            
            # Keep running
            await server.wait_closed()
            
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            raise

async def main():
    """Main function to test different configurations"""
    
    # Test different host configurations
    test_configs = [
        ("localhost", 8765),
        ("127.0.0.1", 8765),
        ("0.0.0.0", 8765),
    ]
    
    for host, port in test_configs:
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing configuration: {host}:{port}")
        logger.info(f"{'='*50}")
        
        server = MinimalWebSocketServer(host, port)
        try:
            await asyncio.wait_for(server.start(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.info(f"✅ Server {host}:{port} started successfully (timeout reached)")
            break
        except Exception as e:
            logger.error(f"❌ Failed to start server on {host}:{port}: {e}")
            continue
    
    logger.info("🏁 Test completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")