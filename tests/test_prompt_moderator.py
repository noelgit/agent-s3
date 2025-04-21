# Unit tests for PromptModerator UI methods
import unittest
from io import StringIO
import sys
from unittest.mock import patch, MagicMock

try:
    from agent_s3.prompt_moderator import PromptModerator
except ImportError:
    PromptModerator = None

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
        self.assertIn("PERSONA DEBATE DISCUSSION:", output)
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

if __name__ == '__main__':
    unittest.main()
