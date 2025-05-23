import pytest
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config

@pytest.fixture
def coordinator():
    config = Config()
    config.config = {
        "complexity_threshold": 300.0,
        "max_attempts": 3,
        "max_plan_attempts": 2,
        "task_state_directory": "./task_snapshots",
        "sandbox_environment": True,
        "host_os_type": "linux",
        "context_management": {"enabled": False}
    }
    with patch('agent_s3.coordinator.EnhancedScratchpadManager'), \
         patch('agent_s3.coordinator.ProgressTracker'), \
         patch('agent_s3.coordinator.FileTool'), \
         patch('agent_s3.coordinator.BashTool'), \
         patch('agent_s3.coordinator.GitTool'), \
         patch('agent_s3.coordinator.CodeAnalysisTool'), \
         patch('agent_s3.coordinator.TaskStateManager'), \
         patch('agent_s3.coordinator.TaskResumer'), \
         patch('agent_s3.coordinator.WorkspaceInitializer'), \
         patch('agent_s3.coordinator.DatabaseManager'):

        coord = Coordinator(config=config)
        coord.prompt_moderator = MagicMock()
        coord.prompt_moderator.max_plan_iterations = 0
        coord.scratchpad = MagicMock()
        coord.error_handler = MagicMock()
        coord.error_handler.error_context = MagicMock(return_value=MagicMock(__enter__=lambda self: None, __exit__=lambda self, exc, val, tb: False))
        coord.context_registry = MagicMock()
        coord.router_agent = MagicMock()
        yield coord

def test_plan_approval_loop_returns_two_elements(coordinator):
    plan = {"plan_id": 1}
    decision, returned_plan = coordinator.plan_approval_loop(plan)
    assert isinstance(decision, str)
    assert returned_plan == plan
