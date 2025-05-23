from agent_s3.tools.file_tool import FileTool


def test_prefix_path_rejected(tmp_path):
    allowed_dir = tmp_path / "tmp"
    allowed_dir.mkdir()
    prefix_dir = tmp_path / "tmpfoo" / "bar"
    prefix_dir.mkdir(parents=True)
    ft = FileTool(allowed_dirs=[str(allowed_dir)])
    allowed, msg = ft._is_path_allowed(str(prefix_dir))
    assert not allowed
    assert "outside allowed directories" in msg


def test_subdirectory_allowed(tmp_path):
    allowed_dir = tmp_path / "tmp"
    sub_dir = allowed_dir / "foo" / "bar"
    sub_dir.mkdir(parents=True)
    ft = FileTool(allowed_dirs=[str(allowed_dir)])
    allowed, _ = ft._is_path_allowed(str(sub_dir))
    assert allowed
