import importlib.util
from pathlib import Path
import sys
import types

def load_json_editor_bridge(monkeypatch):
    """Load json_editor_bridge module with stubbed VSCode dependencies."""
    comm_pkg = types.ModuleType("agent_s3.communication")
    vb_pkg = types.ModuleType("agent_s3.communication.vscode_bridge")
    vb_pkg.VSCodeBridge = type("VSCodeBridge", (), {})
    mpkg = types.ModuleType("agent_s3.communication.message_protocol")
    mpkg.Message = type("Message", (), {})
    mpkg.MessageType = type("MessageType", (), {})

    monkeypatch.setitem(sys.modules, "agent_s3.communication", comm_pkg)
    monkeypatch.setitem(sys.modules, "agent_s3.communication.vscode_bridge", vb_pkg)
    monkeypatch.setitem(sys.modules, "agent_s3.communication.message_protocol", mpkg)

    module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "communication" / "json_editor_bridge.py"
    spec = importlib.util.spec_from_file_location("agent_s3.communication.json_editor_bridge", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_path(monkeypatch):
    mod = load_json_editor_bridge(monkeypatch)
    path = "feature_groups[0].features[1].name"
    components = mod.JSONPath.parse_path(path)
    assert components == ["feature_groups", 0, "features", 1, "name"]


def test_set_and_get_value(monkeypatch):
    mod = load_json_editor_bridge(monkeypatch)
    data = {}
    mod.JSONPath.set_value(data, "a.b[0].c", 42)
    assert data == {"a": {"b": [{"c": 42}]}}
    value = mod.JSONPath.get_value(data, "a.b[0].c")
    assert value == 42

