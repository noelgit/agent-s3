from pathlib import Path
import sys
import pytest
from unittest.mock import MagicMock

# Add project root to sys.path for module resolution
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_coordinator():
    """Create a canonical mock coordinator for testing.
    
    This is the single source of truth for coordinator mocking.
    Use this instead of creating custom coordinator mocks in individual tests.
    """
    coordinator = MagicMock()
    
    # Common coordinator attributes
    coordinator.config = MagicMock()
    coordinator.config.config = {}
    coordinator.scratchpad = MagicMock()
    coordinator.progress_tracker = MagicMock()
    coordinator.task_state_manager = MagicMock()
    coordinator.workspace_initializer = MagicMock()
    coordinator.implementation_manager = MagicMock()
    coordinator.deployment_manager = MagicMock()
    coordinator.context_manager = MagicMock()
    coordinator.bash_tool = MagicMock()
    coordinator.file_tool = MagicMock()
    coordinator.database_manager = MagicMock()
    
    # Common method return values
    coordinator.workspace_initializer.initialize_workspace.return_value = True
    coordinator.bash_tool.run_command.return_value = (0, "Command output")
    coordinator.initialize_workspace.return_value = {
        "success": True,
        "is_workspace_valid": True,
        "created_files": [],
        "errors": []
    }
    
    return coordinator
