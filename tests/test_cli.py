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
        # Stub command processor to emulate minimal command handling
        def stub_process_command(cmd: str):
            if cmd.startswith("/plan"):
                arg = cmd[len("/plan"):].strip()
                self.mock_coordinator.generate_plan(arg)
                return "Plan written to plan.txt"
            if cmd == "/test":
                self.mock_coordinator.run_tests_all()
                return "Executing /test: running all tests..."
            if cmd == "/debug":
                self.mock_coordinator.debug_last_test()
                return "Executing /debug: analyzing last test failure..."
            if cmd.startswith("/terminal"):
                arg = cmd[len("/terminal"):].strip()
                self.mock_coordinator.execute_terminal_command(arg)
                return f"Executing terminal command: {arg}"
            if cmd.startswith("/request"):
                arg = cmd[len("/request"):].strip()
                self.mock_coordinator.process_change_request(arg)
                return ""
            if cmd.startswith("/continue"):
                continue_type = cmd.split(" ", 1)[1].strip() if " " in cmd else "implementation"
                result = self.mock_coordinator.execute_continue(continue_type)
                if not result.get("success", False):
                    return f"Continuation failed: {result.get('error', 'Unknown error')}"
                if continue_type == "implementation":
                    if result.get("next_task"):
                        return f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}"
                    return result.get("message", "All implementation tasks completed.")
                return result.get("message", f"{continue_type.capitalize()} continuation completed.")
            return f"Unknown command: {cmd}"

        self.mock_coordinator.command_processor = MagicMock()
        self.mock_coordinator.command_processor.process_command.side_effect = stub_process_command

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
    def test_continue_command(self, mock_print):
        # Success scenario
        self.mock_coordinator.execute_continue.return_value = {
            "success": True,
            "message": "done",
        }
        process_command(self.mock_coordinator, "/continue")
        self.mock_coordinator.execute_continue.assert_called_once_with("implementation")
        mock_print.assert_any_call("done")

        # Failure scenario
        mock_print.reset_mock()
        self.mock_coordinator.execute_continue.reset_mock()
        self.mock_coordinator.execute_continue.return_value = {
            "success": False,
            "error": "msg",
        }
        process_command(self.mock_coordinator, "/continue")
        self.mock_coordinator.execute_continue.assert_called_once_with("implementation")
        mock_print.assert_any_call("Continuation failed: msg")

    @patch('builtins.print')
    def test_unknown_command(self, mock_print):
        process_command(self.mock_coordinator, "/unknown")
        mock_print.assert_called_once_with("Unknown command: /unknown")
        self.mock_coordinator.execute_terminal_command.assert_not_called()

if __name__ == '__main__':
    unittest.main()
