import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_s3.coordinator.orchestrator import WorkflowOrchestrator
from agent_s3.coordinator.registry import CoordinatorRegistry
from agent_s3.tools.file_tool import FileTool
from agent_s3.enhanced_scratchpad_manager import LogLevel


class DummyScratchpad:
    def __init__(self):
        self.log = MagicMock()


class DummyCoordinator:
    def __init__(self):
        self.scratchpad = DummyScratchpad()
        self.LogLevel = LogLevel


def setup_orchestrator(tmp_path):
    registry = CoordinatorRegistry(config=None)
    file_tool = FileTool(allowed_dirs=[str(tmp_path)])
    bash_tool = MagicMock()
    registry.register_tool("file_tool", file_tool)
    registry.register_tool("bash_tool", bash_tool)
    coordinator = DummyCoordinator()
    orchestrator = WorkflowOrchestrator(coordinator, registry)
    return orchestrator, bash_tool, file_tool


@pytest.fixture
def orchestrator_fixture(tmp_path, monkeypatch):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    orchestrator, bash_tool, file_tool = setup_orchestrator(tmp_path)
    yield orchestrator, bash_tool, file_tool
    os.chdir(cwd)


def test_dependency_added_and_installed(orchestrator_fixture):
    orchestrator, bash_tool, file_tool = orchestrator_fixture
    file_tool.write_file("requirements.txt", "requests\n")
    changes = {str(Path("app.py")): "import requests\nimport flask\n"}
    bash_tool.run_command.return_value = (0, "installed")

    result = orchestrator._apply_changes_and_manage_dependencies(changes)

    assert result is True
    bash_tool.run_command.assert_called_once_with(
        "pip install -r requirements.txt", timeout=300
    )
    success, content = file_tool.read_file("requirements.txt")
    assert success
    assert "flask" in content


def test_install_failure_returns_false(orchestrator_fixture):
    orchestrator, bash_tool, file_tool = orchestrator_fixture
    file_tool.write_file("requirements.txt", "")
    changes = {"mod.py": "import flask"}
    bash_tool.run_command.return_value = (1, "failed")

    result = orchestrator._apply_changes_and_manage_dependencies(changes)

    assert result is False
    bash_tool.run_command.assert_called_once()
