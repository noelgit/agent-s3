import os
import pytest
from unittest.mock import MagicMock

from agent_s3.deployment_manager import DeploymentManager, DeploymentConfig, DatabaseConfig


@pytest.fixture
def manager():
    coordinator = MagicMock()
    coordinator.bash_tool = MagicMock()
    coordinator.file_tool = MagicMock()
    coordinator.env_tool = MagicMock()
    coordinator.database_tool = MagicMock()
    coordinator.scratchpad = MagicMock()
    return DeploymentManager(coordinator)


def test_setup_environment_existing_requirements(manager, monkeypatch):
    config = DeploymentConfig(app_name="app", app_type="python")
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    manager.env_tool.activate_virtual_env.return_value = "source venv/bin/activate && "
    manager.bash_tool.run_command.return_value = (0, "ok")

    result = manager._setup_environment(config)

    assert result["success"] is True
    manager.bash_tool.run_command.assert_called_once_with(
        "source venv/bin/activate && pip install -r requirements.txt", timeout=300
    )


def test_setup_environment_install_failure(manager, monkeypatch):
    config = DeploymentConfig(app_name="app", app_type="python")
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    manager.env_tool.activate_virtual_env.return_value = ""
    manager.bash_tool.run_command.return_value = (1, "fail")

    result = manager._setup_environment(config)

    assert result["success"] is False
    assert "fail" in result["error"]


def test_setup_environment_generates_requirements(manager, monkeypatch):
    config = DeploymentConfig(app_name="app", app_type="python")
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.setattr(
        DeploymentManager,
        "_generate_default_requirements",
        lambda self, c: "flask\n",
    )
    manager.file_tool.write_file.return_value = True
    manager.bash_tool.run_command.return_value = (0, "done")

    result = manager._setup_environment(config)

    assert result["success"] is True
    manager.file_tool.write_file.assert_called_once_with("requirements.txt", "flask\n")


def test_create_env_file_success(manager):
    config = DeploymentConfig(app_name="app", app_type="flask")
    config.get_environment_vars = MagicMock(return_value={"APP_NAME": "app"})
    manager._generate_secret_key = MagicMock(return_value="SECRET")
    manager.file_tool.write_file.return_value = True

    result = manager._create_env_file(config)

    assert result["success"] is True
    assert result["env_vars"]["SECRET_KEY"] == "SECRET"
    manager.file_tool.write_file.assert_called_once()


def test_create_env_file_write_failure(manager):
    config = DeploymentConfig(app_name="app", app_type="flask")
    config.get_environment_vars = MagicMock(return_value={})
    manager._generate_secret_key = MagicMock(return_value="SECRET")
    manager.file_tool.write_file.return_value = False

    result = manager._create_env_file(config)

    assert result["success"] is False


def test_setup_database_sqlite_creates_dir(manager, monkeypatch):
    db_config = DatabaseConfig(db_type="sqlite", database="data/db.sqlite")
    made_dirs = []

    monkeypatch.setattr(os.path, "exists", lambda p: False)
    monkeypatch.setattr(os, "makedirs", lambda p, exist_ok=True: made_dirs.append(p))

    result = manager._setup_database(db_config)

    assert result["success"] is True
    assert made_dirs == ["data"]


def test_setup_database_postgresql_with_tool(manager):
    db_tool = manager.database_tool
    db_tool.config = MagicMock()
    db_tool.config.config = {}
    db_tool.test_connection.return_value = {"success": True}

    db_config = DatabaseConfig(
        db_type="postgresql",
        host="localhost",
        port=5432,
        username="user",
        password="pass",
        database="testdb",
    )

    result = manager._setup_database(db_config)

    assert result["success"] is True
    assert "deployment" in db_tool.config.config.get("databases", {})
    db_tool.test_connection.assert_called_once_with("deployment")
