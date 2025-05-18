import os
import json
import unittest
import tempfile
from pathlib import Path
import importlib.util
import sys
import types

module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "router_agent.py"
spec = importlib.util.spec_from_file_location("router_agent", module_path)
router_agent = importlib.util.module_from_spec(spec)
sys.modules.setdefault("requests", types.ModuleType("requests"))
jsonschema_stub = types.ModuleType("jsonschema")

class _ValidationError(Exception):
    def __init__(self, message, path=None):
        super().__init__(message)
        self.message = message
        self.path = path or []

def _validate(instance, schema):
    required = ["model", "role", "context_window", "parameters", "api"]
    for key in required:
        if key not in instance:
            raise _ValidationError(f"Missing {key}", path=[key])
    if not isinstance(instance["context_window"], int):
        raise _ValidationError("context_window must be int", path=["context_window"])
jsonschema_stub.validate = _validate
jsonschema_stub.exceptions = types.SimpleNamespace(ValidationError=_ValidationError)
sys.modules.setdefault("jsonschema", jsonschema_stub)
spec.loader.exec_module(router_agent)


class TestLLMConfigSchema(unittest.TestCase):
    def test_invalid_schema_rejected(self):
        """LLM config with wrong types should raise ValueError."""
        invalid = [{"model": 123, "role": "test"}]
        with tempfile.TemporaryDirectory() as tmp_dir:
            llm_path = Path(tmp_dir) / "llm.json"
            llm_path.write_text(json.dumps(invalid))
            cwd = os.getcwd()
            os.chdir(tmp_dir)
            try:
                with self.assertRaises(ValueError):
                    router_agent._load_llm_config()
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
