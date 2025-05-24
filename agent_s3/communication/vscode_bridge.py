"""Simplified VS Code bridge used for unit tests."""
import logging
import queue
import threading
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from .message_protocol import Message
from .message_protocol import MessageBus
from .message_protocol import MessageType

logger = logging.getLogger(__name__)


class VSCodeBridgeConfig:
    """Configuration for :class:`VSCodeBridge`."""

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self.enabled = False
        self.prefer_ui = True
        self.show_terminal_output = True
        self.interactive_prompts = True
        self.fallback_to_terminal = True
        self.host = "localhost"
        self.port = 9000
        self.auth_token = None
        self.heartbeat_interval = 15
        self.debug_mode = False
        self.ui_components: Dict[str, bool] = {
            "approval_requests": True,
            "diff_viewer": True,
            "progress_indicators": True,
            "debate_visualization": True,
            "chat_interface": True,
            "file_explorer": False,
            "terminal_output": True,
        }

        if data:
            for key, value in data.items():
                if key == "ui_components" and isinstance(value, dict):
                    self.ui_components.update(value)
                else:
                    setattr(self, key, value)


class VSCodeBridge:
    """Bridge between Agent-S3 and the VS Code extension."""

    def __init__(
        self,
        config: VSCodeBridgeConfig,
        message_bus: MessageBus,
        websocket_server: Any,
    ) -> None:
        self.config = config
        self.message_bus = message_bus
        self.websocket_server = websocket_server

        self.message_queue: queue.Queue[Message] = queue.Queue()
        self.response_events: Dict[str, threading.Event] = {}
        self.response_data: Dict[str, Dict[str, Any]] = {}
        self.active_requests: Dict[str, Dict[str, Any]] = {}

        self.connection_active = False
        self.running = False
        self.server_thread = None
        self.queue_worker_thread = None

        self.metrics = {
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0,
            "approvals_requested": 0,
            "approvals_granted": 0,
            "approvals_denied": 0,
            "connection_attempts": 0,
            "successful_connections": 0,
            "reconnects": 0,
        }

        self.message_bus.register_handler(
            MessageType.USER_RESPONSE, self._handle_user_response
        )

    def initialize(self) -> bool:
        """Start the bridge if enabled."""
        self.metrics["connection_attempts"] += 1
        if not self.config.enabled:
            return False
        try:
            self.server_thread = self.websocket_server.start_in_thread()
            self.connection_active = True
            self.metrics["successful_connections"] += 1
            self.running = True
            self.queue_worker_thread = threading.Thread(
                target=self._queue_worker, daemon=True
            )
            self.queue_worker_thread.start()
            return True
        except Exception as exc:  # pragma: no cover - server errors
            logger.error("Bridge initialization failed: %s", exc)
            self.metrics["errors"] += 1
            return False

    def shutdown(self) -> None:
        """Stop the bridge and worker threads."""
        if self.connection_active:
            try:
                self.websocket_server.stop_from_main_thread()
            except Exception as exc:  # pragma: no cover
                logger.error("Error stopping server: %s", exc)
            self.connection_active = False
        self.running = False
        if self.queue_worker_thread and self.queue_worker_thread.is_alive():
            self.queue_worker_thread.join(timeout=1)

    # Internal helper -----------------------------------------------------
    def _queue_worker(self) -> None:
        while self.running:
            try:
                msg = self.message_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self.message_bus.publish(msg)
            self.metrics["messages_sent"] += 1
            self.message_queue.task_done()

    def _process_message(self, message: Message) -> None:
        if not self.connection_active:
            return
        self.message_queue.put(message)

    def _handle_user_response(self, message: Message) -> None:
        request_id = message.content.get("request_id")
        if request_id in self.response_events:
            self.response_data[request_id] = message.content
            self.response_events[request_id].set()
            self.metrics["approvals_granted"] += 1
            self.metrics["messages_received"] += 1

    # Public send methods ------------------------------------------------
    def send_terminal_output(self, text: str) -> None:
        print(text)
        if not self.connection_active:
            return
        self._process_message(
            Message(MessageType.TERMINAL_OUTPUT, {"text": text})
        )

    def send_approval_request(self, text: str, options: List[str]):
        if not self.connection_active:
            return None
        request_id = f"req-{int(time.time()*1000)}"
        event = threading.Event()
        self.response_events[request_id] = event
        self.active_requests[request_id] = {
            "type": "approval",
            "timestamp": time.time(),
            "text": text,
            "options": options,
        }
        opts = [{"id": o, "label": o} for o in options]
        self.metrics["approvals_requested"] += 1
        self._process_message(
            Message(
                MessageType.INTERACTIVE_APPROVAL,
                {
                    "title": text,
                    "description": text,
                    "options": opts,
                    "request_id": request_id,
                },
            )
        )

        def wait_fn(timeout: Optional[float] = None):
            event.wait(timeout)
            return self.response_data.get(request_id)

        return wait_fn

    def send_diff_display(self, text: str, files: List[Dict[str, Any]], interactive: bool = False):
        if not self.connection_active:
            return None
        msg_type = MessageType.INTERACTIVE_DIFF if interactive else MessageType.DIFF_DISPLAY
        content: Dict[str, Any] = {"text": text, "files": files}
        if interactive:
            content["stats"] = self._compute_diff_stats(files)
        self._process_message(Message(msg_type, content))
        return lambda: None

    # Utility helpers ----------------------------------------------------
    def _extract_before_after(self, diff: str) -> (str, str):
        before_lines: List[str] = []
        after_lines: List[str] = []
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                after_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                before_lines.append(line[1:])
            elif not line.startswith("@@"):
                before_lines.append(line)
                after_lines.append(line)
        return "\n".join(before_lines).strip(), "\n".join(after_lines).strip()

    def _compute_diff_stats(self, files: List[Dict[str, Any]]) -> Dict[str, int]:
        insertions = deletions = 0
        for f in files:
            before = f.get("before", "").splitlines()
            after = f.get("after", "").splitlines()
            insertions += max(len(after) - len(before), 0)
            deletions += max(len(before) - len(after), 0)
        return {
            "files_changed": len(files),
            "insertions": insertions,
            "deletions": deletions,
        }

    def get_metrics(self) -> Dict[str, Any]:
        metrics = self.metrics.copy()
        try:
            bus_metrics = self.message_bus.get_metrics()
            metrics.update({
                "message_bus_messages_published": bus_metrics.get("messages_published", 0),
                "message_bus_messages_handled": bus_metrics.get("messages_handled", 0),
                "message_bus_handler_errors": bus_metrics.get("handler_errors", 0),
            })
        except Exception:
            pass
        return metrics

    def reset_metrics(self) -> None:
        preserved = {
            "connection_attempts": self.metrics["connection_attempts"],
            "successful_connections": self.metrics["successful_connections"],
            "reconnects": self.metrics["reconnects"],
        }
        for key in self.metrics:
            self.metrics[key] = 0
        self.metrics.update(preserved)
        try:
            self.message_bus.reset_metrics()
        except Exception:
            pass
