import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


def load_bash_tool():
    module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "tools" / "bash_tool.py"
    spec = importlib.util.spec_from_file_location("bash_tool", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BashTool = load_bash_tool().BashTool


class TestBashToolBlocking(unittest.TestCase):
    def setUp(self):
        with patch.object(BashTool, "_check_docker_available", return_value=False):
            self.tool = BashTool()

    def test_blocked_command_with_spaces(self):
        code, msg = self.tool.run_command(" rm -rf /tmp ")
        self.assertEqual(code, 1)
        self.assertIn("blocked", msg)

    def test_blocked_command_in_quotes(self):
        code, msg = self.tool.run_command("echo 'rm -rf'")
        self.assertEqual(code, 1)
        self.assertIn("blocked", msg)

    def test_allowed_command(self):
        with patch.object(self.tool, "_run_with_subprocess", return_value=(0, "ok")):
            code, msg = self.tool.run_command("ls -la")
        self.assertEqual(code, 0)
        self.assertEqual(msg, "ok")


if __name__ == "__main__":
    unittest.main()
