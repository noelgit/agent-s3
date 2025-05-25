import io
import subprocess
import types

from agent_s3.terminal_executor import TerminalExecutor
from agent_s3.tools.error_context_manager import ErrorContextManager
from agent_s3.tools.git_tool import GitTool

class DummyConfig:
    def __init__(self):
        self.config = {}

def test_terminal_executor_uses_list(monkeypatch):
    captured = {}
    def fake_popen(args, **kwargs):
        captured['args'] = args
        captured['shell'] = kwargs.get('shell')
        class P:
            def __init__(self):
                self.stdout = io.StringIO('out')
                self.returncode = 0
            def wait(self):
                pass
            def kill(self):
                pass
        return P()
    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    executor = TerminalExecutor(DummyConfig())
    code, out = executor.run_command('echo hello')
    assert captured['args'] == ['echo', 'hello']
    assert captured['shell'] is None
    assert code == 0

def test_git_tool_uses_list(monkeypatch):
    captured = {}
    def fake_popen(args, **kwargs):
        captured['args'] = args
        captured['shell'] = kwargs.get('shell')
        class P:
            def communicate(self):
                return ('git output', '')
            @property
            def returncode(self):
                return 0
        return P()
    monkeypatch.setattr(subprocess, 'Popen', fake_popen)
    tool = GitTool(github_token='tok')
    code, out = tool.run_git_command('status')
    assert captured['args'] == ['git', 'status']
    assert captured['shell'] is None
    assert code == 0

def test_error_context_manager_sanitizes_package(monkeypatch):
    captured = {}
    def fake_run(args, **kwargs):
        captured['args'] = args
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    ecm = ErrorContextManager()
    res = ecm.attempt_automated_recovery({
        'error_type': 'import',
        'message': "No module named 'mypkg'"
    }, {})
    assert captured['args'] == ['pip', 'install', 'mypkg']
    assert res[0]

    res_invalid = ecm.attempt_automated_recovery({
        'error_type': 'import',
        'message': "No module named 'bad;rm'"
    }, {})
    assert 'Invalid package name' in res_invalid[1]
