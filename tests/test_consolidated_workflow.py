import unittest
from unittest.mock import MagicMock, patch, ANY
import json
import os
import tempfile
import shutil
from pathlib import Path
import uuid

from agent_s3.coordinator import Coordinator
from agent_s3.feature_group_processor import FeatureGroupProcessor


class TestConsolidatedWorkflow(unittest.TestCase):
    """Test the full consolidated workflow with cross-phase validation."""

    def setUp(self):
        """Set up test environment with mocked components."""
        # Create a mock coordinator with all the necessary components
        self.coordinator = MagicMock()
        self.coordinator.scratchpad = MagicMock()
        self.coordinator.context_manager = MagicMock()
        self.coordinator.context_registry = MagicMock()
        self.coordinator.router_agent = MagicMock()
        self.coordinator.static_analyzer = MagicMock()
        self.coordinator.prompt_moderator = MagicMock()
        
        # Create a feature group processor that uses our mock coordinator
        self.processor = FeatureGroupProcessor(coordinator=self.coordinator)
        
        # Sample pre-planning data
        self.pre_planning_data = {
            "feature_groups": [
                {
                    "group_name": "Authentication",
                    "group_description": "User authentication features",
                    "features": [
                        {
                            "name": "Login", 
                            "description": "User login", 
                            "files_affected": ["src/auth.js"]
                        },
                        {
                            "name": "Logout", 
                            "description": "User logout", 
                            "files_affected": ["src/auth.js"]
                        }
                    ],
                    "risk_assessment": {
                        "critical_files": ["src/auth.js"],
                        "high_risk_areas": [
                            {
                                "name": "Authentication", 
                                "components": ["src/auth.js"]
                            }
                        ]
                    }
                }
            ]
        }
        
        # Mock architecture review
        self.architecture_review = {
            "logical_gaps": [
                {
                    "description": "Error handling for failed login",
                    "impact": "High - security implications",
                    "recommendation": "Add proper error handling",
                    "affected_components": ["src/auth.js"]
                }
            ],
            "optimization_suggestions": [
                {
                    "description": "Cache authentication token",
                    "benefit": "Improved performance",
                    "implementation_approach": "Use local storage",
                    "affected_components": ["src/auth.js"]
                }
            ],
            "additional_considerations": [
                "Security: Consider rate limiting login attempts"
            ]
        }
        
        # Mock implementation plan
        self.implementation_plan = {
            "implementation_plan": {
                "src/auth.js": [
                    {
                        "function": "async function login(username, password)",
                        "description": "Authenticate user",
                        "steps": [
                            "Validate input",
                            "Call API endpoint",
                            "Store authentication token",
                            "Handle errors"
                        ],
                        "edge_cases": [
                            "Invalid credentials",
                            "Network error",
                            "Server error"
                        ]
                    }
                ]
            },
            "discussion": "Authentication implementation approach"
        }
        
        # Mock tests
        self.tests = {
            "unit_tests": [
                {
                    "file": "tests/auth.test.js",
                    "implementation_file": "src/auth.js",
                    "test_name": "test_login_success",
                    "description": "Test successful login",
                    "code": "...",
                    "setup_requirements": "Mock API"
                }
            ],
            "integration_tests": [],
            "property_based_tests": [],
            "acceptance_tests": []
        }
        
        # Mock validation results
        self.validation_results = {
            "warnings": [
                {
                    "type": "test_coverage",
                    "message": "Missing test types: integration_tests, property_based_tests, acceptance_tests",
                    "details": {}
                }
            ]
        }
        
        # Set up return values for mocked methods
        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests)
        ]
        
        # Configure static_analyzer validation methods
        self.coordinator.static_analyzer.validate_architecture_implementation.return_value = (
            True, "Valid", {}
        )
        
        self.coordinator.static_analyzer.validate_test_coverage_against_risk.return_value = (
            False, 
            "Missing test types: integration_tests, property_based_tests, acceptance_tests",
            {
                "uncovered_high_risk_areas": []
            }
        )
        
        # Configure prompt_moderator
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"
        
        # Create a temp directory for saving plan files
        self.temp_dir = tempfile.mkdtemp()
        self.plans_dir = Path(self.temp_dir) / "plans"
        self.plans_dir.mkdir(exist_ok=True)
        
        # Mock open function for saving plans
        self.original_open = open
        
        def mock_open(*args, **kwargs):
            # If it's opening a plan file for writing, redirect to temp directory
            if len(args) > 0 and str(args[0]).startswith('plans/plan_') and 'w' in kwargs.get('mode', args[1] if len(args) > 1 else 'r'):
                path = Path(args[0])
                new_path = self.plans_dir / path.name
                return self.original_open(new_path, *(args[1:]), **kwargs)
            return self.original_open(*args, **kwargs)
        
        # Apply the patch
        self.open_patcher = patch('builtins.open', mock_open)
        self.mock_open = self.open_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.open_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_full_consolidated_workflow(self):
        """Test the full process_pre_planning_output workflow."""
        # Process the pre-planning data
        result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["feature_group_results"]), 1)
        
        # Verify architecture review was requested
        self.coordinator.router_agent.route_query.assert_any_call(ANY)
        
        # Verify cross-phase validation was performed
        self.coordinator.static_analyzer.validate_architecture_implementation.assert_called_once_with(
            self.architecture_review,
            self.implementation_plan["implementation_plan"]
        )
        
        self.coordinator.static_analyzer.validate_test_coverage_against_risk.assert_called_once_with(
            self.tests,
            self.pre_planning_data["feature_groups"][0]["risk_assessment"]
        )
        
        # Verify validation results were recorded in context management system
        self.coordinator.context_manager.add_to_context.assert_any_call(
            "validation_results", 
            {
                "validation_type": "test_coverage",
                "is_valid": False,
                "error_message": "Missing test types: integration_tests, property_based_tests, acceptance_tests",
                "details": {"uncovered_high_risk_areas": []},
                "timestamp": ANY
            }
        )
        
        # Verify context registry received the validation data
        self.coordinator.context_registry.register_data.assert_called_with(
            "feature_group_validation", 
            {
                "feature_group": "Authentication",
                "timestamp": ANY,
                "warnings": ANY,
                "validation_complete": True
            }
        )
    
    def test_workflow_with_user_modifications(self):
        """Test workflow when user requests modifications."""
        # Mock the prompt_moderator to return 'modify'
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Add two-factor authentication"
        
        # Process the pre-planning data
        result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Check the result
        self.assertTrue(result["success"])
        
        # Verify user modification validation was performed
        self.coordinator.context_manager.add_to_context.assert_any_call(
            "plan_modifications", 
            {
                "plan_id": ANY,
                "feature_group": "Authentication",
                "modification_text": "Add two-factor authentication",
                "timestamp": ANY,
                "diff_summary": ANY
            }
        )
        
        # Check that a plan file was saved
        plan_files = list(self.plans_dir.glob("*.json"))
        self.assertEqual(len(plan_files), 1)
        
        # Read the plan file and verify it contains the user modification
        with open(plan_files[0], 'r') as f:
            plan_data = json.load(f)
            self.assertEqual(plan_data["user_decision"], "modified")
            self.assertEqual(plan_data["modification_text"], "Add two-factor authentication")
            self.assertIn("timestamp", plan_data)
            
            # Verify modification was added to architecture review
            considerations = plan_data["consolidated_plan"]["architecture_review"]["additional_considerations"]
            self.assertTrue(any("USER MODIFICATION: Add two-factor authentication" in c for c in considerations))

    def test_integration_with_static_analyzer(self):
        """Test that the static analyzer integration works properly."""
        # Mock static analyzer to report validation issues
        self.coordinator.static_analyzer.validate_architecture_implementation.return_value = (
            False, 
            "Logical gap not addressed: Error handling for failed login",
            {
                "unaddressed_gaps": [
                    {
                        "description": "Error handling for failed login",
                        "affected_components": ["src/auth.js"]
                    }
                ],
                "unaddressed_optimizations": []
            }
        )
        
        # Process the pre-planning data
        result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Verify warnings were captured and added to test critic results
        feature_group_result = list(result["feature_group_results"].values())[0]
        consolidated_plan = feature_group_result["consolidated_plan"]
        test_critic_results = consolidated_plan.get("test_critic_results", {})
        
        # Check that validation warnings are in the test_critic_results
        self.assertIn("warnings", test_critic_results)
        warnings = test_critic_results["warnings"]
        self.assertTrue(any(warning["type"] == "architecture_implementation" for warning in warnings))
        self.assertTrue(any(warning["type"] == "test_coverage" for warning in warnings))
        
        # Verify context manager received both warnings
        context_calls = [call[0][1] for call in self.coordinator.context_manager.add_to_context.call_args_list 
                        if call[0][0] == "validation_results"]
        
        validation_types = [call["validation_type"] for call in context_calls if "validation_type" in call]
        self.assertIn("architecture_implementation", validation_types)
        self.assertIn("test_coverage", validation_types)

    def test_checkpoint_synchronization(self):
        """Test that the workflow properly synchronizes with checkpoints."""
        # Setup a real context manager checkpoint call
        def add_to_context(key, data):
            if key == "plan_modifications":
                # Save a checkpoint when plan modifications are recorded
                from agent_s3.tools.context_management.checkpoint_manager import save_checkpoint
                save_checkpoint("plan_modified", data, {"modification": data["modification_text"]})
                return True
            return False
        
        self.coordinator.context_manager.add_to_context.side_effect = add_to_context
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Add password reset feature"
        
        # Process the pre-planning data with a mocked phase_validator
        with patch('agent_s3.tools.phase_validator.validate_user_modifications') as mock_validate:
            mock_validate.return_value = (True, "Valid")
            result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Check that validation was called
        mock_validate.assert_called_once_with("Add password reset feature")
        
        # Verify the modification is tracked in the plan data
        feature_group_result = list(result["feature_group_results"].values())[0]
        consolidated_plan = feature_group_result["consolidated_plan"]
        versions = consolidated_plan.get("versions", [])
        self.assertEqual(len(versions), 2)  # Initial + user modification
        self.assertEqual(versions[1]["modification_type"], "user_modification")
        self.assertEqual(versions[1]["changes"]["text"], "Add password reset feature")

    def test_revalidation_after_plan_modification(self):
        """Test that re-validation occurs after a user modifies a plan."""
        # Mock the prompt_moderator to return 'modify'
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Make login more secure with 2FA"
        
        # Mock phase_validator functions to test re-validation
        with patch('agent_s3.tools.phase_validator.validate_user_modifications') as mock_validate_mods, \
             patch('agent_s3.tools.phase_validator.validate_architecture_implementation') as mock_validate_arch, \
             patch('agent_s3.tools.phase_validator.validate_test_coverage_against_risk') as mock_validate_tests, \
             patch('agent_s3.feature_group_processor.FeatureGroupProcessor._present_revalidation_results') as mock_present:
            
            # Configure the validation mocks
            mock_validate_mods.return_value = (True, "Valid")
            mock_validate_arch.return_value = (
                False, 
                "Architecture validation failed: Missing implementation for 2FA",
                {
                    "unaddressed_gaps": [
                        {
                            "description": "2FA implementation missing",
                            "affected_components": ["src/auth.js"]
                        }
                    ]
                }
            )
            mock_validate_tests.return_value = (
                True, 
                "Valid", 
                {"covered_risk_areas": 1, "total_risk_areas": 1}
            )
            
            # Process the pre-planning data
            result = self.processor.process_pre_planning_output(
                self.pre_planning_data, 
                "Implement authentication"
            )
            
            # Extract the consolidated plan from results
            feature_group_result = list(result["feature_group_results"].values())[0]
            consolidated_plan = feature_group_result["consolidated_plan"]
            
            # Get the updated plan with modifications directly for testing
            modified_plan = self.processor.update_plan_with_modifications(
                consolidated_plan, 
                "Make login more secure with 2FA"
            )
            
            # Verify that the re-validation occurred
            mock_validate_mods.assert_called_once_with("Make login more secure with 2FA")
            mock_validate_arch.assert_called_once_with(
                modified_plan.get("architecture_review", {}),
                modified_plan.get("implementation_plan", {})
            )
            mock_validate_tests.assert_called_once()
            
            # Verify re-validation results are stored in the plan
            self.assertIn("revalidation_results", modified_plan)
            self.assertIn("revalidation_status", modified_plan)
            
            # Check specific revalidation results
            revalidation_results = modified_plan["revalidation_results"]
            self.assertIn("architecture_implementation", revalidation_results)
            self.assertFalse(revalidation_results["architecture_implementation"]["is_valid"])
            
            # Verify the revalidation status
            self.assertFalse(modified_plan["revalidation_status"]["is_valid"])
            self.assertIn("Missing implementation for 2FA", modified_plan["revalidation_status"]["issues_found"])
            
            # Verify results were presented to the user
            mock_present.assert_called_once_with(modified_plan)
            
            # Check that the plan file was saved with revalidation results
            plan_files = list(self.plans_dir.glob("*.json"))
            self.assertGreaterEqual(len(plan_files), 1)
            
            # Verify the file contains revalidation results
            with open(plan_files[-1], 'r') as f:
                plan_data = json.load(f)
                self.assertIn("revalidation_results", plan_data["consolidated_plan"])
                self.assertIn("revalidation_status", plan_data["consolidated_plan"])
                self.assertIn("timestamp", plan_data)

if __name__ == "__main__":
    unittest.main()
