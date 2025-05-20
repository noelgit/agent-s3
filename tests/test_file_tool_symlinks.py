import os
from agent_s3.tools.file_tool import FileTool


def test_symlink_outside_workspace_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("secret")
    link = workspace / "link.txt"
    link.symlink_to(secret)

    ft = FileTool(allowed_dirs=[str(workspace)])
    allowed, msg = ft._is_path_allowed(str(link))
    assert not allowed
    assert "outside allowed directories" in msg
