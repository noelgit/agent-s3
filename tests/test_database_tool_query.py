from unittest.mock import MagicMock

import pytest

from agent_s3.tools.database_tool import DatabaseTool

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
