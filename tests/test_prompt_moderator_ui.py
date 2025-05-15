"""Tests for the enhanced UI integration in PromptModerator."""

import unittest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

from agent_s3.prompt_moderator import PromptModerator
from agent_s3.communication.vscode_bridge import VSCodeBridge
from agent_s3.communication.message_protocol import MessageType


class TestPromptModeratorUI(unittest.TestCase):
    """Test the enhanced UI integration in PromptModerator."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create mock coordinator
        self.coordinator = MagicMock()
        self.coordinator.scratchpad = MagicMock()
        
        # Create PromptModerator
        self.moderator = PromptModerator(coordinator=self.coordinator)
        
        # Create mock VSCodeBridge
        self.vscode_bridge = MagicMock(spec=VSCodeBridge)
        self.vscode_bridge.connection_active = True
        self.vscode_bridge.config = MagicMock()
        self.vscode_bridge.config.prefer_ui = True
        self.vscode_bridge.config.enabled = True
        
        # Set up VSCodeBridge in moderator
        self.moderator.set_vscode_bridge(self.vscode_bridge)
    
    def test_present_plan_with_interactive_approval(self):
        """Test presenting a plan with interactive approval request."""
        # Mock response
        mock_response = {"option_id": "yes"}
        self.vscode_bridge.send_interactive_approval.return_value = lambda: mock_response
        
        # Test presenting plan
        plan = "Step 1: Do something\nStep 2: Do something else"
        summary = "A plan to do things"
        
        approved, final_plan = self.moderator.present_plan(plan, summary)
        
        # Verify interactive approval was used
        self.vscode_bridge.send_interactive_approval.assert_called_once()
        args = self.vscode_bridge.send_interactive_approval.call_args[1]
        
        self.assertEqual(args["title"], "Plan Approval Required")
        self.assertTrue("Summary: A plan to do things" in args["description"])
        self.assertEqual(len(args["options"]), 3)
        self.assertEqual(args["options"][0]["id"], "yes")
        
        # Verify result
        self.assertTrue(approved)
        self.assertEqual(final_plan, plan)
    
    def test_present_patch_with_interactive_diff(self):
        """Test presenting a patch with interactive diff."""
        # Set up coordinator mock for diff computation
        file_content = "def test():\n    return True"
        self.coordinator.config.config = {"project_root": "/test"}
        
        # Mock file operations
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch.object(self.moderator, "_compute_diffs") as mock_compute_diffs, \
             patch.object(self.moderator, "_extract_before_after_content") as mock_extract:
            
            # Mock diff computation
            mock_compute_diffs.return_value = {
                "test.py": "diff content for test.py"
            }
            
            # Mock before/after extraction
            mock_extract.return_value = ("old content", "new content")
            
            # Mock response
            mock_response = {"response": "yes"}
            self.vscode_bridge.send_interactive_diff.return_value = lambda: mock_response
            
            # Test presenting patch
            changes = {"test.py": file_content}
            result = self.moderator.present_patch_with_diff(changes, iteration=1)
            
            # Verify interactive diff was used
            self.vscode_bridge.send_interactive_diff.assert_called_once()
            args = self.vscode_bridge.send_interactive_diff.call_args[1]
            
            self.assertEqual(args["summary"], "Code Changes (Iteration 1)")
            self.assertEqual(len(args["files"]), 1)
            self.assertEqual(args["files"][0]["filename"], "test.py")
            self.assertEqual(args["files"][0]["before"], "old content")
            self.assertEqual(args["files"][0]["after"], "new content")
            
            # Verify result
            self.assertTrue(result)
    
    def test_show_progress_with_progress_indicator(self):
        """Test showing progress with progress indicator."""
        # Set up progress tracking
        self.moderator.setup_progress_tracking([
            "Planning", 
            "Implementation", 
            "Testing"
        ])
        
        # Show progress for first step
        self.moderator.show_progress("Planning in progress", 0.5)
        
        # Verify progress indicator was used with correct steps
        args = self.vscode_bridge.send_progress_indicator.call_args_list[1][1]
        self.assertEqual(args["title"], "Task Progress")
        self.assertEqual(args["description"], "Planning in progress")
        self.assertEqual(len(args["steps"]), 3)
        self.assertEqual(args["steps"][0]["name"], "Planning")
        self.assertEqual(args["steps"][0]["status"], "in_progress")
        self.assertEqual(args["steps"][1]["status"], "pending")
        
        # Complete first step and move to second
        self.moderator.show_progress("Planning completed", 1.0)
        args = self.vscode_bridge.send_progress_indicator.call_args_list[2][1]
        
        # Verify step status transitions
        for step in args["steps"]:
            if step["name"] == "Planning":
                self.assertEqual(step["status"], "completed")
                self.assertEqual(step["percentage"], 100)
                
        # Show progress for second step
        self.moderator.show_progress("Implementation in progress", 0.3)
        
        # Verify correct overall progress calculation
        args = self.vscode_bridge.send_progress_indicator.call_args_list[3][1]
        self.assertGreater(args["percentage"], 33)  # Should be more than 1/3 complete
    
    def test_display_discussion_with_debate_visualization(self):
        """Test displaying discussion with debate visualization."""
        # Create mock discussion with personas
        discussion = """## Engineer Perspective:
We should implement this using a service-based architecture.

## Designer Perspective:
The UI should be minimal and focus on usability.

## Final Consensus:
We'll use a service architecture with a clean, minimal UI."""
        
        plan = "Step 1: Design services\nStep 2: Implement UI"
        
        # Display discussion and plan
        self.moderator.display_discussion_and_plan(discussion, plan)
        
        # Verify debate visualization was used
        self.vscode_bridge.send_debate_visualization.assert_called_once()
        args = self.vscode_bridge.send_debate_visualization.call_args[1]
        
        self.assertEqual(args["title"], "Implementation Strategy Debate")
        self.assertEqual(len(args["personas"]), 3)  # Engineer, Designer, Consensus
        self.assertEqual(len(args["phases"]), 2)    # Discussion and Consensus
        self.assertTrue("service architecture with a clean, minimal UI" in args["consensus"])


if __name__ == "__main__":
    unittest.main()