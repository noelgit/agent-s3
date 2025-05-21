"""Simplified WebSocket server used by tests for message streaming."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from .message_protocol import Message, MessageBus, MessageQueue, MessageType

logger = logging.getLogger(__name__)


class EnhancedWebSocketServer:
    """Lightweight WebSocket server implementation for unit tests."""

    def __init__(
        self,
        message_bus: MessageBus,
        host: str = "localhost",
        port: int = 0,
        auth_token: Optional[str] = None,
        heartbeat_interval: int = 15,
        rate_limits: Optional[Dict[str, int]] = None,
        max_queue_size: int = 50,
    ) -> None:
        self.message_bus = message_bus
        self.host = host
        self.port = port
        self.auth_token = auth_token
        self.heartbeat_interval = heartbeat_interval
        self.rate_limits = rate_limits or {"messages_per_second": 5}
        self.max_queue_size = max_queue_size
        self.running = False
        self.server = None
        self.clients: Dict[str, Any] = {}
        self.authenticated_clients: set[str] = set()
        self.client_message_counters: Dict[str, Dict[str, Any]] = {}
        self.client_queues: Dict[str, List[Message]] = {}
        self.message_queue = MessageQueue()
        self.connection_file = ".agent_s3_ws_connection.json"
        self.heartbeat_task = None
        self.queue_processor_task = None
        self.expiry_cleaner_task = None
        self.metrics_logger_task = None

        handlers = {
            MessageType.TERMINAL_OUTPUT: self._handle_terminal_output,
            MessageType.APPROVAL_REQUEST: self._handle_approval_request,
            MessageType.DIFF_DISPLAY: self._handle_diff_display,
            MessageType.LOG_OUTPUT: self._handle_log_output,
            MessageType.DEBATE_CONTENT: self._handle_debate_content,
            MessageType.PROGRESS_UPDATE: self._handle_progress_update,
            MessageType.ERROR_NOTIFICATION: self._handle_error_notification,
            MessageType.INTERACTIVE_DIFF: self._handle_interactive_diff,
            MessageType.INTERACTIVE_APPROVAL: self._handle_interactive_approval,
            MessageType.DEBATE_VISUALIZATION: self._handle_debate_visualization,
            MessageType.PROGRESS_INDICATOR: self._handle_progress_indicator,
            MessageType.CHAT_MESSAGE: self._handle_chat_message,
            MessageType.CODE_SNIPPET: self._handle_code_snippet,
            MessageType.FILE_TREE: self._handle_file_tree,
            MessageType.TASK_BREAKDOWN: self._handle_task_breakdown,
        }
        for mt, handler in handlers.items():
            self.message_bus.register_handler(mt, handler)

    async def start(self) -> None:
        """Start the WebSocket server."""
        import websockets

        self.server = await websockets.serve(self._handle_client, self.host, self.port)
        if self.server.sockets:
            sock = self.server.sockets[0]
            self.port = sock.getsockname()[1]
        info = {
            "host": self.host,
            "port": self.port,
            "auth_token": self.auth_token,
            "protocol": "ws",
        }
        with open(self.connection_file, "w") as f:
            json.dump(info, f)
        self.running = True
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.queue_processor_task = asyncio.create_task(self._queue_processor_loop())
        self.expiry_cleaner_task = asyncio.create_task(self._expiry_cleaner_loop())
        self.metrics_logger_task = asyncio.create_task(self._metrics_logger_loop())

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        if not self.running:
            return
        self.running = False
        tasks = [
            self.heartbeat_task,
            self.queue_processor_task,
            self.expiry_cleaner_task,
            self.metrics_logger_task,
        ]
        await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
        for t in tasks:
            if t:
                t.cancel()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for client in self.clients.values():
            try:
                await client.close()
            except Exception:
                pass
        if os.path.exists(self.connection_file):
            os.remove(self.connection_file)

    async def _heartbeat_loop(self) -> None:
        while self.running:
            await asyncio.sleep(self.heartbeat_interval)

    async def _queue_processor_loop(self) -> None:
        while self.running:
            msg = self.message_queue.dequeue()
            if msg:
                await self.broadcast_message(msg)
            await asyncio.sleep(0.1)

    async def _expiry_cleaner_loop(self) -> None:
        while self.running:
            await asyncio.sleep(60)

    async def _metrics_logger_loop(self) -> None:
        while self.running:
            await asyncio.sleep(60)

    async def _handle_client(self, websocket, path) -> None:
        client_id = str(id(websocket))
        self.clients[client_id] = websocket
        if self.auth_token:
            try:
                raw = await websocket.recv()
                data = json.loads(raw)
                if data.get("type") != "authenticate" or data.get("content", {}).get("token") != self.auth_token:
                    await websocket.close(1008, "Authentication failed")
                    return
            except Exception as e:
                logger.error("Authentication error: %s", e)
                await websocket.close(1008, "Authentication error")
                return
        self.authenticated_clients.add(client_id)
        await websocket.send(json.dumps({"type": "connection_established"}))
        try:
            while True:
                await websocket.recv()
        except Exception as exc:
            logger.error("WebSocket error: %s", exc)
            await websocket.send(json.dumps({"type": "error_notification"}))
        finally:
            self.clients.pop(client_id, None)
            self.authenticated_clients.discard(client_id)

    async def broadcast_message(self, message: Message) -> None:
        for client_id in list(self.authenticated_clients):
            await self.send_message(client_id, message)

    async def send_message(self, client_id: str, message: Message) -> bool:
        if not self._check_rate_limit(client_id):
            return False
        websocket = self.clients.get(client_id)
        if websocket:
            await websocket.send(json.dumps(message.to_dict()))
            return True
        return await self._queue_message(client_id, message)

    def _check_rate_limit(self, client_id: str) -> bool:
        limit = self.rate_limits.get("messages_per_second", 1)
        entry = self.client_message_counters.setdefault(
            client_id, {"count": 0, "last_reset": time.time(), "batch": []}
        )
        now = time.time()
        if now - entry["last_reset"] >= 1:
            entry["count"] = 0
            entry["last_reset"] = now
        entry["count"] += 1
        return entry["count"] <= limit

    async def _send_batch(self, client_id: str) -> None:
        entry = self.client_message_counters.get(client_id)
        if not entry or not entry["batch"]:
            return
        websocket = self.clients.get(client_id)
        if not websocket:
            return
        data = {"type": "batch", "messages": [m.to_dict() for m in entry["batch"]]}
        await websocket.send(json.dumps(data))
        entry["batch"].clear()

    async def _queue_message(self, client_id: str, message: Message) -> bool:
        queue = self.client_queues.setdefault(client_id, [])
        if len(queue) >= self.max_queue_size:
            return False
        queue.append(message)
        return True

    async def _send_queued_messages(self, old_id: str, new_id: str) -> int:
        messages = self.client_queues.pop(old_id, [])
        count = 0
        for msg in messages:
            if await self.send_message(new_id, msg):
                count += 1
        return count

    def _handle_terminal_output(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_approval_request(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_diff_display(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_log_output(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_debate_content(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_progress_update(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_error_notification(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_interactive_diff(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_interactive_approval(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_debate_visualization(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_progress_indicator(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_chat_message(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_code_snippet(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_file_tree(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))

    def _handle_task_breakdown(self, message: Message) -> None:
        asyncio.create_task(self.broadcast_message(message))
