"""
Unit tests for EnvTool.
"""
from unittest.mock import MagicMock
from agent_s3.tools.env_tool import EnvTool

def test_activate_virtual_env_detects_venv(monkeypatch):
    bash_tool = MagicMock()
    # Simulate .venv exists
    monkeypatch.setattr("os.path.exists", lambda p: p.endswith(".venv/bin/activate"))
    env_tool = EnvTool(bash_tool)
    prefix = env_tool.activate_virtual_env()
    assert prefix.startswith("source .venv/bin/activate")

def test_activate_virtual_env_no_env(monkeypatch):
    bash_tool = MagicMock()
    monkeypatch.setattr("os.path.exists", lambda p: False)
    env_tool = EnvTool(bash_tool)
    prefix = env_tool.activate_virtual_env()
    assert prefix == ""

def test_get_installed_packages_parses_output():
    bash_tool = MagicMock()
    bash_tool.run_command.return_value = (0, "requests==2.31.0\nnumpy==1.25.0\n")
    env_tool = EnvTool(bash_tool)
    pkgs = env_tool.get_installed_packages()
    assert "requests" in pkgs and pkgs["requests"] == "2.31.0"
    assert "numpy" in pkgs and pkgs["numpy"] == "1.25.0"
