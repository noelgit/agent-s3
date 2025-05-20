"""VS Code Chat UI Integration Module for Agent-S3."""

import json
import logging
import os
from typing import Dict, Any, Optional, List
import threading
import time
import websockets
import asyncio
from queue import Queue
import uuid  # For session IDs
import atexit

# Message Protocol Definition
MESSAGE_TYPES = {
    "auth": {"desc": "Authenticate client session", "fields": ["token"]},
    "auth_failed": {"desc": "Authentication failed", "fields": ["message"]},
    "connection_established": {"desc": "Connection success", "fields": ["message"]},
    "ping": {"desc": "Heartbeat ping", "fields": []},
    "pong": {"desc": "Heartbeat pong", "fields": ["timestamp"]},
    "status": {"desc": "Backend status", "fields": ["status", "connections"]},
    "plan": {"desc": "Show plan to user", "fields": ["summary", "plan"]},
    "discussion": {"desc": "Show discussion transcript", "fields": ["discussion"]},
    "code": {"desc": "Show code block", "fields": ["code", "language", "file_path"]},
    "diff": {"desc": "Show file diff", "fields": ["diff", "file_path"]},
    "progress": {"desc": "Progress update", "fields": ["phase", "status", "details"]},
    "request_input": {"desc": "Request user input", "fields": ["request"]},
    "approval": {"desc": "Request approval", "fields": ["message", "options"]},
    "response": {"desc": "User response", "fields": ["selection", "input"]},
    "command": {"desc": "Command from client", "fields": ["command", "args"]},
    # Add more as needed
}

# Configure logging
logger = logging.getLogger(__name__)

class VSCodeIntegration:
    """
    Handles communication between Agent-S3 backend and the VS Code extension chat UI.
    
    This class provides methods to send data to the VS Code Chat UI and receive user responses
    through a WebSocket connection.
    """
    
    def __init__(self, port: int = 3939, host: str = "127.0.0.1"):
        """
        Initialize the VS Code Integration.
        
        Args:
            port: WebSocket server port (default: 3939)
            host: WebSocket server host (default: 127.0.0.1/localhost)
        """
        self.port = port
        self.host = host
        self.server = None
        self.active_connections = set()
        self.message_queue = Queue()
        self.response_queue = Queue()
        self.is_running = False
        self.server_thread = None
        self.connect_file_path = self._get_connect_file_path()
        self._atexit_registered = False
        
        # Authentication token for VS Code clients
        self.auth_token = os.getenv('VSCODE_AUTH_TOKEN', None)
        # Map websockets to session info
        self.connection_sessions: Dict[Any, Dict[str, Any]] = {}

    def __enter__(self) -> "VSCodeIntegration":
        """Start the server when entering a context."""
        self.start_server()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Ensure the server is stopped when leaving a context."""
        self.stop_server()
        
    def _get_connect_file_path(self) -> str:
        """Get the path to the VS Code connection file."""
        # Determine the appropriate location based on OS
        if os.name == 'nt':  # Windows
            base_dir = os.path.join(os.environ['APPDATA'], 'agent-s3')
        else:  # Unix/Linux/Mac
            base_dir = os.path.join(os.path.expanduser('~'), '.agent-s3')
            
        # Create directory if it doesn't exist
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            
        return os.path.join(base_dir, 'vscode-connection.json')
    
    def start_server(self) -> bool:
        """
        Start the WebSocket server in a separate thread.
        
        Returns:
            True if server started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("WebSocket server is already running")
            return True
            
        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Wait for server to start up
        time_waited = 0
        while not self.is_running and time_waited < 5:  # Wait up to 5 seconds
            time.sleep(0.1)
            time_waited += 0.1
            
        if not self.is_running:
            logger.error("Failed to start WebSocket server within timeout")
            return False
            
        # Write connection info to file for VS Code to discover
        self._write_connection_info()

        # Ensure server shutdown on process exit
        if not self._atexit_registered:
            atexit.register(self.stop_server)
            self._atexit_registered = True

        logger.info(f"WebSocket server started on {self.host}:{self.port}")
        return True
        
    def _run_server(self) -> None:
        """Run the WebSocket server in the event loop."""
        async def handler(websocket, path):
            """Handle incoming WebSocket connections with authentication and session management."""
            # Authentication handshake
            try:
                auth_msg = await asyncio.wait_for(websocket.recv(), timeout=5)
                auth_data = json.loads(auth_msg)
                if auth_data.get('type') != 'auth' or auth_data.get('token') != self.auth_token:
                    await websocket.send(json.dumps({"type":"auth_failed","message":"Invalid auth token"}))
                    return
                # Register session
                session_id = str(uuid.uuid4())
                self.connection_sessions[websocket] = {"session_id": session_id, "start_time": time.time()}
            except Exception:
                await websocket.close()
                return
            self.active_connections.add(websocket)
            logger.info(f"New VS Code connection established: {path}")
            
            try:
                # Send a welcome message
                await websocket.send(json.dumps({
                    "type": "connection_established",
                    "message": "Connected to Agent-S3 backend"
                }))
                
                # Handle messages from this connection
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        logger.debug(f"Received message from VS Code: {data}")
                        
                        # Handle different message types
                        if data.get("type") == "response":
                            # Put user response in the queue
                            self.response_queue.put(data)
                        elif data.get("type") == "command":
                            # Process commands from VS Code
                            await self._handle_command(websocket, data)
                        else:
                            logger.warning(f"Unknown message type: {data.get('type')}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse message: {message}")
            except websockets.exceptions.ConnectionClosed:
                logger.info("VS Code connection closed")
            finally:
                self.active_connections.remove(websocket)
                
        async def message_sender():
            """Send queued messages to all active connections."""
            while True:
                # Check if there are messages to send
                if not self.message_queue.empty():
                    message = self.message_queue.get()
                    
                    # Send message to all active connections
                    if self.active_connections:
                        websockets_tasks = [
                            websocket.send(json.dumps(message))
                            for websocket in self.active_connections
                        ]
                        await asyncio.gather(*websockets_tasks, return_exceptions=True)
                    else:
                        logger.warning("No active VS Code connections to send message to")
                        
                    self.message_queue.task_done()
                    
                # Sleep to prevent high CPU usage
                await asyncio.sleep(0.1)

        async def heartbeat():
            """Send heartbeat pings and close dead connections."""
            while True:
                to_remove = []
                for ws in list(self.active_connections):
                    try:
                        await ws.send(json.dumps({"type": "ping"}))
                    except Exception:
                        to_remove.append(ws)
                for ws in to_remove:
                    self.active_connections.remove(ws)
                    if ws in self.connection_sessions:
                        del self.connection_sessions[ws]
                await asyncio.sleep(30)  # 30s heartbeat interval

        async def start_server():
            """Start the WebSocket server."""
            # Create server
            self.server = await websockets.serve(
                handler, self.host, self.port
            )
            
            # Start the message sender and heartbeat tasks
            asyncio.create_task(message_sender())
            asyncio.create_task(heartbeat())
            
            # Set running flag
            self.is_running = True
            
            # Keep server running
            await self.server.wait_closed()
            
        # Run the server in the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(start_server())
        except OSError as e:
            logger.error(f"Failed to start WebSocket server: {e}")
        finally:
            self.is_running = False
            loop.close()
            
    async def _handle_command(self, websocket, data: Dict[str, Any]) -> None:
        """
        Handle commands from VS Code.
        
        Args:
            websocket: The WebSocket connection
            data: The command data
        """
        command = data.get("command")
        
        if command == "ping":
            # Respond to ping
            await websocket.send(json.dumps({
                "type": "pong",
                "timestamp": time.time()
            }))
        elif command == "get_status":
            # Respond with current status
            await websocket.send(json.dumps({
                "type": "status",
                "status": "active",
                "connections": len(self.active_connections)
            }))
        else:
            logger.warning(f"Unknown command: {command}")
    
    def _write_connection_info(self) -> None:
        """Write connection information to a file for VS Code to discover."""
        try:
            connection_info = {
                "host": self.host,
                "port": self.port,
                "protocol": "ws",
                "timestamp": time.time()
            }
            
            with open(self.connect_file_path, 'w') as f:
                json.dump(connection_info, f)

            # Restrict permissions on POSIX systems for security
            if os.name == 'posix':
                import stat
                os.chmod(self.connect_file_path, stat.S_IRUSR | stat.S_IWUSR)

            logger.info(
                f"Connection info written to {self.connect_file_path}"
            )
        except Exception as e:
            logger.error(f"Failed to write connection info: {e}")
            
    def stop_server(self) -> None:
        """Stop the WebSocket server."""
        if not self.is_running:
            logger.warning("WebSocket server is not running")
            return
            
        # Close server
        if self.server:
            asyncio.run(self.server.close())
            
        # Wait for server thread to end
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                logger.warning("WebSocket server thread did not terminate")
            self.server_thread = None
            
        self.is_running = False
        logger.info("WebSocket server stopped")
        
        # Remove connection file
        try:
            if os.path.exists(self.connect_file_path):
                os.remove(self.connect_file_path)
                logger.info("Connection file removed")
        except Exception as e:
            logger.error(f"Failed to remove connection file: {e}")
    
    def send_to_chat_ui(self, message: Dict[str, Any]) -> bool:
        """
        Send a message to the VS Code Chat UI.
        
        Args:
            message: The message to send
            
        Returns:
            True if message was queued successfully, False otherwise
        """
        if not self.is_running:
            logger.warning("Cannot send message, WebSocket server is not running")
            return False
            
        try:
            self.message_queue.put(message)
            return True
        except Exception as e:
            logger.error(f"Failed to queue message: {e}")
            return False
    
    def get_user_response(self, request: Dict[str, Any], timeout: int = 300) -> Optional[Dict[str, Any]]:
        """
        Get a response from the user via VS Code Chat UI.
        
        Args:
            request: The request to send to VS Code
            timeout: Maximum time to wait for a response in seconds
            
        Returns:
            User response or None if timeout or error occurred
        """
        if not self.is_running:
            logger.warning("Cannot get user response, WebSocket server is not running")
            return None
            
        # Clear any previous responses
        while not self.response_queue.empty():
            self.response_queue.get()
            
        # Send request
        if not self.send_to_chat_ui({
            "type": "request_input",
            "request": request
        }):
            return None
            
        # Wait for response
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.response_queue.empty():
                    response = self.response_queue.get()
                    return response
                    
                time.sleep(0.1)
                
            logger.warning(f"Timeout waiting for user response after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error getting user response: {e}")
            return None
            
    def display_plan(self, plan: str, summary: str) -> None:
        """
        Display a plan in the VS Code Chat UI.
        
        Args:
            plan: The detailed execution plan
            summary: A summary of the plan
        """
        self.send_to_chat_ui({
            "type": "plan",
            "summary": summary,
            "plan": plan
        })
        
    def display_discussion(self, discussion: str) -> None:
        """
        Display a discussion transcript in the VS Code Chat UI.
        
        Args:
            discussion: The discussion transcript
        """
        self.send_to_chat_ui({
            "type": "discussion",
            "discussion": discussion
        })
        
    def display_code(self, code: str, language: str = "", file_path: str = "") -> None:
        """
        Display code in the VS Code Chat UI.
        
        Args:
            code: The code to display
            language: The language of the code (e.g., "python", "javascript")
            file_path: The path to the file containing the code
        """
        self.send_to_chat_ui({
            "type": "code",
            "code": code,
            "language": language,
            "file_path": file_path
        })
        
    def display_diff(self, diff: str, file_path: str = "") -> None:
        """
        Display a diff in the VS Code Chat UI.
        
        Args:
            diff: The diff to display
            file_path: The path to the file being diffed
        """
        self.send_to_chat_ui({
            "type": "diff",
            "diff": diff,
            "file_path": file_path
        })
        
    def update_progress(self, phase: str, status: str, details: str = "") -> None:
        """
        Update progress in the VS Code Chat UI.
        
        Args:
            phase: The current phase (e.g., "planning", "coding")
            status: The status of the phase (e.g., "started", "completed")
            details: Additional details about the progress
        """
        self.send_to_chat_ui({
            "type": "progress",
            "phase": phase,
            "status": status,
            "details": details
        })
        
    def request_approval(self, message: str, options: List[str] = ["approve", "reject"]) -> Optional[str]:
        """
        Request approval from the user via VS Code Chat UI.
        
        Args:
            message: The message to display to the user
            options: The options to present to the user
            
        Returns:
            The user's selection or None if timeout or error occurred
        """
        response = self.get_user_response({
            "type": "approval",
            "message": message,
            "options": options
        })
        
        if response and "selection" in response:
            return response["selection"]
            
        return None
        
    @staticmethod
    def create_standalone() -> 'VSCodeIntegration':
        """
        Create a standalone VSCodeIntegration instance.
        
        Returns:
            A new VSCodeIntegration instance with server started
        """
        instance = VSCodeIntegration()
        success = instance.start_server()
        
        if not success:
            logger.error("Failed to start VS Code integration server")
            
        return instance
