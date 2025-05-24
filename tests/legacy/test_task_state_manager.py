"""Unit tests for the TaskStateManager functionality."""
import os
import shutil
import tempfile
from unittest import TestCase
from unittest import mock

from agent_s3.task_state_manager import ExecutionState
from agent_s3.task_state_manager import PlanningState
from agent_s3.task_state_manager import TaskState
from agent_s3.task_state_manager import TaskStateManager

    TaskStateManager,
    TaskState,
    PlanningState,
    ExecutionState
)


class TestTaskStateManager(TestCase):
    """Tests for the TaskStateManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for task snapshots
        self.temp_dir = tempfile.mkdtemp()
        self.manager = TaskStateManager(base_dir=self.temp_dir)

        # Create a sample task state
        self.task_id = self.manager.create_new_task_id()
        self.test_state = PlanningState(
            task_id=self.task_id,
            request_text="Test request",
            code_context={"file1.py": "content"},
            tech_stack={"languages": ["python"]}
        )
        self.test_state.plan = {"steps": ["step1", "step2"]}
        self.test_state.discussion = "Test discussion"

    def tearDown(self):
        """Tear down test fixtures."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_create_new_task_id(self):
        """Test creating a new task ID."""
        task_id = self.manager.create_new_task_id()
        self.assertIsNotNone(task_id)
        self.assertIsInstance(task_id, str)

    def test_get_task_dir(self):
        """Test getting the task directory."""
        task_dir = self.manager.get_task_dir(self.task_id)
        self.assertTrue(os.path.exists(task_dir))
        self.assertTrue(os.path.isdir(task_dir))

    def test_save_and_load_task_snapshot(self):
        """Test saving and loading a task snapshot."""
        # Save the state
        success = self.manager.save_task_snapshot(self.test_state)
        self.assertTrue(success)

        # Check that the file was created
        snapshot_file = os.path.join(self.manager.get_task_dir(self.task_id), "planning.json")
        self.assertTrue(os.path.exists(snapshot_file))

        # Load the state
        loaded_state = self.manager.load_task_snapshot(self.task_id, "planning")
        self.assertIsNotNone(loaded_state)
        self.assertEqual(loaded_state.task_id, self.task_id)
        self.assertEqual(loaded_state.phase, "planning")
        self.assertEqual(loaded_state.request_text, "Test request")
        self.assertEqual(loaded_state.plan, {"steps": ["step1", "step2"]})
        self.assertEqual(loaded_state.discussion, "Test discussion")

    def test_get_active_tasks(self):
        """Test getting active tasks."""
        # Save multiple states
        self.manager.save_task_snapshot(self.test_state)

        # Create another task
        task_id2 = self.manager.create_new_task_id()
        state2 = ExecutionState(
            task_id=task_id2,
            changes=[{"file_path": "file1.py", "content": "content"}],
            iteration=1,
            test_results={"success": True}
        )
        self.manager.save_task_snapshot(state2)

        # Get active tasks
        active_tasks = self.manager.get_active_tasks()
        self.assertEqual(len(active_tasks), 2)

        # Check that task IDs are in the active tasks
        task_ids = [task.get("task_id") for task in active_tasks]
        self.assertIn(self.task_id, task_ids)
        self.assertIn(task_id2, task_ids)

    def test_delete_task(self):
        """Test deleting a task."""
        # Save a state
        self.manager.save_task_snapshot(self.test_state)

        # Delete the task
        success = self.manager.delete_task(self.task_id)
        self.assertTrue(success)

        # Check that the task directory no longer exists
        task_dir = os.path.join(self.temp_dir, self.task_id)
        self.assertFalse(os.path.exists(task_dir))

        # Check that the task is no longer in active tasks
        active_tasks = self.manager.get_active_tasks()
        task_ids = [task.get("task_id") for task in active_tasks]
        self.assertNotIn(self.task_id, task_ids)

    def test_clear_state(self):
        """Test clearing a task state."""
        # Save a state
        self.manager.save_task_snapshot(self.test_state)

        # Clear the state
        success = self.manager.clear_state(self.task_id)
        self.assertTrue(success)

        # Check that the task directory no longer exists
        task_dir = os.path.join(self.temp_dir, self.task_id)
        self.assertFalse(os.path.exists(task_dir))

    def test_cleanup_old_snapshots(self):
        """Test cleaning up old snapshots."""
        # Save a state
        self.manager.save_task_snapshot(self.test_state)

        # Mock the getmtime function to make the task look old
        with mock.patch('os.path.getmtime', return_value=0):
            # Run cleanup
            self.manager._cleanup_old_snapshots(max_age_days=0)

            # Check that the task was deleted
            task_dir = os.path.join(self.temp_dir, self.task_id)
            self.assertFalse(os.path.exists(task_dir))

    def test_recover_from_corrupted_snapshot(self):
        """Test recovering from a corrupted snapshot."""
        # Save a state
        self.manager.save_task_snapshot(self.test_state)

        # Corrupt the snapshot file
        snapshot_file = os.path.join(self.manager.get_task_dir(self.task_id), "planning.json")
        with open(snapshot_file, "r") as f:
            content = f.read()

        with open(snapshot_file, "w") as f:
            f.write("CORRUPTED" + content)

        # Try to recover
        recovered_state = self.manager.recover_from_corrupted_snapshot(self.task_id, "planning")

        # It should successfully recover since our corruption still contains the valid JSON
        self.assertIsNotNone(recovered_state)
        self.assertEqual(recovered_state.task_id, self.task_id)
        self.assertEqual(recovered_state.phase, "planning")
        self.assertEqual(recovered_state.request_text, "Test request")

    def test_base_task_state(self):
        """Test the base TaskState class."""
        state = TaskState(task_id=self.task_id)
        self.assertEqual(state.task_id, self.task_id)
        self.assertEqual(state.phase, "base")

        # Test to_dict method
        state_dict = state.to_dict()
        self.assertEqual(state_dict["task_id"], self.task_id)
        self.assertEqual(state_dict["phase"], "base")

        # Test from_dict method
        loaded_state = TaskState.from_dict(state_dict)
        self.assertEqual(loaded_state.task_id, self.task_id)
        self.assertEqual(loaded_state.phase, "base")
