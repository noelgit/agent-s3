"""Shared fixtures and configuration for system tests."""

import os
import tempfile
import json
from pathlib import Path
import pytest
import sys

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager, LogLevel


@pytest.fixture
def workspace():
    """
    Create a temporary workspace for the system tests.
    
    Returns:
        Path object for the workspace directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def basic_project(workspace):
    """
    Set up a basic project with some sample files.
    
    Args:
        workspace: The workspace fixture
        
    Returns:
        Dictionary with project information
    """
    # Create project structure
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    
    # Create a sample module file
    sample_module = workspace / "src" / "greetings.py"
    sample_module.write_text("""
def greet(name):
    \"\"\"Return a greeting message.\"\"\"
    return f"Hello, {name}!"

def farewell(name):
    \"\"\"Return a farewell message.\"\"\"
    return f"Goodbye, {name}!"
""")
    
    # Create a test file
    test_file = workspace / "tests" / "test_greetings.py"
    test_file.write_text("""
import unittest
from src.greetings import greet, farewell

class TestGreetings(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(greet("World"), "Hello, World!")
        
    def test_farewell(self):
        self.assertEqual(farewell("World"), "Goodbye, World!")
""")
    
    # Create a requirements file
    req_file = workspace / "requirements.txt"
    req_file.write_text("pytest==7.3.1\n")
    
    # Return project metadata
    return {
        "root": workspace,
        "module_file": sample_module,
        "test_file": test_file
    }


@pytest.fixture
def test_config(workspace):
    """
    Create a test configuration.
    
    Args:
        workspace: The workspace fixture
        
    Returns:
        Config object
    """
    # Create config data
    config_data = {
        "workspace_path": str(workspace),
        "use_persona_debate": True,
        "use_semantic_cache": True,
        "max_plan_tokens": 4000,
        "cache_debounce_delay": 0.1,
        "llm_model": "gpt-3.5-turbo"
    }
    
    # Write config file
    config_path = workspace / "config.json"
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    
    # Return config object
    return Config(str(config_path))


@pytest.fixture
def scratchpad():
    """
    Create a scratchpad for logging.
    
    Returns:
        ScratchpadManager instance
    """
    return EnhancedScratchpadManager(config)


@pytest.fixture
def mock_llm_responses():
    """
    Provide standard mock responses for LLM calls.
    
    Returns:
        Dictionary of mock responses
    """
    # We'll organize mock responses by task type
    return {
        "feature_addition": {
            "plan": {
                "discussion": "This task requires adding a new feature to the greetings module.",
                "plan": [
                    "Add a personalized_greeting function to src/greetings.py",
                    "Add tests for the new function",
                    "Ensure tests pass"
                ],
                "test_specifications": [
                    {
                        "implementation_file": "src/greetings.py",
                        "test_file": "tests/test_greetings.py",
                        "framework": "unittest",
                        "scenarios": [
                            {
                                "function": "personalized_greeting",
                                "cases": [
                                    {
                                        "description": "Test basic greeting with title",
                                        "inputs": {"name": "Smith", "title": "Mr."},
                                        "expected_output": "Hello, Mr. Smith!",
                                        "assertions": ["self.assertEqual(personalized_greeting('Smith', 'Mr.'), 'Hello, Mr. Smith!')"]
                                    },
                                    {
                                        "description": "Test greeting with no title",
                                        "inputs": {"name": "Jane", "title": None},
                                        "expected_output": "Hello, Jane!",
                                        "assertions": ["self.assertEqual(personalized_greeting('Jane', None), 'Hello, Jane!')"]
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "code": {
                "greetings.py": """
def greet(name):
    \"\"\"Return a greeting message.\"\"\"
    return f"Hello, {name}!"

def farewell(name):
    \"\"\"Return a farewell message.\"\"\"
    return f"Goodbye, {name}!"
    
def personalized_greeting(name, title=None):
    \"\"\"
    Return a personalized greeting with optional title.
    
    Args:
        name: The name to greet
        title: Optional title (Mr., Mrs., Dr., etc.)
        
    Returns:
        Personalized greeting message
    \"\"\"
    if title:
        return f"Hello, {title} {name}!"
    else:
        return f"Hello, {name}!"
"""
            }
        },
        
        "bug_fix": {
            "plan": {
                "discussion": "The greetings module has a bug that needs to be fixed.",
                "plan": [
                    "Fix the bug in the farewell function in src/greetings.py",
                    "Update tests to verify the fix",
                    "Ensure tests pass"
                ]
            },
            "code": {
                "greetings.py": """
def greet(name):
    \"\"\"Return a greeting message.\"\"\"
    return f"Hello, {name}!"

def farewell(name):
    \"\"\"Return a farewell message.\"\"\"
    # Fixed missing exclamation mark
    return f"Goodbye, {name}!"
"""
            }
        }
    }