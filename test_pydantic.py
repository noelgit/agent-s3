#!/usr/bin/env python3
"""Test script to verify Pydantic installation and functionality."""

import pydantic
from pydantic import BaseModel

print(f"Pydantic version: {pydantic.__version__}")

class TestModel(BaseModel):
    name: str
    age: int = 25

# Test basic functionality
test_instance = TestModel(name="test_user")
print(f"Test successful - Name: {test_instance.name}, Age: {test_instance.age}")

# Test validation
try:
    invalid_instance = TestModel(name="test", age="not_a_number")
except Exception as e:
    print(f"Validation working correctly - caught error: {type(e).__name__}")

print("✅ Pydantic is working correctly!")
