"""Tests for the CodeGenerator's handling of JSON plans."""

import json
import pytest
from unittest.mock import MagicMock

from agent_s3.code_generator import CodeGenerator


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.memory_manager = MagicMock()
    coordinator.memory_manager.estimate_token_count.return_value = 100
    coordinator.memory_manager.summarize.return_value = "Summarized content"
    coordinator.scratchpad = MagicMock()
    coordinator.file_tool = MagicMock()
    return coordinator


@pytest.fixture
def sample_json_plan():
    """Create a sample JSON plan for testing."""
    return {
        "functional_plan": {
            "overview": "Implement feature XYZ",
            "file_changes": [
                {
                    "file_path": "agent_s3/feature_xyz.py",
                    "change_type": "create",
                    "description": "Create new feature module"
                },
                {
                    "file_path": "tests/test_feature_xyz.py",
                    "change_type": "create",
                    "description": "Create tests for feature"
                }
            ],
            "functions": [
                {
                    "name": "process_xyz",
                    "description": "Process XYZ data",
                    "parameters": ["data"],
                    "return_value": "Processed data"
                }
            ]
        },
        "test_plan": {
            "test_scenarios": [
                {
                    "name": "Basic functionality",
                    "description": "Test basic functionality of XYZ feature"
                }
            ],
            "test_cases": [
                {
                    "name": "test_process_xyz_valid_input",
                    "inputs": {"data": "sample_data"},
                    "expected_output": "Processed sample_data"
                }
            ]
        }
    }


def test_minimal_context_with_json_plan(mock_coordinator, sample_json_plan):
    """Test that _gather_minimal_context handles JSON plans correctly."""
    generator = CodeGenerator(coordinator=mock_coordinator)
    
    # Set up token budgets
    token_budgets = {
        "task": 1000,
        "plan": 2000,
        "code_context": 3000,
        "tech_stack": 500
    }
    
    # Test with JSON plan
    context = generator._gather_minimal_context(
        task="Implement XYZ feature", 
        plan=sample_json_plan,
        tech_stack={"languages": ["Python"]},
        token_budgets=token_budgets
    )
    
    # Verify context structure
    assert context["is_json_plan"] is True
    assert "test_plan" in context
    assert context["test_plan"] == sample_json_plan["test_plan"]
    
    # Verify files_to_modify was extracted correctly
    # We can't directly check this since it's a local variable in the method,
    # but we can check that the paths were correctly extracted from the plan
    assert "agent_s3/feature_xyz.py" in str(context["plan"])
    assert "tests/test_feature_xyz.py" in str(context["plan"])


def test_create_generation_prompt_with_json_plan(mock_coordinator, sample_json_plan):
    """Test that _create_generation_prompt handles JSON plan format properly."""
    generator = CodeGenerator(coordinator=mock_coordinator)
    
    # Create context with JSON plan
    context = {
        "task": "Implement XYZ feature",
        "plan": json.dumps(sample_json_plan, indent=2),
        "is_json_plan": True,
        "test_plan": sample_json_plan["test_plan"],
        "code_context": {},
        "tech_stack": {"languages": ["Python"]}
    }
    
    # Generate prompt
    prompt = generator._create_generation_prompt(context)
    
    # Verify prompt contains JSON plan sections
    assert "# Structured Plan (JSON Format)" in prompt
    assert "# Test Plan" in prompt
    
    # Verify JSON plan-specific instructions are included
    assert "# Instructions for JSON Plan Implementation" in prompt
    assert "Follow these steps to implement the feature based on the JSON structured plan" in prompt
    
    # Should not include traditional plan instructions
    assert "# Plan" not in prompt
    assert "Based *only* on the '# Test Specifications' section of the plan" not in prompt


def test_full_context_with_json_plan(mock_coordinator, sample_json_plan):
    """Test that _gather_full_context handles JSON plans with prioritized formatting."""
    generator = CodeGenerator(coordinator=mock_coordinator)
    
    # Set up token budgets
    token_budgets = {
        "task": 1000,
        "plan": 2000,
        "code_context": 3000,
        "tech_stack": 500
    }
    
    # Configure memory manager to simulate truncation needs
    mock_coordinator.memory_manager.estimate_token_count.side_effect = lambda x: len(x) if isinstance(x, str) else 5000
    
    # Test with JSON plan that needs truncation
    context = generator._gather_full_context(
        task="Implement XYZ feature", 
        plan=sample_json_plan,
        tech_stack={"languages": ["Python"]},
        token_budgets=token_budgets,
        failed_attempts=[{"response": "Previous error message"}]
    )
    
    # Verify context structure
    assert context["is_json_plan"] is True
    assert "test_plan" in context
    assert context["test_plan"] == sample_json_plan["test_plan"]
    
    # Since we're simulating a large JSON plan with our side_effect,
    # we should see that the context is properly structured
    assert context["is_json_plan"] is True
    
    # With our custom side_effect that makes the plan too large,
    # the code should use a fixed version when the full JSON doesn't fit
    assert context["plan"] is not None
    
    # Verify previous attempts are included
    assert len(context["previous_attempts"]) == 1