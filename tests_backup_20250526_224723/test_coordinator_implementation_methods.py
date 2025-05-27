from unittest.mock import MagicMock
from unittest.mock import patch

from agent_s3.coordinator import Coordinator

def create_coordinator():
    coord = Coordinator.__new__(Coordinator)
    coord.scratchpad = MagicMock()
    coord.scratchpad.log = MagicMock()
    coord.error_handler = MagicMock()
    coord.error_handler.handle_exception = MagicMock()
    coord.implementation_manager = MagicMock()
    coord.orchestrator = MagicMock()
    # Add missing attributes that the real coordinator would have
    coord.orchestrator.execute_implementation = MagicMock()
    coord.orchestrator.execute_continue = MagicMock()
    return coord


@patch('os.path.exists', return_value=True)
def test_execute_implementation_delegates(mock_exists):
    coord = create_coordinator()
    coord.orchestrator.execute_implementation.return_value = {"success": True}

    result = coord.execute_implementation("design.txt")

    coord.orchestrator.execute_implementation.assert_called_once_with("design.txt")
    assert result["success"] is True


def test_execute_continue_delegates():
    coord = create_coordinator()
    coord.orchestrator.execute_continue.return_value = {"success": True}

    result = coord.execute_continue("implementation")

    coord.orchestrator.execute_continue.assert_called_once_with("implementation")
    assert result["success"] is True
