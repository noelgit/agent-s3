from unittest.mock import MagicMock
from agent_s3.coordinator import Coordinator


def _make_coordinator():
    coord = Coordinator.__new__(Coordinator)
    coord.scratchpad = MagicMock()
    coord.coordinator_config = MagicMock()
    git_tool = MagicMock()
    git_tool.create_branch.return_value = {"success": True}
    git_tool.commit_changes.return_value = {"success": True}
    git_tool.push_changes.return_value = {"success": True}
    git_tool.create_pull_request.return_value = "https://example.com/pr/1"
    git_tool.run_git_command.return_value = (0, "")
    coord.coordinator_config.get_tool.return_value = git_tool
    return coord, git_tool


def test_create_pr_success():
    coord, git_tool = _make_coordinator()
    pr_url = coord._create_pr([], "body", branch_name="feature", pr_title="title")

    assert pr_url == "https://example.com/pr/1"
    git_tool.create_branch.assert_called_once_with("feature", source_branch="main")
    git_tool.run_git_command.assert_called_with("add -A")
    git_tool.commit_changes.assert_called_once_with("title", add_all=False)
    git_tool.push_changes.assert_called_once_with("feature", set_upstream=True)
    git_tool.create_pull_request.assert_called_once_with(
        "title", "body", head_branch="feature", base_branch="main", draft=False
    )
