import pytest
from unittest.mock import MagicMock
from agent_s3.task_resumer import TaskResumer
from agent_s3.task_state_manager import PRCreationState


def _make_resumer():
    coord = MagicMock()
    coord._create_pr_branch = MagicMock()
    coord._stage_pr_changes = MagicMock()
    coord._commit_pr_changes = MagicMock()
    coord._push_pr_branch = MagicMock()
    coord._submit_pr = MagicMock()
    task_state_manager = MagicMock()
    return TaskResumer(coord, task_state_manager, scratchpad=MagicMock(), progress_tracker=MagicMock()), coord


def test_resume_pr_creation_from_branch():
    resumer, coord = _make_resumer()
    state = PRCreationState("task1", "feature", "title", "body", None)
    state.sub_state = "CREATING_BRANCH"
    resumer._resume_pr_creation_phase(state)

    coord._create_pr_branch.assert_called_once_with("feature", "main")
    coord._stage_pr_changes.assert_called_once()
    coord._commit_pr_changes.assert_called_once_with("title")
    coord._push_pr_branch.assert_called_once_with("feature")
    coord._submit_pr.assert_called_once_with("feature", "title", "body", "main", False)
