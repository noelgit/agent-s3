"""VS Code bridge for communication between the agent and VS Code extension."""
import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

try:
    from agent_s3.message_bus import Message, MessageBus, MessageType
except ImportError:
    # Patch: Provide dummy MessageBus and MessageType for test isolation
    class Message:
        pass
    class MessageBus:
        def publish(self, message):
            pass
        def register_handler(self, *args, **kwargs):
            pass
    class MessageType:
        USER_RESPONSE = 1

logger = logging.getLogger(__name__)

class WebSocketServer:
    """WebSocket server for communication with VS Code extension."""
    
    def __init__(self, message_bus: MessageBus, port: int, auth_token: Optional[str] = None):
        """Initialize WebSocket server.
        
        Args:
            message_bus: Message bus for communication with the agent
            port: Port to listen on
            auth_token: Optional authentication token
        """
        self.message_bus = message_bus
        self.port = port
        self.auth_token = auth_token
        self.websocket = None
        
    async def start(self):
        """Start the WebSocket server."""
        import websockets
        
        # Define connection handler
        async def handler(websocket, path):
            logger.info(f"Client connected from {websocket.remote_address}")
            
            # Authenticate the client
            if self.auth_token:
                try:
                    auth_message = await websocket.recv()
                    auth_data = json.loads(auth_message)
                    if "auth_token" not in auth_data or auth_data["auth_token"] != self.auth_token:
                        logger.warning("Authentication failed")
                        await websocket.close(1008, "Authentication failed")
                        return
                except Exception as e:
                    logger.error(f"Authentication error: {e}")
                    await websocket.close(1008, "Authentication error")
                    return
                
                logger.info("Client authenticated")
            
            self.websocket = websocket
            
            # Process incoming messages
            try:
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        # Process message from VS Code extension
                        logger.debug(f"Received message: {data}")
                        await self._process_message(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {message}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            except websockets.exceptions.ConnectionClosed:
                logger.info("Client disconnected")
            finally:
                self.websocket = None
                
        # Start server
        start_server = websockets.serve(handler, "localhost", self.port)
        await start_server
    
    async def _process_message(self, data: Dict[str, Any]):
        """Process a message from the VS Code extension.
        
        Args:
            data: Message data
        """
        if "type" not in data:
            logger.warning("Message missing type field")
            return
        
        # Convert to internal message format and publish to the message bus
        message_type = data.get("type")
        content = data.get("content", {})
        
        # Map message types
        internal_message_type = None
        if message_type == "user_response":
            internal_message_type = MessageType.USER_RESPONSE
        
        if internal_message_type:
            message = Message(internal_message_type, content)
            self.message_bus.publish(message)
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    async def send_message(self, message_type: str, content: Dict[str, Any] = None):
        """Send a message to the VS Code extension.
        
        Args:
            message_type: Type of message to send
            content: Message content
        """
        if not self.websocket:
            logger.warning("No WebSocket connection available")
            return
        
        message = {
            "type": message_type,
            "content": content or {},
            "timestamp": int(time.time())
        }
        
        try:
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message: {e}")


class VSCodeBridge:
    """Bridge between the agent and VS Code extension."""
    
    def __init__(self, message_bus: MessageBus, websocket_port: int = 0, auth_token: Optional[str] = None):
        """Initialize the VS Code bridge.
        
        Args:
            message_bus: Message bus for communication with the agent
            websocket_port: Port for WebSocket server (0 = auto-assign)
            auth_token: Optional authentication token
        """
        self.message_bus = message_bus
        
        # Generate a random auth token if none is provided
        if not auth_token and websocket_port != 0:
            import secrets
            auth_token = secrets.token_hex(16)
            
        # Create WebSocket server
        self.websocket_server = WebSocketServer(
            message_bus=message_bus,
            port=websocket_port,
            auth_token=auth_token
        )
        
        # Create connection file
        self._create_connection_file(websocket_port, auth_token)
        
        # Start WebSocket server
        asyncio.create_task(self.websocket_server.start())
        logger.info(f"VS Code bridge initialized with WebSocket on port {websocket_port}")
        
        # Register handlers for extension communication
        self._setup_message_handlers()
    
    def _create_connection_file(self, port: int, auth_token: Optional[str]) -> None:
        """Create a connection file for the VS Code extension to use.
        
        Args:
            port: The WebSocket port
            auth_token: The authentication token
        """
        connection_info = {
            "host": "localhost",
            "port": port,
            "auth_token": auth_token or "",
            "timestamp": int(time.time()),
            "protocol": "ws"
        }
        
        # Save to a file in the workspace root
        try:
            # Try to get workspace root
            workspace_root = os.getcwd()
            connection_file = os.path.join(workspace_root, ".agent_s3_ws_connection.json")
            
            with open(connection_file, "w") as f:
                json.dump(connection_info, f)

            # Restrict permissions on POSIX systems for security
            if os.name == "posix":
                import stat
                os.chmod(connection_file, stat.S_IRUSR | stat.S_IWUSR)

            logger.info(
                f"Created WebSocket connection file at {connection_file}"
            )
        except (OSError, ValueError) as e:
            logger.error(f"Failed to create WebSocket connection file: {e}")
            raise
    
    def _setup_message_handlers(self) -> None:
        """Set up handlers for extension messages."""
        # Register handlers for user responses from the extension
        self.message_bus.register_handler(MessageType.USER_RESPONSE, self._handle_user_response)
    
    def _handle_user_response(self, message: Message) -> None:
        """Handle user response messages from the extension.
        
        Args:
            message: The message from the extension
        """
        # Process user responses from the UI
        logger.debug(f"Received user response: {message.content}")
        # Further processing would be implemented here
