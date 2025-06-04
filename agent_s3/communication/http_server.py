#!/usr/bin/env python3
"""HTTP server for Agent-S3 communication."""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Agent3HTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Agent-S3."""

    def __init__(self, *args, coordinator=None, **kwargs):
        self.coordinator = coordinator
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use our logger instead of stderr."""
        logger.info("%s - - %s" % (self.address_string(), format % args))

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        mount = getattr(self.server, "mount_path", "")
        mount_no_slash = mount.rstrip("/")

        if mount_no_slash and not parsed.path.startswith(mount_no_slash):
            self.send_error(404)
            return

        rel_path = parsed.path[len(mount_no_slash):] if mount_no_slash else parsed.path

        if mount_no_slash and parsed.path == mount_no_slash:
            self.send_response(301)
            self.send_header("Location", f"{mount_no_slash}/")
            self.end_headers()
            return

        if rel_path == "/health":
            self.send_json({"status": "ok"})
        elif rel_path == "/help":
            result = self.execute_command("/help")
            self.send_json(result)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        """Handle POST requests."""
        mount = getattr(self.server, "mount_path", "")
        mount_no_slash = mount.rstrip("/")
        path = self.path
        if mount_no_slash:
            if not path.startswith(mount_no_slash + "/"):
                self.send_error(404)
                return
            path = path[len(mount_no_slash):]

        if path == "/command":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode("utf-8"))
                command = data.get("command", "")
                result = self.execute_command(command)
                self.send_json(result)
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)
                self.send_json({"error": str(e)}, status=500)
        else:
            self.send_error(404)

    def execute_command(self, command: str) -> Dict[str, Any]:
        """Execute Agent-S3 command and capture output."""
        from contextlib import redirect_stdout
        import io

        output_buffer = io.StringIO()
        try:
            if not self.coordinator:
                # Fallback simple responses if no coordinator
                if command == "/help":
                    from agent_s3.cli import get_help_text
                    return {"result": get_help_text(), "output": "", "success": True}
                elif command == "/config":
                    return {"result": "Agent-S3 Configuration: Ready", "output": "", "success": True}
                elif command.startswith("/plan"):
                    description = command.replace("/plan", "").strip()
                    plan = (
                        f"Plan for: {description}\n1. Analyze requirements\n2. Design solution\n3. Implement\n4. Test"
                    )
                    return {"result": plan, "output": "", "success": True}
                else:
                    return {"result": f"Unknown command: {command}", "output": "", "success": False}

            # Use coordinator's command processor
            if not hasattr(self.coordinator, "command_processor"):
                from agent_s3.command_processor import CommandProcessor

                self.coordinator.command_processor = CommandProcessor(self.coordinator)

            # Handle help command specially
            if command == "/help":
                from agent_s3.cli import get_help_text

                return {"result": get_help_text(), "output": "", "success": True}

            # Process through coordinator's command processor
            from agent_s3.cli.dispatcher import dispatch

            with redirect_stdout(output_buffer):
                result, success = dispatch(self.coordinator.command_processor, command)
            output = output_buffer.getvalue()
            return {"result": result, "output": output, "success": success}

        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            return {"result": f"Error: {str(e)}", "output": output_buffer.getvalue(), "success": False}

    def send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        response = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        self.wfile.write(response)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server with each request handled in a new thread."""

    daemon_threads = True


class EnhancedHTTPServer:
    """Enhanced HTTP server for Agent-S3."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8081,
        coordinator=None,
        mount_path: str = "",
    ):
        self.host = host
        self.port = port
        self.coordinator = coordinator
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

        mount_path = mount_path.strip()
        mount_path = mount_path.rstrip("/")
        if mount_path and not mount_path.startswith("/"):
            mount_path = f"/{mount_path}"
        self.mount_path = mount_path

    def create_handler(self):
        """Create handler class with coordinator reference."""
        coordinator = self.coordinator

        class BoundHandler(Agent3HTTPHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, coordinator=coordinator, **kwargs)

        return BoundHandler

    def start_in_thread(self) -> threading.Thread:
        """Start the HTTP server in a separate thread."""
        if self.running:
            logger.warning("HTTP server is already running")
            return self.server_thread

        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        return self.server_thread

    def _run_server(self) -> None:
        """Run the HTTP server."""
        try:
            handler_class = self.create_handler()
            self.server = ThreadedHTTPServer((self.host, self.port), handler_class)
            self.server.mount_path = self.mount_path
            self.running = True

            # Write connection info for VS Code
            base_url = f"http://{self.host}:{self.port}{self.mount_path or ''}"
            connection_info = {
                "type": "http",
                "host": self.host,
                "port": self.port,
                "base_url": base_url,
            }

            with open(".agent_s3_http_connection.json", "w") as f:
                json.dump(connection_info, f)

            logger.info(f"HTTP server started on http://{self.host}:{self.port}")
            logger.info("Available endpoints: GET /health, GET /help, POST /command")

            self.server.serve_forever()
        except Exception as e:
            logger.error(f"HTTP server error: {e}", exc_info=True)
            self.running = False
        finally:
            self.running = False

    def stop_sync(self) -> None:
        """Stop the HTTP server synchronously."""
        if not self.running or not self.server:
            return

        logger.info("Stopping HTTP server...")
        self.server.shutdown()
        self.server.server_close()
        self.running = False

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)

        logger.info("HTTP server stopped")

    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.stop_sync()
        except Exception:
            pass
