from agent_s3.tools.file_tool import FileTool

def test_read_file_override_max_size(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "test.txt"
    test_file.write_text("0123456789")  # 10 bytes

    ft = FileTool(allowed_dirs=[str(workspace)], max_file_size=100)

    # Without override should succeed
    success, content = ft.read_file(str(test_file))
    assert success
    assert content == "0123456789"

    # Override with smaller max_size to trigger failure
    success, error = ft.read_file(str(test_file), max_size=5)
    assert not success
    assert "exceeds" in error

