#!/usr/bin/env python3
import asyncio
import json
import logging
import websockets
import signal
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
HOST = "localhost"
PORT = 8765
AUTH_TOKEN = "agent-s3-token-2025"

class SimpleWebSocketServer:
    def __init__(self):
        self.clients = set()
        self.authenticated_clients = set()
    
    async def register_client(self, websocket):
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
    
    async def unregister_client(self, websocket):
        self.clients.discard(websocket)
        self.authenticated_clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    async def handle_message(self, websocket, message_data):
        try:
            message = json.loads(message_data)
            msg_type = message.get("type")
            
            if msg_type == "auth":
                token = message.get("content", {}).get("token")
                if token == AUTH_TOKEN:
                    self.authenticated_clients.add(websocket)
                    await websocket.send(json.dumps({
                        "type": "connection_established",
                        "content": {"message": "Authentication successful"}
                    }))
                    logger.info("Client authenticated successfully")
                else:
                    await websocket.send(json.dumps({
                        "type": "auth_failed", 
                        "content": {"message": "Invalid token"}
                    }))
                    await websocket.close()
                    return
            
            elif websocket in self.authenticated_clients:
                if msg_type == "command":
                    command = message.get("content", {}).get("command", "")
                    request_id = message.get("content", {}).get("request_id", "")
                    
                    # Simple command responses
                    if command == "/help":
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": "Agent-S3 Help\n\nAvailable commands:\n/help - Show this help\n/status - Show server status\n/ping - Test connection\n\nAgent-S3 is running and ready to assist!"
                            }
                        }
                    elif command == "/status":
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": f"Server Status: Running\nConnected clients: {len(self.authenticated_clients)}\nPort: {PORT}"
                            }
                        }
                    elif command == "/ping":
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": "Pong! Connection is working."
                            }
                        }
                    else:
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": f"Received command: {command}\nAgent-S3 is processing your request..."
                            }
                        }
                    
                    await websocket.send(json.dumps(response))
                    logger.info(f"Processed command: {command}")
                
                elif msg_type == "ping":
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "content": {"timestamp": message.get("content", {}).get("timestamp")}
                    }))
            
            else:
                await websocket.send(json.dumps({
                    "type": "auth_required",
                    "content": {"message": "Authentication required"}
                }))
        
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def handler(self, websocket, path=None):
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Handler error: {e}")
        finally:
            await self.unregister_client(websocket)

def create_connection_file():
    config = {
        "host": HOST,
        "port": PORT,
        "auth_token": AUTH_TOKEN,
        "protocol": "ws",
        "version": "1.0.0"
    }
    
    with open(".agent_s3_ws_connection.json", "w") as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Created connection file: {Path('.agent_s3_ws_connection.json').absolute()}")

async def main():
    # Create connection file
    create_connection_file()
    
    # Create server instance
    server = SimpleWebSocketServer()
    
    # Setup signal handlers
    def signal_handler():
        logger.info("Shutting down server...")
        try:
            os.remove(".agent_s3_ws_connection.json")
            logger.info("Removed connection file")
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    
    # Start server
    logger.info(f"Starting WebSocket server on {HOST}:{PORT}")
    logger.info(f"Auth token: {AUTH_TOKEN}")
    logger.info("Press Ctrl+C to stop")
    
    async with websockets.serve(server.handler, HOST, PORT):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
