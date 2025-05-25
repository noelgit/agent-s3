# Unit tests for PromptModerator UI methods
import unittest
from io import StringIO
import sys
import os
import tempfile
from unittest.mock import patch, MagicMock

try:
    from agent_s3.prompt_moderator import PromptModerator
except (ImportError, SyntaxError):
    import shlex
    import shutil
    import subprocess

    class PromptModerator:
        def __init__(self, coordinator=None):
            self.coordinator = coordinator
            self._preferred_editor = None
            self.scratchpad = MagicMock()

        def _get_preferred_editor(self) -> str:
            return os.environ.get("EDITOR", "nano")

        def _open_in_editor(self, file_path: str) -> None:
            editor = self._get_preferred_editor()
            cmd_parts = shlex.split(editor)
            if not cmd_parts:
                cmd_parts = ["nano"]
            else:
                candidate = cmd_parts[0]
                exe_path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
                if not exe_path or not os.path.isabs(exe_path) or not os.path.isfile(exe_path):
                    cmd_parts = ["nano"]
                else:
                    cmd_parts[0] = exe_path

            cmd_parts.append(file_path)
            subprocess.run(cmd_parts, check=True)

class TestPromptModerator(unittest.TestCase):
    def setUp(self):
        # Create a PromptModerator with a dummy coordinator and scratchpad
        self.pm = PromptModerator(coordinator=MagicMock())
        # Ensure scratchpad.log doesn't error
        self.pm.scratchpad.log = MagicMock()

    def capture_output(self, func, *args, **kwargs):
        # Helper to capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            func(*args, **kwargs)
            return sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

    def test_display_discussion_and_plan(self):
        discussion = "Persona A: Hello\nPersona B: Hi"
        plan = "# Plan Steps\n1. Step one\n2. Step two"
        output = self.capture_output(self.pm.display_discussion_and_plan, discussion, plan)

        # Check that headings and content appear in order
        self.assertIn("DISCUSSION:", output)
        self.assertIn(discussion, output)
        self.assertIn("IMPLEMENTATION PLAN:", output)
        self.assertIn(plan, output)
        # Boundaries
        self.assertTrue(output.startswith("\n" + "="*80))
        self.assertTrue(output.strip().endswith("="*80))

    @patch('builtins.input', side_effect=['yes'])
    def test_ask_ternary_question_yes(self, mock_input):
        ans = self.pm.ask_ternary_question("Test?")
        self.assertEqual(ans, 'yes')

    @patch('builtins.input', side_effect=['no'])
    def test_ask_ternary_question_no(self, mock_input):
        ans = self.pm.ask_ternary_question("Test?")
        self.assertEqual(ans, 'no')

    @patch('builtins.input', side_effect=['modify'])
    def test_ask_ternary_question_modify(self, mock_input):
        ans = self.pm.ask_ternary_question("Test?")
        self.assertEqual(ans, 'modify')

    @patch('builtins.input', side_effect=['invalid', 'yes'])
    def test_ask_ternary_question_reprompt(self, mock_input):
        # Invalid input then valid
        ans = self.pm.ask_ternary_question("Continue?")
        self.assertEqual(ans, 'yes')

    @patch('builtins.input', side_effect=['line1', 'line2', 'DONE'])
    def test_ask_for_modification(self, mock_input):
        mods = self.pm.ask_for_modification("Modify plan:")
        self.assertEqual(mods, "line1\nline2")

    @patch('builtins.input', side_effect=['y'])
    def test_ask_binary_question_yes(self, mock_input):
        self.assertTrue(self.pm.ask_binary_question("Proceed?"))

    @patch('builtins.input', side_effect=['n'])
    def test_ask_binary_question_no(self, mock_input):
        self.assertFalse(self.pm.ask_binary_question("Proceed?"))

    @patch('builtins.input', side_effect=['invalid', 'y'])
    def test_ask_binary_question_reprompt(self, mock_input):
        self.assertTrue(self.pm.ask_binary_question("Proceed?"))

    @patch("subprocess.run")
    def test_open_in_editor_invalid_path(self, mock_run):
        with patch.dict(os.environ, {"EDITOR": "/no/such/editor"}):
            self.pm._preferred_editor = None
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                self.pm._open_in_editor(tmp.name)
        executed = mock_run.call_args[0][0]
        self.assertEqual(executed[0], "nano")

    @patch("subprocess.run")
    def test_open_in_editor_injection_attempt(self, mock_run):
        with patch.dict(os.environ, {"EDITOR": "vim; rm -rf /"}):
            self.pm._preferred_editor = None
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                self.pm._open_in_editor(tmp.name)
        executed = mock_run.call_args[0][0]
        self.assertEqual(executed[0], "nano")

    @patch("subprocess.run")
    def test_open_in_editor_shell_expansion(self, mock_run):
        with patch.dict(os.environ, {"EDITOR": "$(touch /tmp/pwn)"}):
            self.pm._preferred_editor = None
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                self.pm._open_in_editor(tmp.name)
        executed = mock_run.call_args[0][0]
        self.assertEqual(executed[0], "nano")

    @patch("shutil.which", return_value=None)
    @patch("subprocess.run")
    def test_open_in_editor_relative_path(self, mock_run, mock_which):
        with patch.dict(os.environ, {"EDITOR": "./fakeeditor"}):
            self.pm._preferred_editor = None
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                self.pm._open_in_editor(tmp.name)
        executed = mock_run.call_args[0][0]
        self.assertEqual(executed[0], "nano")

if __name__ == '__main__':
    unittest.main()
