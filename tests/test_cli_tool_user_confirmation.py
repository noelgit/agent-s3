import os
import sys
from unittest.mock import patch, MagicMock

from agent_s3 import cli


def run_main_with_prompt(prompt, user_input):
    with patch.object(sys, 'argv', ['agent-s3', prompt]):
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token'}):
            dummy_config = MagicMock()
            dummy_config.config = {}
            with patch('agent_s3.cli.Config', return_value=dummy_config):
                with patch('agent_s3.cli.Coordinator') as MockCoordinator:
                    coordinator_instance = MockCoordinator.return_value
                    with patch('agent_s3.cli.RouterAgent') as MockRouter:
                        router_instance = MockRouter.return_value
                        router_instance.call_llm_by_role.return_value = (
                            '{"category": "tool_user", "rationale": "", "confidence": 0.99}'
                        )
                        with patch('builtins.input', return_value=user_input):
                            cli.main()
                            return coordinator_instance


def test_tool_user_executes_on_confirmation():
    coord = run_main_with_prompt('ls', 'y')
    coord.execute_terminal_command.assert_called_once_with('ls')


def test_tool_user_aborts_without_confirmation():
    coord = run_main_with_prompt('ls', 'n')
    coord.execute_terminal_command.assert_not_called()

