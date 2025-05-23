import os
import sys
from unittest.mock import patch, MagicMock
from agent_s3 import cli

class MinimalCoordinator:
    def __init__(self, *args, **kwargs):
        self._command_processor = None

    @property
    def command_processor(self):
        if self._command_processor is None:
            self._command_processor = MagicMock()
        return self._command_processor


def test_tool_user_branch_without_preexisting_command_processor():
    with patch.object(sys, 'argv', ['agent-s3', 'ls']):
        with patch.dict(os.environ, {'GITHUB_TOKEN': 't'}):
            dummy_config = MagicMock()
            dummy_config.config = {}
            with patch('agent_s3.cli.Config', return_value=dummy_config):
                instance_holder = {}

                def factory(*args, **kwargs):
                    instance_holder['obj'] = MinimalCoordinator(*args, **kwargs)
                    return instance_holder['obj']

                with patch('agent_s3.cli.Coordinator', side_effect=factory):
                    with patch('agent_s3.cli.RouterAgent') as MockRouter:
                        MockRouter.return_value.call_llm_by_role.return_value = (
                            '{"category": "tool_user", "rationale": "", "confidence": 0.99}'
                        )
                        with patch('builtins.input', return_value='y'):
                            cli.main()
                            assert instance_holder['obj'].command_processor.execute_terminal_command.called
