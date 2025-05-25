"""Task State Manager for task resumption functionality.

Defines serializable state interfaces for each workflow phase and handles state persistence.
"""

import os
import json
import uuid
import logging
import time
from typing import Dict, Any, List, Optional, Type, cast
from datetime import datetime
import stat

# Set up logging
logger = logging.getLogger(__name__)

class TaskState:
    """Base class for all task state objects."""

    def __init__(self, task_id: str):
        """Initialize the task state with a unique task ID.

        Args:
            task_id: Unique identifier for the task
        """
        self.task_id = task_id
        self.timestamp = datetime.now().isoformat()
        self.phase = "base"  # Will be overridden by subclasses

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization.

        Returns:
            Dictionary representation of the state
        """
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            "phase": self.phase
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskState':
        """Create a task state from a dictionary.

        Args:
            data: Dictionary representation of the state

        Returns:
            Instantiated task state object
        """
        state = cls(task_id=data.get("task_id", ""))
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.phase = data.get("phase", "base")
        return state


class PlanningState(TaskState):
    """State for the planning phase."""

    def __init__(self, task_id: str, request_text: str, code_context: Dict[str, Any],
         tech_stack: Dict[str, Any]):        """Initialize the planning state.

        Args:
            task_id: Unique identifier for the task
            request_text: The original user request
            code_context: Context about the code relevant to the task
            tech_stack: Information about the tech stack
        """
        super().__init__(task_id)
        self.phase = "planning"
        self.request_text = request_text
        self.code_context = code_context
        self.tech_stack = tech_stack
        self.plan: Dict[str, Any] = {}  # Will be populated during planning
        self.discussion: str = ""  # Will be populated during planning

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "request_text": self.request_text,
            "code_context": self.code_context,
            "tech_stack": self.tech_stack,
            "plan": self.plan,
            "discussion": self.discussion
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanningState':
        """Create a planning state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            request_text=data.get("request_text", ""),
            code_context=data.get("code_context", {}),
            tech_stack=data.get("tech_stack", {})
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.plan = data.get("plan", {})
        state.discussion = data.get("discussion", "")
        return state


class PromptApprovalState(TaskState):
    """State for the prompt approval phase."""

    def __init__(self, task_id: str, plan: Dict[str, Any], discussion: str):
        """Initialize the prompt approval state.

        Args:
            task_id: Unique identifier for the task
            plan: The plan generated during planning
            discussion: Discussion from the planning phase
        """
        super().__init__(task_id)
        self.phase = "prompt_approval"
        self.plan = plan
        self.discussion = discussion
        self.is_approved = False
        self.user_modifications = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "plan": self.plan,
            "discussion": self.discussion,
            "is_approved": self.is_approved,
            "user_modifications": self.user_modifications
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptApprovalState':
        """Create a prompt approval state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            plan=data.get("plan", {}),
            discussion=data.get("discussion", "")
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.is_approved = data.get("is_approved", False)
        state.user_modifications = data.get("user_modifications", "")
        return state


class IssueCreationState(TaskState):
    """State for the issue creation phase."""

    def __init__(self, task_id: str, title: str, body: str):
        """Initialize the issue creation state.

        Args:
            task_id: Unique identifier for the task
            title: Issue title
            body: Issue body
        """
        super().__init__(task_id)
        self.phase = "issue_creation"
        self.title = title
        self.body = body
        self.issue_url = None
        self.is_created = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "title": self.title,
            "body": self.body,
            "issue_url": self.issue_url,
            "is_created": self.is_created
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IssueCreationState':
        """Create an issue creation state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            title=data.get("title", ""),
            body=data.get("body", "")
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.issue_url = data.get("issue_url")
        state.is_created = data.get("is_created", False)
        return state


class CodeGenerationState(TaskState):
    """State for the code generation phase."""

    def __init__(self, task_id: str, plan: Dict[str, Any], issue_url: Optional[str],
                 code_context: Dict[str, Any], tech_stack: Dict[str, Any]):
        """Initialize the code generation state.

        Args:
            task_id: Unique identifier for the task
            plan: The plan to implement
            issue_url: URL of the issue (if created)
            code_context: Context about the code relevant to the task
            tech_stack: Information about the tech stack
        """
        super().__init__(task_id)
        self.phase = "code_generation"
        self.plan = plan
        self.issue_url = issue_url
        self.code_context = code_context
        self.tech_stack = tech_stack
        self.generated_changes: List[Dict[str, Any]] = []
        self.current_iteration = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "plan": self.plan,
            "issue_url": self.issue_url,
            "code_context": self.code_context,
            "tech_stack": self.tech_stack,
            "generated_changes": self.generated_changes,
            "current_iteration": self.current_iteration
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodeGenerationState':
        """Create a code generation state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            plan=data.get("plan", {}),
            issue_url=data.get("issue_url"),
            code_context=data.get("code_context", {}),
            tech_stack=data.get("tech_stack", {})
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.generated_changes = data.get("generated_changes", [])
        state.current_iteration = data.get("current_iteration", 0)
        return state


class ExecutionState(TaskState):
    """State for the execution phase."""

    def __init__(self, task_id: str, changes: List[Dict[str, Any]], iteration: int,
         test_results: Dict[str, Any]):        """Initialize the execution state.

        Args:
            task_id: Unique identifier for the task
            changes: List of code changes to apply
            iteration: Current iteration number
            test_results: Results of tests (if any)
        """
        super().__init__(task_id)
        self.phase = "execution"
        self.changes = changes
        self.iteration = iteration
        self.test_results = test_results
        self.is_applied = False
        self.errors: List[Dict[str, Any]] = []

        # Added sub-state for fine-grained resumption
        self.sub_state = "PREPARING"  # Possible values: PREPARING, APPLYING_CHANGES, RUNNING_TESTS, ANALYZING_RESULTS

        # Added intermediate data for resumption
        self.raw_test_output: Optional[str] = None  # Store raw test output before parsing
        self.pending_changes: List[Dict[str, Any]] = []  # Track which changes still need to be applied
        self.applied_changes: List[Dict[str, Any]] = []  # Track which changes have been applied

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "changes": self.changes,
            "iteration": self.iteration,
            "test_results": self.test_results,
            "is_applied": self.is_applied,
            "errors": self.errors,
            "sub_state": self.sub_state,
            "raw_test_output": self.raw_test_output,
            "pending_changes": self.pending_changes,
            "applied_changes": self.applied_changes
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionState':
        """Create an execution state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            changes=data.get("changes", []),
            iteration=data.get("iteration", 0),
            test_results=data.get("test_results", {})
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.is_applied = data.get("is_applied", False)
        state.errors = data.get("errors", [])

        # Restore granular sub-state for resumption
        state.sub_state = data.get("sub_state", "PREPARING")
        state.raw_test_output = data.get("raw_test_output")
        state.pending_changes = data.get("pending_changes", [])
        state.applied_changes = data.get("applied_changes", [])

        return state


class PRCreationState(TaskState):
    """State for the pull request creation phase."""

    def __init__(self, task_id: str, branch_name: str, pr_title: str, pr_body: str,
         issue_url: Optional[str]):        """Initialize the PR creation state.

        Args:
            task_id: Unique identifier for the task
            branch_name: Git branch name for the PR
            pr_title: Pull request title
            pr_body: Pull request body
            issue_url: URL of the issue (if created)
        """
        super().__init__(task_id)
        self.phase = "pr_creation"
        self.branch_name = branch_name
        self.pr_title = pr_title
        self.pr_body = pr_body
        self.issue_url = issue_url
        self.pr_url = None
        self.is_created = False

        # Added sub-state for fine-grained resumption
        self.sub_state = "PREPARING"  # Possible values: PREPARING, CREATING_BRANCH, COMMITTING, PUSHING, CREATING_API_REQUEST

        # Added intermediate data for resumption
        self.commit_sha = None  # Store commit SHA for atomic operations
        self.base_branch = "main"  # Default base branch
        self.draft = False  # Default PR type (not draft)
        self.api_response = None  # Store API response data

    def to_dict(self) -> Dict[str, Any]:
        """Convert the state to a dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "branch_name": self.branch_name,
            "pr_title": self.pr_title,
            "pr_body": self.pr_body,
            "issue_url": self.issue_url,
            "pr_url": self.pr_url,
            "is_created": self.is_created,
            "sub_state": self.sub_state,
            "commit_sha": self.commit_sha,
            "base_branch": self.base_branch,
            "draft": self.draft,
            "api_response": self.api_response
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PRCreationState':
        """Create a PR creation state from a dictionary."""
        state = cls(
            task_id=data.get("task_id", ""),
            branch_name=data.get("branch_name", ""),
            pr_title=data.get("pr_title", ""),
            pr_body=data.get("pr_body", ""),
            issue_url=data.get("issue_url")
        )
        state.timestamp = data.get("timestamp", datetime.now().isoformat())
        state.pr_url = data.get("pr_url")
        state.is_created = data.get("is_created", False)

        # Restore granular sub-state for resumption
        state.sub_state = data.get("sub_state", "PREPARING")
        state.commit_sha = data.get("commit_sha")
        state.base_branch = data.get("base_branch", "main")
        state.draft = data.get("draft", False)
        state.api_response = data.get("api_response")

        return state


class TaskStateManager:
    """Manages task state snapshots for resumption."""

    def __init__(self, base_dir: str):
        """Initialize the task state manager.

        Args:
            base_dir: Base directory for storing task snapshots
        """
        self.base_dir = base_dir
        self.state_classes: Dict[str, Type[TaskState]] = {
            "planning": PlanningState,
            "prompt_approval": PromptApprovalState,
            "issue_creation": IssueCreationState,
            "code_generation": CodeGenerationState,
            "execution": ExecutionState,
            "pr_creation": PRCreationState
        }

        # Create the base directory if it doesn't exist
        os.makedirs(self.base_dir, exist_ok=True)

        # Clean up old task snapshots (>7 days old)
        self._cleanup_old_snapshots()

    def create_new_task_id(self) -> str:
        """Create a new unique task ID.

        Returns:
            A unique task ID string
        """
        return str(uuid.uuid4())

    def get_task_dir(self, task_id: str) -> str:
        """Get the directory path for a task.

        Args:
            task_id: Task ID

        Returns:
            Path to the task directory
        """
        task_dir = os.path.join(self.base_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        return task_dir

    def save_task_snapshot(self, state: TaskState) -> bool:
        """Save a task state snapshot.

        Args:
            state: Task state to save

        Returns:
            True if saved successfully, False otherwise
        """
        task_dir = self.get_task_dir(state.task_id)
        snapshot_file = os.path.join(task_dir, f"{state.phase}.json")

        try:
            # Convert state to dictionary
            state_dict = state.to_dict()

            # Add metadata
            state_dict["_snapshot_timestamp"] = datetime.now().isoformat()

            # Write to temporary file first for atomic operation
            temp_file = f"{snapshot_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(state_dict, f, indent=2)

            # Set secure permissions (read/write for owner only)
            os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)

            # Atomic rename to the final file
            os.replace(temp_file, snapshot_file)

            logger.info("%s", Saved task snapshot: {snapshot_file})
            return True
        except Exception:
            logger.exception("Error saving task snapshot")
            return False

    def load_task_snapshot(self, task_id: str, phase: str) -> Optional[TaskState]:
        """Load a task state snapshot.

        Args:
            task_id: Task ID
            phase: Workflow phase

        Returns:
            Task state or None if not found or error
        """
        task_dir = self.get_task_dir(task_id)
        snapshot_file = os.path.join(task_dir, f"{phase}.json")

        if not os.path.exists(snapshot_file):
            logger.warning("%s", Task snapshot not found: {snapshot_file})
            return None

        try:
            with open(snapshot_file, "r") as f:
                state_dict = json.load(f)

            if phase not in self.state_classes:
                logger.warning("%s", Unknown phase: {phase})
                return None

            # Create state object from dictionary
            state_class = self.state_classes[phase]
            state = cast(TaskState, state_class.from_dict(state_dict))

            logger.info("%s", Loaded task snapshot: {snapshot_file})
            return state
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in task snapshot: %s", snapshot_file)
            return None
        except Exception:
            logger.exception("Error loading task snapshot")
            return None

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get a list of active tasks.

        Returns:
            List of task metadata dictionaries
        """
        active_tasks = []

        try:
            # List task directories
            if not os.path.exists(self.base_dir):
                return []

            task_dirs = [d for d in os.listdir(self.base_dir)
                         if os.path.isdir(os.path.join(self.base_dir, d))]

            for task_id in task_dirs:
                task_dir = os.path.join(self.base_dir, task_id)

                # Check for valid task snapshots
                snapshot_files = [f for f in os.listdir(task_dir)
                                  if f.endswith(".json") and not f.endswith(".tmp")]

                if not snapshot_files:
                    continue

                # Get the latest snapshot
                latest_file = max(snapshot_files, key=lambda f: os.path.getmtime(os.path.join(task_dir, f)))
                latest_phase = latest_file.replace(".json", "")

                try:
                    # Load the snapshot to get task metadata
                    with open(os.path.join(task_dir, latest_file), "r") as f:
                        state_dict = json.load(f)

                    # Get basic task information
                    active_tasks.append({
                        "task_id": task_id,
                        "phase": latest_phase,
                        "timestamp": state_dict.get("timestamp", ""),
                        "last_updated": datetime.fromtimestamp(
                            os.path.getmtime(os.path.join(task_dir, latest_file))).isoformat(),
                        "request_text": state_dict.get("request_text", "Unknown task")
                    })
                except Exception:
                    logger.exception("Error reading task snapshot")

            # Sort by last updated time, newest first
            active_tasks.sort(key=lambda t: t.get("last_updated", ""), reverse=True)

            return active_tasks
        except Exception:
            logger.exception("Error getting active tasks")
            return []

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and all its snapshots.

        Args:
            task_id: Task ID

        Returns:
            True if deleted successfully, False otherwise
        """
        task_dir = self.get_task_dir(task_id)

        if not os.path.exists(task_dir):
            logger.warning("%s", Task directory not found: {task_dir})
            return False

        try:
            # Delete all files in the task directory
            for file in os.listdir(task_dir):
                os.remove(os.path.join(task_dir, file))

            # Delete the task directory
            os.rmdir(task_dir)

            logger.info("%s", Deleted task: {task_id})
            return True
        except Exception:
            logger.exception("Error deleting task")
            return False

    def clear_state(self, task_id: str) -> bool:
        """Clear a task's state after successful completion.

        This is an alias for delete_task() that provides a more semantically
        appropriate name for clearing completed task state.

        Args:
            task_id: Task ID

        Returns:
            True if cleared successfully, False otherwise
        """
        return self.delete_task(task_id)

    def _cleanup_old_snapshots(self, max_age_days: int = 7) -> None:
        """Clean up old task snapshots.

        Args:
            max_age_days: Maximum age of snapshots in days
        """
        if not os.path.exists(self.base_dir):
            return

        try:
            # Get current time
            now = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60

            # List task directories
            task_dirs = [d for d in os.listdir(self.base_dir)
                         if os.path.isdir(os.path.join(self.base_dir, d))]

            for task_id in task_dirs:
                task_dir = os.path.join(self.base_dir, task_id)

                # Check the modification time of the task directory
                mtime = os.path.getmtime(task_dir)
                age = now - mtime

                if age > max_age_seconds:
                    # Delete old tasks
                    logger.info("%s", Cleaning up old task: {task_id} (age: {age/86400:.1f} days))
                    self.delete_task(task_id)
        except Exception:
            logger.exception("Error cleaning up old snapshots")

    def recover_from_corrupted_snapshot(self, task_id: str, phase: str) -> Optional[TaskState]:
        """Attempt to recover from a corrupted snapshot.

        Args:
            task_id: Task ID
            phase: Workflow phase

        Returns:
            Recovered task state or None if recovery failed
        """
        task_dir = self.get_task_dir(task_id)
        snapshot_file = os.path.join(task_dir, f"{phase}.json")

        if not os.path.exists(snapshot_file):
            logger.warning("%s", Snapshot file not found: {snapshot_file})
            return None

        try:
            # Try to read the file as raw text
            with open(snapshot_file, "r") as f:
                content = f.read()

            # Look for valid JSON in the content
            valid_json = None
            for i in range(len(content)):
                try:
                    # Try to parse a substring as JSON
                    candidate = content[i:]
                    state_dict = json.loads(candidate)
                    if isinstance(state_dict, dict) and "task_id" in state_dict:
                        valid_json = state_dict
                        break
                except json.JSONDecodeError:
                    continue

            if valid_json:
                # Create state object from recovered JSON
                if phase in self.state_classes:
                    state_class = self.state_classes[phase]
                    state = cast(TaskState, state_class.from_dict(valid_json))

                    # Save the recovered state
                    self.save_task_snapshot(state)

                    logger.info("%s", Recovered task snapshot: {snapshot_file})
                    return state

            # If recovery failed, try to find an earlier version of the same phase
            backup_files = [f for f in os.listdir(task_dir)
                           if f.startswith(f"{phase}_") and f.endswith(".json")]

            if backup_files:
                # Get the latest backup
                latest_backup = max(backup_files, key=lambda f: os.path.getmtime(os.path.join(task_dir, f)))

                with open(os.path.join(task_dir, latest_backup), "r") as f:
                    state_dict = json.load(f)

                # Create state object from backup
                if phase in self.state_classes:
                    state_class = self.state_classes[phase]
                    state = cast(TaskState, state_class.from_dict(state_dict))

                    # Save the recovered state
                    self.save_task_snapshot(state)

                    logger.info("%s", Recovered task snapshot from backup: {latest_backup})
                    return state

            # Try to find the previous phase
            phase_order = ["planning", "prompt_approval", "issue_creation", "code_generation", "execution", "pr_creation"]
            if phase in phase_order:
                phase_idx = phase_order.index(phase)
                if phase_idx > 0:
                    prev_phase = phase_order[phase_idx - 1]
                    prev_state = self.load_task_snapshot(task_id, prev_phase)

                    if prev_state:
                        logger.info("%s", Found previous phase snapshot: {prev_phase})
                        return prev_state

            logger.exception("Failed to recover task snapshot: %s", snapshot_file)
            return None
        except Exception:
            logger.exception("Error recovering task snapshot")
            return None
