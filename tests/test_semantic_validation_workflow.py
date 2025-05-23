import unittest
from unittest.mock import MagicMock, patch

from agent_s3.tools.validation_result import ValidationResult
import json
import tempfile
import shutil
from pathlib import Path

from agent_s3.feature_group_processor import FeatureGroupProcessor


class TestSemanticValidationWorkflow(unittest.TestCase):
    """Test the semantic validation and revalidation workflow enhancements."""

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
        self.coordinator.test_critic = MagicMock()
        
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
                        }
                    ],
                    "risk_assessment": {
                        "critical_files": ["src/auth.js"]
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
                            "Network error"
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
                    "code": "test code",
                    "setup_requirements": "Mock API"
                }
            ],
            "integration_tests": [],
            "property_based_tests": [],
            "acceptance_tests": []
        }
        
        # Mock semantic validation results
        self.semantic_validation_results = {
            "is_valid": True,
            "critical_issues": [],
            "minor_issues": [
                {
                    "description": "Edge case handling for server errors is missing",
                    "affected_components": ["src/auth.js"],
                    "recommendation": "Add error handling for server errors"
                }
            ],
            "coherence_score": 8,
            "technical_consistency_score": 9
        }
        
        # Set up return values for mocked methods
        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests),
            json.dumps(self.semantic_validation_results)  # For semantic validation
        ]
        
        # Configure static_analyzer validation methods
        self.coordinator.static_analyzer.validate_architecture_implementation.return_value = (
            True, "Valid", {}
        )
        
        self.coordinator.static_analyzer.validate_test_coverage_against_risk.return_value = (
            True, "Valid", {}
        )
        
        # Configure prompt_moderator
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"
        
        # Create a temp directory for saving plan files
        self.temp_dir = tempfile.mkdtemp()
        self.plans_dir = Path(self.temp_dir) / "plans"
        self.plans_dir.mkdir(exist_ok=True)
        
        # Mock Path.mkdir to handle the plans directory creation
        self.original_mkdir = Path.mkdir
        def mock_mkdir(self, *args, **kwargs):
            if str(self) == "plans":
                return None  # Already created in temp dir
            return self.original_mkdir(*args, **kwargs)
        
        # Apply the patch
        self.mkdir_patcher = patch.object(Path, 'mkdir', mock_mkdir)
        self.mkdir_patcher.start()
        
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
        self.mkdir_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_semantic_validation_during_plan_creation(self):
        """Test that semantic validation is performed during plan creation."""
        # Process the pre-planning data
        result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Check the result
        self.assertTrue(result["success"])
        self.assertEqual(len(result["feature_group_results"]), 1)
        
        # Verify semantic validation was called with appropriate prompt
        semantic_validation_calls = [
            call for call in self.coordinator.router_agent.route_query.call_args_list 
            if "You are an expert architecture and code reviewer" in call[0][0]
        ]
        self.assertEqual(len(semantic_validation_calls), 1)
        
        # Verify semantic validation results are in the consolidated plan
        feature_group_result = list(result["feature_group_results"].values())[0]
        consolidated_plan = feature_group_result["consolidated_plan"]
        self.assertIn("semantic_validation_results", consolidated_plan)
        
        # Verify that semantic validation warnings are added to test critic results
        test_critic_results = consolidated_plan.get("test_critic_results", {})
        warnings = test_critic_results.get("warnings", [])
        self.assertTrue(any(warning.get("type") == "semantic_validation" for warning in warnings))

    def test_semantic_validation_during_plan_modification(self):
        """Test that semantic validation is performed during plan modification."""
        # Mock semantic validation to have critical issues during revalidation
        critical_semantic_revalidation = {
            "is_valid": False,
            "critical_issues": [
                {
                    "description": "Serious inconsistency between architecture and implementation",
                    "affected_components": ["src/auth.js"],
                    "recommendation": "Address the architectural requirements in implementation"
                }
            ],
            "minor_issues": [],
            "coherence_score": 4,
            "technical_consistency_score": 5
        }
        
        # Set up the router agent to return different responses for different calls
        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests),
            json.dumps(self.semantic_validation_results),  # Initial semantic validation
            json.dumps(critical_semantic_revalidation)  # Re-validation after modification
        ]
        
        # Configure prompt_moderator for modification
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Add two-factor authentication"
        
        # Mock the _present_revalidation_results method
        with patch('agent_s3.feature_group_processor.FeatureGroupProcessor._present_revalidation_results') as mock_present:
            # Process the pre-planning data
            result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
            
            # Check the result
            self.assertTrue(result["success"])
            
            # Extract the consolidated plan from results
            feature_group_result = list(result["feature_group_results"].values())[0]
            consolidated_plan = feature_group_result["consolidated_plan"]
            
            # Update the plan with modifications
            modified_plan = self.processor.update_plan_with_modifications(
                consolidated_plan, 
                "Add two-factor authentication"
            )
            
            # Verify semantic validation was called during revalidation
            semantic_validation_calls = [
                call for call in self.coordinator.router_agent.route_query.call_args_list 
                if "You are an expert architecture and code reviewer" in call[0][0]
            ]
            self.assertEqual(len(semantic_validation_calls), 2)  # Once during creation, once during modification
            
            # Verify revalidation results include semantic validation
            self.assertIn("revalidation_results", modified_plan)
            self.assertIn("semantic_validation", modified_plan["revalidation_results"])
            
            # Verify semantic validation issues affect overall validation status
            self.assertIn("revalidation_status", modified_plan)
            self.assertFalse(modified_plan["revalidation_status"]["is_valid"])
            
            # Verify results were presented to the user
            mock_present.assert_called_once_with(modified_plan)

    def test_modification_loop_prevention(self):
        """Test that loop prevention works when exceeding max modification attempts."""
        # Configure prompt_moderator for modification
        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        modification_messages = [
            "Add two-factor authentication",
            "Make it more secure",
            "Add biometric authentication",
            "Add security questions"  # This should exceed the limit
        ]
        self.coordinator.prompt_moderator.ask_for_modification.side_effect = modification_messages
        
        # Mock print function to capture output
        with patch('builtins.print') as mock_print:
            # Process the pre-planning data
            result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
            
            # Extract the consolidated plan from results
            feature_group_result = list(result["feature_group_results"].values())[0]
            consolidated_plan = feature_group_result["consolidated_plan"]
            
            # Apply modifications sequentially until we hit the limit
            modified_plan = consolidated_plan
            for i, mod_text in enumerate(modification_messages):
                modified_plan = self.processor.update_plan_with_modifications(
                    modified_plan, 
                    mod_text
                )
                
                if i >= 2:  # After the third modification (index 2), we should hit the limit
                    # Verify the max_attempts_reached flag is set
                    self.assertTrue(modified_plan.get("max_attempts_reached", False))
                    
                    # Verify warning was printed
                    mock_print.assert_any_call(
                        "\n⚠️  Maximum modification attempts (3) exceeded."
                    )
                    
                    # Verify the modification_attempts counter was updated
                    self.assertEqual(modified_plan.get("modification_attempts", 0), 4)  # 0-based + 1 for each attempt
                    break
                else:
                    # Verify modifications were applied successfully
                    self.assertFalse(modified_plan.get("max_attempts_reached", False))
                    considerations = modified_plan["architecture_review"]["additional_considerations"]
                    self.assertIn(f"USER MODIFICATION: {mod_text}", considerations)

    def test_critical_semantic_validation_failure(self):
        """Test workflow when semantic validation fails with critical issues."""
        # Mock semantic validation with critical issues
        critical_semantic_validation = {
            "is_valid": False,
            "critical_issues": [
                {
                    "description": "Design is fundamentally flawed",
                    "affected_components": ["src/auth.js"],
                    "recommendation": "Redesign the authentication flow"
                }
            ],
            "minor_issues": [],
            "coherence_score": 3,
            "technical_consistency_score": 4
        }
        
        # Set up router agent to return the critical validation
        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests),
            json.dumps(critical_semantic_validation)
        ]
        
        # Process the pre-planning data
        result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
        
        # Check the result
        self.assertTrue(result["success"])  # Should still succeed even with validation issues
        
        # Extract the consolidated plan from results
        feature_group_result = list(result["feature_group_results"].values())[0]
        consolidated_plan = feature_group_result["consolidated_plan"]
        
        # Verify semantic validation results indicate failure
        self.assertIn("semantic_validation_results", consolidated_plan)
        semantic_results = consolidated_plan["semantic_validation_results"]
        self.assertFalse(semantic_results["is_valid"])
        
        # Verify warnings are added with critical severity
        test_critic_results = consolidated_plan.get("test_critic_results", {})
        warnings = test_critic_results.get("warnings", [])
        self.assertTrue(any(
            warning.get("type") == "semantic_validation" and 
            warning.get("severity") == "critical" 
            for warning in warnings
        ))
        
        # Verify low coherence score is flagged as a critical issue
        self.assertTrue(any(
            warning.get("type") == "semantic_validation" and
            "Low coherence score: 3/10" in warning.get("message", "") and
            warning.get("severity") == "critical"
            for warning in warnings
        ))

    def test_invalid_modification_triggers_validation_error(self):
        """Ensure invalid user modifications surface validation errors."""

        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests),
            json.dumps(self.semantic_validation_results),
        ]

        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Break plan"

        invalid_plan = {
            "architecture_review": self.architecture_review,
            "tests": self.tests,
            "implementation_plan": {},
        }

        validation_issue = {
            "issue_type": "structure",
            "severity": "critical",
            "description": "Implementation plan is empty",
        }

        with patch(
            'agent_s3.feature_group_processor.regenerate_consolidated_plan_with_modifications',
            return_value=invalid_plan,
        ) as mock_regen, patch(
            'agent_s3.tools.implementation_validator.validate_implementation_plan'
        ) as mock_validate, patch(
            'agent_s3.feature_group_processor.FeatureGroupProcessor._present_revalidation_results'
        ) as mock_present:

            mock_validate.return_value = ValidationResult(
                data=invalid_plan["implementation_plan"],
                issues=[validation_issue],
                needs_repair=True,
            )

            result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
            self.assertTrue(result["success"])
            consolidated_plan = list(result["feature_group_results"].values())[0]["consolidated_plan"]

            modified_plan = self.processor.update_plan_with_modifications(consolidated_plan, "Break plan")

            mock_regen.assert_called_once()
            mock_validate.assert_called_once()
            mock_present.assert_called_once_with(modified_plan)

            self.assertIn("revalidation_status", modified_plan)
            self.assertFalse(modified_plan["revalidation_status"]["is_valid"])
        self.assertIn("Implementation plan is empty", ''.join(modified_plan["revalidation_status"].get("issues_found", [])))

    def test_invalid_element_ids_trigger_validation_error(self):
        """Ensure invalid element IDs are reported during plan modification."""

        self.coordinator.router_agent.route_query.side_effect = [
            json.dumps(self.architecture_review),
            json.dumps(self.implementation_plan),
            json.dumps(self.tests),
            json.dumps(self.semantic_validation_results),
        ]

        self.coordinator.prompt_moderator.ask_ternary_question.return_value = "modify"
        self.coordinator.prompt_moderator.ask_for_modification.return_value = "Change plan"

        invalid_plan = {
            "architecture_review": self.architecture_review,
            "tests": {
                "unit_tests": [
                    {"target_element_id": "invalid_id"}
                ],
                "integration_tests": [],
                "property_based_tests": [],
                "acceptance_tests": []
            },
            "implementation_plan": {
                "file.py": [
                    {"function": "f", "element_id": "invalid_id", "steps": []}
                ]
            },
            "system_design": {
                "code_elements": [
                    {"element_id": "valid_id"}
                ]
            }
        }

        with patch(
            'agent_s3.feature_group_processor.regenerate_consolidated_plan_with_modifications',
            return_value=invalid_plan,
        ) as mock_regen, patch(
            'agent_s3.tools.implementation_validator.validate_implementation_plan'
        ) as mock_validate, patch(
            'agent_s3.feature_group_processor.FeatureGroupProcessor._present_revalidation_results'
        ) as mock_present:

            mock_validate.return_value = ValidationResult(
                data=invalid_plan["implementation_plan"],
                issues=[],
                needs_repair=False,
            )

            result = self.processor.process_pre_planning_output(self.pre_planning_data, "Implement authentication")
            self.assertTrue(result["success"])
            consolidated_plan = list(result["feature_group_results"].values())[0]["consolidated_plan"]

            modified_plan = self.processor.update_plan_with_modifications(consolidated_plan, "Change plan")

            mock_regen.assert_called_once()
            mock_validate.assert_called_once()
            mock_present.assert_called_once_with(modified_plan)

            self.assertIn("revalidation_status", modified_plan)
            self.assertFalse(modified_plan["revalidation_status"]["is_valid"])
            issues = ''.join(modified_plan["revalidation_status"].get("issues_found", []))
            self.assertIn("Invalid test element IDs", issues)


if __name__ == "__main__":
    unittest.main()
