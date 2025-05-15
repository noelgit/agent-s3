"""
Integration tests for the pre_planner_json_enforced module with coordinator.

Tests that the enforced JSON pre-planning integrates correctly with the coordinator.
"""

import pytest
import json
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config
from agent_s3.pre_planner_json_enforced import integrate_with_coordinator
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager


class TestEnforcedJsonCoordinatorIntegration:
    """Integration tests for enforced JSON with coordinator."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration with enforced JSON pre-planning enabled."""
        config = MagicMock(spec=Config)
        config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": False,  # Should prioritize enforced JSON
            "workspace_path": "/tmp/test",
            "log_file_path": "/tmp/test/logs",
            "sandbox_environment": True,
            "complexity_threshold": 100.0,
            "context_management": {"enabled": False}
        }
        # Add host_os_type as an attribute, not just in the config dict
        config.host_os_type = "linux"
        config.get_log_file_path.return_value = "/tmp/test/logs/test.log"
        config.github_token = "fake_token"
        return config

    @pytest.fixture
    def mock_router_agent(self):
        """Create a mock router agent that returns fake JSON responses."""
        agent = MagicMock()
        
        # Setup fake JSON response
        json_response = {
            "original_request": "Implement authentication",
            "features": [
                {
                    "name": "User Login",
                    "description": "Implement user login functionality",
                    "test_requirements": {
                        "unit": ["Test password validation"],
                        "integration": ["Test login flow"],
                        "property_based": ["Test with varied inputs"]
                    },
                    "dependencies": {
                        "internal": ["user_model"],
                        "external": ["passlib"]
                    },
                    "acceptance_tests": [
                        {
                            "given": "A user with valid credentials",
                            "when": "The user submits login form",
                            "then": "The user is authenticated and redirected"
                        }
                    ],
                    "end_to_end_system_tests": ["test_complete_login_flow"]
                }
            ],
            "complexity_score": 75.5,
            "complexity_breakdown": {
                "total_lines": 150,
                "total_branches": 30,
                "per_file": {
                    "auth.py": {"lines": 100, "branches": 20}
                },
                "score": 180
            }
        }
        
        # Return as string to simulate LLM response
        agent.call_llm_by_role.return_value = json.dumps(json_response)
        
        return agent

    @pytest.fixture
    def mock_coordinator(self, mock_config, mock_router_agent):
        """Create a mock coordinator with necessary components for testing."""
        # Create mock scratchpad
        scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        
        # Create mock progress tracker
        progress_tracker = MagicMock()
        
        # Create and patch coordinator
        with patch('agent_s3.coordinator.TaskStateManager'), \
             patch('agent_s3.coordinator.WorkspaceInitializer'), \
             patch('agent_s3.coordinator.TechStackDetector'), \
             patch('agent_s3.coordinator.FileHistoryAnalyzer'), \
             patch('agent_s3.coordinator.DebuggingManager'), \
             patch('agent_s3.coordinator.CommandProcessor'):
            
            coordinator = Coordinator(config=mock_config)
            
            # Replace with mocks
            coordinator.scratchpad = scratchpad
            coordinator.progress_tracker = progress_tracker
            coordinator.router_agent = mock_router_agent
            
            # Patch any init-related methods to prevent errors
            coordinator.file_tool = MagicMock()
            coordinator.bash_tool = MagicMock()
            coordinator.git_tool = MagicMock()
            coordinator.code_analysis_tool = MagicMock()
            coordinator.embedding_client = MagicMock()
            coordinator.memory_manager = MagicMock()
            coordinator.database_tool = MagicMock()
            coordinator.env_tool = MagicMock()
            coordinator.test_frameworks = MagicMock()
            coordinator.test_critic = MagicMock()
            coordinator.test_planner = MagicMock()
            coordinator.error_context_manager = MagicMock()
            coordinator.tech_stack_detector = MagicMock()
            coordinator.workspace_initializer = MagicMock()
            coordinator.file_history_analyzer = MagicMock()
            coordinator.debugging_manager = MagicMock()
            coordinator.planner = MagicMock()
            coordinator.design_manager = MagicMock()
            coordinator.implementation_manager = MagicMock()
            coordinator.deployment_manager = MagicMock()
            coordinator.code_generator = MagicMock()
            coordinator.prompt_moderator = MagicMock()
            coordinator.pre_planner = MagicMock()
            coordinator.task_resumer = MagicMock()
            coordinator.persona_debate = MagicMock()
            coordinator.command_processor = MagicMock()
            
            yield coordinator

    def test_execute_pre_planning_phase_with_enforced_json(self, mock_coordinator):
        """Test that coordinator correctly uses enforced JSON pre-planning when enabled."""
        # Execute pre-planning with a test task
        task_description = "Implement user authentication system"
        result = mock_coordinator._execute_pre_planning_phase(task_description)
        
        # Verify results
        assert result["success"] is True
        assert result["status"] == "completed"
        assert "uses_enforced_json" in result
        assert result["uses_enforced_json"] is True
        
        # Verify the call to router_agent was made
        mock_coordinator.router_agent.call_llm_by_role.assert_called_once()
        
        # Verify progress tracker was updated
        mock_coordinator.progress_tracker.update_progress.assert_called()
        
        # Extract the first update_progress call arguments
        first_call_args = mock_coordinator.progress_tracker.update_progress.call_args_list[0][0][0]
        
        # Verify pre-planning was started
        assert first_call_args["phase"] == "pre_planning"
        assert first_call_args["status"] == "started"
        
        # Extract the second update_progress call arguments
        second_call_args = mock_coordinator.progress_tracker.update_progress.call_args_list[1][0][0]
        
        # Verify pre-planning was completed
        assert second_call_args["phase"] == "pre_planning"
        assert second_call_args["status"] == "completed"
        assert second_call_args["json_formatted"] is True
        assert second_call_args["enforced_json"] is True

    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    def test_coordinator_fallback_to_standard_json(self, mock_integrate, mock_coordinator):
        """Test that coordinator falls back to standard JSON when enforced JSON fails."""
        # Make enforced JSON fail
        mock_integrate.side_effect = Exception("Enforced JSON failed")
        
        # Setup standard JSON to succeed
        with patch('agent_s3.pre_planner_json.integrate_with_pre_planning_manager') as mock_standard_json:
            mock_standard_json.return_value = {
                "status": "completed",
                "success": True,
                "complexity_score": 50.0,
                "json_formatted": True
            }
            
            # Enable standard JSON as fallback
            mock_coordinator.config.config["use_json_pre_planning"] = True
            
            # Execute pre-planning
            result = mock_coordinator._execute_pre_planning_phase("Test task")
            
            # Verify standard JSON was used as fallback
            assert result["success"] is True
            assert result["status"] == "completed"
            assert "uses_enforced_json" not in result
            assert mock_standard_json.called
            
            # Verify progress tracker was updated with fallback info
            second_call_args = mock_coordinator.progress_tracker.update_progress.call_args_list[1][0][0]
            assert second_call_args["json_formatted"] is True
            assert not second_call_args.get("enforced_json", False)

    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    @patch('agent_s3.pre_planner_json.integrate_with_pre_planning_manager')
    def test_coordinator_fallback_to_standard_planning(self, mock_standard_json, mock_enforced_json, mock_coordinator):
        """Test that coordinator falls back to standard planning when both JSON formats fail."""
        # Make both JSON formats fail
        mock_enforced_json.side_effect = Exception("Enforced JSON failed")
        mock_standard_json.side_effect = Exception("Standard JSON failed")
        
        # Setup mocks for standard planning
        mock_coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]
        mock_coordinator.pre_planner.estimate_complexity_from_request.return_value = {"risk": "medium"}
        mock_coordinator.pre_planner.get_complexity_breakdown.return_value = {
            "total_lines": 100, 
            "total_branches": 20
        }
        mock_coordinator.pre_planner.identify_test_requirements.return_value = ["Test requirement 1"]
        mock_coordinator.pre_planner.analyze_dependencies.return_value = {"internal": ["dep1"]}
        
        # Enable both JSON formats to test complete fallback
        mock_coordinator.config.config["use_json_pre_planning"] = True
        mock_coordinator.config.config["use_enforced_json_pre_planning"] = True
        
        # Execute pre-planning
        result = mock_coordinator._execute_pre_planning_phase("Test task")
        
        # Verify standard planning was used
        assert result["success"] is True
        assert result["status"] == "completed"
        assert "impacted_files" in result
        assert "complexity_score" in result
        assert "test_requirements" in result
        assert "dependencies" in result
        
        # Verify both JSON methods were attempted
        assert mock_enforced_json.called
        assert mock_standard_json.called
        
        # Verify standard pre-planning methods were called
        assert mock_coordinator.pre_planner.collect_impacted_files.called
        assert mock_coordinator.pre_planner.estimate_complexity_from_request.called
        assert mock_coordinator.pre_planner.get_complexity_breakdown.called

    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    def test_direct_integration_with_coordinator(self, mock_call, mock_coordinator):
        """Test direct integration between pre_planner_json_enforced and coordinator."""
        task = "Implement new authentication feature"
        
        # Setup mock for call_pre_planner_with_enforced_json
        json_data = {
            "original_request": task,
            "features": [
                {
                    "name": "Test Feature",
                    "description": "Test Description",
                    "test_requirements": {
                        "unit": ["Test validation"],
                        "integration": ["Test flow"],
                        "property_based": ["Test inputs"]
                    },
                    "dependencies": {
                        "internal": ["user_model"],
                        "external": ["auth_lib"]
                    },
                    "acceptance_tests": [
                        {
                            "given": "Valid credentials",
                            "when": "Submit login",
                            "then": "Authenticated"
                        }
                    ],
                    "end_to_end_system_tests": ["test_login"]
                }
            ],
            "complexity_score": 75,
            "complexity_breakdown": {
                "total_lines": 150,
                "total_branches": 30,
                "per_file": {},
                "score": 180
            }
        }
        mock_call.return_value = (True, json_data)
        
        # Call the integration function directly
        result = integrate_with_coordinator(mock_coordinator, task)
        
        # Verify integration results
        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        assert "test_requirements" in result
        assert "dependencies" in result
        assert "features" in result
        assert "complexity_score" in result
        
        # Verify the right function was called with the right arguments
        mock_call.assert_called_once_with(mock_coordinator.router_agent, task)


if __name__ == "__main__":
    pytest.main(["-xvs", "test_enforced_json_coordinator_integration.py"])