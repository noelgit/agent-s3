from unittest.mock import MagicMock, patch
from contextlib import nullcontext

from agent_s3.coordinator import Coordinator
from agent_s3.tools.context_management.context_registry import ContextRegistry


def test_coordinator_get_current_context_snapshot_returns_mock():
    """Coordinator.get_current_context_snapshot should return registry snapshot."""
    mocked_snapshot = {"context": "mock"}
    with patch.object(ContextRegistry, "get_current_context_snapshot", return_value=mocked_snapshot) as mock_snapshot:
        coordinator = Coordinator.__new__(Coordinator)
        coordinator.context_registry = ContextRegistry()
        coordinator.error_handler = MagicMock()
        coordinator.error_handler.error_context.return_value = nullcontext()

        result = coordinator.get_current_context_snapshot(context_type="test", query="value")

        mock_snapshot.assert_called_once_with(context_type="test", query="value")
        assert result == mocked_snapshot
