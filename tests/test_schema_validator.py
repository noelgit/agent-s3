import importlib.util
from pathlib import Path

from pydantic import BaseModel

module_path = Path(__file__).resolve().parents[1] / "agent_s3" / "schema_validator.py"
spec = importlib.util.spec_from_file_location("schema_validator", module_path)
schema_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schema_validator)


def test_extract_json_from_code_block():
    text = "Here is data:\n```json\n{\"a\": 1}\n```"
    result = schema_validator.extract_json(text)
    assert result == {"a": 1}


def test_extract_json_from_braces():
    text = "prefix {\"b\": 2} suffix"
    result = schema_validator.extract_json(text)
    assert result == {"b": 2}


def test_validate_llm_response_success():
    class Simple(BaseModel):
        foo: int

    success, model_or_error = schema_validator.validate_llm_response("{\"foo\": 5}", Simple)
    assert success is True
    assert isinstance(model_or_error, Simple)
    assert model_or_error.foo == 5


def test_validate_llm_response_failure():
    class Simple(BaseModel):
        foo: int

    success, error = schema_validator.validate_llm_response("not json", Simple)
    assert success is False
    assert isinstance(error, str)

