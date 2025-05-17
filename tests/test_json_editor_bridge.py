import unittest
import sys
import types
from pathlib import Path

# Stub out agent_s3 package to avoid importing heavy dependencies via __init__.
if 'agent_s3' not in sys.modules:
    pkg = types.ModuleType('agent_s3')
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'agent_s3')]
    sys.modules['agent_s3'] = pkg

# Stub communication package to avoid importing its __init__ which requires
# optional dependencies like jsonschema.
comm_pkg = types.ModuleType('agent_s3.communication')
comm_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'agent_s3' / 'communication')]
sys.modules.setdefault('agent_s3.communication', comm_pkg)

# Provide a minimal vscode_bridge module to satisfy imports inside json_editor_bridge
vc_stub = types.ModuleType('agent_s3.communication.vscode_bridge')
class VSCodeBridge:
    pass
vc_stub.VSCodeBridge = VSCodeBridge
sys.modules['agent_s3.communication.vscode_bridge'] = vc_stub

# Stub message_protocol to avoid jsonschema dependency
mp_stub = types.ModuleType('agent_s3.communication.message_protocol')
class Message: ...
class MessageType: ...
class MessageBus: ...
class OutputCategory: ...
mp_stub.Message = Message
mp_stub.MessageType = MessageType
mp_stub.MessageBus = MessageBus
mp_stub.OutputCategory = OutputCategory
sys.modules['agent_s3.communication.message_protocol'] = mp_stub

from agent_s3.communication.json_editor_bridge import JSONPath


class TestJSONPath(unittest.TestCase):
    """Tests for JSONPath helper methods."""

    def test_parse_path(self):
        path = "feature_groups[0].features[1].name"
        components = JSONPath.parse_path(path)
        self.assertEqual(components, ["feature_groups", 0, "features", 1, "name"])

    def test_get_and_set_value(self):
        data = {}
        JSONPath.set_value(data, "items[0].name", "foo")
        self.assertEqual(data, {"items": [{"name": "foo"}]})
        self.assertEqual(JSONPath.get_value(data, "items[0].name"), "foo")

        JSONPath.set_value(data, "items[1]", {"name": "bar"})
        self.assertEqual(JSONPath.get_value(data, "items[1].name"), "bar")
        self.assertEqual(len(data["items"]), 2)


if __name__ == "__main__":
    unittest.main()
