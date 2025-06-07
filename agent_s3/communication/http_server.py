#!/usr/bin/env python3
"""HTTP server for Agent-S3 communication."""

import json
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
from uuid import uuid4
from typing import Any, Dict, Optional
import hmac

logger = logging.getLogger(__name__)


class Agent3HTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Agent-S3."""

    def __init__(self, *args, coordinator=None, allowed_origins=None, jobs=None, job_lock=None, auth_token=None, **kwargs):
        self.coordinator = coordinator
        # Default to allow any origin for backward compatibility
        self.allowed_origins = allowed_origins or ["*"]
        self.jobs = jobs if jobs is not None else {}
        self.job_lock = job_lock or threading.Lock()
        self.auth_token = auth_token
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use our logger instead of stderr."""
        logger.info("%s - - %s" % (self.address_string(), format % args))

    def _authorized(self) -> bool:
        """Check Authorization header against configured token."""
        if not self.auth_token:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header.split(" ", 1)[1]
            try:
                return hmac.compare_digest(token, self.auth_token)
            except Exception:
                return False
        return False

    def do_GET(self) -> None:
        """Handle GET requests."""
        if not self._authorized():
            self.send_json({"error": "Unauthorized"}, status=401)
            return
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json({"status": "ok"})
        elif parsed.path == "/help":
            result = self.execute_command("/help")
            self.send_json(result)
        else:
            self.send_error(404)

    def _run_async_job(self, job_id: str, command: str) -> None:
        """Execute a command asynchronously and store the result."""
        result = self.execute_command(command)
        with self.job_lock:
            self.jobs[job_id] = result

    def do_POST(self) -> None:
        """Handle POST requests."""
        if not self._authorized():
            self.send_json({"error": "Unauthorized"}, status=401)
            return
        if self.path == "/command":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode("utf-8"))
                command = data.get("command", "")
                if data.get("async"):
                    job_id = str(uuid4())
                    threading.Thread(
                        target=self._run_async_job,
                        args=(job_id, command),
                        daemon=True,
                    ).start()
                    self.send_json({"job_id": job_id})
                else:
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

        origin = self.headers.get("Origin")
        allow_origin = None
        if "*" in self.allowed_origins:
            allow_origin = "*"
        elif origin and origin in self.allowed_origins:
            allow_origin = origin

        if allow_origin:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Content-Type, Authorization",
            )

        self.end_headers()

        self.wfile.write(response)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight."""
        origin = self.headers.get("Origin")
        allow_origin = None
        if "*" in self.allowed_origins:
            allow_origin = "*"
        elif origin and origin in self.allowed_origins:
            allow_origin = origin

        self.send_response(200)
        if allow_origin:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
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
        allowed_origins=None,
        auth_token: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.coordinator = coordinator
        self.allowed_origins = allowed_origins or ["*"]
        self.auth_token = auth_token
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_lock = threading.Lock()
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.running = False

    def create_handler(self):
        """Create handler class with coordinator reference."""
        coordinator = self.coordinator
        allowed_origins = self.allowed_origins
        jobs = self.jobs
        job_lock = self.job_lock
        auth_token = self.auth_token

        class BoundHandler(Agent3HTTPHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(
                    *args,
                    coordinator=coordinator,
                    allowed_origins=allowed_origins,
                    jobs=jobs,
                    job_lock=job_lock,
                    auth_token=auth_token,
                    **kwargs,
                )

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

            connection_file = ".agent_s3_http_connection.json"
            if os.name == "nt":
                with open(connection_file, "w") as f:
                    json.dump(connection_info, f)
            else:
                fd = os.open(
                    connection_file,
                    os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                    0o600,
                )
                with os.fdopen(fd, "w") as f:
                    json.dump(connection_info, f)

            # Set restrictive permissions on non-Windows systems
            if os.name != "nt":
                try:
                    os.chmod(connection_file, 0o600)
                except OSError:
                    logger.warning(
                        "Unable to set permissions on %s", connection_file, exc_info=True
                    )

            logger.info(f"HTTP server started on http://{self.host}:{self.port}")
            logger.info(
                "Available endpoints: GET /health, GET /help, POST /command"
            )

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
