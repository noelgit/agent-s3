#!/usr/bin/env python3
"""
Start the Agent-S3 WebSocket server for VS Code extension integration.
This script creates the necessary connection file and starts the server.
"""

import asyncio
import json
import logging
import sys
import os
import signal
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer
from agent_s3.communication.message_protocol import MessageBus
from agent_s3.coordinator import Coordinator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_connection_file(host="localhost", port=8765, auth_token="agent-s3-dev-token"):
    """Create the connection file needed by the VS Code extension."""
    connection_file = Path(".agent_s3_ws_connection.json")
    
    config = {
        "host": host,
        "port": port,
        "auth_token": auth_token,
        "protocol": "ws",
        "version": "1.0.0"
    }
    
    with open(connection_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    logger.info(f"Created connection file: {connection_file.absolute()}")
    return config

def main():
    """Start the Agent-S3 system with WebSocket server."""
    
    # Configuration
    host = "localhost"
    port = 8765
    auth_token = "agent-s3-dev-token"
    
    try:
        # Create connection file for VS Code extension
        config = create_connection_file(host, port, auth_token)
        
        # Create a temporary config file with WebSocket settings
        import tempfile
        import json
        
        config_data = {
            "WEBSOCKET_HOST": host,
            "WEBSOCKET_PORT": port,
            "WEBSOCKET_AUTH_TOKEN": auth_token
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_config_path = f.name
        
        logger.info("=" * 60)
        logger.info("🚀 Starting FULL Agent-S3 System")
        logger.info("=" * 60)
        logger.info(f"📡 Server URL: ws://{host}:{port}")
        logger.info(f"🔑 Auth Token: {auth_token}")
        logger.info(f"📄 Connection File: {Path('.agent_s3_ws_connection.json').absolute()}")
        logger.info("=" * 60)
        
        # Create the REAL Agent-S3 coordinator with full functionality
        logger.info("🧠 Initializing REAL Agent-S3 Coordinator...")
        coordinator = Coordinator(config_path=temp_config_path)
        logger.info("✅ Agent-S3 Coordinator initialized successfully!")
        logger.info("📡 WebSocket server started automatically by coordinator!")
        logger.info("💡 FULL Agent-S3 system is now available via WebSocket!")
        logger.info("🔌 Install the extension: agent-s3-working-0.1.0.vsix")
        logger.info("💬 Open chat window: Ctrl+Shift+P → 'Agent-S3: Open Chat Window'")
        logger.info("📋 Try typing: /help, or any Agent-S3 task!")
        logger.info("🚀 You now have access to ALL Agent-S3 functionality!")
        logger.info("=" * 60)
        logger.info("Server is running. Press Ctrl+C to stop.")
        
        # Setup graceful shutdown
        def signal_handler(signum, frame):
            logger.info("🛑 Received shutdown signal, stopping Agent-S3...")
            coordinator.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the coordinator running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Agent-S3...")
    except Exception as e:
        logger.error(f"❌ Agent-S3 startup error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if 'coordinator' in locals():
            coordinator.shutdown()
        if 'temp_config_path' in locals():
            try:
                os.unlink(temp_config_path)
            except:
                pass
        logger.info("✅ Agent-S3 stopped.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")