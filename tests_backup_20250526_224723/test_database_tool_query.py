from unittest.mock import MagicMock
from contextlib import contextmanager

import pytest

from agent_s3.tools.database_tool import DatabaseTool, OperationalError

class DummyConfig:
    def __init__(self):
        self.config = {
            "databases": {
                "default": {
                    "type": "postgresql",
                    "host": "localhost",
                    "port": 5432,
                    "database": "db",
                    "username": "user",
                    "password": "pass",
                }
            }
        }


@pytest.fixture
def db_tool(monkeypatch):
    monkeypatch.setattr("agent_s3.tools.database_tool.BashTool", MagicMock())
    monkeypatch.setattr(DatabaseTool, "_setup_connections", lambda self: None)
    return DatabaseTool(DummyConfig())


def test_execute_query_sqlalchemy_success(db_tool, monkeypatch):
    db_tool.use_sqlalchemy = True
    db_tool.connections["default"] = MagicMock()
    db_tool._execute_with_sqlalchemy = MagicMock(return_value={"success": True, "results": [1]})
    db_tool._execute_with_bash_tool = MagicMock()

    result = db_tool.execute_query("SELECT 1")

    db_tool._execute_with_sqlalchemy.assert_called_once()
    db_tool._execute_with_bash_tool.assert_not_called()
    assert result["success"] is True
    assert result["results"] == [1]


def test_execute_query_cli_when_no_sqlalchemy(db_tool):
    db_tool.use_sqlalchemy = False
    db_tool._execute_with_bash_tool = MagicMock(return_value={"success": True})

    result = db_tool.execute_query("SELECT 1")

    db_tool._execute_with_bash_tool.assert_called_once()
    assert result["success"] is True


def test_execute_query_fallback_on_error(db_tool, monkeypatch):
    class DummyOpError(Exception):
        pass

    monkeypatch.setattr("agent_s3.tools.database_tool.OperationalError", DummyOpError)
    db_tool.use_sqlalchemy = True
    db_tool.connections["default"] = MagicMock()
    db_tool._execute_with_sqlalchemy = MagicMock(side_effect=DummyOpError("fail"))
    db_tool._execute_with_bash_tool = MagicMock(return_value={"success": True})

    result = db_tool.execute_query("SELECT 1")

    db_tool._execute_with_bash_tool.assert_called_once()
    assert result["success"] is True


def test_execute_with_bash_tool_sqlalchemy_path(monkeypatch):
    monkeypatch.setattr(DatabaseTool, "_setup_connections", lambda self: None)
    tool = DatabaseTool(DummyConfig())
    tool.use_sqlalchemy = True

    mock_conn = MagicMock()

    @contextmanager
    def fake_conn(*_args, **_kwargs):
        yield mock_conn

    monkeypatch.setattr(tool, "get_connection", fake_conn)
    mock_conn.execute.return_value = MagicMock(mappings=lambda: [{"n": 1}])
    tool.bash_tool.run_command = MagicMock()

    result = tool._execute_with_bash_tool("SELECT :n", {"n": 1}, "default")

    mock_conn.execute.assert_called_once()
    tool.bash_tool.run_command.assert_not_called()
    assert result["success"] is True


def test_execute_with_bash_tool_shell_fallback(monkeypatch):
    monkeypatch.setattr(DatabaseTool, "_setup_connections", lambda self: None)
    tool = DatabaseTool(DummyConfig())
    tool.use_sqlalchemy = True

    @contextmanager
    def fail_conn(*_args, **_kwargs):
        raise OperationalError("fail", {}, None)
        yield  # pragma: no cover

    monkeypatch.setattr(tool, "get_connection", fail_conn)
    tool.bash_tool.run_command = MagicMock(return_value=(0, "[]"))
    monkeypatch.setattr(tool, "_build_db_command", lambda *a, **k: "cmd")
    monkeypatch.setattr(tool, "_clean_csv_output", lambda x: x)
    monkeypatch.setattr(tool, "_parse_cli_output", lambda x, y: [])

    result = tool._execute_with_bash_tool("SELECT 1", {}, "default")

    tool.bash_tool.run_command.assert_called_once()
    assert result["success"] is True
