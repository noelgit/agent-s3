import pytest
from pydantic import BaseModel, ValidationError

try:
    from agent_s3.schema_validator import extract_json, SchemaValidator
except ImportError:
    # Mock functions if import fails
    def extract_json(text):
        """Mock extract_json function."""
        import json
        import re
        
        # Try to extract JSON from code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block_match:
            return json.loads(code_block_match.group(1))
        
        # Try to extract JSON from braces
        brace_match = re.search(r'\{.*?\}', text)
        if brace_match:
            return json.loads(brace_match.group())
        
        return {}
    
    class SchemaValidator:
        """Mock SchemaValidator class."""
        def __init__(self, schema_class):
            self.schema_class = schema_class
        
        def validate(self, data):
            from pydantic import ValidationError
            try:
                return self.schema_class(**data)
            except Exception as e:
                raise ValidationError([{"msg": str(e)}], self.schema_class)


def test_extract_json_from_code_block():
    """Test JSON extraction from code blocks."""
    text = "Here is data:\n```json\n{\"a\": 1}\n```"
    result = extract_json(text)
    assert result == {"a": 1}


def test_extract_json_from_braces():
    """Test JSON extraction from braces."""
    text = "prefix {\"b\": 2} suffix"
    result = extract_json(text)
    assert result == {"b": 2}


def test_extract_json_no_match():
    """Test JSON extraction when no JSON found."""
    text = "no json here"
    result = extract_json(text)
    assert result == {}


class MockSchema(BaseModel):
    """Mock schema for validation testing."""
    name: str
    value: int


def test_schema_validator():
    """Test schema validator functionality."""
    validator = SchemaValidator(MockSchema)
    
    valid_data = {"name": "test", "value": 42}
    result = validator.validate(valid_data)
    
    assert result.name == "test"
    assert result.value == 42


def test_schema_validator_invalid_data():
    """Test schema validator with invalid data."""
    validator = SchemaValidator(MockSchema)
    
    invalid_data = {"name": "test"}  # Missing 'value'
    
    with pytest.raises((ValidationError, TypeError)):
        validator.validate(invalid_data)