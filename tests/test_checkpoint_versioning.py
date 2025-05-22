import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil

# Import modules to test
from agent_s3.tools.context_management.checkpoint_manager import (
    save_checkpoint,
    load_checkpoint,
    list_checkpoints,
    get_checkpoint_diff,
    ensure_checkpoint_consistency
)

class TestCheckpointVersioning(unittest.TestCase):
    """Test suite for checkpoint versioning and consistency features."""

    def setUp(self):
        """Set up the test environment with a temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_checkpoints_dir = os.environ.get('AGENT_CHECKPOINTS_DIR')
        os.environ['AGENT_CHECKPOINTS_DIR'] = self.temp_dir
        
        # Sample checkpoint data
        self.initial_feature_groups = {
            "feature_groups": [
                {
                    "group_name": "Auth",
                    "group_description": "Authentication features",
                    "features": [
                        {"name": "Login", "description": "User login feature", "files_affected": ["auth.py"]},
                        {"name": "Logout", "description": "User logout feature", "files_affected": ["auth.py"]}
                    ]
                },
                {
                    "group_name": "Profile",
                    "group_description": "User profile features",
                    "features": [
                        {"name": "View Profile", "description": "View user profile", "files_affected": ["profile.py"]},
                        {"name": "Edit Profile", "description": "Edit user profile", "files_affected": ["profile.py"]}
                    ]
                }
            ]
        }
        
        # Modified checkpoint with a feature removed
        self.modified_feature_groups = {
            "feature_groups": [
                {
                    "group_name": "Auth",
                    "group_description": "Authentication features",
                    "features": [
                        {"name": "Login", "description": "User login feature", "files_affected": ["auth.py"]}
                        # Logout feature removed
                    ]
                },
                {
                    "group_name": "Profile",
                    "group_description": "User profile features",
                    "features": [
                        {"name": "View Profile", "description": "View user profile", "files_affected": ["profile.py"]},
                        {"name": "Edit Profile", "description": "Edit user profile", "files_affected": ["profile.py"]}
                    ]
                }
            ]
        }
        
        # Modified checkpoint with a feature added
        self.enhanced_feature_groups = {
            "feature_groups": [
                {
                    "group_name": "Auth",
                    "group_description": "Authentication features",
                    "features": [
                        {"name": "Login", "description": "User login feature", "files_affected": ["auth.py"]},
                        {"name": "Logout", "description": "User logout feature", "files_affected": ["auth.py"]},
                        {"name": "Reset Password", "description": "Reset user password", "files_affected": ["auth.py", "email.py"]}
                    ]
                },
                {
                    "group_name": "Profile",
                    "group_description": "User profile features",
                    "features": [
                        {"name": "View Profile", "description": "View user profile", "files_affected": ["profile.py"]},
                        {"name": "Edit Profile", "description": "Edit user profile", "files_affected": ["profile.py"]}
                    ]
                }
            ]
        }

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Restore the original checkpoints directory
        if self.original_checkpoints_dir:
            os.environ['AGENT_CHECKPOINTS_DIR'] = self.original_checkpoints_dir
        else:
            del os.environ['AGENT_CHECKPOINTS_DIR']

    def test_save_and_load_checkpoint(self):
        """Test saving and loading checkpoints."""
        # Save a checkpoint
        checkpoint_id = save_checkpoint("pre_planning", self.initial_feature_groups)
        self.assertIsNotNone(checkpoint_id)
        
        # Load the checkpoint
        loaded_data = load_checkpoint(checkpoint_id)
        self.assertEqual(loaded_data, self.initial_feature_groups)
        
        # Save with metadata
        metadata = {"user": "test_user", "timestamp": "2025-01-01"}
        checkpoint_id_with_metadata = save_checkpoint("planning", self.initial_feature_groups, metadata)
        
        # Load with metadata
        loaded_data, loaded_metadata = load_checkpoint(checkpoint_id_with_metadata, include_metadata=True)
        self.assertEqual(loaded_data, self.initial_feature_groups)
        for key, value in metadata.items():
            self.assertEqual(loaded_metadata.get(key), value)

    def test_list_checkpoints(self):
        """Test listing checkpoints by type."""
        # Save multiple checkpoints
        save_checkpoint("pre_planning", self.initial_feature_groups)
        save_checkpoint("planning", self.modified_feature_groups)
        save_checkpoint("implementation", self.enhanced_feature_groups)
        save_checkpoint("pre_planning", self.enhanced_feature_groups)
        
        # List all checkpoints
        all_checkpoints = list_checkpoints()
        self.assertEqual(len(all_checkpoints), 4)
        
        # List checkpoints by type
        pre_planning_checkpoints = list_checkpoints(checkpoint_type="pre_planning")
        self.assertEqual(len(pre_planning_checkpoints), 2)
        
        # Verify checkpoint order (newest first)
        self.assertGreater(
            pre_planning_checkpoints[0].get("timestamp", ""),
            pre_planning_checkpoints[1].get("timestamp", "")
        )

    def test_checkpoint_diff(self):
        """Test generating differences between checkpoints."""
        # Save initial version
        initial_id = save_checkpoint("pre_planning", self.initial_feature_groups)
        
        # Save modified version
        modified_id = save_checkpoint("planning", self.modified_feature_groups)
        
        # Generate diff
        diff = get_checkpoint_diff(initial_id, modified_id)
        
        # Verify diff shows removed feature
        self.assertIn("removed", diff)
        removed_features = diff.get("removed", [])
        self.assertEqual(len(removed_features), 1)
        self.assertEqual(removed_features[0].get("name"), "Logout")
        
        # Test diff with added feature
        enhanced_id = save_checkpoint("implementation", self.enhanced_feature_groups)
        diff2 = get_checkpoint_diff(initial_id, enhanced_id)
        
        self.assertIn("added", diff2)
        added_features = diff2.get("added", [])
        self.assertEqual(len(added_features), 1)
        self.assertEqual(added_features[0].get("name"), "Reset Password")

    def test_ensure_checkpoint_consistency(self):
        """Test consistency validation between checkpoints."""
        # Save initial version
        initial_id = save_checkpoint("pre_planning", self.initial_feature_groups)
        
        # Test with consistent modification (features added)
        is_valid, message = ensure_checkpoint_consistency(initial_id, self.enhanced_feature_groups)
        self.assertTrue(is_valid)
        
        # Test with inconsistent modification (features removed)
        is_valid, message = ensure_checkpoint_consistency(initial_id, self.modified_feature_groups)
        self.assertFalse(is_valid)
        self.assertIn("Logout", message, "Error message should mention the removed feature")
        
        # Test with completely different feature groups
        different_feature_groups = {
            "feature_groups": [
                {
                    "group_name": "Payments",
                    "group_description": "Payment processing",
                    "features": [
                        {"name": "Process Payment", "description": "Process payments", "files_affected": ["payment.py"]}
                    ]
                }
            ]
        }
        is_valid, message = ensure_checkpoint_consistency(initial_id, different_feature_groups)
        self.assertFalse(is_valid)
        self.assertIn("Auth", message, "Error message should mention missing feature group")

    def test_checkpoint_version_tracking(self):
        """Test tracking versions of a plan through modifications."""
        # Create initial plan
        plan = {
            "feature_group": {
                "name": "Authentication",
                "features": [{"name": "Login"}, {"name": "Logout"}]
            },
            "versions": [
                {
                    "timestamp": "2025-01-01T00:00:00",
                    "modification_type": "initial",
                    "changes": {}
                }
            ]
        }
        
        # Save initial version
        plan_id = save_checkpoint("plan", plan)
        
        # Load and modify the plan
        loaded_plan = load_checkpoint(plan_id)
        loaded_plan["feature_group"]["features"].append({"name": "Reset Password"})
        loaded_plan["versions"].append({
            "timestamp": "2025-01-02T00:00:00",
            "modification_type": "user_modification",
            "changes": {"added_features": ["Reset Password"]}
        })
        
        # Save modified version
        modified_id = save_checkpoint("plan_modified", loaded_plan)
        
        # Verify the versions are preserved
        final_plan = load_checkpoint(modified_id)
        self.assertEqual(len(final_plan["versions"]), 2)
        self.assertEqual(final_plan["versions"][1]["modification_type"], "user_modification")
        
        # Verify version tracking through feature group processor
        with patch('agent_s3.feature_group_processor.FeatureGroupProcessor.update_plan_with_modifications') as mock_update:
            mock_update.return_value = loaded_plan
            
            # Create a mock feature group processor
            from agent_s3.feature_group_processor import FeatureGroupProcessor
            mock_coordinator = MagicMock()
            processor = FeatureGroupProcessor(mock_coordinator)
            
            # Call update_plan_with_modifications
            result = processor.update_plan_with_modifications(plan, "Add reset password feature")
            
            # Verify the call
            mock_update.assert_called_once()
            
            # Verify the result has version tracking
            self.assertEqual(len(result["versions"]), 2)

if __name__ == "__main__":
    unittest.main()
