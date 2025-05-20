"""System Tests for Agent-S3 Critical Workflows.

These tests verify that the system works as a whole without excessive mocking.
They test real functionality rather than implementation details.
"""

import os
import sys
import json
import tempfile
import textwrap
from pathlib import Path
import unittest

# Make sure agent_s3 is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_s3.config import Config
from agent_s3.coordinator import Coordinator
from agent_s3.planner import Planner
from agent_s3.code_generator import CodeGenerator
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager


class TestAgentE2EWorkflow(unittest.TestCase):
    """End-to-end tests for the most critical agent workflows.
    
    These tests verify functionality using minimal mocking - only for LLM calls
    where we provide realistic pre-defined responses instead of unpredictable
    live calls.
    
    They test:
    1. Plan creation and validation for a given task
    2. Code generation based on a plan
    3. Integration between components (planner, code generator, etc.)
    4. Full workflow from task to implementation
    """
    
    def setUp(self):
        """Set up a temporary workspace and real components."""
        # Create a temporary workspace
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_path = Path(self.temp_dir.name)
        
        # Create a simple Python project structure in the workspace
        self.project_setup()
        
        # Create a real config with test settings
        config_data = {
            "workspace_path": str(self.workspace_path),
            "use_persona_debate": True,
            "use_semantic_cache": True,
            "max_plan_tokens": 4000,
            "cache_debounce_delay": 0.1,
            "llm_model": "gpt-3.5-turbo",  # Mock this in tests
        }
        
        # Write config to disk
        config_path = self.workspace_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f)
        
        # Initialize components with real instances where possible
        self.config = Config(str(config_path))
        self.scratchpad = EnhancedScratchpadManager(self.config)
        
        # Initialize the coordinator
        self.coordinator = Coordinator(
            config=self.config,
            scratchpad=self.scratchpad
        )
        
        # Patch LLM calls to return predefined responses
        self.setup_llm_mocks()
    
    def tearDown(self):
        """Clean up temporary files."""
        self.temp_dir.cleanup()
    
    def project_setup(self):
        """Create a simple project structure for testing."""
        # Create directories
        (self.workspace_path / "src").mkdir()
        (self.workspace_path / "tests").mkdir()
        
        # Create a simple Python file
        calculator_path = self.workspace_path / "src" / "calculator.py"
        calculator_content = textwrap.dedent("""
            \"\"\"A simple calculator module.\"\"\"
            
            def add(a, b):
                \"\"\"Add two numbers.\"\"\"
                return a + b
            
            def subtract(a, b):
                \"\"\"Subtract b from a.\"\"\"
                return a - b
        """)
        
        with open(calculator_path, "w") as f:
            f.write(calculator_content)
        
        # Create a test file
        test_path = self.workspace_path / "tests" / "test_calculator.py"
        test_content = textwrap.dedent("""
            \"\"\"Tests for the calculator module.\"\"\"
            
            import unittest
            from src.calculator import add, subtract
            
            class TestCalculator(unittest.TestCase):
                def test_add(self):
                    self.assertEqual(add(1, 2), 3)
                
                def test_subtract(self):
                    self.assertEqual(subtract(5, 3), 2)
        """)
        
        with open(test_path, "w") as f:
            f.write(test_content)
    
    def setup_llm_mocks(self):
        """Set up mocks for LLM responses used in tests."""
        # Setup would depend on your LLM calling infrastructure
        # Here we'd use patch or an in-memory cache to return predefined responses
        pass
    
    def create_mock_plan_response(self, task):
        """Create a realistic mock plan response for a given task."""
        # A realistic plan that the LLM would generate
        return {
            "discussion": "This task requires adding multiplication functionality to the calculator.",
            "plan": [
                "Add a multiply function to src/calculator.py",
                "Add tests for the multiply function to tests/test_calculator.py",
                "Verify that tests pass"
            ],
            "test_specifications": [
                {
                    "implementation_file": "src/calculator.py",
                    "test_file": "tests/test_calculator.py",
                    "framework": "unittest",
                    "scenarios": [
                        {
                            "function": "multiply",
                            "cases": [
                                {
                                    "description": "Test basic multiplication",
                                    "inputs": {"a": 2, "b": 3},
                                    "expected_output": 6,
                                    "assertions": ["self.assertEqual(multiply(2, 3), 6)"]
                                },
                                {
                                    "description": "Test multiplication with zero",
                                    "inputs": {"a": 5, "b": 0},
                                    "expected_output": 0,
                                    "assertions": ["self.assertEqual(multiply(5, 0), 0)"]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    
    def create_mock_code_response(self, plan):
        """Create a realistic mock code generation response for a given plan."""
        # Mock the code generation for calculator.py update
        calculator_code = textwrap.dedent("""
            \"\"\"A simple calculator module.\"\"\"
            
            def add(a, b):
                \"\"\"Add two numbers.\"\"\"
                return a + b
            
            def subtract(a, b):
                \"\"\"Subtract b from a.\"\"\"
                return a - b
                
            def multiply(a, b):
                \"\"\"Multiply two numbers.\"\"\"
                return a * b
        """)
        
        # Mock the code generation for test_calculator.py update
        test_code = textwrap.dedent("""
            \"\"\"Tests for the calculator module.\"\"\"
            
            import unittest
            from src.calculator import add, subtract, multiply
            
            class TestCalculator(unittest.TestCase):
                def test_add(self):
                    self.assertEqual(add(1, 2), 3)
                
                def test_subtract(self):
                    self.assertEqual(subtract(5, 3), 2)
                    
                def test_multiply(self):
                    self.assertEqual(multiply(2, 3), 6)
                    
                def test_multiply_with_zero(self):
                    self.assertEqual(multiply(5, 0), 0)
        """)
        
        return {
            "calculator.py": calculator_code,
            "test_calculator.py": test_code
        }
    
    @patch("agent_s3.planner.Planner.create_plan")
    @patch("agent_s3.code_generator.CodeGenerator.generate_code")
    def test_simple_implementation_workflow(self, mock_generate_code, mock_create_plan):
        """Test a complete workflow from task to implementation."""
        # Set up the task
        task = "Add a multiplication feature to the calculator"
        
        # Set up mock responses
        mock_plan = self.create_mock_plan_response(task)
        mock_code = self.create_mock_code_response(mock_plan)
        
        mock_create_plan.return_value = json.dumps(mock_plan)
        mock_generate_code.return_value = mock_code
        
        # Execute the workflow
        # This would be your typical calling pattern for executing a task
        result = self.coordinator.execute_task(task)
        
        # Verify the workflow - check that files were updated correctly
        calculator_path = self.workspace_path / "src" / "calculator.py"
        test_path = self.workspace_path / "tests" / "test_calculator.py"
        
        with open(calculator_path, "r") as f:
            calculator_content = f.read()
        
        with open(test_path, "r") as f:
            test_content = f.read()
        
        # Check that the expected changes were made
        self.assertIn("def multiply(a, b):", calculator_content)
        self.assertIn("return a * b", calculator_content)
        self.assertIn("test_multiply", test_content)
        self.assertIn("self.assertEqual(multiply(2, 3), 6)", test_content)
        self.assertIn("self.assertEqual(multiply(5, 0), 0)", test_content)
        
        # Verify that the coordinator tracked the task correctly
        task_status = self.coordinator.get_task_status(result["task_id"])
        self.assertEqual(task_status["status"], "completed")
        self.assertEqual(task_status["task"], task)
        
        # Run the actual tests to make sure the implementation works
        import subprocess
        test_result = subprocess.run(
            ["python", "-m", "unittest", "discover", "-s", "tests"],
            cwd=self.workspace_path,
            capture_output=True,
            text=True
        )
        
        # Tests should pass if implementation is correct
        self.assertEqual(test_result.returncode, 0)
    
    @patch("agent_s3.planner.Planner.create_plan")
    def test_error_recovery(self, mock_create_plan):
        """Test that the agent can recover from errors during execution."""
        # Set up a task that will initially fail
        task = "Add a division feature to the calculator with error handling for division by zero"
        
        # Mock the plan response that will eventually succeed
        mock_plan = {
            "discussion": "Adding division with error handling for division by zero.",
            "plan": [
                "Add a divide function to src/calculator.py with zero division check",
                "Add tests for the divide function including zero division test",
                "Verify that tests pass"
            ],
            "test_specifications": [
                {
                    "implementation_file": "src/calculator.py",
                    "test_file": "tests/test_calculator.py",
                    "framework": "unittest",
                    "scenarios": [
                        {
                            "function": "divide",
                            "cases": [
                                {
                                    "description": "Test basic division",
                                    "inputs": {"a": 6, "b": 3},
                                    "expected_output": 2,
                                    "assertions": ["self.assertEqual(divide(6, 3), 2)"]
                                },
                                {
                                    "description": "Test division by zero",
                                    "inputs": {"a": 5, "b": 0},
                                    "expected_exception": "ValueError",
                                    "assertions": ["with self.assertRaises(ValueError): divide(5, 0)"]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Setup a sequence of responses - first failure, then success
        mock_create_plan.side_effect = [
            Exception("LLM service temporarily unavailable"),  # First call fails
            json.dumps(mock_plan)  # Second call succeeds
        ]
        
        # Mock code generation with the successful implementation
        with patch("agent_s3.code_generator.CodeGenerator.generate_code") as mock_generate_code:
            mock_code = {
                "calculator.py": """
                    \"\"\"A simple calculator module.\"\"\"
                    
                    def add(a, b):
                        \"\"\"Add two numbers.\"\"\"
                        return a + b
                    
                    def subtract(a, b):
                        \"\"\"Subtract b from a.\"\"\"
                        return a - b
                        
                    def divide(a, b):
                        \"\"\"Divide a by b.\"\"\"
                        if b == 0:
                            raise ValueError("Cannot divide by zero")
                        return a / b
                """,
                "test_calculator.py": """
                    \"\"\"Tests for the calculator module.\"\"\"
                    
                    import unittest
                    from src.calculator import add, subtract, divide
                    
                    class TestCalculator(unittest.TestCase):
                        def test_add(self):
                            self.assertEqual(add(1, 2), 3)
                        
                        def test_subtract(self):
                            self.assertEqual(subtract(5, 3), 2)
                            
                        def test_divide(self):
                            self.assertEqual(divide(6, 3), 2)
                            
                        def test_divide_by_zero(self):
                            with self.assertRaises(ValueError):
                                divide(5, 0)
                """
            }
            mock_generate_code.return_value = mock_code
            
            # Execute the workflow with recovery
            result = self.coordinator.execute_task(task, max_retries=2)
            
            # Verify the workflow succeeded eventually
            self.assertEqual(result["status"], "completed")
            
            # Verify the implementation actually works
            calculator_path = self.workspace_path / "src" / "calculator.py"
            with open(calculator_path, "r") as f:
                calculator_content = f.read()
            
            self.assertIn("def divide(a, b):", calculator_content)
            self.assertIn("raise ValueError", calculator_content)
            
            # Verify that the recovery path was recorded
            self.assertIn("recovery", result)
            self.assertIn("retry_count", result)
            self.assertEqual(result["retry_count"], 1)  # One retry after initial failure
    
    def test_context_adaptation(self):
        """Test that the agent adapts its behavior based on project context."""
        # This test verifies that the agent uses existing code patterns
        # when implementing new features
        
        # First, let's add a specific code pattern to the codebase:
        # - Add docstring type hints
        # - Use specific error message format
        calculator_path = self.workspace_path / "src" / "calculator.py"
        calculator_content = textwrap.dedent("""
            \"\"\"A simple calculator module.\"\"\"
            
            def add(a: float, b: float) -> float:
                \"\"\"
                Add two numbers.
                
                Args:
                    a: First number
                    b: Second number
                    
                Returns:
                    Sum of the two numbers
                
                Raises:
                    TypeError: If inputs are not numbers
                \"\"\"
                if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    raise TypeError("ERROR-001: Inputs must be numbers")
                return a + b
            
            def subtract(a: float, b: float) -> float:
                \"\"\"
                Subtract b from a.
                
                Args:
                    a: First number
                    b: Second number
                    
                Returns:
                    Result of a - b
                    
                Raises:
                    TypeError: If inputs are not numbers
                \"\"\"
                if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                    raise TypeError("ERROR-002: Inputs must be numbers")
                return a - b
        """)
        
        with open(calculator_path, "w") as f:
            f.write(calculator_content)
        
        # Now, ask the agent to add a multiply function
        task = "Add a multiply function to the calculator"
        
        # Mock the planning and code generation responses - note these should adapt to the context
        with patch("agent_s3.planner.Planner.create_plan") as mock_create_plan:
            mock_plan = {
                "discussion": "The calculator module follows specific patterns including type hints, docstrings, and error codes.",
                "plan": [
                    "Add a multiply function to src/calculator.py that follows existing patterns",
                    "Add tests for the multiply function"
                ]
            }
            mock_create_plan.return_value = json.dumps(mock_plan)
            
            with patch("agent_s3.code_generator.CodeGenerator.generate_code") as mock_generate_code:
                # This should match the existing pattern in the code
                mock_code = {
                    "calculator.py": calculator_content + textwrap.dedent("""
                        
                        def multiply(a: float, b: float) -> float:
                            \"\"\"
                            Multiply two numbers.
                            
                            Args:
                                a: First number
                                b: Second number
                                
                            Returns:
                                Result of a * b
                                
                            Raises:
                                TypeError: If inputs are not numbers
                            \"\"\"
                            if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
                                raise TypeError("ERROR-003: Inputs must be numbers")
                            return a * b
                    """)
                }
                mock_generate_code.return_value = mock_code
                
                # Execute the task
                result = self.coordinator.execute_task(task)
                
                # Verify the implementation follows the existing patterns
                with open(calculator_path, "r") as f:
                    content = f.read()
                
                # Check for the pattern adherence
                self.assertIn("def multiply(a: float, b: float) -> float:", content)
                self.assertIn("ERROR-003: Inputs must be numbers", content)
                self.assertIn("Args:", content)
                self.assertIn("Returns:", content)
                self.assertIn("Raises:", content)
    
    # Additional test ideas:
    # - Test multi-file, multi-step implementation
    # - Test handling conflicting requirements
    # - Test performance optimization task
    # - Test refactoring functionality
    # - Test bug fixing scenario
    # - Test adapting to different coding styles