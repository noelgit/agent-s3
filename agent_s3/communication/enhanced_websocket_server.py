"""Enhanced WebSocket Server for Agent-S3 UI Flow.

This module enhances the basic WebSocket server with message bus integration,
improved reconnection handling, and structured message routing.
"""

import asyncio
import json
import logging
import os
# import signal # No longer needed here
import socket
import threading
import time
import uuid
from typing import Dict, Any, Optional, Set, List
import websockets

from .message_protocol import Message, MessageType, MessageBus, MessageQueue

CONNECTION_FILE_NAME = ".agent_s3_ws_connection.json"

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
        heartbeat_interval: int = 15,
        max_message_size: int = 65536,
    ):
        """Initialize the WebSocket server.

        Args:
            message_bus: Optional message bus instance
            host: Host to bind to
            port: Port to listen on
            auth_token: Optional authentication token
            heartbeat_interval: Heartbeat interval in seconds
            max_message_size: Maximum allowed size for a single message in bytes
        """
        self.host = host
        self.port = port
        self.auth_token = auth_token or str(uuid.uuid4())
        self.heartbeat_interval = heartbeat_interval
        env_size = os.getenv("WEBSOCKET_MAX_MESSAGE_SIZE")
        self.max_message_size = (
            int(env_size) if env_size else max_message_size
        )

        # Message bus and queue
        self.message_bus = message_bus or MessageBus()
        self.message_queue = MessageQueue()

        # WebSocket server state
        self.server = None
        self.running = False
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.authenticated_clients: Set[str] = set()
        self.connection_file = os.path.join(os.getcwd(), CONNECTION_FILE_NAME)

        # WebSocket tasks
        self.heartbeat_task = None
        self.queue_processor_task = None
        self.expiry_cleaner_task = None
        self.metrics_logger_task = None  # Ensure this is initialized
        
        # Active streams tracking
        self._active_streams: Set[str] = set()

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

        # Workflow control handlers
        self.message_bus.register_handler(MessageType.PROGRESS_RESPONSE,
                                          self._handle_progress_response)
        self.message_bus.register_handler(MessageType.WORKFLOW_CONTROL,
                                          self._handle_workflow_control)
        self.message_bus.register_handler(MessageType.WORKFLOW_STATUS,
                                          self._handle_workflow_status)

    def _handle_terminal_output(self, message: Message):
        """Handle terminal output messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling terminal output: {e}")
            raise

    def _handle_approval_request(self, message: Message):
        """Handle approval request messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling approval request: {e}")
            raise

    def _handle_diff_display(self, message: Message):
        """Handle diff display messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling diff display: {e}")
            raise

    def _handle_log_output(self, message: Message):
        """Handle log output messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling log output: {e}")
            raise

    def _handle_progress_update(self, message: Message):
        """Handle progress update messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling progress update: {e}")
            raise

    def _handle_error_notification(self, message: Message):
        """Handle error notification messages.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling error notification: {e}")
            raise

    def _handle_interactive_diff(self, message: Message):
        """Handle interactive diff messages with enhanced diff displays.

        Args:
            message: The message to handle
        """
        try:
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
        except Exception as e:
            logger.error(f"Error handling interactive diff: {e}")
            raise

    def _handle_interactive_approval(self, message: Message):
        """Handle interactive approval messages with rich option displays.

        Args:
            message: The message to handle
        """
        try:
            # Extract relevant information for metrics/logging
            content = message.content
            title = content.get("title", "")
            options = content.get("options", [])
            request_id = content.get("request_id", "")

            # Log details about the approval request for monitoring
            logger.info(
                "%s",
                (
                    f"Interactive approval request '{title}' with {len(options)}"
                    f" options (ID: {request_id})"
                ),
            )

            # Broadcast the message to all clients
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling interactive approval: {e}")
            raise

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
        completed_steps = sum(
            1 for step in steps if step.get("status") == "completed")
        total_steps = len(steps) or 1  # Avoid division by zero
        completion_ratio = f"{completed_steps}/{total_steps}"

        # Log details about the progress for monitoring
        if steps:
            logger.info(
                "%s",
                f"Progress indicator: '{title}' at {percentage}% ({completion_ratio} steps completed)",
            )
        else:
            logger.info(
                "%s",
                f"Progress indicator: '{title}' at {percentage}%",
            )

        # Broadcast the message to all clients
        asyncio.create_task(self.broadcast_message(message))

    def _handle_chat_message(self, message: Message):
        """Handle chat message.

        Args:
            message: The message to handle
        """
        try:
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling chat message: {e}")
            raise

    def _handle_thinking(self, message: Message):
        """Handle thinking indicator messages.

        Args:
            message: The message to handle
        """
        try:
            # Extract stream ID for tracking
            content = message.content
            stream_id = content.get("stream_id", "")
            source = content.get("source", "agent")

            logger.debug(
                "%s",
                f"Agent thinking indicator received from {source} (stream: {stream_id})",
            )

            # Broadcast the thinking indicator to all clients
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling thinking indicator: {e}")
            raise

    def _handle_stream_start(self, message: Message):
        """Handle stream start messages.

        Args:
            message: The message to handle
        """
        try:
            # Extract stream ID for tracking
            content = message.content
            stream_id = content.get("stream_id", "")
            source = content.get("source", "agent")

            logger.debug(
                "%s",
                f"Content stream started from {source} (stream: {stream_id})",
            )

            # Initialize tracking for this stream ID
            self._active_streams.add(stream_id)

            # Broadcast the stream start to all clients
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling stream start: {e}")
            raise

    def _handle_stream_content(self, message: Message):
        """Handle stream content messages.

        Args:
            message: The message to handle
        """
        try:
            # Extract stream ID and content
            content = message.content
            stream_id = content.get("stream_id", "")
            # Extract the raw text content if needed for future processing
            # Currently, the server does not use the content directly

            # Ensure we're tracking this stream
            if stream_id not in self._active_streams:
                logger.warning(
                    "%s", f"Received content for unknown stream: {stream_id}"
                )
                self._active_streams.add(stream_id)

            # Broadcast the stream content to all clients
            asyncio.create_task(self.broadcast_message(message))
        except Exception as e:
            logger.error(f"Error handling stream content: {e}")
            raise

    def _handle_stream_end(self, message: Message):
        """Handle stream end messages.

        Args:
            message: The message to handle
        """
        # Extract stream ID
        content = message.content
        stream_id = content.get("stream_id", "")

        logger.debug("%s", f"Content stream ended (stream: {stream_id})")

        # Remove from active streams tracking
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

    def _handle_progress_response(self, message: Message):
        """Handle progress response messages from UI (pause/resume/stop/cancel).

        Args:
            message: The message to handle
        """
        content = message.content
        action = content.get("action", "")

        logger.info(f"Received workflow control action: {action}")

        # Find the coordinator instance and handle the control action
        try:
            # Get the coordinator from the registry if available
            coordinator = getattr(self, 'coordinator', None)
            if not coordinator and hasattr(self, 'message_bus'):
                # Try to find coordinator through message bus subscribers
                for handler_list in self.message_bus.handlers.values():
                    for handler in handler_list:
                        if hasattr(
                                handler, '__self__') and hasattr(
                                handler.__self__, 'coordinator'):
                            coordinator = handler.__self__.coordinator
                            break
                    if coordinator:
                        break

            if coordinator and hasattr(coordinator, 'orchestrator'):
                orchestrator = coordinator.orchestrator
                if action == "pause":
                    orchestrator.pause_workflow("User requested pause via UI")
                elif action == "resume":
                    orchestrator.resume_workflow(
                        "User requested resume via UI")
                elif action == "stop":
                    orchestrator.stop_workflow("User requested stop via UI")
                elif action == "cancel":
                    orchestrator.stop_workflow("User requested cancel via UI")
                else:
                    logger.warning(
                        f"Unknown workflow control action: {action}")
            else:
                logger.warning(
                    "Could not find coordinator/orchestrator to handle workflow control")

        except Exception as e:
            logger.error(
                f"Error handling workflow control action '{action}': {e}")

    def _handle_workflow_control(self, message: Message):
        """Handle direct workflow control messages.

        Args:
            message: The message to handle
        """
        # This is mainly for internal workflow control, just broadcast it
        asyncio.create_task(self.broadcast_message(message))

    def _handle_workflow_status(self, message: Message):
        """Handle workflow status messages.

        Args:
            message: The message to handle
        """
        content = message.content
        status = content.get("status", "")
        phase = content.get("current_phase", "")

        logger.info(f"Workflow status update: {status} (phase: {phase})")

        # Broadcast status to all clients
        asyncio.create_task(self.broadcast_message(message))

    async def _handle_client(
            self,
            websocket: websockets.WebSocketServerProtocol,
            path: str):
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
        logger.info("%s", f"New client connected: {client_id}")

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
                    if len(message_data) > self.max_message_size:
                        await self.send_message(client_id, Message(
                            type=MessageType.ERROR_NOTIFICATION,
                            content={"error": "Message exceeds maximum size"}
                        ))
                        continue
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
                            logger.info(
                                "%s", f"Client {client_id} authenticated successfully", )

                            # Set up client preferences if provided
                            client_preferences = message_dict.get(
                                "content", {}).get("preferences", {})
                            if client_preferences:
                                logger.info(
                                    "%s", f"Setting preferences for client {client_id}: {client_preferences}", )
                        else:
                            await self.send_message(client_id, Message(
                                type=MessageType.AUTHENTICATION_RESULT,
                                content={
                                    "success": False,
                                    "error": "Invalid authentication token"
                                }
                            ))
                            logger.warning(
                                "%s", f"Client {client_id} failed authentication")
                        continue

                    # Handle reconnection
                    if message_type == "reconnect":
                        previous_id = message_dict.get(
                            "content", {}).get("previous_id")
                        if previous_id and previous_id in self.authenticated_clients:
                            # Transfer authenticated status
                            self.authenticated_clients.add(client_id)

                            # Send queued messages
                            await self._send_queued_messages(previous_id, client_id)

                            # Transfer state
                            state_data = message_dict.get(
                                "content", {}).get("state", {})
                            if state_data:
                                logger.info(
                                    "%s", f"Received state data from reconnecting client {client_id}", )

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
                            logger.info(
                                "%s", f"Client {client_id} reconnected as {previous_id}")
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
                    logger.error("%s", f"Invalid JSON from client {client_id}")
                    await self.send_message(client_id, Message(
                        type=MessageType.ERROR_NOTIFICATION,
                        content={"error": "Invalid JSON message"}
                    ))
                except Exception as e:
                    logger.error(
                        "%s", f"Error handling message from client {client_id}: {e}")
                    await self.send_message(client_id, Message(
                        type=MessageType.ERROR_NOTIFICATION,
                        content={
                            "error": f"Error processing message: {str(e)}"}
                    ))
        except websockets.exceptions.ConnectionClosed:
            logger.info("%s", f"Client {client_id} disconnected")
        finally:
            # Keep authenticated status for reconnection
            if client_id in self.clients:
                del self.clients[client_id]
            if client_id in self.client_message_counters:
                del self.client_message_counters[client_id]

    async def _handle_sync_request(
            self, client_id: str, message_dict: Dict[str, Any]):
        """Handle a synchronization request.

        Args:
            client_id: The client ID
            message_dict: The message dictionary
        """
        # Get sync markers from client (timestamps, sequence IDs)
        # Extract client-provided synchronization markers if available
        # sync_markers = message_dict.get("content", {}).get("sync_markers", {})
        # TODO: Implement synchronization logic using sync_markers when needed

        # Determine what data needs to be sent
        # This is application-specific, but we'll send back some state for
        # example
        await self.send_message(client_id, Message(
            type=MessageType.UI_STATE_UPDATE,
            content={
                "sync_complete": True,
                "server_time": time.time(),
                # Using time as a placeholder
                "state_hash": str(hash(str(time.time()))),
                "missing_messages": []  # Placeholder
            }
        ))

    async def _handle_preferences_update(
            self, client_id: str, message_dict: Dict[str, Any]):
        """Handle a preferences update request.

        Args:
            client_id: The client ID
            message_dict: The message dictionary
        """
        preferences = message_dict.get("content", {}).get("preferences", {})

        # Process preferences update
        # This is application-specific, but we'll acknowledge for example
        logger.info(
            "%s", f"Updated preferences for client {client_id}: {preferences}"
        )

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
                        if len(
                                counter["batch"]) >= self.rate_limits["batch_size"]:
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
                logger.error("%s", f"Error sending to client {client_id}: {e}")
                return await self._queue_message(client_id, message)
        elif client_id in self.authenticated_clients:
            # Queue for disconnected authenticated client
            return await self._queue_message(client_id, message)
        else:
            logger.warning("%s", f"Client {client_id} not found")
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
            logger.error(
                "%s", f"Error sending batch to client {client_id}: {e}"
            )

            # Try to queue individual messages
            success = True
            for message in batch:
                if not await self._queue_message(client_id, message):
                    success = False
            return success

    async def broadcast_message(
            self,
            message: Message,
            authenticated_only: bool = True):
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
            logger.warning("%s", f"Queue full for client {client_id}")
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
        logger.info("%s", f"Sent {count} queued messages to client {new_id}")
        return count

    async def _clean_expired_queues(self):
        """Periodically clean up expired client message queues."""
        while self.running:
            # Check periodically
            await asyncio.sleep(self.queue_expiry_seconds / 2)
            now = time.time()
            expired_clients = [
                client_id for client_id,
                last_access_time in self.queue_last_access.items() if now -
                last_access_time > self.queue_expiry_seconds]
            for client_id in expired_clients:
                if client_id in self.client_queues:
                    del self.client_queues[client_id]
                if client_id in self.queue_last_access:
                    del self.queue_last_access[client_id]
                logger.info(
                    f"Expired message queue for client {client_id} cleaned up.")

    async def _log_server_metrics(self):  # Correctly defined as async
        """Periodically logs server metrics."""
        try:
            while self.running:  # Check self.running
                # In a real implementation, you would gather and log actual
                # metrics
                active_clients = len(self.clients)
                # Assuming self.message_counter exists or is added
                total_messages_processed = getattr(self, 'message_counter', 0)

                logger.info(f"Server Metrics: Active Clients={active_clients}, "
                            f"Messages Processed={total_messages_processed}")
                # Example: Log queue sizes if relevant
                # for client_id, client_data in self.clients.items():
                #     if 'queue' in client_data and hasattr(client_data['queue'], 'qsize'):
                #          logger.debug(f"Client {client_id}: Queue Size={client_data['queue'].qsize()}")

                await asyncio.sleep(
                    self.config.get("METRICS_LOG_INTERVAL", 60) if hasattr(
                        self, 'config') else 60
                )
        except asyncio.CancelledError:
            logger.info("Metrics logging task was cancelled.")
        except Exception as e:
            logger.error(f"Error in metrics logging task: {e}", exc_info=True)
        finally:
            logger.info("Metrics logging task finished.")

    async def _process_queue(self):  # Renamed from _process_message_queue
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
                logger.error("%s", f"Error processing queue: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """Start the WebSocket server."""
        serve_host = None if self.host and self.host.lower() == "localhost" else self.host
        self.server = await websockets.serve(
            self._handle_client,
            serve_host,  # Use None to listen on all interfaces if original host was 'localhost'
            self.port,
            ping_interval=self.heartbeat_interval,
            ping_timeout=self.heartbeat_interval * 2,
            max_size=self.max_message_size,
        )

        # Get actual port if auto-selected
        for sock in self.server.sockets:
            if isinstance(
                    sock,
                    socket.socket) and sock.family == socket.AF_INET:
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

        if os.name == "posix":  # Restrict permissions for security
            os.chmod(self.connection_file, 0o600)

        # Start tasks
        self.running = True
        self.heartbeat_task = asyncio.create_task(
            self._send_heartbeats())
        self.queue_processor_task = asyncio.create_task(
            self._process_queue())
        self.expiry_cleaner_task = asyncio.create_task(
            self._clean_expired_queues())
        self.metrics_logger_task = asyncio.create_task(
            self._log_server_metrics())

        logger.info(
            "%s",
            (
                f"EnhancedWebSocketServer running on {self.host}:{self.port} "
                f"(listening on {'all interfaces' if serve_host is None else serve_host})"
            ),
        )

    async def stop(self):  # Ensure this is the primary async stop method
        """Gracefully stop the WebSocket server (async version)."""
        if not self.running:
            logger.info("Server is not running.")
            return

        logger.info("Initiating asynchronous server shutdown...")
        self.running = False  # Signal to stop processing new connections/messages

        # Close all client connections
        # Create a list of client IDs to iterate over, as self.clients might
        # change during iteration
        client_ids = list(self.clients.keys())
        for client_id in client_ids:
            websocket = self.clients.get(client_id)
            if websocket and websocket.open:
                try:
                    logger.debug(f"Closing connection to client {client_id}")
                    await websocket.close(code=1001, reason="Server shutting down")
                except Exception as e:
                    logger.warning(
                        f"Error closing client connection {client_id}: {e}")
        self.clients.clear()
        self.authenticated_clients.clear()

        # Cancel background tasks
        tasks_to_cancel = [
            self.heartbeat_task,
            self.queue_processor_task,
            self.expiry_cleaner_task,
            self.metrics_logger_task  # Ensure this task is cancelled
        ]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await task  # Wait for task to acknowledge cancellation
                except asyncio.CancelledError:
                    logger.debug(
                        f"Task {task.get_name()} cancelled successfully.")

        # Close the server itself
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
                logger.info("WebSocket server has been closed.")
            except Exception as e:
                logger.error(f"Error waiting for server to close: {e}")
            self.server = None

        self._remove_connection_info()
        logger.info("WebSocket server shutdown sequence complete.")

    async def _shutdown_server_async(self):
        """Internal async shutdown logic, called by _server_runner's finally block."""
        logger.info("Executing _shutdown_server_async.")
        await self.stop()  # Call the main async stop method

    async def _connection_handler(
            self,
            websocket: websockets.WebSocketServerProtocol,
            path: str):
        """Handle new client connections, authentication, and message routing."""
        client_id = str(uuid.uuid4())
        self.clients[client_id] = websocket
        logger.info(
            "New client connected: %s from %s",
            client_id,
            websocket.remote_address,
        )
        self.scratchpad_log(
            "WebSocket",
            f"Client {client_id} connected from {websocket.remote_address}",
        )

        try:
            # Authentication (optional, based on server config)
            if self.auth_token:
                authenticated = await self._authenticate_client(websocket, client_id)
                if not authenticated:
                    return  # Authentication failed, connection closed by _authenticate_client
            else:
                self.authenticated_clients.add(client_id)
                logger.info(
                    f"Client {client_id} auto-authenticated (no auth token set).")
                self.scratchpad_log(
                    "WebSocket", f"Client {client_id} auto-authenticated.")

            # Restore or create message queue for the client
            self._restore_or_create_client_queue(client_id)

            # Main message loop for this client
            await self._client_handler(websocket, client_id)

        except websockets.exceptions.ConnectionClosedError as e:
            logger.info(
                "Client %s disconnected (ConnectionClosedError): %s %s",
                client_id,
                e.code,
                e.reason,
            )
            self.scratchpad_log(
                "WebSocket",
                f"Client {client_id} disconnected: {e.code}",
            )
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(
                "Client %s disconnected gracefully (ConnectionClosedOK).",
                client_id,
            )
            self.scratchpad_log(
                "WebSocket",
                f"Client {client_id} disconnected gracefully.",
            )
        except Exception as e:
            logger.error(
                f"Error handling client {client_id}: {e}", exc_info=True)
            self.scratchpad_log(
                "WebSocket",
                f"Error with client {client_id}: {e}",
                level="ERROR")
            if websocket.open:
                try:
                    await websocket.close(code=1011, reason="Internal server error")
                except Exception as close_exc:
                    logger.error(
                        f"Error closing websocket for client {client_id} after error: {close_exc}")
        finally:
            self._cleanup_client(client_id)

    async def _authenticate_client(
            self,
            websocket: websockets.WebSocketServerProtocol,
            client_id: str) -> bool:
        """Handle client authentication."""
        # This is a simplified authentication.
        # In a real scenario, you would have a more robust mechanism.
        if self.auth_token:
            try:
                # Example: Expect an auth message from client
                # auth_message_str = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                # auth_data = json.loads(auth_message_str)
                # if auth_data.get("type") == MessageType.AUTHENTICATION_REQUEST.value and \
                #    auth_data.get("payload", {}).get("token") == self.auth_token:
                #    self.authenticated_clients.add(client_id)
                #    await websocket.send(Message(type=MessageType.AUTHENTICATION_RESULT,
                #                                  payload={"success": True}).to_json())
                #    logger.info(f"Client {client_id} authenticated successfully.")
                #    return True
                # else:
                #    await websocket.send(Message(type=MessageType.AUTHENTICATION_RESULT,
                #                                  payload={"success": False, "error": "Invalid token"}).to_json())
                #    logger.warning(f"Client {client_id} authentication failed: Invalid token.")
                #    await websocket.close(code=1008, reason="Authentication failed")
                #    return False

                # For now, if auth_token is present, we assume client will send it or it's handled elsewhere.
                # This part needs to align with the client-side auth flow.
                # If no specific auth message is expected here, we can auto-authenticate if a token exists.
                # This is a placeholder for a more complete auth handshake.
                logger.debug(f"Client {client_id} attempting authentication (token required). "
                             "Placeholder: auto-passing.")
                self.authenticated_clients.add(client_id)  # Placeholder
                # It's better to send an explicit success message if auth is expected
                # await websocket.send(Message(type=MessageType.AUTHENTICATION_RESULT,
                # payload={"success": True}).to_json())
                return True

            except asyncio.TimeoutError:
                logger.warning(
                    f"Client {client_id} timed out during authentication.")
                await websocket.close(code=1008, reason="Authentication timeout")
                return False
            except Exception as e:
                logger.error(
                    f"Error during authentication for client {client_id}: {e}")
                await websocket.close(code=1008, reason="Authentication error")
                return False
        else:
            # No auth token configured on the server, so client is considered
            # authenticated.
            self.authenticated_clients.add(client_id)
            return True

    async def _client_handler(
            self,
            websocket: websockets.WebSocketServerProtocol,
            client_id: str):
        """Handle messages from a single client."""
        async for message_str in websocket:
            if not isinstance(message_str, str):  # Should be string for JSON
                logger.warning(
                    "Received non-string message from %s: %s. Expected JSON string.",
                    client_id,
                    type(message_str),
                )
                # Consider sending an error message back to client
                try:
                    await websocket.send(json.dumps({
                        "type": MessageType.ERROR_NOTIFICATION.value,
                        "payload": {"error": "Invalid message format. Expected JSON string."}
                    }))
                except Exception:  # nosec
                    pass  # Ignore if can't send error
                continue

            # Add rate limiting check if necessary
            # if not self._check_rate_limit(client_id):
            #     logger.warning(f"Rate limit exceeded for client {client_id}")
            #     # Send error and potentially disconnect
            #     continue
            await self._process_incoming_message(client_id, message_str)

    async def _process_incoming_message(
            self, client_id: str, message_str: str):
        """Process a raw message string from a client."""
        try:
            message_data = json.loads(message_str)

            # Validate basic message structure (more specific validation in
            # Message.from_dict)
            if (not isinstance(message_data, dict)
                    or 'type' not in message_data or 'content' not in message_data):
                logger.warning(
                    f"Invalid message structure from {client_id}: {message_str[:200]}")
                # Send error back to client
                error_payload = {
                    "error": "Invalid message structure. 'type' and 'content' are required."}
                await self._send_message_to_client(
                    client_id, Message(
                        type=MessageType.ERROR_NOTIFICATION, content=error_payload)
                )
                return

            # Use Message.from_dict for validation and object creation
            # Assuming schema_validation is True by default in
            # Message.from_dict
            message = Message.from_dict(message_data)
            message.sender_id = client_id  # Ensure sender_id is set

            logger.debug(
                "Received message from %s: Type='%s', ID='%s'",
                client_id,
                message.type.value,
                message.id,
            )

            # Publish to internal message bus
            # The message bus handlers will then decide what to do (e.g.,
            # process, broadcast)
            self.message_bus.publish(message)

        except json.JSONDecodeError:
            logger.error(
                f"Failed to decode JSON message from {client_id}: {message_str[:200]}")
            error_payload = {"error": "Invalid JSON format."}
            await self._send_message_to_client(
                client_id, Message(
                    type=MessageType.ERROR_NOTIFICATION, content=error_payload)
            )
        # Catches invalid MessageType enum or
        # jsonschema.exceptions.ValidationError from Message.from_dict
        except ValueError as e:
            logger.error(f"Invalid message content or type from {client_id}: {e} - "
                         f"Message: {message_str[:200]}")
            error_payload = {
                "error": f"Invalid message content or type: {str(e)}"}
            await self._send_message_to_client(
                client_id, Message(
                    type=MessageType.ERROR_NOTIFICATION, content=error_payload)
            )
        except Exception as e:
            logger.error(f"Unexpected error processing message from {client_id}: {e} - "
                         f"Message: {message_str[:200]}", exc_info=True)
            error_payload = {
                "error": "Internal server error processing message."}
            await self._send_message_to_client(
                client_id, Message(
                    type=MessageType.ERROR_NOTIFICATION, content=error_payload)
            )

    async def _send_heartbeats(self):
        """Periodically send heartbeat messages to clients."""
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)
            client_ids = list(self.clients.keys())
            for client_id in client_ids:
                websocket = self.clients.get(client_id)
                if websocket and websocket.open:
                    try:
                        await websocket.ping()
                        logger.debug(f"Sent ping to client {client_id}")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(
                            f"Heartbeat failed for client {client_id}: Connection closed.")
                        self._cleanup_client(client_id)
                    except Exception as e:
                        logger.error(
                            f"Error sending heartbeat to {client_id}: {e}")
                elif client_id in self.clients:
                    logger.warning(f"Client {client_id} found in self.clients but websocket not open "
                                   "or not found during heartbeat. Cleaning up.")
                    self._cleanup_client(client_id)

    # Ensure scratchpad_log is defined once
    def scratchpad_log(self, component: str, message: str, level: str = "INFO",
                       details: Optional[Dict[str, Any]] = None):
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, f"[{component}] {message}" +
                   (f" Details: {details}" if details else ""))

    async def _send_message_to_client(self, client_id: str, message: Message):
        """Send a message to a specific client."""
        await self.send_message(client_id, message)

    def _restore_or_create_client_queue(self, client_id: str):
        """Restore or create message queue for a client."""
        if client_id not in self.client_queues:
            self.client_queues[client_id] = []
        self.queue_last_access[client_id] = time.time()

    def _cleanup_client(self, client_id: str):
        """Clean up client-related data structures."""
        if client_id in self.clients:
            del self.clients[client_id]
        if client_id in self.client_message_counters:
            del self.client_message_counters[client_id]
        # Note: Keep authenticated status and queues for potential reconnection

    def _write_connection_info(self):
        """Write connection info to a file."""
        info = {
            "host": self.host,
            "port": self.port,
            "auth_token": self.auth_token,
            "pid": os.getpid(),
            "timestamp": time.time()
        }
        try:
            with open(self.connection_file, 'w') as f:
                json.dump(info, f)
            if os.name == 'posix':
                os.chmod(self.connection_file, 0o600)
            logger.info(
                f"WebSocket connection info written to {self.connection_file}")
        except IOError as e:
            logger.error(f"Failed to write connection info: {e}")

    def _remove_connection_info(self):
        """Remove connection info file."""
        try:
            if os.path.exists(self.connection_file):
                os.remove(self.connection_file)
                logger.info(
                    "WebSocket connection info file %s removed.",
                    self.connection_file,
                )
        except IOError as e:
            logger.error(f"Failed to remove connection info file: {e}")

    # The _server_runner, start_in_thread, stop_sync methods are typically at the end
    # or grouped for threading management
    # Ensure they are correctly defined and not causing redefinition issues.
    # ... (rest of the file, ensuring no redefinitions of start, stop, _log_metrics, _process_queue, scratchpad_log) ...

    # Make sure the _server_runner method correctly uses the async tasks
    async def _server_runner(self):
        """Runs the WebSocket server in an asyncio event loop."""
        # self.loop is already set by _run_server_thread_target
        # asyncio.set_event_loop(self.loop) # Not needed here if loop is passed
        # correctly

        serve_host = ('0.0.0.0' if self.host and self.host.lower()
                      in ["localhost", "127.0.0.1"] else self.host)

        logger.info(
            "Attempting to start WebSocket server on %s:%s",
            serve_host,
            self.port,
        )
        # self.stop_event is initialized in start_in_thread before this coro
        # runs

        try:
            server_coro = websockets.serve(
                self._connection_handler,
                serve_host,
                self.port,
                ping_interval=self.heartbeat_interval,
                ping_timeout=self.heartbeat_interval * 2,
                max_size=self.max_message_size,
            )
            # self.server = self.loop.run_until_complete(server_coro) # This
            # was causing loop conflict
            self.server = await server_coro  # Run the coro directly in the current loop

            if self.server and self.server.sockets:
                for sock in self.server.sockets:
                    if isinstance(
                            sock, socket.socket) and sock.family == socket.AF_INET:
                        actual_host, self.port = sock.getsockname()[:2]
                        logger.info(
                            "Server bound to %s:%s. Configured host: %s",
                            actual_host,
                            self.port,
                            self.host,
                        )
                        break

            self._write_connection_info()

            logger.info(
                "EnhancedWebSocketServer running on %s:%s (listening on %s)",
                self.host,
                self.port,
                serve_host or "all interfaces",
            )
            self.scratchpad_log(
                "WebSocket", f"Server started on {self.host}:{self.port}")
            self.running = True

            # Start background tasks in this loop
            self.heartbeat_task = self.loop.create_task(
                self._send_heartbeats())
            self.queue_processor_task = self.loop.create_task(
                self._process_queue())
            self.metrics_logger_task = self.loop.create_task(
                self._log_server_metrics())
            if hasattr(self, '_clean_expired_queues'):
                self.expiry_cleaner_task = self.loop.create_task(
                    self._clean_expired_queues())

            await self.stop_event.wait()

        except OSError as e:
            logger.error(
                "OSError starting WebSocket server on %s:%s: %s",
                serve_host,
                self.port,
                e,
                exc_info=True,
            )
            self.scratchpad_log("WebSocket", f"OSError: {e}", level="ERROR")
            self.running = False  # Ensure running is set to False on error
            raise
        except Exception as e:
            logger.error(
                f"Exception in WebSocket server runner: {e}", exc_info=True)
            self.scratchpad_log(
                "WebSocket", f"Runner Exception: {e}", level="ERROR")
            self.running = False  # Ensure running is set to False on error
        finally:
            logger.info(
                "WebSocket server runner initiating shutdown sequence...")
            self.running = False

            tasks_to_cancel = [
                self.heartbeat_task,
                self.queue_processor_task,  # Corrected name
                self.metrics_logger_task,
            ]
            if hasattr(
                    self,
                    'expiry_cleaner_task') and self.expiry_cleaner_task:
                tasks_to_cancel.append(self.expiry_cleaner_task)

            for task in tasks_to_cancel:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        task_name = (
                            task.get_name() if hasattr(
                                task, 'get_name') else 'Unnamed task')
                        logger.info(f"Task {task_name} cancelled.")
                    except Exception as e_task:
                        logger.error(f"Error cancelling task: {e_task}")

            client_ids = list(self.clients.keys())
            for client_id in client_ids:
                websocket = self.clients.get(client_id)
                if websocket and websocket.open:
                    try:
                        await websocket.close(code=1001, reason="Server shutting down")
                    except Exception as e_close:
                        logger.warning(
                            f"Error closing client {client_id}: {e_close}")
            self.clients.clear()
            self.authenticated_clients.clear()

            if self.server:
                self.server.close()
                await self.server.wait_closed()  # Directly await in the loop
                logger.info("WebSocket server has been closed.")

            self._remove_connection_info()
            # The loop itself will be stopped by _run_server_thread_target's
            # finally block
            logger.info(
                "WebSocket server event loop in thread has finished its tasks.")
            self.scratchpad_log(
                "WebSocket", "Server tasks finished, loop will stop.")

    def start_in_thread(self) -> threading.Thread:
        """Starts the WebSocket server in a new thread."""
        self.loop = asyncio.new_event_loop()  # Create the loop here
        # The stop_event will be created in the thread with the correct loop context

        self.thread = threading.Thread(
            target=self._run_server_thread_target, daemon=True)
        self.thread.start()
        logger.info(
            f"WebSocket server thread started (ID: {self.thread.ident}).")
        self.scratchpad_log("WebSocket", "Server thread started.")
        return self.thread

    def _run_server_thread_target(self):
        """Target function for the server thread. Sets up and runs the asyncio event loop."""
        asyncio.set_event_loop(self.loop)  # Set the loop for this thread
        # Create the stop event in the correct loop context
        self.stop_event = asyncio.Event()
        try:
            self.loop.run_until_complete(self._server_runner())
        except Exception as e:
            logger.error(
                f"Exception in server thread target execution: {e}",
                exc_info=True)
            self.scratchpad_log(
                "WebSocket",
                f"Thread target execution exception: {e}",
                level="ERROR")
        finally:
            logger.info(
                "Server thread target: _server_runner completed. Cleaning up loop.")
            try:
                # Clean up any remaining tasks in the loop before closing
                remaining_tasks = asyncio.all_tasks(loop=self.loop)
                if remaining_tasks:
                    logger.info(
                        "Cancelling %s remaining tasks in server loop...",
                        len(remaining_tasks),
                    )
                    for task in remaining_tasks:
                        task.cancel()
                    self.loop.run_until_complete(asyncio.gather(
                        *remaining_tasks, return_exceptions=True))
                    logger.info("Remaining tasks cancelled.")

                if self.loop.is_running():
                    self.loop.call_soon_threadsafe(
                        self.loop.stop)  # Request loop stop
                    # Give it a moment to stop if it was running something blocking
                    # This is a bit tricky; ideally, all coroutines respect cancellation.
                    # For robust shutdown, run_forever() and explicit stop is better
                    # than run_until_complete on main coro.
                    # However, with stop_event, run_until_complete should exit
                    # when _server_runner finishes.

                # Wait for loop to close fully
                # This might not be strictly necessary if run_until_complete has exited
                # and no other tasks are keeping it alive.
                # Forcing close if it hasn't stopped after a short delay.
                if not self.loop.is_closed():
                    # Give a chance for loop to stop gracefully
                    # self.loop.run_until_complete(asyncio.sleep(0.1,
                    # loop=self.loop)) # if loop is still running
                    self.loop.close()
                    logger.info("Server event loop closed.")
                else:
                    logger.info("Server event loop was already closed.")

            except Exception as e_loop_cleanup:
                logger.error(
                    f"Error during server loop cleanup: {e_loop_cleanup}",
                    exc_info=True)

            logger.info("Server thread target finished.")

    def stop_sync(self, timeout: float = 10.0):
        """Stops the WebSocket server synchronously from any thread."""
        logger.info("Attempting to stop WebSocket server synchronously...")
        self.scratchpad_log("WebSocket", "Attempting synchronous stop...")
        if hasattr(
                self,
                'stop_event') and self.stop_event and hasattr(
                self,
                'loop') and self.loop:
            if not self.stop_event.is_set():  # Check if already set
                self.loop.call_soon_threadsafe(self.stop_event.set)
                logger.info("Stop event set for server loop.")
            else:
                logger.info("Stop event was already set.")
        else:
            logger.warning(
                "Stop event or server loop not found. Server might not have "
                "started correctly or already stopped.")

        if hasattr(self, 'thread') and self.thread and self.thread.is_alive():
            logger.info(
                "Waiting for server thread (ID: %s) to join...",
                self.thread.ident,
            )
            self.thread.join(timeout=timeout)
            if self.thread.is_alive():
                logger.warning(
                    f"Server thread did not join within {timeout}s timeout.")
                self.scratchpad_log(
                    "WebSocket",
                    "Server thread join timeout.",
                    level="WARNING")
            else:
                logger.info("Server thread joined successfully.")
                self.scratchpad_log("WebSocket", "Server thread joined.")
        else:
            logger.info(
                "Server thread not found or not alive. No join needed.")

        self._remove_connection_info()
        logger.info("Synchronous stop sequence complete.")
        self.scratchpad_log("WebSocket", "Synchronous stop complete.")

    # ... (rest of the class) ...
