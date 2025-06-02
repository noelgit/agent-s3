#!/usr/bin/env python3
"""
Simple WebSocket server for Agent-S3 that works with all versions.
"""
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Error: websockets library not found. Install it with: pip install websockets")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
HOST = "localhost"
PORT = 8765
AUTH_TOKEN = "agent-s3-token-2025"

# Global state
clients = set()
authenticated_clients = set()

async def register_client(websocket):
    """Register a new client connection."""
    clients.add(websocket)
    logger.info(f"Client connected from {websocket.remote_address}. Total: {len(clients)}")

async def unregister_client(websocket):
    """Unregister a client connection."""
    clients.discard(websocket)
    authenticated_clients.discard(websocket)
    logger.info(f"Client disconnected. Total: {len(clients)}")

async def send_message(websocket, message_type, content):
    """Send a message to a websocket client."""
    try:
        message = {
            "type": message_type,
            "content": content
        }
        await websocket.send(json.dumps(message))
        logger.debug(f"Sent {message_type} to client")
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def handle_auth(websocket, content):
    """Handle authentication request."""
    token = content.get("token")
    if token == AUTH_TOKEN:
        authenticated_clients.add(websocket)
        await send_message(websocket, "connection_established", {
            "message": "Authentication successful"
        })
        logger.info("Client authenticated successfully")
        return True
    else:
        await send_message(websocket, "auth_failed", {
            "message": "Invalid authentication token"
        })
        await websocket.close()
        return False

async def handle_command(websocket, content):
    """Handle command request."""
    command = content.get("command", "")
    request_id = content.get("request_id", "")
    args = content.get("args", "")
    
    logger.info(f"Processing command: {command}")
    
    # Command responses
    if command == "/help":
        result = """Agent-S3 Help

Available commands:
/help - Show this help message
/status - Show server status
/ping - Test connection

Agent-S3 WebSocket Server is running and ready to assist!
The connection is working properly."""
        
    elif command == "/status":
        result = f"""Server Status: ✅ Running
Host: {HOST}
Port: {PORT}
Connected clients: {len(authenticated_clients)}
Total connections: {len(clients)}

All systems operational!"""
        
    elif command == "/ping":
        result = "🏓 Pong! Connection is working perfectly."
        
    else:
        result = f"""Command received: {command}
Arguments: {args}

Agent-S3 is ready to process your request.
This is a working WebSocket connection!"""
    
    response_content = {
        "success": True,
        "command": command,
        "request_id": request_id,
        "result": result
    }
    
    await send_message(websocket, "command_result", response_content)
    logger.info(f"Command {command} processed successfully")

async def handle_message(websocket, message_data):
    """Handle incoming WebSocket message."""
    try:
        message = json.loads(message_data)
        msg_type = message.get("type")
        content = message.get("content", {})
        
        logger.debug(f"Received message type: {msg_type}")
        
        if msg_type == "auth":
            await handle_auth(websocket, content)
            
        elif websocket in authenticated_clients:
            if msg_type == "command":
                await handle_command(websocket, content)
            elif msg_type == "ping":
                await send_message(websocket, "pong", {
                    "timestamp": content.get("timestamp")
                })
            else:
                logger.warning(f"Unknown message type: {msg_type}")
        else:
            await send_message(websocket, "auth_required", {
                "message": "Please authenticate first"
            })
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON received: {e}")
        await send_message(websocket, "error", {
            "message": "Invalid JSON format"
        })
    except Exception as e:
        logger.error(f"Error handling message: {e}")

async def websocket_handler(websocket, path=None):
    """Main WebSocket connection handler."""
    await register_client(websocket)
    try:
        async for message in websocket:
            await handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client connection closed normally")
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        await unregister_client(websocket)

def create_connection_file():
    """Create the connection configuration file."""
    config = {
        "host": HOST,
        "port": PORT,
        "auth_token": AUTH_TOKEN,
        "protocol": "ws",
        "version": "1.0.0"
    }
    
    connection_file = Path(".agent_s3_ws_connection.json")
    with open(connection_file, "w") as f:
        json.dump(config, f, indent=2)
    
    # Set secure permissions on Unix systems
    if os.name == 'posix':
        os.chmod(connection_file, 0o600)
    
    logger.info(f"Created connection file: {connection_file.absolute()}")
    return config

def cleanup():
    """Clean up resources on shutdown."""
    logger.info("Cleaning up...")
    try:
        connection_file = Path(".agent_s3_ws_connection.json")
        if connection_file.exists():
            connection_file.unlink()
            logger.info("Removed connection file")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

async def main():
    """Main server function."""
    # Create connection file
    config = create_connection_file()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the WebSocket server
    logger.info("=" * 60)
    logger.info("🚀 Agent-S3 WebSocket Server Starting")
    logger.info("=" * 60)
    logger.info(f"Host: {HOST}")
    logger.info(f"Port: {PORT}")
    logger.info(f"Auth Token: {AUTH_TOKEN}")
    logger.info(f"Connection File: {Path('.agent_s3_ws_connection.json').absolute()}")
    logger.info("=" * 60)
    logger.info("Server is ready! Press Ctrl+C to stop.")
    
    try:
        # Start server with compatibility for different websockets versions
        if hasattr(websockets, 'serve'):
            # websockets 10+ style
            async with websockets.serve(websocket_handler, HOST, PORT):
                await asyncio.Future()  # Run forever
        else:
            # Older websockets style
            start_server = websockets.serve(websocket_handler, HOST, PORT)
            await start_server
            await asyncio.Future()  # Run forever
            
    except Exception as e:
        logger.error(f"Server error: {e}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
        cleanup()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        cleanup()
        sys.exit(1)
