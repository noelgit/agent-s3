"""WebSocket server for Agent-S3.

This module implements a WebSocket server to facilitate real-time communication 
between the Agent-S3 Python backend and the VS Code extension.
"""

import asyncio
import json
import logging
import os
import signal
import socket
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Callable, Set
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

logger = logging.getLogger(__name__)

class WebSocketServer:
    """Manages WebSocket connections and message routing for Agent-S3."""
    
    def __init__(self, host: str = "localhost", port: int = 0, auth_token: Optional[str] = None):
        """Initialize the WebSocket server.
        
        Args:
            host: The hostname to bind to
            port: The port to listen on (0 = auto-select available port)
            auth_token: Optional authentication token to secure connections
        """
        self.host = host
        self.port = port
        self.auth_token = auth_token or self._generate_auth_token()
        self.actual_port = None
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        self.authenticated_clients: Set[str] = set()
        self.server = None
        self.server_task = None
        self.running = False
        self.connection_file = os.path.join(os.getcwd(), ".agent_s3_ws_connection.json")
        self.message_handlers: Dict[str, Callable] = {}
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_task = None
        
        # Message queue for disconnected clients
        self.message_queues: Dict[str, List[Dict[str, Any]]] = {}
        self.max_queued_messages = 100
        self.queue_expiry_seconds = 3600  # 1 hour
        self.queue_last_access: Dict[str, float] = {}
        
        # Register default message handlers
        self._register_default_handlers()
        
    def _generate_auth_token(self) -> str:
        """Generate a random authentication token."""
        return str(uuid.uuid4())
    
    def _register_default_handlers(self):
        """Register default message handlers."""
        self.register_handler("authenticate", self._handle_authenticate)
        self.register_handler("heartbeat", self._handle_heartbeat)
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler for a specific message type.
        
        Args:
            message_type: The type of message to handle
            handler: The handler function that accepts the message and client_id
        """
        self.message_handlers[message_type] = handler
        
    async def _handle_authenticate(self, message: Dict[str, Any], client_id: str):
        """Handle authentication messages.
        
        Args:
            message: The authentication message
            client_id: The client ID
        """
        token = message.get("token")
        if token == self.auth_token:
            self.authenticated_clients.add(client_id)
            await self.send_message(client_id, {
                "type": "authentication_result",
                "success": True
            })
            logger.info(f"Client {client_id} authenticated successfully")
        else:
            await self.send_message(client_id, {
                "type": "authentication_result",
                "success": False,
                "error": "Invalid authentication token"
            })
            logger.warning(f"Client {client_id} failed authentication attempt")
    
    async def _handle_heartbeat(self, message: Dict[str, Any], client_id: str):
        """Handle heartbeat messages.
        
        Args:
            message: The heartbeat message
            client_id: The client ID
        """
        await self.send_message(client_id, {
            "type": "heartbeat_response",
            "timestamp": time.time()
        })
    
    async def _send_periodic_heartbeats(self):
        """Send periodic heartbeats to all clients to keep connections alive."""
        while self.running:
            try:
                for client_id in list(self.authenticated_clients):
                    try:
                        if client_id in self.clients:
                            await self.send_message(client_id, {
                                "type": "server_heartbeat",
                                "timestamp": time.time()
                            })
                    except Exception as e:
                        logger.debug(f"Failed to send heartbeat to client {client_id}: {e}")
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle a client connection.
        
        Args:
            websocket: The WebSocket connection
            path: The connection path
        """
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        logger.info(f"New client connected: {client_id}")
        
        try:
            # Send connection acknowledgment
            await websocket.send(json.dumps({
                "type": "connection_established",
                "client_id": client_id,
                "requires_authentication": self.auth_token is not None
            }))
            
            # Handle messages
            async for message_data in websocket:
                try:
                    message = json.loads(message_data)
                    message_type = message.get("type")
                    
                    # Handle client reconnection
                    if message_type == "reconnect" and "previous_id" in message:
                        previous_id = message.get("previous_id")
                        if previous_id in self.authenticated_clients:
                            # Transfer authenticated status to new connection
                            self.authenticated_clients.add(client_id)
                            logger.info(f"Client {client_id} reconnected as {previous_id}")
                            
                            # Send any queued messages for the previous client ID
                            await self.send_queued_messages(previous_id)
                            
                            # Acknowledge reconnection
                            await websocket.send(json.dumps({
                                "type": "reconnection_result",
                                "success": True,
                                "previous_id": previous_id,
                                "new_id": client_id
                            }))
                            continue
                    
                    # Check authentication for non-authenticate messages
                    if message_type != "authenticate" and self.auth_token and client_id not in self.authenticated_clients:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Authentication required"
                        }))
                        continue
                    
                    # Route message to appropriate handler
                    if message_type in self.message_handlers:
                        await self.message_handlers[message_type](message, client_id)
                    else:
                        logger.warning(f"Unknown message type: {message_type}")
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": f"Unknown message type: {message_type}"
                        }))
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON message from client {client_id}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": "Invalid JSON message"
                    }))
                except Exception as e:
                    logger.error(f"Error handling message from client {client_id}: {e}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"Error processing message: {str(e)}"
                    }))
        except ConnectionClosedOK:
            logger.info(f"Client {client_id} disconnected normally")
        except ConnectionClosedError as e:
            logger.info(f"Client {client_id} connection closed with error: {e}")
        except Exception as e:
            logger.error(f"Error in client {client_id} handler: {e}")
        finally:
            # Keep client in authenticated_clients list for message queueing
            # but remove from active clients
            if client_id in self.clients:
                del self.clients[client_id]
            logger.info(f"Client {client_id} connection cleaned up")
    
    async def send_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific client.
        
        Args:
            client_id: The client ID
            message: The message to send
        
        Returns:
            bool: True if message was sent, False otherwise
        """
        if client_id in self.clients:
            try:
                await self.clients[client_id].send(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                # Queue message for disconnected client
                if client_id in self.authenticated_clients:
                    return await self.queue_message(client_id, message)
                return False
        else:
            # If client is authenticated but disconnected, queue the message
            if client_id in self.authenticated_clients:
                logger.info(f"Client {client_id} not connected. Queuing message.")
                return await self.queue_message(client_id, message)
            else:
                logger.warning(f"Client {client_id} not found")
                return False
    
    async def broadcast_message(self, message: Dict[str, Any], authenticated_only: bool = True):
        """Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
            authenticated_only: Whether to send only to authenticated clients
        """
        clients_to_message = self.authenticated_clients if authenticated_only else self.clients.keys()
        for client_id in list(clients_to_message):  # Convert to list to avoid modification during iteration
            await self.send_message(client_id, message)
    
    async def broadcast_progress_update(self, progress_data: Dict[str, Any]):
        """Broadcast a progress update to all connected clients.
        
        Args:
            progress_data: The progress data to broadcast
        """
        await self.broadcast_message({
            "type": "progress_update",
            "data": progress_data
        })
    
    async def broadcast_terminal_output(self, output: str):
        """Broadcast terminal output to all connected clients.
        
        Args:
            output: The terminal output to broadcast
        """
        await self.broadcast_message({
            "type": "terminal_output",
            "data": output
        })
    
    async def queue_message(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Queue a message for a disconnected client.
        
        Args:
            client_id: The client ID
            message: The message to queue
            
        Returns:
            bool: True if message was queued, False otherwise
        """
        # Update last access time
        self.queue_last_access[client_id] = time.time()
        
        # Initialize queue if it doesn't exist
        if client_id not in self.message_queues:
            self.message_queues[client_id] = []
        
        # Add message to queue
        if len(self.message_queues[client_id]) < self.max_queued_messages:
            self.message_queues[client_id].append(message)
            logger.debug(f"Message queued for client {client_id}. Queue size: {len(self.message_queues[client_id])}")
            return True
        else:
            logger.warning(f"Message queue full for client {client_id}. Dropping message.")
            return False
            
    async def send_queued_messages(self, client_id: str) -> int:
        """Send all queued messages to a client.
        
        Args:
            client_id: The client ID
            
        Returns:
            int: Number of messages sent
        """
        if client_id not in self.message_queues or not self.message_queues[client_id]:
            return 0
            
        # Update last access time
        self.queue_last_access[client_id] = time.time()
        
        # Send all queued messages
        count = 0
        for message in self.message_queues[client_id]:
            success = await self.send_message(client_id, message)
            if success:
                count += 1
                
        # Clear queue after sending
        if count > 0:
            logger.info(f"Sent {count} queued messages to client {client_id}")
            self.message_queues[client_id] = []
            
        return count
        
    async def clean_expired_queues(self):
        """Clean up expired message queues."""
        current_time = time.time()
        expired_clients = []
        
        for client_id, last_access in list(self.queue_last_access.items()):
            if current_time - last_access > self.queue_expiry_seconds:
                expired_clients.append(client_id)
                
        for client_id in expired_clients:
            if client_id in self.message_queues:
                queue_size = len(self.message_queues[client_id])
                del self.message_queues[client_id]
                del self.queue_last_access[client_id]
                logger.info(f"Expired message queue for client {client_id}. Dropped {queue_size} messages.")
                
        return len(expired_clients)
    
    async def start_server(self):
        """Start the WebSocket server."""
        self.server = await websockets.serve(self._handle_client, self.host, self.port)
        
        # Get the actual port if auto-selected
        for sock in self.server.sockets:
            if sock.family == socket.AF_INET:
                _, self.actual_port = sock.getsockname()
                break
        
        # Write connection info to file for VS Code extension
        connection_info = {
            "host": self.host,
            "port": self.actual_port,
            "auth_token": self.auth_token,
            "timestamp": time.time()
        }
        with open(self.connection_file, "w") as f:
            json.dump(connection_info, f)
        
        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._send_periodic_heartbeats())
        self.running = True
        
        logger.info(f"WebSocket server started on {self.host}:{self.actual_port}")
    
    async def stop_server(self):
        """Stop the WebSocket server."""
        if self.running:
            # Cancel heartbeat task
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Close all client connections
            close_coroutines = []
            for client_id, websocket in list(self.clients.items()):
                try:
                    close_coroutines.append(websocket.close())
                except Exception as e:
                    logger.error(f"Error closing client {client_id} connection: {e}")
            
            if close_coroutines:
                await asyncio.gather(*close_coroutines, return_exceptions=True)
            
            # Close server
            self.server.close()
            await self.server.wait_closed()
            
            # Clean up connection file
            if os.path.exists(self.connection_file):
                try:
                    os.remove(self.connection_file)
                except Exception as e:
                    logger.error(f"Error removing connection file: {e}")
            
            self.running = False
            logger.info("WebSocket server stopped")
    
    def start(self):
        """Start the WebSocket server in a separate thread."""
        def run_server():
            import socket  # Import here to avoid circular imports
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Setup signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop_server()))
            
            try:
                self.server_task = loop.create_task(self.start_server())
                loop.run_forever()
            except Exception as e:
                logger.error(f"Error in WebSocket server thread: {e}")
            finally:
                if not loop.is_closed():
                    loop.close()
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
    
    def stop(self):
        """Stop the WebSocket server."""
        if self.running:
            # Create a new event loop to stop the server
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.stop_server())
            finally:
                loop.close()