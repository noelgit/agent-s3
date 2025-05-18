"""
Tests for the coordinator's pre-planning JSON enforcement functionality.

Tests that verify the coordinator correctly prioritizes and uses enforced JSON pre-planning.
"""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.pre_planner_json_enforced import integrate_with_coordinator


class TestCoordinatorJsonPrePlanning:
    """Tests for the coordinator's pre-planning functionality with JSON enforcement."""
    
    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    def test_pre_planning_prioritizes_enforced_json(self, mock_enforced_json):
        """Test that enforced JSON integration is used."""
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True
        }

        mock_enforced_json.return_value = {
            "status": "completed",
            "success": True,
            "complexity_score": 50,
            "uses_enforced_json": True,
        }

        result = integrate_with_coordinator(coordinator, "Test task")

        mock_enforced_json.assert_called_once()
        assert result.get("status") == "completed"
        assert result.get("success") is True
        assert result.get("uses_enforced_json") is True
    
    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    def test_fallback_to_standard_json_when_enforced_fails(self, mock_enforced_json):
        """Test that errors propagate when enforced JSON fails."""
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True,
        }

        mock_enforced_json.side_effect = Exception("Enforced JSON failed")

        with pytest.raises(Exception):
            integrate_with_coordinator(coordinator, "Test task")
    
    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    def test_direct_integration_function(self, mock_call):
        """Test the integration function directly."""
        # Setup mock for call_pre_planner_with_enforced_json
        json_data = {
            "original_request": "Test task",
            "features": [
                {
                    "name": "Feature",
                    "description": "Description",
                    "test_requirements": {
                        "unit": ["Test validation"],
                        "integration": ["Test flow"],
                        "property_based": ["Test inputs"]
                    },
                    "dependencies": {
                        "internal": ["model"],
                        "external": ["lib"]
                    },
                    "acceptance_tests": [
                        {
                            "given": "Condition",
                            "when": "Action",
                            "then": "Result"
                        }
                    ],
                    "end_to_end_system_tests": ["test_flow"]
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
        
        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.router_agent = MagicMock()
        
        # Call the integration function directly
        task = "Test task"
        result = integrate_with_coordinator(mock_coordinator, task)
        
        # Verify the call to call_pre_planner_with_enforced_json
        mock_call.assert_called_once_with(mock_coordinator.router_agent, task)
        
        # Verify the result
        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        assert "test_requirements" in result
        assert "dependencies" in result
        assert "features" in result
        assert "complexity_score" in result
    
    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    def test_updated_test_requirements_integration(self, mock_call):
        """Test that updated test requirements are correctly integrated."""
        # Setup mock for call_pre_planner_with_enforced_json
        json_data = {
            "original_request": "Test task",
            "features": [
                {
                    "name": "Feature",
                    "description": "Description",
                    "test_requirements": {
                        "unit": ["Test validation"],
                        "integration": ["Test flow"],
                        "property_based": ["Test inputs"],
                        "acceptance": [
                            {
                                "given": "Condition",
                                "when": "Action",
                                "then": "Result"
                            }
                        ],
                        "approval_baseline": ["Baseline test"]
                    },
                    "dependencies": {
                        "internal": ["model"],
                        "external": ["lib"]
                    },
                    "acceptance_tests": [
                        {
                            "given": "Condition",
                            "when": "Action",
                            "then": "Result"
                        }
                    ],
                    "end_to_end_system_tests": ["test_flow"]
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

        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.router_agent = MagicMock()

        # Call the integration function directly
        task = "Test task"
        result = integrate_with_coordinator(mock_coordinator, task)

        # Verify the call to call_pre_planner_with_enforced_json
        mock_call.assert_called_once_with(mock_coordinator.router_agent, task)

        # Verify the result
        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        assert "test_requirements" in result
        assert "approval_baseline" in result["test_requirements"]
        assert result["test_requirements"]["approval_baseline"] == ["Baseline test"]

    def test_pre_planning_with_updated_complexity(self):
        """Test that complexity scoring is reflected in results."""
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True,
        }
        coordinator.pre_planner.assess_complexity.return_value = {
            "score": 60,
            "is_complex": True,
        }

        with patch(
            'agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json'
        ) as mock_call:
            mock_call.return_value = (
                True,
                {
                    "original_request": "Test task",
                    "feature_groups": [],
                    "complexity_score": 60,
                },
            )

            result = integrate_with_coordinator(coordinator, "Test task")

        assert result["success"] is True
        assert result["complexity_score"] == 60
        mock_call.assert_called_once_with(coordinator.router_agent, "Test task")

    def test_pre_planning_with_repeated_calls(self):
        """Test repeated integration calls."""
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True,
        }

        with patch(
            'agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json'
        ) as mock_call:
            mock_call.return_value = (
                True,
                {
                    "original_request": "Test task",
                    "feature_groups": [],
                    "complexity_score": 60,
                },
            )

            result1 = integrate_with_coordinator(coordinator, "Test task")
            result2 = integrate_with_coordinator(coordinator, "Test task")

        assert result1 == result2
        assert mock_call.call_count == 2


