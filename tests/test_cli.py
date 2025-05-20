# tests/test_cli.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

import unittest
from unittest.mock import patch, MagicMock
from agent_s3.cli import process_command
from agent_s3.coordinator import Coordinator

class TestCliProcessCommand(unittest.TestCase):
    def setUp(self):
        self.mock_coordinator = MagicMock(spec=Coordinator)

    @patch('builtins.print')
    def test_plan_command(self, mock_print):
        self.mock_coordinator.generate_plan.return_value = "step1\nstep2"
        process_command(self.mock_coordinator, "/plan add login")
        mock_print.assert_any_call("Plan written to plan.txt")

    @patch('builtins.print')
    def test_test_command(self, mock_print):
        process_command(self.mock_coordinator, "/test")
        self.mock_coordinator.run_tests_all.assert_called_once()
        mock_print.assert_any_call("Executing /test: running all tests...")

    @patch('builtins.print')
    def test_debug_command(self, mock_print):
        process_command(self.mock_coordinator, "/debug")
        self.mock_coordinator.debug_last_test.assert_called_once()
        mock_print.assert_any_call("Executing /debug: analyzing last test failure...")

    @patch('builtins.print')
    def test_terminal_command(self, mock_print):
        process_command(self.mock_coordinator, "/terminal echo hi")
        self.mock_coordinator.execute_terminal_command.assert_called_once_with("echo hi")
        mock_print.assert_any_call("Executing terminal command: echo hi")

    @patch('builtins.print')
    def test_request_command(self, mock_print):
        process_command(self.mock_coordinator, "/request add login")
        self.mock_coordinator.process_change_request.assert_called_once_with("add login")
        mock_print.assert_not_called()

    @patch('builtins.print')
    def test_unknown_command(self, mock_print):
        process_command(self.mock_coordinator, "/unknown")
        mock_print.assert_called_once_with("Unknown command: /unknown")
        self.mock_coordinator.execute_terminal_command.assert_not_called()

if __name__ == '__main__':
    unittest.main()