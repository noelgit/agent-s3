"""
Unit tests for the feature-based workflow in Coordinator.

Tests the new feature-based iterative approach to task execution.
"""

import pytest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

from agent_s3.coordinator import Coordinator
from agent_s3.enhanced_scratchpad_manager import LogLevel


class TestFeatureBasedWorkflow:
    """Test the feature-based workflow in the Coordinator."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator with all required components."""
        coordinator = MagicMock(spec=Coordinator)
        
        # Mock the enhanced scratchpad
        coordinator.scratchpad = MagicMock()
        coordinator.scratchpad.log = MagicMock()
        
        # Mock the progress tracker
        coordinator.progress_tracker = MagicMock()
        coordinator.progress_tracker.update_progress = MagicMock()
        
        # Mock the prompt moderator
        coordinator.prompt_moderator = MagicMock()
        coordinator.prompt_moderator.ask_binary_question = MagicMock(return_value=True)  # User confirms
        
        # Mock the config
        coordinator.config = MagicMock()
        coordinator.config.config = {
            "complexity_threshold": 100.0,
            "max_attempts": 2
        }
        
        # Mock the methods used in the new consolidated workflow
        coordinator._validate_pre_planning_data = MagicMock(return_value=True)
        coordinator._regenerate_pre_planning_with_modifications = MagicMock()
        coordinator._present_pre_planning_results_to_user = MagicMock(return_value=("yes", None))
        coordinator._apply_changes_and_manage_dependencies = MagicMock(return_value=True)
        coordinator._run_validation_phase = MagicMock(return_value=(True, "validation", "All checks passed"))
        coordinator._finalize_task = MagicMock()
        coordinator.run_persona_debate = MagicMock()
        coordinator.code_generator = MagicMock()
        coordinator.error_context_manager = MagicMock()
        
        # Mock feature_group_processor
        coordinator.feature_group_processor = MagicMock()
        coordinator.feature_group_processor.process_pre_planning_output = MagicMock()
        coordinator.feature_group_processor.present_consolidated_plan_to_user = MagicMock(return_value=("yes", None))
        coordinator.feature_group_processor.update_plan_with_modifications = MagicMock()
        
        return coordinator

    @pytest.fixture
    def sample_pre_planning_result(self):
        """Create a sample pre-planning result with multiple features."""
        return {
            "success": True,
            "status": "completed",
            "complexity_score": 120.0,
            "features": [
                {
                    "name": "Feature 1",
                    "description": "Description of feature 1",
                    "test_requirements": {
                        "unit": ["Test 1.1", "Test 1.2"],
                        "integration": ["Integration test 1"],
                        "property_based": []
                    },
                    "dependencies": {
                        "internal": ["dep1"],
                        "external": ["ext1"]
                    },
                    "acceptance_tests": [
                        {
                            "given": "Condition 1",
                            "when": "Action 1",
                            "then": "Result 1"
                        }
                    ]
                },
                {
                    "name": "Feature 2",
                    "description": "Description of feature 2",
                    "test_requirements": {
                        "unit": ["Test 2.1"],
                        "integration": [],
                        "property_based": ["Property test 2"]
                    },
                    "dependencies": {
                        "internal": ["dep2"],
                        "external": []
                    },
                    "acceptance_tests": []
                }
            ],
            "test_requirements": {
                "needed_test_types": ["unit", "integration", "property-based"]
            }
        }

    def test_run_task_with_feature_groups(self, mock_coordinator, sample_pre_planning_result):
        """Test that run_task processes feature groups using the consolidated workflow."""
        # Configure pre-planning mocks
        from agent_s3.pre_planner_json_enforced import pre_planning_workflow
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, sample_pre_planning_result)
            
            # Configure mocks for feature group processing
            feature_groups_result = {
                "success": True,
                "feature_group_results": {
                    "feature_group_0": {
                        "success": True,
                        "feature_group": {"group_name": "Feature Group 1"},
                        "consolidated_plan": {
                            "architecture_review": {"logical_gaps": []},
                            "implementation_plan": {
                                "file1.py": [{"function": "function1()"}],
                                "file2.py": [{"function": "function2()"}]
                            },
                            "tests": {"unit_tests": []}
                        }
                    },
                    "feature_group_1": {
                        "success": True,
                        "feature_group": {"group_name": "Feature Group 2"},
                        "consolidated_plan": {
                            "architecture_review": {"logical_gaps": []},
                            "implementation_plan": {
                                "file3.py": [{"function": "function3()"}]
                            },
                            "tests": {"unit_tests": []}
                        }
                    }
                }
            }
            mock_coordinator.feature_group_processor.process_pre_planning_output.return_value = feature_groups_result
            
            # Call the run_task method
            mock_coordinator.run_task("Implement new features")
            
            # Verify interactions with feature_group_processor
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_called_once_with(
                sample_pre_planning_result, "Implement new features"
            )
            
            # Verify plan presentation was called for each feature group
            assert mock_coordinator.feature_group_processor.present_consolidated_plan_to_user.call_count == 2
            
            # Verify progress tracking was updated correctly
            mock_coordinator.progress_tracker.update_progress.assert_any_call(
                {"phase": "feature_group_processing", "status": "completed"}
            )

    def test_warning_for_high_complexity_many_feature_groups(self, mock_coordinator, sample_pre_planning_result):
        """Test that a warning is shown for high complexity with many feature groups."""
        # Modify the sample to have high complexity and many feature groups
        high_complexity_data = {
            "success": True,
            "status": "completed",
            "complexity_score": 150.0,  # Above threshold
            "feature_groups": []
        }
        
        # Add multiple feature groups to exceed thresholds
        for i in range(1, 6):  # 5 feature groups
            high_complexity_data["feature_groups"].append({
                "group_name": f"Feature Group {i}",
                "group_description": f"Description of feature group {i}",
                "features": [
                    {"name": f"Feature {i}.1", "files_affected": [f"file{i}_1.py"]},
                    {"name": f"Feature {i}.2", "files_affected": [f"file{i}_2.py"]}
                ]
            })
        
        # Configure pre-planning to return high complexity data
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, high_complexity_data)
            
            # Configure warning confirmation
            mock_coordinator.prompt_moderator.ask_binary_question.return_value = True  # User confirms complex task
            
            # Mock feature group processing to succeed
            feature_groups_result = {
                "success": True,
                "feature_group_results": {}
            }
            
            # Add a result for each feature group
            for i in range(1, 6):
                feature_groups_result["feature_group_results"][f"feature_group_{i-1}"] = {
                    "success": True,
                    "feature_group": {"group_name": f"Feature Group {i}"},
                    "consolidated_plan": {
                        "architecture_review": {"logical_gaps": []},
                        "implementation_plan": {f"file{i}.py": [{"function": f"function{i}()"}]},
                        "tests": {"unit_tests": []}
                    }
                }
            
            mock_coordinator.feature_group_processor.process_pre_planning_output.return_value = feature_groups_result
            
            # Call run_task
            mock_coordinator.run_task("Implement complex feature groups")
            
            # Verify that user was asked for confirmation due to high complexity
            mock_coordinator.prompt_moderator.ask_binary_question.assert_called_once()
            
            # Verify feature_group_processor was called with the pre-planning data
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_called_once_with(
                high_complexity_data, "Implement complex feature groups"
            )
            
            # Verify each feature group plan was presented to the user
            assert mock_coordinator.feature_group_processor.present_consolidated_plan_to_user.call_count == 5
    
    def test_complexity_check_user_proceed(self, mock_coordinator):
        """Test that a complex task prompts the user and proceeds when the user chooses 'yes'."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,  # Explicitly marked as complex
            "complexity_score": 8.5,  # Above complexity threshold
            "feature_groups": [{
                "group_name": "Complex Feature",
                "group_description": "A complex feature requiring confirmation",
                "features": [
                    {"name": "Complex Feature 1", "files_affected": ["complex.py"]}
                ]
            }]
        }
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, complex_task_data)
            
            # Mock feature group processing to succeed
            feature_groups_result = {
                "success": True,
                "feature_group_results": {
                    "feature_group_0": {
                        "success": True,
                        "feature_group": {"group_name": "Complex Feature"},
                        "consolidated_plan": {
                            "architecture_review": {"logical_gaps": []},
                            "implementation_plan": {"complex.py": [{"function": "complex_function()"}]},
                            "tests": {"unit_tests": []}
                        }
                    }
                }
            }
            mock_coordinator.feature_group_processor.process_pre_planning_output.return_value = feature_groups_result
            
            # Configure user to PROCEED with complex task (first ask_ternary_question for complexity warning)
            mock_coordinator.prompt_moderator.ask_ternary_question.side_effect = ["yes", "yes"]
            
            # Call run_task
            mock_coordinator.run_task("Implement complex feature")
            
            # Verify complexity warning was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                f"Task assessed as complex (Score: 8.5)",
                level=any
            )
            
            # Verify user was asked for confirmation due to complexity
            mock_coordinator.prompt_moderator.ask_ternary_question.assert_any_call(
                "How would you like to proceed?"
            )
            
            # Verify feature group processing was called after user confirmed
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_called_once_with(
                complex_task_data, "Implement complex feature"
            )
            
            # Verify plan presentation occurred
            mock_coordinator.feature_group_processor.present_consolidated_plan_to_user.assert_called_once()
    
    def test_complexity_check_user_modify(self, mock_coordinator):
        """Test that a complex task terminates when the user chooses 'modify'."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 9.0,
            "feature_groups": [{
                "group_name": "Complex Feature",
                "group_description": "A complex feature requiring modification",
                "features": [
                    {"name": "Complex Feature 1", "files_affected": ["complex.py"]}
                ]
            }]
        }
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, complex_task_data)
            
            # Configure user to choose MODIFY for complex task
            mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
            
            # Call run_task
            mock_coordinator.run_task("Implement complex feature for modification")
            
            # Verify complexity warning was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                f"Task assessed as complex (Score: 9.0)",
                level=any
            )
            
            # Verify user was asked for confirmation
            mock_coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with(
                "How would you like to proceed?"
            )
            
            # Verify user's decision to modify was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                "User chose to refine the request.",
                level=any
            )
            
            # Verify feature group processing was NOT called
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()
    
    def test_complexity_check_user_cancel(self, mock_coordinator):
        """Test that a complex task terminates when the user chooses 'no'."""
        # Create complex task data
        complex_task_data = {
            "success": True,
            "status": "completed",
            "is_complex": True,
            "complexity_score": 9.5,
            "feature_groups": [{
                "group_name": "Complex Feature",
                "group_description": "A complex feature to be cancelled",
                "features": [
                    {"name": "Complex Feature 1", "files_affected": ["complex.py"]}
                ]
            }]
        }
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, complex_task_data)
            
            # Configure user to choose NO (cancel) for complex task
            mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "no"
            
            # Call run_task
            mock_coordinator.run_task("Implement complex feature to cancel")
            
            # Verify complexity warning was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                f"Task assessed as complex (Score: 9.5)",
                level=any
            )
            
            # Verify user was asked for confirmation
            mock_coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with(
                "How would you like to proceed?"
            )
            
            # Verify user's decision to cancel was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                "User cancelled the complex task.",
                level=any
            )
            
            # Verify feature group processing was NOT called
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()
    
    def test_complexity_check_fallback_score(self, mock_coordinator):
        """Test that tasks with high fallback complexity scores are also flagged."""
        # Create task data with high fallback complexity score
        complex_task_data = {
            "success": True,
            "status": "completed",
            "complexity_score": 7.5,  # Just above the threshold
            "feature_groups": [{
                "group_name": "Feature",
                "group_description": "A feature with high fallback complexity score",
                "features": [
                    {"name": "Feature 1", "files_affected": ["feature.py"]}
                ]
            }]
        }
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, complex_task_data)
            
            # Configure user to PROCEED with task
            mock_coordinator.prompt_moderator.ask_ternary_question.side_effect = ["yes", "yes"]
            
            # Configure feature group processing to succeed
            feature_groups_result = {
                "success": True,
                "feature_group_results": {
                    "feature_group_0": {
                        "success": True,
                        "feature_group": {"group_name": "Feature"},
                        "consolidated_plan": {
                            "architecture_review": {"logical_gaps": []},
                            "implementation_plan": {"feature.py": [{"function": "feature_function()"}]},
                            "tests": {"unit_tests": []}
                        }
                    }
                }
            }
            mock_coordinator.feature_group_processor.process_pre_planning_output.return_value = feature_groups_result
            
            # Call run_task
            mock_coordinator.run_task("Implement feature with high fallback complexity")
            
            # Verify complexity warning was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                f"Task assessed as complex (Score: 7.5)",
                level=any
            )
            
            # Verify user was asked for confirmation due to high fallback complexity
            mock_coordinator.prompt_moderator.ask_ternary_question.assert_any_call(
                "How would you like to proceed?"
            )
            
            # Verify feature group processing was called after confirmation
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()
    
    def test_user_cancellation_for_high_complexity(self, mock_coordinator):
        """Test that task execution is cancelled if user declines a high complexity warning."""
        # Create high complexity data with many feature groups
        high_complexity_data = {
            "success": True,
            "status": "completed",
            "complexity_score": 180.0,  # Well above threshold
            "switch_workflow": False,
            "feature_groups": []
        }
        
        # Add multiple feature groups
        for i in range(1, 6):  # 5 feature groups
            high_complexity_data["feature_groups"].append({
                "group_name": f"Feature Group {i}",
                "group_description": f"Description of feature group {i}",
                "features": [
                    {"name": f"Feature {i}.1", "files_affected": [f"file{i}_1.py"]},
                    {"name": f"Feature {i}.2", "files_affected": [f"file{i}_2.py"]}
                ]
            })
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, high_complexity_data)
            
            # Configure user to decline the task due to complexity
            mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "no"  # User rejects the complex task
            
            # Call run_task
            mock_coordinator.run_task("Implement very complex feature")
            
            # Verify that presenting results was called once
            mock_coordinator._present_pre_planning_results_to_user.assert_called_once()
            
            # Verify that no feature group processing happened
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_not_called()
            
            # Verify rejection log was recorded
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                "User terminated the workflow at pre-planning handoff.", 
                level=LogLevel.WARNING if hasattr(LogLevel, 'WARNING') else any
            )
    
    def test_partial_success_with_some_feature_groups_failing(self, mock_coordinator):
        """Test that the workflow handles partial success with some feature groups failing."""
        # Create pre-planning data with multiple feature groups
        pre_planning_data = {
            "success": True,
            "status": "completed",
            "complexity_score": 85.0,
            "feature_groups": [
                {
                    "group_name": "Authentication",
                    "group_description": "User authentication features",
                    "features": [
                        {"name": "Login", "files_affected": ["auth.py"]}
                    ]
                },
                {
                    "group_name": "User Management",
                    "group_description": "User profile management",
                    "features": [
                        {"name": "Profile", "files_affected": ["user.py"]}
                    ]
                }
            ]
        }
        
        # Configure pre-planning mocks
        with patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow:
            mock_pre_planning_workflow.return_value = (True, pre_planning_data)
            
            # Configure feature group processing with mixed success/failure
            feature_groups_result = {
                "success": True,  # Overall success (partial)
                "feature_group_results": {
                    "feature_group_0": {
                        "success": True,
                        "feature_group": {"group_name": "Authentication"},
                        "consolidated_plan": {
                            "architecture_review": {"logical_gaps": []},
                            "implementation_plan": {"auth.py": [{"function": "login()"}]},
                            "tests": {"unit_tests": []}
                        }
                    },
                    "feature_group_1": {
                        "success": False,
                        "feature_group": {"group_name": "User Management"},
                        "error": "Failed to generate implementation plan",
                        "error_context": "Insufficient context for implementation planning"
                    }
                }
            }
            mock_coordinator.feature_group_processor.process_pre_planning_output.return_value = feature_groups_result
            
            # Set up mocks for user responses
            mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"
            mock_coordinator.feature_group_processor.present_consolidated_plan_to_user.return_value = ("yes", None)
            
            # Call run_task
            mock_coordinator.run_task("Implement features with partial success")
            
            # Verify feature_group_processor was called
            mock_coordinator.feature_group_processor.process_pre_planning_output.assert_called_once()
            
            # Verify that only one feature group plan was presented to user (the successful one)
            assert mock_coordinator.feature_group_processor.present_consolidated_plan_to_user.call_count == 1
            
            # Verify the error was logged
            mock_coordinator.scratchpad.log.assert_any_call(
                "Coordinator", 
                "Feature group User Management processing failed: Failed to generate implementation plan", 
                level=LogLevel.WARNING if hasattr(LogLevel, 'WARNING') else any
            )


