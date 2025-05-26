# tests/test_cli.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))

import unittest
from unittest.mock import patch, MagicMock
import types

# Provide a dummy Coordinator to avoid heavy imports during testing
sys.modules['agent_s3.coordinator'] = types.SimpleNamespace(Coordinator=object)
sys.modules['agent_s3.router_agent'] = types.SimpleNamespace(RouterAgent=object)
sys.modules['agent_s3.config'] = types.SimpleNamespace(Config=object)
from agent_s3.cli import process_command


class TestCliProcessCommand(unittest.TestCase):
    def setUp(self):
        self.mock_coordinator = MagicMock()
        command_processor = MagicMock()

        def stub_plan(args: str):
            self.mock_coordinator.generate_plan(args)
            return "Plan written to plan.txt"

        def stub_test(args: str):
            self.mock_coordinator.run_tests_all()
            return "Executing /test: running all tests..."

        def stub_debug(args: str):
            self.mock_coordinator.debug_last_test()
            return "Executing /debug: analyzing last test failure..."

        def stub_terminal(args: str):
            self.mock_coordinator.execute_terminal_command(args)
            return f"Executing terminal command: {args}"

        def stub_request(args: str):
            self.mock_coordinator.process_change_request(args)
            return ""

        def stub_continue(args: str):
            continue_type = args.strip() if args else "implementation"
            result = self.mock_coordinator.execute_continue(continue_type)
            if not result.get("success", False):
                return f"Continuation failed: {result.get('error', 'Unknown error')}"
            if continue_type == "implementation":
                if result.get("next_task"):
                    return f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}"
                return result.get("message", "All implementation tasks completed.")
            return result.get("message", f"{continue_type.capitalize()} continuation completed.")

        command_processor.execute_plan_command.side_effect = stub_plan
        command_processor.execute_test_command.side_effect = stub_test
        command_processor.execute_debug_command.side_effect = stub_debug
        command_processor.execute_terminal_command.side_effect = stub_terminal
        command_processor.execute_request_command.side_effect = stub_request
        command_processor.execute_continue_command.side_effect = stub_continue

        self.mock_coordinator.command_processor = command_processor

    @patch('builtins.print')
    def test_plan_command(self, mock_print):
        self.mock_coordinator.generate_plan.return_value = "step1\nstep2"
        process_command(self.mock_coordinator, "/plan add login")
        self.mock_coordinator.command_processor.execute_plan_command.assert_called_once_with("add login")
        mock_print.assert_any_call("Plan written to plan.txt")

    @patch('builtins.print')
    def test_test_command(self, mock_print):
        process_command(self.mock_coordinator, "/test")
        self.mock_coordinator.command_processor.execute_test_command.assert_called_once_with("")
        mock_print.assert_any_call("Executing /test: running all tests...")

    @patch('builtins.print')
    def test_debug_command(self, mock_print):
        process_command(self.mock_coordinator, "/debug")
        self.mock_coordinator.command_processor.execute_debug_command.assert_called_once_with("")
        mock_print.assert_any_call("Executing /debug: analyzing last test failure...")

    @patch('builtins.print')
    def test_terminal_command(self, mock_print):
        process_command(self.mock_coordinator, "/terminal echo hi")
        self.mock_coordinator.command_processor.execute_terminal_command.assert_called_once_with("echo hi")
        mock_print.assert_any_call("Executing terminal command: echo hi")

    @patch('builtins.print')
    def test_request_command(self, mock_print):
        process_command(self.mock_coordinator, "/request add login")
        self.mock_coordinator.command_processor.execute_request_command.assert_called_once_with("add login")
        mock_print.assert_not_called()

    @patch('builtins.print')
    def test_continue_command(self, mock_print):
        # Success scenario
        self.mock_coordinator.execute_continue.return_value = {
            "success": True,
            "message": "done",
        }
        process_command(self.mock_coordinator, "/continue")
        self.mock_coordinator.command_processor.execute_continue_command.assert_called_once_with("")
        mock_print.assert_any_call("done")

        # Failure scenario
        mock_print.reset_mock()
        self.mock_coordinator.command_processor.execute_continue_command.reset_mock()
        self.mock_coordinator.execute_continue.reset_mock()
        self.mock_coordinator.execute_continue.return_value = {
            "success": False,
            "error": "msg",
        }
        process_command(self.mock_coordinator, "/continue")
        self.mock_coordinator.command_processor.execute_continue_command.assert_called_once_with("")
        mock_print.assert_any_call("Continuation failed: msg")

    @patch('builtins.print')
    def test_unknown_command(self, mock_print):
        process_command(self.mock_coordinator, "/unknown")
        mock_print.assert_called_once_with("Unknown command: unknown. Type /help for available commands.")
        self.mock_coordinator.command_processor.execute_terminal_command.assert_not_called()

if __name__ == '__main__':
    unittest.main()
