import os
import pytest

from agent_s3.context_manager import ContextManager


def test_symlink_outside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("x")
    link = workspace / "link.txt"
    link.symlink_to(secret)

    prev_cwd = os.getcwd()
    os.chdir(workspace)
    try:
        with pytest.raises(ValueError):
            ContextManager._validate_path(str(link))
    finally:
        os.chdir(prev_cwd)


def test_symlink_inside_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "target.txt"
    target.write_text("y")
    link = workspace / "link.txt"
    link.symlink_to(target)

    prev_cwd = os.getcwd()
    os.chdir(workspace)
    try:
        ContextManager._validate_path(str(link))
    finally:
        os.chdir(prev_cwd)
