"""Test the agent's ability to recover from errors during execution.

These tests verify that the system can:
1. Detect and analyze errors
2. Implement recovery strategies 
3. Continue execution after errors occur
4. Learn from errors to avoid them in future tasks
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.coordinator import Coordinator
from agent_s3.code_generator import CodeGenerator
from agent_s3.debugging_manager import DebuggingManager


@pytest.fixture
def buggy_project(workspace):
    """Create a project with some deliberate bugs for testing error recovery."""
    # Create directories
    (workspace / "src").mkdir()
    (workspace / "tests").mkdir()
    
    # Create a buggy data processing module
    processor_path = workspace / "src" / "data_processor.py"
    processor_content = """
def process_data(data):
    \"\"\"Process a list of numeric data, returning statistics.\"\"\"
    if not data:
        return {"count": 0, "sum": 0, "average": 0}
    
    # BUG: Doesn't check if all items are numeric
    result = {
        "count": len(data),
        "sum": sum(data),
        "average": sum(data) / len(data)
    }
    
    # BUG: KeyError when max/min is accessed for empty list
    if data:
        result["max"] = max(data)
        result["min"] = min(data)
    
    return result

def filter_data(data, threshold):
    \"\"\"Filter data to include only values above the threshold.\"\"\"
    # BUG: Returns original data instead of filtered data
    filtered = [x for x in data if x > threshold]
    return data  # Should return filtered
"""
    
    with open(processor_path, "w") as f:
        f.write(processor_content)
    
    # Create a test file
    test_path = workspace / "tests" / "test_data_processor.py"
    test_content = """
import unittest
from src.data_processor import process_data, filter_data

class TestDataProcessor(unittest.TestCase):
    def test_process_data_normal(self):
        \"\"\"Test process_data with normal input.\"\"\"
        result = process_data([1, 2, 3, 4, 5])
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["sum"], 15)
        self.assertEqual(result["average"], 3)
        self.assertEqual(result["max"], 5)
        self.assertEqual(result["min"], 1)
    
    def test_process_data_empty(self):
        \"\"\"Test process_data with empty list.\"\"\"
        result = process_data([])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["sum"], 0)
        self.assertEqual(result["average"], 0)
        # BUG in test: No max/min for empty list
        # self.assertEqual(result["max"], None)
        # self.assertEqual(result["min"], None)
    
    def test_filter_data(self):
        \"\"\"Test filter_data functionality.\"\"\"
        # BUG in test: This will pass even though the function is wrong
        result = filter_data([1, 2, 3, 4, 5], 3)
        self.assertEqual(len(result), 5)  # Should be 2
"""
    
    with open(test_path, "w") as f:
        f.write(test_content)
    
    # Return information about the project
    return {
        "root": workspace,
        "processor_path": processor_path,
        "test_path": test_path,
        "known_bugs": [
            {"file": "data_processor.py", "function": "process_data", "issue": "No type checking"},
            {"file": "data_processor.py", "function": "process_data", "issue": "KeyError risk with empty list"},
            {"file": "data_processor.py", "function": "filter_data", "issue": "Returns original data instead of filtered"},
            {"file": "test_data_processor.py", "function": "test_process_data_empty", "issue": "Missing max/min checks"},
            {"file": "test_data_processor.py", "function": "test_filter_data", "issue": "Test passes despite bug"}
        ]
    }


def test_error_detection_and_analysis(buggy_project, test_config, scratchpad):
    """Test the system's ability to detect and analyze errors."""
    # Setup coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)
    
    # Configure the debugging manager
    debugging_manager = DebuggingManager(coordinator=coordinator)
    coordinator.debugging_manager = debugging_manager
    
    # Task to run tests and report issues
    task = "Run the data processor tests and report any issues"
    
    # Mock the debugging manager's analyze_error method
    with patch.object(DebuggingManager, 'analyze_error') as mock_analyze:
        # Setup mock response
        mock_analyze.return_value = {
            "error_type": "TypeError",
            "file": "src/data_processor.py",
            "function": "process_data",
            "line": "result = sum(data) / len(data)",
            "analysis": "The function doesn't validate that all data items are numeric",
            "suggested_fix": "Add type checking for each item in data"
        }
        
        # Mock test execution to simulate the TypeError
        with patch('subprocess.run') as mock_run:
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.stdout = "TypeError: unsupported operand type(s) for +: 'int' and 'str'"
            mock_run.return_value = mock_process
            
            # Run the analysis
            result = coordinator.analyze_project_issues(buggy_project["root"])
            
            # Verify that errors were detected
            assert "errors" in result
            assert len(result["errors"]) > 0
            assert any("TypeError" in err.get("error_type", "") for err in result["errors"])
            
            # Verify the analyze_error method was called
            mock_analyze.assert_called()


def test_error_recovery_strategies(buggy_project, test_config, scratchpad):
    """Test the system's ability to implement recovery strategies for different error types."""
    # Setup coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)
    
    # Task to fix the bugs in the data processor
    task = "Fix the bugs in the data processor module"
    
    # Mock the error detection to simulate finding the bugs
    with patch.object(Coordinator, 'analyze_project_issues') as mock_analyze:
        mock_analyze.return_value = {
            "errors": [
                {
                    "error_type": "TypeError",
                    "file": "src/data_processor.py",
                    "function": "process_data",
                    "line": "result = sum(data) / len(data)",
                    "analysis": "The function doesn't validate that all data items are numeric"
                },
                {
                    "error_type": "Logic Error",
                    "file": "src/data_processor.py",
                    "function": "filter_data",
                    "line": "return data",
                    "analysis": "Function returns original data instead of filtered data"
                }
            ]
        }
        
        # Mock the code generator to simulate fix implementation
        with patch.object(CodeGenerator, 'generate_code') as mock_generate:
            mock_generate.return_value = {
                "src/data_processor.py": """
def process_data(data):
    \"\"\"Process a list of numeric data, returning statistics.\"\"\"
    if not data:
        return {"count": 0, "sum": 0, "average": 0}
    
    # Fixed: Check that all items are numeric
    for item in data:
        if not isinstance(item, (int, float)):
            raise TypeError(f"All items must be numeric, got {type(item).__name__}")
    
    result = {
        "count": len(data),
        "sum": sum(data),
        "average": sum(data) / len(data)
    }
    
    # Fixed: Only add max/min for non-empty lists
    if data:
        result["max"] = max(data)
        result["min"] = min(data)
    
    return result

def filter_data(data, threshold):
    \"\"\"Filter data to include only values above the threshold.\"\"\"
    # Fixed: Return filtered data instead of original
    filtered = [x for x in data if x > threshold]
    return filtered
"""
            }
            
            # Execute the task
            result = coordinator.execute_task(task)
            
            # Verify the task execution and error recovery
            assert result.get("status") == "completed"
            
            # Verify that the fixes were applied as expected
            mock_generate.assert_called()
            
            # The generated code should include the fixes
            generated_code = mock_generate.call_args[0][0]
            assert "isinstance" in generated_code or "type" in generated_code
            assert "return filtered" in generated_code


def test_continuous_execution_after_error(buggy_project, test_config, scratchpad):
    """Test that the system can continue execution after encountering and fixing errors."""
    # Setup coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)
    
    # Multi-step task that will encounter errors
    task = "Add a new calculation function to data_processor.py to calculate the median value"
    
    # Mock the sequence of execution with error recovery
    with patch.object(Coordinator, 'execute_single_step') as mock_execute:
        # Define the behavior of each step execution
        def side_effect(step_description, context):
            if "Add median function" in step_description:
                # First step succeeds
                return {"status": "completed", "step": step_description}
            elif "Run tests" in step_description:
                # Tests fail with TypeError
                return {
                    "status": "failed", 
                    "error": "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
                    "step": step_description
                }
            elif "Fix error" in step_description:
                # Error fix succeeds
                return {"status": "completed", "step": step_description}
            elif "Verify fix" in step_description:
                # Final verification succeeds
                return {"status": "completed", "step": step_description}
            return {"status": "unknown", "step": step_description}
        
        mock_execute.side_effect = side_effect
        
        # Execute the task
        result = coordinator.execute_task(task)
        
        # Verify the task completed despite the error
        assert result.get("status") == "completed"
        
        # Verify that all steps were attempted
        assert mock_execute.call_count >= 3
        
        # Should have these calls in sequence
        expected_calls = [
            call(step_description=lambda s: "Add median function" in s, context={}),
            call(step_description=lambda s: "Run tests" in s, context={}),
            call(step_description=lambda s: "Fix error" in s, context={})
        ]
        
        # Check that the expected calls were made (simplified check)
        for i, exp_call in enumerate(expected_calls):
            # Only checking up to min of actual calls and expected calls
            if i < mock_execute.call_count:
                actual_step = mock_execute.call_args_list[i][1]["step_description"]
                expected_pattern = exp_call[1]["step_description"]
                assert expected_pattern(actual_step), f"Expected '{expected_pattern}' to match '{actual_step}'"


def test_learning_from_errors(buggy_project, test_config, scratchpad):
    """Test that the system learns from errors to avoid them in future tasks."""
    # Setup coordinator
    coordinator = Coordinator(config=test_config, scratchpad=scratchpad)
    
    # Add a learning component to the coordinator (mock)
    coordinator.error_memory = []
    
    # Mock recording errors for learning
    def record_error(error_data):
        coordinator.error_memory.append(error_data)
    
    coordinator.record_error = record_error
    
    # First task that encounters an error
    first_task = "Calculate the average of some data including string values"
    
    # Run first task that will generate a TypeError
    with patch.object(Coordinator, 'execute_single_step') as mock_execute_first:
        # Define the behavior for the first task
        def first_side_effect(step_description, context):
            if "Calculate" in step_description:
                # Step fails with TypeError
                error_data = {
                    "error_type": "TypeError", 
                    "context": "Mixing numeric and string values in calculations",
                    "solution": "Add type checking before calculations"
                }
                record_error(error_data)
                return {
                    "status": "failed", 
                    "error": "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
                    "step": step_description
                }
            return {"status": "unknown", "step": step_description}
        
        mock_execute_first.side_effect = first_side_effect
        
        # Execute the first task
        coordinator.execute_task(first_task)
    
    # Second task that could encounter a similar error
    second_task = "Calculate the median of a list of values"
    
    # Mock the planning stage to verify it incorporates the learned error
    with patch('agent_s3.planner.Planner.create_plan') as mock_plan:
        # Setup mock response
        coordinator.execute_task(second_task)
        
        # Verify the planner was called with context including the previous error
        args, kwargs = mock_plan.call_args
        task_arg = args[0]
        
        # The plan generation should have been given the error context
        assert second_task in task_arg
        
        # Should have access to error memory
        assert coordinator.error_memory
        assert len(coordinator.error_memory) == 1
        assert coordinator.error_memory[0]["error_type"] == "TypeError"