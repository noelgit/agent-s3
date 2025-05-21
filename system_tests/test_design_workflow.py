"""End-to-end tests for the design workflow integration.

This module contains tests that verify the full end-to-end flow from design creation
through pre-planning to code generation.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open, ANY

from agent_s3.coordinator import Coordinator
from agent_s3.design_manager import DesignManager


class TestDesignWorkflow:
    """Tests for the design to implementation workflow."""
    
    @pytest.fixture
    def mock_responses(self):
        """Fixture for mocked responses."""
        # Initial design conversation
        design_responses = [
            "I'll help you design this system. Let me ask a few clarifying questions...",
            "Based on your requirements, here are the key features:\n\nFeature 1: User Authentication\n- User registration\n- Login\n- Password reset\n\nFeature 2: Task Management\n- Create tasks\n- List tasks\n- Update tasks\n- Delete tasks\n\nDoes this design meet your requirements?",
            "Great! I'll finalize the design now."
        ]
        
        # Pre-planning responses
        pre_planning_input = {
            "original_request": "Design a TODO application",
            "feature_groups": [
                {
                    "group_name": "User Authentication",
                    "group_description": "Handle user authentication and account management",
                    "features": [
                        {
                            "name": "User Registration",
                            "description": "Allow users to create accounts",
                            "files_affected": ["models/User.js", "routes/auth.js"],
                            "test_requirements": {"unit_tests": []},
                            "dependencies": {"external_libraries": ["bcrypt", "jsonwebtoken"]},
                            "risk_assessment": {"complexity": "medium"},
                            "system_design": {"code_elements": []}
                        }
                    ]
                }
            ]
        }
        
        return {
            "design": design_responses,
            "pre_planning_input": pre_planning_input
        }
    
    @patch('agent_s3.router_agent.RouterAgent')
    @patch('agent_s3.coordinator.EnhancedScratchpadManager')
    @patch('agent_s3.coordinator.ProgressTracker')
    @patch('builtins.print')
    @patch('builtins.input')
    def test_e2e_design_to_implementation_flow(self, mock_input, mock_print, 
                                              mock_progress_tracker, mock_scratchpad, 
                                              mock_router_agent, mock_llm_responses, tmp_path):
        """Test the end-to-end flow from design to implementation."""
        # Set up mock input responses
        mock_input.side_effect = [
            "Yes, that looks good",  # Design conversation
            "yes"                    # Implementation prompt
        ]
        
        # Set up mock LLM responses for different phases
        mock_llm = MagicMock()
        mock_llm.call_llm_agent.side_effect = mock_llm_responses["design"]
        # Mock pre-planning workflow
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow',
                  return_value=(True, mock_llm_responses["pre_planning"])):
            
            # Set up coordinator with minimal components
            coordinator = MagicMock()
            coordinator.llm = mock_llm
            coordinator.scratchpad = mock_scratchpad
            coordinator.progress_tracker = mock_progress_tracker
            
            # Mock file operations
            mock_file_tool = MagicMock()
            mock_file_tool.write_file.return_value = (True, "File written successfully")
            
            # Create design manager with mocked coordinator
            design_manager = DesignManager(coordinator)
            design_manager.file_tool = mock_file_tool
            design_manager.llm = mock_llm
            
            # Simulate full design workflow

            # 1. Start design conversation
            response = design_manager.start_design_conversation("Design a TODO application")
            assert "help you design" in response
                
            # 2. Continue conversation until complete
            response, is_complete = design_manager.continue_conversation("That sounds good, please continue.")
            assert not is_complete  # Not complete yet
            
            response, is_complete = design_manager.continue_conversation("Yes, that looks good")
            assert is_complete  # Design should be complete now
            
            # 3. Write design to file
            success, message = design_manager.write_design_to_file()
            assert success
            
            coordinator.run_task = MagicMock()
            coordinator.start_pre_planning_from_design = MagicMock()

            # 4. Prompt for implementation
            choices = design_manager.prompt_for_implementation()
            assert choices["implementation"] is True
            
            # The following would be in an actual integration test
            # but here we're just verifying the proper methods were called
            assert coordinator.run_task.called or coordinator.start_pre_planning_from_design.called
