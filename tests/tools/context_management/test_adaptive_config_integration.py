"""
Integration tests for the adaptive configuration system.
"""

import os
import unittest
import tempfile
import shutil
import json
from unittest import mock

from agent_s3.tools.context_management.coordinator_integration import (
    setup_context_management,
    get_configuration_report, optimize_configuration, reset_configuration
)


class MockCoordinator:
    """Mock coordinator for testing."""

    def __init__(self, workspace_dir):
        """Initialize mock coordinator."""
        self.workspace_dir = workspace_dir
        self.config = mock.MagicMock()
        self.config.config = {
            'context_management': {
                'enabled': True,
                'adaptive_config': {
                    'enabled': True
                }
            }
        }
        self.tech_stack = {
            "languages": ["python"],
            "frameworks": ["flask"]
        }
        self.context_manager = None
        self.adaptive_config_manager = None
        self.config_explainer = None
        self.logs = []

    def shutdown(self):
        """Mock shutdown method."""
        return True

    def get_file_modification_info(self):
        """Mock file modification info."""
        return {}

    def scratchpad_log(self, source, message, level=None, section=None):
        """Mock scratchpad logging."""
        self.logs.append({
            "source": source,
            "message": message,
            "level": level,
            "section": section
        })

    @property
    def scratchpad(self):
        """Mock scratchpad property."""
        return self

    def log(self, source, message, level=None, section=None, metadata=None):
        """Mock log method."""
        self.scratchpad_log(source, message, level, section)


class TestAdaptiveConfigIntegration(unittest.TestCase):
    """Test the integration between adaptive configuration and the coordinator."""

    def setUp(self):
        """Set up test resources."""
        # Create a temporary directory for test repository
        self.test_repo_dir = tempfile.mkdtemp()

        # Create a mock repository structure
        os.makedirs(os.path.join(self.test_repo_dir, "src", "main", "python"))
        os.makedirs(os.path.join(self.test_repo_dir, "src", "test", "python"))
        os.makedirs(os.path.join(self.test_repo_dir, ".agent_s3", "config"), exist_ok=True)

        # Create some mock Python files
        with open(os.path.join(self.test_repo_dir, "src", "main", "python", "app.py"), "w") as f:
            f.write("""
            import flask
            from flask import Flask, request

            app = Flask(__name__)

            @app.route('/')
            def index():
                \"\"\"Return the index page.\"\"\"
                return "Hello, World!"

            @app.route('/api/data')
            def get_data():
                \"\"\"Get some data.\"\"\"
                return {"data": "example"}

            if __name__ == '__main__':
                app.run(debug=True)
            """)

        # Create mock coordinator
        self.coordinator = MockCoordinator(self.test_repo_dir)

    def tearDown(self):
        """Clean up test resources."""
        shutil.rmtree(self.test_repo_dir)

    def test_setup_context_management(self):
        """Test setting up context management with adaptive configuration."""
        # Set up context management
        result = setup_context_management(self.coordinator)

        # Check setup was successful
        self.assertTrue(result)
        self.assertIsNotNone(self.coordinator.context_manager)
        self.assertIsNotNone(self.coordinator.adaptive_config_manager)
        self.assertIsNotNone(self.coordinator.config_explainer)

        # Check adaptive config was created
        self.assertTrue(hasattr(self.coordinator.context_manager, 'adaptive_config_manager'))

        # Check that config explanation works
        report = get_configuration_report(self.coordinator)
        self.assertIsInstance(report, str)
        self.assertIn("Context Management Configuration Report", report)

    def test_optimization_flow(self):
        """Test the optimization flow."""
        # Set up context management
        setup_context_management(self.coordinator)

        # Ensure we have a config manager
        self.assertIsNotNone(self.coordinator.adaptive_config_manager)

        # Mock metrics for relevance
        self.coordinator.adaptive_config_manager.log_context_performance(
            task_type="code_explanation",
            relevance_score=0.6  # Low score to trigger optimization
        )

        # Mock token usage
        self.coordinator.adaptive_config_manager.log_token_usage(
            total_tokens=900,
            available_tokens=1000,
            allocated_tokens={"code": 500, "docs": 400}
        )

        # Manual optimization
        success, message = optimize_configuration(self.coordinator)

        # For the first optimization, we might not have enough data
        # but the function should still return without error
        self.assertIsInstance(success, bool)
        self.assertIsInstance(message, str)

        # Reset configuration
        success, message = reset_configuration(self.coordinator)
        self.assertTrue(success)
        self.assertIn("reset to default", message.lower())

    def test_config_explainer_integration(self):
        """Test integration with ConfigExplainer."""
        # Set up context management
        setup_context_management(self.coordinator)

        # Get configuration report
        report = get_configuration_report(self.coordinator)
        self.assertIsInstance(report, str)

        # Check that the report contains key sections
        self.assertIn("Configuration Overview", report)

        # Since we're using a mock repository, there might not be performance metrics yet
        self.assertIn("Parameters", report)

    def test_context_manager_integration(self):
        """Test integration between adaptive config and context manager."""
        # Set up context management
        setup_context_management(self.coordinator)

        # Check that the context manager and adaptive config manager are connected
        context_manager = self.coordinator.context_manager
        adaptive_config = self.coordinator.adaptive_config_manager

        self.assertIsNotNone(context_manager)
        self.assertIsNotNone(adaptive_config)

        # Mock an optimization
        old_config = adaptive_config.get_current_config()

        # Create a new config with different parameters
        new_config = json.loads(json.dumps(old_config))  # Deep copy
        new_config["context_management"]["embedding"]["chunk_size"] = 1500

        # Update the configuration
        adaptive_config.update_configuration(new_config, "Test update")

        # Get the updated config and check it was applied
        current_config = adaptive_config.get_current_config()
        self.assertEqual(current_config["context_management"]["embedding"]["chunk_size"], 1500)

    def test_coordinator_integration(self):
        """Test integration with the coordinator."""
        # Set up context management
        setup_context_management(self.coordinator)

        # Check that integration methods were added
        self.assertTrue(hasattr(self.coordinator, 'get_config_explanation'))

        # Call the config explanation method
        explanation = self.coordinator.get_config_explanation()
        self.assertIsInstance(explanation, str)

        # Verify shutdown hook functionality
        with mock.patch.object(self.coordinator.context_manager, 'stop_background_optimization') as mock_stop:
            self.coordinator.shutdown()
            mock_stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
