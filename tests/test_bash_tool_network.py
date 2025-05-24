import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

def load_bash_tool():
    module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "tools" / "bash_tool.py"
    spec = importlib.util.spec_from_file_location("bash_tool", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BashTool = load_bash_tool().BashTool


class DummyResult:
    def __init__(self, returncode=0, stdout=""):
        self.returncode = returncode
        self.stdout = stdout


class TestBashToolNetwork(unittest.TestCase):
    def setUp(self):
        self.tool = BashTool()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tool.workspace_dir = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_in_container_uses_restricted_network(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            return DummyResult(returncode=0, stdout="ok")

        with patch.object(subprocess, "run", fake_run):
            code, out = self.tool._run_in_container("echo hi", timeout=5)

        self.assertEqual(code, 0)
        self.assertIn("--network", captured["args"])
        net_idx = captured["args"].index("--network") + 1
        self.assertNotEqual(captured["args"][net_idx], "host")

    def test_disallowed_network_access_fails(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            return DummyResult(returncode=1, stdout="network unreachable")

        with patch.object(subprocess, "run", fake_run):
            code, out = self.tool._run_in_container("curl http://example.com", timeout=5)

        self.assertNotEqual(code, 0)
        self.assertIn("--network", captured["args"])
        net_idx = captured["args"].index("--network") + 1
        self.assertNotEqual(captured["args"][net_idx], "host")


if __name__ == "__main__":
    unittest.main()
