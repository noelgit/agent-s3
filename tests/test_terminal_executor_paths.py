import os
from agent_s3.terminal_executor import TerminalExecutor

class DummyConfig:
    def __init__(self, allowed_dirs):
        self.config = {"allowed_dirs": allowed_dirs}


def test_validate_absolute_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    file_path = allowed / "file.txt"
    file_path.write_text("data")
    executor = TerminalExecutor(DummyConfig([str(allowed)]))
    is_valid, _ = executor._validate_command(f"cat {file_path}")
    assert is_valid


def test_validate_relative_path(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    file_path = allowed / "file.txt"
    file_path.write_text("data")
    executor = TerminalExecutor(DummyConfig([str(allowed)]))
    prev_cwd = os.getcwd()
    os.chdir(allowed)
    try:
        is_valid, _ = executor._validate_command("cat ./file.txt")
    finally:
        os.chdir(prev_cwd)
    assert is_valid


def test_symlink_outside_directory(tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("secret")
    link = allowed / "link.txt"
    link.symlink_to(target)
    executor = TerminalExecutor(DummyConfig([str(allowed)]))
    is_valid, msg = executor._validate_command(f"cat {link}")
    assert not is_valid
    assert "restricted path" in msg


def test_command_substitution_backticks(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    executor = TerminalExecutor(DummyConfig([str(allowed)]))
    is_valid, msg = executor._validate_command("echo `whoami`")
    assert not is_valid
    assert "substitution" in msg.lower()


def test_command_substitution_dollar_parens(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    executor = TerminalExecutor(DummyConfig([str(allowed)]))
    is_valid, msg = executor._validate_command("echo $(whoami)")
    assert not is_valid
    assert "substitution" in msg.lower()


def test_validate_path_with_spaces(tmp_path):
    allowed = tmp_path / "allowed dir"
    allowed.mkdir()
    file_path = allowed / "file.txt"
    file_path.write_text("data")
    executor = TerminalExecutor(DummyConfig([str(tmp_path)]))
    cmd = f'cat "{file_path}"'
    is_valid, _ = executor._validate_command(cmd)
    assert is_valid
