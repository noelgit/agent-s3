from agent_s3.terminal_executor import TerminalExecutor

class DummyConfig:
    def __init__(self):
        self.config = {}


def test_block_rm_rf_with_extra_spaces():
    executor = TerminalExecutor(DummyConfig())
    is_valid, msg = executor._validate_command("rm    -rf /")
    assert not is_valid
    assert "forbidden token" in msg.lower()


def test_block_rm_rf_with_quotes():
    executor = TerminalExecutor(DummyConfig())
    is_valid, msg = executor._validate_command('"rm -rf"')
    assert not is_valid
    assert "forbidden token" in msg.lower()
