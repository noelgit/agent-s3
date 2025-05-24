"""Unit tests for the implementation manager."""

import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from agent_s3.implementation_manager import ImplementationManager


class TestImplementationManager(unittest.TestCase):
    """Test cases for ImplementationManager."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_coordinator = MagicMock()
        self.mock_coordinator.scratchpad = MagicMock()
        self.mock_coordinator.router_agent = MagicMock()
        self.implementation_manager = ImplementationManager(self.mock_coordinator)

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # Override progress file path for testing
        self.implementation_manager.progress_file = str(
            self.temp_path / "implementation_progress.json"
        )

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.temp_dir.cleanup()

    def test_initialize_progress_tracker(self) -> None:
        """Test initializing a new progress tracker from design file."""
        # Create a mock design file
        design_content = """# System Design: Test Project

1. Feature One
   1.1. Subfeature A
   1.2. Subfeature B

2. Feature Two
   2.1. Subfeature C
        """

        design_file = self.temp_path / "design.txt"
        with open(design_file, "w") as f:
            f.write(design_content)

        # Call the method
        self.implementation_manager._initialize_progress_tracker(str(design_file))

        # Check the result
        self.assertTrue(os.path.exists(self.implementation_manager.progress_file))
        with open(self.implementation_manager.progress_file, "r") as f:
            progress = json.load(f)

        # Verify structure - markdown header should be stripped
        self.assertEqual(progress["design_objective"], "System Design: Test Project")
        self.assertGreaterEqual(len(progress["tasks"]), 4)  # At least 4 tasks total

        # Verify task IDs and descriptions
        task_ids = [task["id"] for task in progress["tasks"]]
        self.assertIn("1", task_ids)
        self.assertIn("1.1", task_ids)
        self.assertIn("1.2", task_ids)
        self.assertIn("2", task_ids)

        # Verify all tasks are pending
        for task in progress["tasks"]:
            self.assertEqual(task["status"], "pending")

    def test_initialize_progress_tracker_strips_multiple_headers(self) -> None:
        """Ensure markdown headers are removed from the design objective."""
        design_content = """## Another Project

1. Feature One
        """

        design_file = self.temp_path / "design.txt"
        with open(design_file, "w") as f:
            f.write(design_content)

        self.implementation_manager._initialize_progress_tracker(str(design_file))

        with open(self.implementation_manager.progress_file, "r") as f:
            progress = json.load(f)

        self.assertEqual(progress["design_objective"], "Another Project")

    def test_find_next_task(self) -> None:
        """Test finding the next pending task."""
        # Create sample progress data
        progress = {
            "tasks": [
                {"id": "1", "description": "Task 1", "status": "completed"},
                {"id": "2", "description": "Task 2", "status": "pending"},
                {"id": "3", "description": "Task 3", "status": "pending"},
            ]
        }

        # Find next task
        next_task = self.implementation_manager._find_next_task(progress)

        # Verify a task was found
        self.assertIsNotNone(next_task)
        if next_task:  # Add type guard for mypy
            self.assertEqual(next_task["id"], "2")
            self.assertEqual(next_task["description"], "Task 2")

    @patch.object(ImplementationManager, "_load_progress_tracker")
    @patch.object(ImplementationManager, "_save_progress_tracker")
    @patch.object(ImplementationManager, "_execute_implementation_request")
    @patch.object(ImplementationManager, "_find_next_task")
    def test_implement_next_task(
        self,
        mock_find: MagicMock,
        mock_execute: MagicMock,
        mock_save: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """Test implementing the next task."""
        # Create sample progress data
        progress = {
            "tasks": [
                {"id": "1", "description": "Task 1", "status": "completed"},
                {"id": "2", "description": "Task 2", "status": "pending"},
                {"id": "3", "description": "Task 3", "status": "pending"},
            ]
        }

        # Mock successful implementation
        mock_execute.return_value = {"success": True}

        # Task to implement
        task = {"id": "2", "description": "Task 2", "status": "pending"}

        # Mock find_next_task to return None (no next task)
        mock_find.return_value = None

        # Call the method
        result = self.implementation_manager._implement_next_task(progress, task)

        # Verify the task was updated
        self.assertEqual(task["status"], "completed")
        self.assertIn("completed_at", task)

        # Verify save was called
        mock_save.assert_called()

        # Verify success result
        self.assertTrue(result["success"])
        self.assertEqual(result["task_id"], "2")
        self.assertEqual(result["task_status"], "completed")

    @patch.object(ImplementationManager, "_load_progress_tracker")
    @patch.object(ImplementationManager, "_save_progress_tracker")
    @patch.object(ImplementationManager, "_execute_implementation_request")
    @patch.object(ImplementationManager, "_find_next_task")
    def test_implement_next_task_failure(
        self,
        mock_find: MagicMock,
        mock_execute: MagicMock,
        mock_save: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """Test implementing a task that fails."""
        # Create sample progress data
        progress = {
            "tasks": [
                {"id": "1", "description": "Task 1", "status": "completed"},
                {"id": "2", "description": "Task 2", "status": "pending"},
                {"id": "3", "description": "Task 3", "status": "pending"},
            ]
        }

        # Mock failed implementation
        mock_execute.return_value = {"success": False, "error": "Implementation failed"}

        # Task to implement
        task = {"id": "2", "description": "Task 2", "status": "pending"}

        # Call the method
        result = self.implementation_manager._implement_next_task(progress, task)

        # Verify the task was updated
        self.assertEqual(task["status"], "failed")
        self.assertIn("error", task)

        # Verify save was called
        mock_save.assert_called()

        # Verify failure result
        self.assertFalse(result["success"])
        self.assertEqual(result["task_id"], task["id"])
        self.assertEqual(result["task_status"], "failed")

    @patch.object(ImplementationManager, "_load_progress_tracker")
    @patch.object(ImplementationManager, "_initialize_progress_tracker")
    @patch.object(ImplementationManager, "_find_next_task")
    @patch.object(ImplementationManager, "_implement_next_task")
    def test_start_implementation(
        self,
        mock_implement: MagicMock,
        mock_find: MagicMock,
        mock_init: MagicMock,
        mock_load: MagicMock,
    ) -> None:
        """Test starting implementation."""
        # Set up mocks
        mock_load.return_value = None  # No existing progress
        mock_init.return_value = {"tasks": [{"id": "1", "status": "pending"}]}
        mock_find.return_value = {"id": "1", "status": "pending"}
        mock_implement.return_value = {"success": True}

        # Call the method
        result = self.implementation_manager.start_implementation()

        # Verify initialization flow
        mock_load.assert_called_once()
        mock_init.assert_called_once()
        mock_find.assert_called_once()
        mock_implement.assert_called_once()

        # Verify result
        self.assertEqual(result, {"success": True})

    @patch.object(ImplementationManager, "_load_progress_tracker")
    @patch.object(ImplementationManager, "_find_next_task")
    @patch.object(ImplementationManager, "_implement_next_task")
    def test_continue_implementation(
        self, mock_implement: MagicMock, mock_find: MagicMock, mock_load: MagicMock
    ) -> None:
        """Test continuing implementation."""
        # Set up mocks
        mock_load.return_value = {
            "tasks": [
                {"id": "1", "status": "completed"},
                {"id": "2", "status": "pending"},
            ]
        }
        mock_find.return_value = {"id": "2", "status": "pending"}
        mock_implement.return_value = {"success": True}

        # Call the method
        result = self.implementation_manager.continue_implementation()

        # Verify flow
        mock_load.assert_called_once()
        mock_find.assert_called_once()
        mock_implement.assert_called_once()

        # Verify result
        self.assertEqual(result, {"success": True})

    @patch.object(ImplementationManager, "_load_progress_tracker")
    def test_continue_implementation_no_progress(self, mock_load: MagicMock) -> None:
        """Test continuing implementation when no progress exists."""
        # Set up mocks
        mock_load.return_value = None  # No existing progress

        # Call the method
        result = self.implementation_manager.continue_implementation()

        # Verify result
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "No existing implementation progress found")

    @patch.object(ImplementationManager, "_load_progress_tracker")
    @patch.object(ImplementationManager, "_find_next_task")
    def test_continue_implementation_all_completed(
        self, mock_find: MagicMock, mock_load: MagicMock
    ) -> None:
        """Test continuing implementation when all tasks are completed."""
        # Set up mocks
        mock_load.return_value = {
            "tasks": [
                {"id": "1", "status": "completed"},
                {"id": "2", "status": "completed"},
            ]
        }
        mock_find.return_value = None  # No pending tasks

        # Call the method
        result = self.implementation_manager.continue_implementation()

        # Verify result
        self.assertTrue(result["success"])
        self.assertEqual(result["message"], "All tasks are completed")

    @patch.object(ImplementationManager, "_run_tests")
    def test_execute_request_failed_tests(self, mock_run_tests: MagicMock) -> None:
        """Verify failing tests mark the result as unsuccessful."""
        task = {"description": "Implement feature"}

        # Router agent reports success
        self.implementation_manager.router_agent = MagicMock()
        self.implementation_manager.router_agent.execute_request.return_value = {
            "success": True
        }

        # Tests fail
        mock_run_tests.return_value = {"success": False, "error": "Tests failed"}

        result = self.implementation_manager._execute_implementation_request(task)

        self.assertFalse(result["success"])
        self.assertIn("tests", result)


if __name__ == "__main__":
    unittest.main()
