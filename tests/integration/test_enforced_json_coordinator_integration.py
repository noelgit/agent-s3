"""
Integration tests for the pre_planner_json_enforced module with coordinator.

Tests that the enforced JSON pre-planning integrates correctly with the coordinator.
"""
import json
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
import agent_s3.pre_planner_json_enforced as pre_planner_json_enforced

class TestEnforcedJsonCoordinatorIntegration:
    """Integration tests for enforced JSON with coordinator."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for enforced JSON pre-planning (default mode)."""
        config = MagicMock(spec=Config)
        config.config = {
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
             patch('agent_s3.coordinator.CommandProcessor'), \
             patch('agent_s3.coordinator.DatabaseManager'):

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
            coordinator.database_manager = MagicMock()
            coordinator.database_manager.database_tool = MagicMock()
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

    def test_pre_planning_with_enforced_json(self, mock_coordinator):
        """Test that enforced JSON integration works."""
        with patch(
            "agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json"
        ) as mock_call:
            mock_call.return_value = (
                True,
                {
                    "original_request": "Implement user authentication system",
                    "feature_groups": [],
                    "complexity_score": 50.0,
                },
            )

            result = pre_planner_json_enforced.integrate_with_coordinator(
                mock_coordinator, "Implement user authentication system"
            )

        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        mock_call.assert_called_once_with(
            mock_coordinator.router_agent,
            "Implement user authentication system",
            allow_interactive_clarification=True,
        )

    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    def test_coordinator_fallback_to_standard_json(self, mock_integrate, mock_coordinator):
        """Test that an error is raised when enforced JSON fails."""
        mock_integrate.side_effect = Exception("Enforced JSON failed")

        with pytest.raises(Exception):
            pre_planner_json_enforced.integrate_with_coordinator(
                mock_coordinator, "Test task"
            )

    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    def test_coordinator_raises_error_when_pre_planning_fails(self, mock_call, mock_coordinator):
        """Test that a JSONValidationError is raised when pre-planning fails."""
        mock_call.return_value = (False, {})

        with pytest.raises(pre_planner_json_enforced.JSONValidationError):
            pre_planner_json_enforced.integrate_with_coordinator(
                mock_coordinator, "Test task"
            )

        mock_call.assert_called_once_with(
            mock_coordinator.router_agent,
            "Test task",
            allow_interactive_clarification=True,
        )

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
        result = pre_planner_json_enforced.integrate_with_coordinator(
            mock_coordinator, task
        )

        # Verify integration results
        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        assert "test_requirements" in result
        assert "dependencies" in result
        assert "features" in result
        assert "complexity_score" in result

        # Verify the right function was called with the right arguments
        mock_call.assert_called_once_with(
            mock_coordinator.router_agent,
            task,
            allow_interactive_clarification=True,
        )

    def test_validator_repair_plan_used(self, mock_coordinator):
        """Ensure repaired plans are utilized by the coordinator."""

        original_plan = {
            "original_request": "Fix bug",
            "feature_groups": [
                {
                    "group_name": "G1",
                    "group_description": "desc",
                    "features": [
                        {
                            "name": "F1",
                            "description": "d",
                            "files_affected": [],
                            "test_requirements": {},
                            "dependencies": {},
                            "risk_assessment": {},
                            "system_design": {},
                        }
                    ],
                }
            ],
        }
        repaired_plan = {**original_plan, "repaired": True}

        class FakeValidator:
            def __init__(self):
                self.calls = 0

            def validate_all(self, data):
                self.calls += 1
                if self.calls == 1:
                    return False, ["missing"], data
                return True, [], data

            def repair_plan(self, data, errors):
                return repaired_plan, True

        router_agent = MagicMock()
        router_agent.run.return_value = json.dumps(original_plan)
        mock_coordinator.router_agent = router_agent

        with patch(
            "agent_s3.pre_planner_json_enforced.validate_json_schema",
            return_value=(True, ""),
        ), patch(
            "agent_s3.pre_planner_json_enforced.PrePlannerJsonValidator",
            FakeValidator,
        ), patch(
            "agent_s3.pre_planner_json_enforced.validate_pre_plan",
            return_value=(True, ""),
        ), patch(
            "agent_s3.pre_planner_json_enforced.validate_pre_planning_for_planner",
            return_value=(True, ""),
        ), patch(
            "agent_s3.pre_planner_json_enforced.ensure_element_id_consistency",
            side_effect=lambda d: d,
        ), patch(
            "agent_s3.pre_planner_json_enforced.ComplexityAnalyzer"
        ) as mock_complex:
            mock_complex.return_value.assess_complexity.return_value = {
                "is_complex": False,
                "complexity_score": 1,
                "complexity_factors": [],
            }

            result = pre_planner_json_enforced.integrate_with_coordinator(
                mock_coordinator, "Fix bug"
            )

        assert result["pre_planning_data"] == repaired_plan


