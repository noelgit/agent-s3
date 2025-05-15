"""
Tests for the coordinator's pre-planning JSON enforcement functionality.

Tests that verify the coordinator correctly prioritizes and uses enforced JSON pre-planning.
"""

import pytest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

from agent_s3.coordinator import Coordinator
from agent_s3.pre_planner_json_enforced import integrate_with_coordinator


class TestCoordinatorJsonPrePlanning:
    """Tests for the coordinator's pre-planning functionality with JSON enforcement."""
    
    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    @patch('agent_s3.pre_planner_json.integrate_with_pre_planning_manager')
    def test_execute_pre_planning_phase_prioritizes_enforced_json(self, mock_std_json, mock_enforced_json):
        """Test that coordinator prioritizes enforced JSON when both are enabled."""
        # Setup for the test
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True  # Both enabled
        }
        coordinator.scratchpad = MagicMock()
        coordinator.progress_tracker = MagicMock()
        coordinator.pre_planner = MagicMock()
        
        # Mock the enforced JSON integration to return success
        mock_enforced_json.return_value = {
            "status": "completed",
            "success": True,
            "complexity_score": 50,
            "uses_enforced_json": True
        }
        
        # Original method to intercept to avoid testing everything
        original_method = Coordinator._execute_pre_planning_phase
        
        try:
            # Mock the pre-planning method to call our implementation
            task_description = "Test task"
            result = original_method(coordinator, task_description)
            
            # Verify that enforced JSON was called and standard JSON was not
            mock_enforced_json.assert_called_once()
            mock_std_json.assert_not_called()
            
            # Verify the result
            assert result.get("status") == "completed"
            assert result.get("success") is True
            assert result.get("uses_enforced_json") is True
            
        except Exception as e:
            # Restore original method and re-raise if there's an error
            pytest.fail(f"Test failed: {str(e)}")
    
    @patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator')
    @patch('agent_s3.pre_planner_json.integrate_with_pre_planning_manager')
    def test_fallback_to_standard_json_when_enforced_fails(self, mock_std_json, mock_enforced_json):
        """Test that coordinator falls back to standard JSON when enforced JSON fails."""
        # Setup for the test
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True  # Both enabled
        }
        coordinator.scratchpad = MagicMock()
        coordinator.progress_tracker = MagicMock()
        coordinator.pre_planner = MagicMock()
        
        # Make enforced JSON fail
        mock_enforced_json.side_effect = Exception("Enforced JSON failed")
        
        # Make standard JSON succeed
        mock_std_json.return_value = {
            "status": "completed",
            "success": True,
            "complexity_score": 50,
            "json_formatted": True
        }
        
        # Original method to patch
        original_method = Coordinator._execute_pre_planning_phase
        
        try:
            # Mock the pre-planning method to call our implementation
            task_description = "Test task"
            result = original_method(coordinator, task_description)
            
            # Verify that enforced JSON was attempted
            mock_enforced_json.assert_called_once()
            
            # Verify that standard JSON was used as fallback
            mock_std_json.assert_called_once()
            
            # Verify the result
            assert result.get("status") == "completed"
            assert result.get("success") is True
            assert result.get("json_formatted") is True
            
        except Exception as e:
            # Re-raise if there's an error
            pytest.fail(f"Test failed: {str(e)}")
    
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

    def test_execute_pre_planning_phase_with_updated_complexity(self):
        """Test that updated complexity scoring is reflected in JSON pre-planning."""
        # Setup for the test
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True
        }
        coordinator.pre_planner.assess_complexity.return_value = {
            "score": 60,
            "is_complex": True
        }

        # Mock enforced JSON integration
        with patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator') as mock_enforced_json:
            mock_enforced_json.return_value = {
                "status": "completed",
                "success": True,
                "complexity_score": 60,
                "uses_enforced_json": True
            }

            # Execute
            result = coordinator._execute_pre_planning_phase("Test task")

            # Verify
            assert result["success"] is True
            assert result["complexity_score"] == 60
            mock_enforced_json.assert_called_once()

    def test_execute_pre_planning_phase_with_caching(self):
        """Test that caching is applied to pre-planning phase."""
        # Setup for the test
        coordinator = MagicMock()
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "use_enforced_json_pre_planning": True,
            "use_json_pre_planning": True
        }
        coordinator.pre_planner.collect_impacted_files = MagicMock()
        coordinator.pre_planner.collect_impacted_files.return_value = ["file1.py", "file2.py"]

        # Mock enforced JSON integration
        with patch('agent_s3.pre_planner_json_enforced.integrate_with_coordinator') as mock_enforced_json:
            mock_enforced_json.return_value = {
                "status": "completed",
                "success": True,
                "complexity_score": 60,
                "uses_enforced_json": True
            }

            # Execute twice to test caching
            result1 = coordinator._execute_pre_planning_phase("Test task")
            result2 = coordinator._execute_pre_planning_phase("Test task")

            # Verify
            assert result1["success"] is True
            assert result2["success"] is True
            coordinator.pre_planner.collect_impacted_files.assert_called_once()  # Cached result used
            mock_enforced_json.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-xvs", "test_coordinator_json_preplanning.py"])