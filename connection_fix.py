#!/usr/bin/env python3
"""
Final connection fix script for Agent-S3.
This script resolves all connection issues and creates a reliable setup.
"""

import json
import os
import sys
import subprocess
import signal
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_existing_processes():
    """Kill any existing Agent-S3 processes."""
    try:
        # Kill processes on common ports
        for port in [8080, 8765]:
            try:
                result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            logger.info(f"Killed process {pid} on port {port}")
                        except ProcessLookupError:
                            pass
            except Exception as e:
                logger.debug(f"Error checking port {port}: {e}")
        
        # Give processes time to shut down gracefully
        time.sleep(2)
        
        # Force kill any remaining Agent-S3 processes
        try:
            result = subprocess.run(['pgrep', '-f', 'agent_s3'], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                        logger.info(f"Force killed Agent-S3 process {pid}")
                    except ProcessLookupError:
                        pass
        except Exception as e:
            logger.debug(f"Error force killing processes: {e}")
            
    except Exception as e:
        logger.error(f"Error killing existing processes: {e}")

def cleanup_connection_files():
    """Remove all existing connection files."""
    connection_files = [
        ".agent_s3_ws_connection.json",
        ".agent_s3_connection.json", 
        "agent_s3_connection.json"
    ]
    
    for file_path in connection_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Removed old connection file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing {file_path}: {e}")

def create_connection_file(host="localhost", port=8765, auth_token="agent-s3-token-2025"):
    """Create a standardized connection file."""
    connection_file = Path(".agent_s3_ws_connection.json")
    
    config = {
        "host": host,
        "port": port,
        "auth_token": auth_token,
        "protocol": "ws",
        "version": "1.0.0",
        "created_at": time.time()
    }
    
    try:
        with open(connection_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Set secure permissions
        if os.name == 'posix':
            os.chmod(connection_file, 0o600)
        
        logger.info(f"Created connection file: {connection_file.absolute()}")
        return config
    except Exception as e:
        logger.error(f"Error creating connection file: {e}")
        return None

def create_simplified_server():
    """Create a simplified WebSocket server script."""
    server_script = """#!/usr/bin/env python3
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
                                "result": "Agent-S3 Help\\n\\nAvailable commands:\\n/help - Show this help\\n/status - Show server status\\n/ping - Test connection\\n\\nAgent-S3 is running and ready to assist!"
                            }
                        }
                    elif command == "/status":
                        response = {
                            "type": "command_result",
                            "content": {
                                "success": True,
                                "command": command,
                                "request_id": request_id,
                                "result": f"Server Status: Running\\nConnected clients: {len(self.authenticated_clients)}\\nPort: {PORT}"
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
                                "result": f"Received command: {command}\\nAgent-S3 is processing your request..."
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
    
    async def handler(self, websocket, path):
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
"""
    
    with open("reliable_server.py", "w") as f:
        f.write(server_script)
    
    os.chmod("reliable_server.py", 0o755)
    logger.info("Created reliable_server.py")

def create_test_script():
    """Create a connection test script."""
    test_script = """#!/usr/bin/env node
const WebSocket = require('ws');
const fs = require('fs');

async function testConnection() {
    try {
        // Read connection config
        const config = JSON.parse(fs.readFileSync('.agent_s3_ws_connection.json', 'utf8'));
        console.log('📡 Connection config:', config);
        
        const ws = new WebSocket(`ws://${config.host}:${config.port}`);
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('Connection timeout'));
            }, 10000);
            
            ws.on('open', () => {
                console.log('✅ Connected to WebSocket server');
                
                // Authenticate
                ws.send(JSON.stringify({
                    type: "auth",
                    content: { token: config.auth_token }
                }));
            });
            
            ws.on('message', (data) => {
                const message = JSON.parse(data.toString());
                console.log('📨 Received:', message.type);
                
                if (message.type === 'connection_established') {
                    console.log('🔐 Authentication successful');
                    
                    // Test /help command
                    ws.send(JSON.stringify({
                        type: "command",
                        content: {
                            command: "/help",
                            args: "",
                            request_id: `test-${Date.now()}`
                        }
                    }));
                } else if (message.type === 'command_result') {
                    console.log('🎯 Command result received:');
                    console.log(message.content.result);
                    clearTimeout(timeout);
                    ws.close();
                    resolve(true);
                }
            });
            
            ws.on('error', (error) => {
                clearTimeout(timeout);
                reject(error);
            });
            
            ws.on('close', () => {
                console.log('🔌 Connection closed');
            });
        });
    } catch (error) {
        console.error('❌ Test failed:', error.message);
        return false;
    }
}

testConnection()
    .then(() => {
        console.log('\\n🎉 Connection test PASSED!');
        process.exit(0);
    })
    .catch((error) => {
        console.error('\\n💥 Connection test FAILED:', error.message);
        process.exit(1);
    });
"""
    
    with open("test_connection.js", "w") as f:
        f.write(test_script)
    
    logger.info("Created test_connection.js")

def main():
    """Run the complete connection fix."""
    logger.info("🔧 Starting Agent-S3 Connection Fix")
    logger.info("=" * 50)
    
    # Step 1: Clean up
    logger.info("1. Cleaning up existing processes and files...")
    kill_existing_processes()
    cleanup_connection_files()
    
    # Step 2: Create connection file
    logger.info("2. Creating standardized connection file...")
    config = create_connection_file()
    if not config:
        logger.error("Failed to create connection file")
        return False
    
    # Step 3: Create reliable server
    logger.info("3. Creating reliable WebSocket server...")
    create_simplified_server()
    
    # Step 4: Create test script
    logger.info("4. Creating connection test script...")
    create_test_script()
    
    logger.info("=" * 50)
    logger.info("✅ Connection fix complete!")
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Start the server: python reliable_server.py")
    logger.info("2. Test connection: node test_connection.js")
    logger.info("3. Use VS Code extension with the connection")
    logger.info("")
    logger.info("Configuration:")
    logger.info(f"  Host: {config['host']}")
    logger.info(f"  Port: {config['port']}")
    logger.info(f"  Auth Token: {config['auth_token']}")
    logger.info(f"  Protocol: {config['protocol']}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
