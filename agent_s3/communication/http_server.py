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

        if parsed.path == "/health":
            self.send_json({"status": "ok"})
        elif parsed.path == "/help":
            result = self.execute_command("/help")
            self.send_json({"result": result})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/command":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode("utf-8"))
                command = data.get("command", "")
                result = self.execute_command(command)
                self.send_json({"result": result})
            except Exception as e:
                logger.error(f"Error processing command: {e}", exc_info=True)
                self.send_json({"error": str(e)}, status=500)
        else:
            self.send_error(404)

    def execute_command(self, command: str) -> str:
        """Execute Agent-S3 command."""
        try:
            if not self.coordinator:
                # Fallback simple responses if no coordinator
                if command == "/help":
                    from agent_s3.cli import get_help_text

                    return get_help_text()
                elif command == "/config":
                    return "Agent-S3 Configuration: Ready"
                elif command.startswith("/plan"):
                    description = command.replace("/plan", "").strip()
                    return f"Plan for: {description}\n1. Analyze requirements\n2. Design solution\n3. Implement\n4. Test"
                else:
                    return f"Unknown command: {command}"

            # Use coordinator's command processor
            if not hasattr(self.coordinator, "command_processor"):
                from agent_s3.command_processor import CommandProcessor

                self.coordinator.command_processor = CommandProcessor(self.coordinator)

            # Handle help command specially
            if command == "/help":
                from agent_s3.cli import get_help_text

                return get_help_text()

            # Process through coordinator's command processor
            from agent_s3.cli.dispatcher import dispatch

            result = dispatch(self.coordinator.command_processor, command)
            return result if result else f"Command '{command}' executed successfully"

        except Exception as e:
            logger.error(f"Error executing command '{command}': {e}", exc_info=True)
            return f"Error: {str(e)}"

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

    def __init__(self, host: str = "localhost", port: int = 8081, coordinator=None):
        self.host = host
        self.port = port
        self.coordinator = coordinator
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

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
            self.running = True

            # Write connection info for VS Code
            connection_info = {
                "type": "http",
                "host": self.host,
                "port": self.port,
                "base_url": f"http://{self.host}:{self.port}",
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
