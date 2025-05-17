import json
import unittest
import sys
import types
from pathlib import Path

# Create lightweight agent_s3 package stub to avoid heavy optional dependencies.
if 'agent_s3' not in sys.modules:
    pkg = types.ModuleType('agent_s3')
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'agent_s3')]
    sys.modules['agent_s3'] = pkg

from agent_s3.schema_validator import (
    extract_json,
    sanitize_response,
    parse_with_fallback,
    validate_llm_response,
    JsonValidator,
    TestCase,
)


class TestSchemaValidator(unittest.TestCase):
    """Tests for schema validator helpers."""

    def test_extract_json(self):
        text = "prefix ```json\n{\"a\": 1}\n``` suffix"
        self.assertEqual(extract_json(text), {"a": 1})

        text = "before {\"b\": 2} after"
        self.assertEqual(extract_json(text), {"b": 2})

    def test_sanitize_response(self):
        dirty = "<script>alert('x');</script> rm -rf /tmp && exec('hi')"
        cleaned = sanitize_response(dirty)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("rm -rf", cleaned)
        self.assertNotIn("exec(", cleaned)

    def test_parse_with_fallback(self):
        parser = json.loads
        result = parse_with_fallback('{"x":1}', parser, {})
        self.assertEqual(result, {"x": 1})

        fallback = parse_with_fallback('bad', parser, {"f": True})
        self.assertEqual(fallback, {"f": True})

    def test_validate_llm_response_success(self):
        payload = {
            "description": "d",
            "inputs": {"a": 1},
            "expected_output": 2,
            "expected_exception": None,
            "assertions": ["a == 1"],
        }
        # Pydantic v1 compatibility: provide a model_validate method
        if not hasattr(TestCase, "model_validate"):
            TestCase.model_validate = classmethod(lambda cls, data: cls.parse_obj(data))

        ok, res = validate_llm_response(json.dumps(payload), TestCase)
        self.assertTrue(ok)
        self.assertIsInstance(res, TestCase)

    def test_json_validator_plan_validation(self):
        validator = JsonValidator()
        plan = {
            "functional_plan": {
                "overview": "o",
                "steps": [],
                "file_changes": [],
                "functions": [],
            },
            "test_plan": {
                "test_files": [],
                "test_scenarios": [],
                "test_cases": [],
            },
        }
        valid, err = validator.validate_plan_json(plan)
        self.assertTrue(valid)
        self.assertIsNone(err)

        bad_plan = {"functional_plan": {"overview": "o"}}
        valid, err = validator.validate_plan_json(bad_plan)
        self.assertFalse(valid)
        self.assertIsInstance(err, str)


if __name__ == "__main__":
    unittest.main()
