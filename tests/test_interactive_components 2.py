"""Tests for the interactive components of the VS Code Bridge."""

import unittest
import threading
import time
from unittest.mock import MagicMock, patch

from agent_s3.communication.message_protocol import Message, MessageType, MessageBus
from agent_s3.communication.vscode_bridge import VSCodeBridge
from agent_s3.communication.enhanced_websocket_server import EnhancedWebSocketServer


class TestInteractiveComponents(unittest.TestCase):
    """Test the interactive components of the VS Code Bridge."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create test config
        self.config = {
            "enabled": True,
            "port": 9876,
            "auth_token": "test-token",
            "ui_components": {
                "approval_requests": True,
                "diff_viewer": True,
                "progress_indicators": True,
                "debate_visualization": True
            }
        }
        
        # Create message bus
        self.message_bus = MessageBus()
        
        # Create mock WebSocket server
        self.mock_websocket_server = MagicMock(spec=EnhancedWebSocketServer)
        self.mock_websocket_server.message_bus = self.message_bus
        self.mock_websocket_server.start_in_thread.return_value = MagicMock()
        
        # Create VSCodeBridge
        self.bridge = VSCodeBridge(
            config=self.config,
            message_bus=self.message_bus,
            websocket_server=self.mock_websocket_server
        )
        
        # Activate the bridge
        self.bridge.connection_active = True
    
    def test_interactive_approval(self):
        """Test sending an interactive approval request."""
        # Create interactive approval request
        title = "Confirm Action"
        description = "Do you want to proceed with this action?"
        options = [
            {"id": "yes", "label": "Yes", "shortcut": "Y", "description": "Proceed with the action"},
            {"id": "no", "label": "No", "shortcut": "N", "description": "Cancel the action"},
            {"id": "edit", "label": "Edit", "shortcut": "E", "description": "Edit before proceeding"}
        ]
        
        # Send interactive approval request
        wait_fn = self.bridge.send_interactive_approval(
            title=title,
            description=description,
            options=options
        )
        
        # Verify function was returned
        self.assertIsNotNone(wait_fn)
        
        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)
        
        # Get the message from the queue
        message = self.bridge.message_queue.get()
        
        # Verify message properties
        self.assertEqual(message.type, MessageType.INTERACTIVE_APPROVAL)
        self.assertEqual(message.content["title"], title)
        self.assertEqual(message.content["description"], description)
        self.assertEqual(len(message.content["options"]), 3)
        self.assertEqual(message.content["options"][0]["id"], "yes")
        self.assertEqual(message.content["options"][0]["shortcut"], "Y")
        
        # Verify metrics were updated
        self.assertEqual(self.bridge.metrics["approvals_requested"], 1)
        
        # Simulate a user response
        request_id = message.content["request_id"]
        response = {"request_id": request_id, "option_id": "yes"}
        
        # Set the response data and event
        self.bridge.response_data[request_id] = response
        self.bridge.response_events[request_id].set()
        
        # Get the response
        result = wait_fn()
        
        # Verify response
        self.assertEqual(result["option_id"], "yes")
        
        # Verify metrics were updated
        self.assertEqual(self.bridge.metrics["approvals_granted"], 1)
    
    def test_interactive_diff(self):
        """Test sending an interactive diff display."""
        # Create interactive diff files
        files = [
            {
                "filename": "file1.py",
                "before": "def hello():\n    print('hello')\n",
                "after": "def hello():\n    print('hello, world!')\n",
                "is_new": False
            },
            {
                "filename": "file2.py",
                "before": "",
                "after": "def new_function():\n    return True\n",
                "is_new": True
            }
        ]
        
        # Send interactive diff display
        summary = "Added greeting and new function"
        wait_fn = self.bridge.send_interactive_diff(
            files=files,
            summary=summary
        )
        
        # Verify function was returned
        self.assertIsNotNone(wait_fn)
        
        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)
        
        # Get the message from the queue
        message = self.bridge.message_queue.get()
        
        # Verify message properties
        self.assertEqual(message.type, MessageType.INTERACTIVE_DIFF)
        self.assertEqual(message.content["summary"], summary)
        self.assertEqual(len(message.content["files"]), 2)
        self.assertEqual(message.content["files"][0]["filename"], "file1.py")
        self.assertEqual(message.content["files"][1]["is_new"], True)
        
        # Verify stats were computed
        self.assertIn("stats", message.content)
        self.assertEqual(message.content["stats"]["files_changed"], 2)
        self.assertGreater(message.content["stats"]["insertions"], 0)
    
    def test_progress_indicator(self):
        """Test sending a progress indicator."""
        # Create progress indicator data
        title = "Analyzing Code"
        percentage = 65.5
        description = "Analyzing code structure and dependencies"
        steps = [
            {
                "name": "Parse Files",
                "status": "completed",
                "percentage": 100
            },
            {
                "name": "Extract Dependencies",
                "status": "in_progress",
                "percentage": 75
            },
            {
                "name": "Generate Report",
                "status": "pending",
                "percentage": 0
            }
        ]
        
        # Send progress indicator
        self.bridge.send_progress_indicator(
            title=title,
            percentage=percentage,
            description=description,
            steps=steps,
            estimated_time_remaining=120,
            cancelable=True
        )
        
        # Verify message was queued
        self.assertEqual(self.bridge.message_queue.qsize(), 1)
        
        # Get the message from the queue
        message = self.bridge.message_queue.get()
        
        # Verify message properties
        self.assertEqual(message.type, MessageType.PROGRESS_INDICATOR)
        self.assertEqual(message.content["title"], title)
        self.assertEqual(message.content["percentage"], percentage)
        self.assertEqual(message.content["description"], description)
        self.assertEqual(len(message.content["steps"]), 3)
        self.assertEqual(message.content["steps"][0]["status"], "completed")
        self.assertEqual(message.content["estimated_time_remaining"], 120)
        self.assertEqual(message.content["cancelable"], True)


if __name__ == "__main__":
    unittest.main()