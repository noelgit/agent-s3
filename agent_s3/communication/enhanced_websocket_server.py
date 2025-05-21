"""Enhanced WebSocket Server for Agent-S3 UI Flow.

This module enhances the basic WebSocket server with message bus integration,
improved reconnection handling, and structured message routing.
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
from typing import Dict, Any, Optional, Set, List
import websockets

from .message_protocol import Message, MessageType, MessageBus, MessageQueue

logger = logging.getLogger(__name__)


class EnhancedWebSocketServer:
    """WebSocket server with message bus integration for UI flow.
    
    This server provides enhanced features like message batching, rate limiting,
    connection state recovery, and support for interactive UI components.
    """
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        host: str = "localhost",
        port: int = 9000,
        auth_token: Optional[str] = None,
        heartbeat_interval: int = 15
    ):
        """Initialize the WebSocket server.
        
        Args:
            message_bus: Optional message bus instance
            host: Host to bind to
            port: Port to listen on
            auth_token: Optional authentication token
            heartbeat_interval: Heartbeat interval in seconds
        """
        self.host = host
        self.port = port
        self.auth_token = auth_token or str(uuid.uuid4())
        self.heartbeat_interval = heartbeat_interval
        
        # Message bus and queue
        self.message_bus = message_bus or MessageBus()
        self.message_queue = MessageQueue()
        
        # WebSocket server state
        self.server = None
        self.running = False
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.authenticated_clients: Set[str] = set()
        self.connection_file = os.path.join(os.getcwd(), ".agent_s3_ws_connection.json")
        
        # WebSocket tasks
        self.heartbeat_task = None
        self.queue_processor_task = None
        self.expiry_cleaner_task = None
        self.metrics_logger_task = None
        
        # Client message queues
        self.client_queues: Dict[str, List[Message]] = {}
        self.max_queue_size = 100
        self.queue_expiry_seconds = 3600  # 1 hour
        self.queue_last_access: Dict[str, float] = {}
        
        # Rate limiting
        self.rate_limits = {
            "messages_per_second": 20,  # Max messages per second per client
            "batch_size": 10,  # Max messages to batch together
            "batch_wait_ms": 100  # Time to wait for batch completion
        }
        self.client_message_counters: Dict[str, Dict[str, Any]] = {}
        
        # Register handlers
        self._register_handlers()
        
    def _register_handlers(self):
        """Register message handlers for the message bus."""
        self.message_bus.register_handler(MessageType.TERMINAL_OUTPUT, 
                                          self._handle_terminal_output)
        self.message_bus.register_handler(MessageType.APPROVAL_REQUEST, 
                                          self._handle_approval_request)
        self.message_bus.register_handler(MessageType.DIFF_DISPLAY, 
                                          self._handle_diff_display)
        self.message_bus.register_handler(MessageType.LOG_OUTPUT, 
                                          self._handle_log_output)
        self.message_bus.register_handler(MessageType.PROGRESS_UPDATE, 
                                          self._handle_progress_update)
        self.message_bus.register_handler(MessageType.ERROR_NOTIFICATION, 
                                          self._handle_error_notification)
        
        # Enhanced interactive UI handlers
        self.message_bus.register_handler(MessageType.INTERACTIVE_DIFF,
                                          self._handle_interactive_diff)
        self.message_bus.register_handler(MessageType.INTERACTIVE_APPROVAL,
                                          self._handle_interactive_approval)
        self.message_bus.register_handler(MessageType.PROGRESS_INDICATOR,
                                          self._handle_progress_indicator)
        self.message_bus.register_handler(MessageType.CHAT_MESSAGE,
                                          self._handle_chat_message)
        self.message_bus.register_handler(MessageType.CODE_SNIPPET,
                                          self._handle_code_snippet)
        self.message_bus.register_handler(MessageType.FILE_TREE,
                                          self._handle_file_tree)
        self.message_bus.register_handler(MessageType.TASK_BREAKDOWN,
                                          self._handle_task_breakdown)
        self.message_bus.register_handler(MessageType.THINKING_INDICATOR,
                                          self._handle_thinking)
        self.message_bus.register_handler(MessageType.STREAM_START,
                                          self._handle_stream_start)
        self.message_bus.register_handler(MessageType.STREAM_CONTENT,
                                          self._handle_stream_content)
        self.message_bus.register_handler(MessageType.STREAM_END,
                                          self._handle_stream_end)
        self.message_bus.register_handler(MessageType.STREAM_INTERACTIVE,
                                          self._handle_stream_interactive)
    
    def _handle_terminal_output(self, message: Message):
        """Handle terminal output messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_approval_request(self, message: Message):
        """Handle approval request messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_diff_display(self, message: Message):
        """Handle diff display messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_log_output(self, message: Message):
        """Handle log output messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_progress_update(self, message: Message):
        """Handle progress update messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_error_notification(self, message: Message):
        """Handle error notification messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_interactive_diff(self, message: Message):
        """Handle interactive diff messages with enhanced diff displays.
        
        Args:
            message: The message to handle
        """
        # Extract relevant information for metrics/logging
        content = message.content
        files = content.get("files", [])
        stats = content.get("stats", {})
        
        # Log details about the diff for monitoring
        logger.info(f"Interactive diff with {len(files)} files: " +
                    f"{stats.get('insertions', 0)} insertions, " +
                    f"{stats.get('deletions', 0)} deletions")
        
        # Broadcast the message to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_interactive_approval(self, message: Message):
        """Handle interactive approval messages with rich option displays.
        
        Args:
            message: The message to handle
        """
        # Extract relevant information for metrics/logging
        content = message.content
        title = content.get("title", "")
        options = content.get("options", [])
        request_id = content.get("request_id", "")
        
        # Log details about the approval request for monitoring
        logger.info(f"Interactive approval request '{title}' with {len(options)} options (ID: {request_id})")
        
        # Broadcast the message to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_progress_indicator(self, message: Message):
        """Handle progress indicator messages with detailed progress tracking.
        
        Args:
            message: The message to handle
        """
        # Extract relevant information for metrics/logging
        content = message.content
        title = content.get("title", "")
        percentage = content.get("percentage", 0)
        steps = content.get("steps", [])
        
        # Calculate completed steps
        completed_steps = sum(1 for step in steps if step.get("status") == "completed")
        total_steps = len(steps) or 1  # Avoid division by zero
        completion_ratio = f"{completed_steps}/{total_steps}"
        
        # Log details about the progress for monitoring
        if steps:
            logger.info(f"Progress indicator: '{title}' at {percentage}% ({completion_ratio} steps completed)")
        else:
            logger.info(f"Progress indicator: '{title}' at {percentage}%")
        
        # Broadcast the message to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_chat_message(self, message: Message):
        """Handle chat message.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_thinking(self, message: Message):
        """Handle thinking indicator messages.
        
        Args:
            message: The message to handle
        """
        # Extract stream ID for tracking
        content = message.content
        stream_id = content.get("stream_id", "")
        source = content.get("source", "agent")
        
        logger.debug(f"Agent thinking indicator received from {source} (stream: {stream_id})")
        
        # Broadcast the thinking indicator to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_stream_start(self, message: Message):
        """Handle stream start messages.
        
        Args:
            message: The message to handle
        """
        # Extract stream ID for tracking
        content = message.content
        stream_id = content.get("stream_id", "")
        source = content.get("source", "agent")
        
        logger.debug(f"Content stream started from {source} (stream: {stream_id})")
        
        # Initialize tracking for this stream ID
        self._active_streams = getattr(self, "_active_streams", set())
        self._active_streams.add(stream_id)
        
        # Broadcast the stream start to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_stream_content(self, message: Message):
        """Handle stream content messages.
        
        Args:
            message: The message to handle
        """
        # Extract stream ID and content
        content = message.content
        stream_id = content.get("stream_id", "")
        # Extract the raw text content if needed for future processing
        # Currently, the server does not use the content directly
        
        # Ensure we're tracking this stream
        self._active_streams = getattr(self, "_active_streams", set())
        if stream_id not in self._active_streams:
            logger.warning(f"Received content for unknown stream: {stream_id}")
            self._active_streams.add(stream_id)
        
        # Broadcast the stream content to all clients
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_stream_end(self, message: Message):
        """Handle stream end messages.
        
        Args:
            message: The message to handle
        """
        # Extract stream ID
        content = message.content
        stream_id = content.get("stream_id", "")
        
        logger.debug(f"Content stream ended (stream: {stream_id})")
        
        # Remove from active streams tracking
        self._active_streams = getattr(self, "_active_streams", set())
        if stream_id in self._active_streams:
            self._active_streams.remove(stream_id)

        # Broadcast the stream end to all clients
        asyncio.create_task(self.broadcast_message(message))

    def _handle_stream_interactive(self, message: Message):
        """Handle interactive component messages within a stream."""

        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_code_snippet(self, message: Message):
        """Handle code snippet messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_file_tree(self, message: Message):
        """Handle file tree messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    def _handle_task_breakdown(self, message: Message):
        """Handle task breakdown messages.
        
        Args:
            message: The message to handle
        """
        asyncio.create_task(self.broadcast_message(message))
    
    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle a client connection.
        
        Args:
            websocket: The WebSocket connection
            path: The connection path
        """
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        self.client_message_counters[client_id] = {
            "count": 0,
            "last_reset": time.time(),
            "batch": []
        }
        logger.info(f"New client connected: {client_id}")
        
        try:
            # Send connection acknowledgment
            await websocket.send(json.dumps(Message(
                type=MessageType.CONNECTION_ESTABLISHED,
                content={
                    "client_id": client_id,
                    "requires_authentication": self.auth_token is not None,
                    "server_version": "1.0.0",
                    "protocols": ["json", "msgpack"],
                    "features": [m.value for m in MessageType]
                }
            ).to_dict()))
            
            # Handle messages
            async for message_data in websocket:
                try:
                    # Check rate limits
                    if not self._check_rate_limit(client_id):
                        await self.send_message(client_id, Message(
                            type=MessageType.ERROR_NOTIFICATION,
                            content={"error": "Rate limit exceeded"}
                        ))
                        continue
                        
                    message_dict = json.loads(message_data)
                    message_type = message_dict.get("type")
                    
                    # Handle authentication
                    if message_type == "authenticate":
                        token = message_dict.get("content", {}).get("token")
                        if token == self.auth_token:
                            self.authenticated_clients.add(client_id)
                            await self.send_message(client_id, Message(
                                type=MessageType.AUTHENTICATION_RESULT,
                                content={"success": True}
                            ))
                            logger.info(f"Client {client_id} authenticated successfully")
                            
                            # Set up client preferences if provided
                            client_preferences = message_dict.get("content", {}).get("preferences", {})
                            if client_preferences:
                                logger.info(f"Setting preferences for client {client_id}: {client_preferences}")
                        else:
                            await self.send_message(client_id, Message(
                                type=MessageType.AUTHENTICATION_RESULT,
                                content={
                                    "success": False,
                                    "error": "Invalid authentication token"
                                }
                            ))
                            logger.warning(f"Client {client_id} failed authentication")
                        continue
                    
                    # Handle reconnection
                    if message_type == "reconnect":
                        previous_id = message_dict.get("content", {}).get("previous_id")
                        if previous_id and previous_id in self.authenticated_clients:
                            # Transfer authenticated status
                            self.authenticated_clients.add(client_id)
                            
                            # Send queued messages
                            await self._send_queued_messages(previous_id, client_id)
                            
                            # Transfer state
                            state_data = message_dict.get("content", {}).get("state", {})
                            if state_data:
                                logger.info(f"Received state data from reconnecting client {client_id}")
                            
                            # Acknowledge reconnection
                            await self.send_message(client_id, Message(
                                type=MessageType.RECONNECTION_RESULT,
                                content={
                                    "success": True,
                                    "previous_id": previous_id,
                                    "new_id": client_id,
                                    "server_time": time.time()
                                }
                            ))
                            logger.info(f"Client {client_id} reconnected as {previous_id}")
                        continue
                    
                    # Check authentication for other messages
                    if self.auth_token and client_id not in self.authenticated_clients:
                        await self.send_message(client_id, Message(
                            type=MessageType.ERROR_NOTIFICATION,
                            content={"error": "Authentication required"}
                        ))
                        continue
                    
                    # Handle heartbeat
                    if message_type == "heartbeat":
                        await self.send_message(client_id, Message(
                            type=MessageType.HEARTBEAT_RESPONSE,
                            content={"timestamp": time.time()}
                        ))
                        continue
                    
                    # Handle synchronization request
                    if message_type == "sync_request":
                        await self._handle_sync_request(client_id, message_dict)
                        continue
                    
                    # Handle user preferences update
                    if message_type == "set_preferences":
                        await self._handle_preferences_update(client_id, message_dict)
                        continue
                    
                    # Handle user responses
                    if message_type == "user_response":
                        # Convert to Message object and publish to bus
                        message = Message.from_dict(message_dict)
                        self.message_bus.publish(message)
                    
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from client {client_id}")
                    await self.send_message(client_id, Message(
                        type=MessageType.ERROR_NOTIFICATION,
                        content={"error": "Invalid JSON message"}
                    ))
                except Exception as e:
                    logger.error(f"Error handling message from client {client_id}: {e}")
                    await self.send_message(client_id, Message(
                        type=MessageType.ERROR_NOTIFICATION,
                        content={"error": f"Error processing message: {str(e)}"}
                    ))
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        finally:
            # Keep authenticated status for reconnection
            if client_id in self.clients:
                del self.clients[client_id]
            if client_id in self.client_message_counters:
                del self.client_message_counters[client_id]
    
    async def _handle_sync_request(self, client_id: str, message_dict: Dict[str, Any]):
        """Handle a synchronization request.
        
        Args:
            client_id: The client ID
            message_dict: The message dictionary
        """
        # Get sync markers from client (timestamps, sequence IDs)
        # Extract client-provided synchronization markers if available
        _ = message_dict.get("content", {}).get("sync_markers", {})
        
        # Determine what data needs to be sent
        # This is application-specific, but we'll send back some state for example
        await self.send_message(client_id, Message(
            type=MessageType.UI_STATE_UPDATE,
            content={
                "sync_complete": True,
                "server_time": time.time(),
                "state_hash": str(hash(str(time.time()))),  # Using time as a placeholder
                "missing_messages": []  # Placeholder
            }
        ))
    
    async def _handle_preferences_update(self, client_id: str, message_dict: Dict[str, Any]):
        """Handle a preferences update request.
        
        Args:
            client_id: The client ID
            message_dict: The message dictionary
        """
        preferences = message_dict.get("content", {}).get("preferences", {})
        
        # Process preferences update
        # This is application-specific, but we'll acknowledge for example
        logger.info(f"Updated preferences for client {client_id}: {preferences}")
        
        await self.send_message(client_id, Message(
            type=MessageType.COMMAND_RESULT,
            content={
                "command": "set_preferences",
                "success": True,
                "preferences": preferences
            }
        ))
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if a client has exceeded its rate limit.
        
        Args:
            client_id: The client ID
            
        Returns:
            True if client is within rate limits, False otherwise
        """
        if client_id not in self.client_message_counters:
            return True
            
        counter = self.client_message_counters[client_id]
        current_time = time.time()
        
        # Reset counter if a second has passed
        if current_time - counter["last_reset"] >= 1.0:
            counter["count"] = 0
            counter["last_reset"] = current_time
            
        # Increment counter
        counter["count"] += 1
        
        # Check if over limit
        return counter["count"] <= self.rate_limits["messages_per_second"]
    
    async def send_message(self, client_id: str, message: Message) -> bool:
        """Send a message to a client.
        
        Args:
            client_id: The client ID
            message: The message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if client_id in self.clients:
            try:
                # Check if batching is enabled for this client
                if client_id in self.client_message_counters:
                    counter = self.client_message_counters[client_id]
                    
                    # If batching is active, add to batch
                    if len(counter.get("batch", [])) > 0:
                        counter["batch"].append(message)
                        
                        # If batch is full, send it
                        if len(counter["batch"]) >= self.rate_limits["batch_size"]:
                            return await self._send_batch(client_id)
                            
                        return True
                    
                    # Start a new batch if not already batching
                    counter["batch"] = [message]
                    
                    # Schedule batch send after delay
                    asyncio.create_task(self._delayed_batch_send(client_id))
                    return True
                
                # Fall back to direct send if no batching
                payload = json.dumps(message.to_dict())
                if len(payload) > 4096:
                    import gzip
                    import base64
                    compressed = gzip.compress(payload.encode("utf-8"))
                    payload = json.dumps({
                        "encoding": "gzip",
                        "payload": base64.b64encode(compressed).decode("utf-8")
                    })
                await self.clients[client_id].send(payload)
                return True
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                return await self._queue_message(client_id, message)
        elif client_id in self.authenticated_clients:
            # Queue for disconnected authenticated client
            return await self._queue_message(client_id, message)
        else:
            logger.warning(f"Client {client_id} not found")
            return False
    
    async def _delayed_batch_send(self, client_id: str):
        """Send a batch after a delay.
        
        Args:
            client_id: The client ID
        """
        await asyncio.sleep(self.rate_limits["batch_wait_ms"] / 1000)
        await self._send_batch(client_id)
    
    async def _send_batch(self, client_id: str) -> bool:
        """Send a batch of messages to a client.
        
        Args:
            client_id: The client ID
            
        Returns:
            True if sent successfully, False otherwise
        """
        if client_id not in self.client_message_counters:
            return False
            
        counter = self.client_message_counters[client_id]
        
        if not counter.get("batch"):
            return True
            
        batch = counter["batch"]
        counter["batch"] = []
        
        if client_id not in self.clients:
            # Queue messages for disconnected client
            success = True
            for message in batch:
                if not await self._queue_message(client_id, message):
                    success = False
            return success
            
        try:
            # Send as a batch message
            batch_message = {
                "type": "batch",
                "messages": [m.to_dict() for m in batch],
                "timestamp": time.time()
            }
            await self.clients[client_id].send(json.dumps(batch_message))
            return True
        except Exception as e:
            logger.error(f"Error sending batch to client {client_id}: {e}")
            
            # Try to queue individual messages
            success = True
            for message in batch:
                if not await self._queue_message(client_id, message):
                    success = False
            return success
    
    async def broadcast_message(self, message: Message, authenticated_only: bool = True):
        """Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
            authenticated_only: Whether to send only to authenticated clients
        """
        clients = self.authenticated_clients if authenticated_only else self.clients.keys()
        for client_id in list(clients):
            await self.send_message(client_id, message)
    
    async def _queue_message(self, client_id: str, message: Message) -> bool:
        """Queue a message for a disconnected client.
        
        Args:
            client_id: The client ID
            message: The message to queue
            
        Returns:
            True if queued successfully, False otherwise
        """
        self.queue_last_access[client_id] = time.time()
        
        if client_id not in self.client_queues:
            self.client_queues[client_id] = []
        
        if len(self.client_queues[client_id]) < self.max_queue_size:
            self.client_queues[client_id].append(message)
            return True
        else:
            logger.warning(f"Queue full for client {client_id}")
            return False
    
    async def _send_queued_messages(self, old_id: str, new_id: str) -> int:
        """Send queued messages to a reconnected client.
        
        Args:
            old_id: The old client ID
            new_id: The new client ID
            
        Returns:
            Number of messages sent
        """
        if old_id not in self.client_queues:
            return 0
        
        count = 0
        for message in self.client_queues[old_id]:
            if await self.send_message(new_id, message):
                count += 1
        
        # Clear queue after sending
        self.client_queues[old_id] = []
        logger.info(f"Sent {count} queued messages to client {new_id}")
        return count
    
    async def _clean_expired_queues(self):
        """Clean up expired message queues."""
        while self.running:
            try:
                current_time = time.time()
                expired_clients = []
                
                for client_id, last_access in list(self.queue_last_access.items()):
                    if current_time - last_access > self.queue_expiry_seconds:
                        expired_clients.append(client_id)
                
                for client_id in expired_clients:
                    if client_id in self.client_queues:
                        queue_size = len(self.client_queues[client_id])
                        del self.client_queues[client_id]
                        del self.queue_last_access[client_id]
                        logger.info(f"Expired queue for client {client_id}, dropped {queue_size} messages")
                
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue cleaner: {e}")
                await asyncio.sleep(60)
    
    async def _send_heartbeats(self):
        """Send periodic heartbeats to keep connections alive."""
        while self.running:
            try:
                await self.broadcast_message(Message(
                    type=MessageType.SERVER_HEARTBEAT,
                    content={"timestamp": time.time()}
                ))
                await asyncio.sleep(self.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending heartbeats: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _log_metrics(self):
        """Log metrics periodically."""
        while self.running:
            try:
                # Get metrics
                bus_metrics = self.message_bus.get_metrics()
                queue_metrics = self.message_queue.get_metrics()
                
                # Connection metrics
                connection_metrics = {
                    "connected_clients": len(self.clients),
                    "authenticated_clients": len(self.authenticated_clients),
                    "queued_clients": len(self.client_queues)
                }
                
                # Combine metrics
                all_metrics = {
                    **bus_metrics,
                    **queue_metrics,
                    **connection_metrics,
                    "timestamp": time.time()
                }
                
                # Log metrics
                logger.info(f"WebSocket Server Metrics: {all_metrics}")
                
                await asyncio.sleep(60)  # Log every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error logging metrics: {e}")
                await asyncio.sleep(60)
    
    async def _process_queue(self):
        """Process the message queue."""
        while self.running:
            try:
                if not self.message_queue.is_empty():
                    message = self.message_queue.dequeue()
                    if message:
                        self.message_bus.publish(message)
                await asyncio.sleep(0.01)  # Small delay to prevent CPU hogging
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing queue: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """Start the WebSocket server."""
        self.server = await websockets.serve(
            self._handle_client,
            self.host,
            self.port,
            ping_interval=self.heartbeat_interval,
            ping_timeout=self.heartbeat_interval * 2
        )
        
        # Get actual port if auto-selected
        for sock in self.server.sockets:
            if isinstance(sock, socket.socket) and sock.family == socket.AF_INET:
                _, self.port = sock.getsockname()
                break
        
        # Write connection info to file
        connection_info = {
            "host": self.host,
            "port": self.port,
            "auth_token": self.auth_token,
            "timestamp": time.time(),
            "protocol": "ws",
            "version": "1.0.0"
        }
        with open(self.connection_file, "w") as f:
            json.dump(connection_info, f)
        
        # Start tasks
        self.running = True
        self.heartbeat_task = asyncio.create_task(self._send_heartbeats())
        self.queue_processor_task = asyncio.create_task(self._process_queue())
        self.expiry_cleaner_task = asyncio.create_task(self._clean_expired_queues())
        self.metrics_logger_task = asyncio.create_task(self._log_metrics())
        
        logger.info(f"EnhancedWebSocketServer running on {self.host}:{self.port}")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if self.running:
            self.running = False
            
            # Cancel tasks
            for task in [
                self.heartbeat_task,
                self.queue_processor_task,
                self.expiry_cleaner_task,
                self.metrics_logger_task
            ]:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Close client connections
            close_tasks = []
            for client_id, websocket in list(self.clients.items()):
                close_tasks.append(websocket.close())
            
            if close_tasks:
                await asyncio.gather(*close_tasks, return_exceptions=True)
            
            # Close server
            self.server.close()
            await self.server.wait_closed()
            
            # Remove connection file
            if os.path.exists(self.connection_file):
                try:
                    os.remove(self.connection_file)
                except Exception as e:
                    logger.error(f"Error removing connection file: {e}")
            
            logger.info("EnhancedWebSocketServer stopped")
    
    def start_in_thread(self):
        """Start the WebSocket server in a separate thread."""
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Setup signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            
            try:
                loop.run_until_complete(self.start())
                loop.run_forever()
            except Exception as e:
                logger.error(f"Error in WebSocket server thread: {e}")
            finally:
                if not loop.is_closed():
                    loop.close()
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        return server_thread
    
    def stop_from_main_thread(self):
        """Stop the server from the main thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.stop())
        finally:
            loop.close()
