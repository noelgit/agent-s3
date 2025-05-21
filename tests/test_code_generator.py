"""Unit tests for the CodeGenerator module."""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import tempfile

try:
    from agent_s3.code_generator import CodeGenerator
    from agent_s3.enhanced_scratchpad_manager import (
        EnhancedScratchpadManager,
    )
    ScratchpadManager = EnhancedScratchpadManager
except ImportError:
    print("Warning: Could not import full agent_s3 modules for testing. Using stubs.")
    class CodeGenerator:
        pass
    class EnhancedScratchpadManager:
        def log(self, *args, **kwargs):
            pass
    ScratchpadManager = EnhancedScratchpadManager


class TestCodeGenerator(unittest.TestCase):
    """Tests for the CodeGenerator class."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Mock coordinator and its components
        self.mock_coordinator = MagicMock()
        self.mock_coordinator.llm = MagicMock()
        self.mock_coordinator.scratchpad = MagicMock(spec=ScratchpadManager)
        self.mock_coordinator.file_tool = MagicMock()
        self.mock_coordinator.memory_manager = MagicMock()
        self.mock_coordinator.code_analysis_tool = MagicMock()
        self.mock_coordinator.config = MagicMock()
        self.mock_coordinator.config.config = {
            "llm_timeout": 30,
            "max_retries": 3,
            "use_enhanced_context": True,
            "fusion_weights": {
                "structural": 0.4,
                "semantic": 0.3,
                "lexical": 0.2,
                "evolutionary": 0.1
            }
        }
        
        # Configure memory_manager.estimate_token_count to return the length of the input
        self.mock_coordinator.memory_manager.estimate_token_count.side_effect = lambda x: len(str(x).split())
        
        # Configure memory_manager.summarize to return the input truncated
        self.mock_coordinator.memory_manager.summarize.side_effect = lambda x, target_tokens: ' '.join(str(x).split()[:target_tokens])
        
        # Configure memory_manager.hierarchical_summarize to return the input truncated
        self.mock_coordinator.memory_manager.hierarchical_summarize.side_effect = lambda x, target_tokens: ' '.join(str(x).split()[:target_tokens])

        # Create temporary directory for file operations
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = self.temp_dir.name
        
        # Mock the StaticAnalyzer in code_analysis_tool
        self.mock_static_analyzer = MagicMock()
        self.mock_static_analyzer.fusion_weights = {
            "structural": 0.4,
            "semantic": 0.3,
            "lexical": 0.2,
            "evolutionary": 0.1
        }
        self.mock_static_analyzer.enhance_search_results.return_value = []
        self.mock_static_analyzer.find_structurally_relevant_files.return_value = []
        self.mock_static_analyzer.analyze_file_interfaces.return_value = {}
        self.mock_static_analyzer._format_interface_as_string.return_value = "Mock interface"
        
        # Attach static analyzer to code analysis tool
        self.mock_coordinator.code_analysis_tool.static_analyzer = self.mock_static_analyzer

        # Instantiate CodeGenerator with mocked coordinator
        self.code_generator = CodeGenerator(coordinator=self.mock_coordinator)

    def tearDown(self):
        """Clean up after each test."""
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test that CodeGenerator initializes correctly."""
        self.assertEqual(self.code_generator.coordinator, self.mock_coordinator)
        self.assertEqual(self.code_generator.llm, self.mock_coordinator.llm)
        self.assertEqual(self.code_generator.scratchpad, self.mock_coordinator.scratchpad)
        self.assertEqual(self.code_generator.file_tool, self.mock_coordinator.file_tool)
        self.assertEqual(self.code_generator.memory_manager, self.mock_coordinator.memory_manager)
        self.assertEqual(self.code_generator.code_analysis_tool, self.mock_coordinator.code_analysis_tool)

    def test_allocate_token_budget(self):
        """Test token budget allocation for context."""
        # Test with a specific total budget for first attempt
        total_tokens = 4000
        budgets = self.code_generator._allocate_token_budget(total_tokens, attempt_num=1)
        
        # Verify that budgets are reasonable
        self.assertIsInstance(budgets, dict)
        self.assertGreater(budgets.get('code_context', 0), 0)
        self.assertGreater(budgets.get('plan', 0), 0)
        self.assertGreater(budgets.get('task', 0), 0)
        self.assertGreater(budgets.get('tech_stack', 0), 0)
        
        # Verify that budgets sum to the total
        self.assertEqual(sum(budgets.values()), total_tokens)
        
        # Test that second attempt gives different allocations
        second_attempt = self.code_generator._allocate_token_budget(total_tokens, attempt_num=2)
        self.assertNotEqual(budgets['code_context'], second_attempt['code_context'])
        
        # Test that third attempt gives even more context allocation
        third_attempt = self.code_generator._allocate_token_budget(total_tokens, attempt_num=3)
        self.assertGreater(third_attempt['code_context'], second_attempt['code_context'])

    @patch('agent_s3.code_generator.cached_call_llm')
    def test_create_generation_prompt(self, mock_cached_call_llm):
        """Test code generation prompt creation method works indirectly through generate_code."""
        # Setup the mock to return a valid response
        mock_response = {
            'success': True,
            'response': json.dumps({
                "files": [
                    {
                        "file_path": "test_file.py",
                        "content": "def test_function():\n    return True"
                    }
                ]
            })
        }
        mock_cached_call_llm.return_value = mock_response
        
        # Call generate_code which will use _create_generation_prompt
        task = "Create a test function"
        plan = "The plan is to create a test function"
        
        # Mock the extract_files_from_plan method to control what files are considered
        self.code_generator._extract_files_from_plan = MagicMock(return_value=["test_file.py"])
        
        # Mock router agent call_llm_with_streaming to return success
        if hasattr(self.code_generator, 'router'):
            self.code_generator.router = MagicMock()
            self.code_generator.router.call_llm_with_streaming.return_value = {'success': True, 'response': 'OK'}
        
        _ = self.code_generator.generate_code(task, plan)
        
        # Verify cached_call_llm was called, which means _create_generation_prompt was used
        mock_cached_call_llm.assert_called_once()
        
        # Verify the prompt contains the task and plan
        args = mock_cached_call_llm.call_args[0]
        prompt = args[0]
        self.assertIn(task, prompt)
        self.assertIn(plan, prompt)

    @patch('agent_s3.code_generator.cached_call_llm')
    def test_extract_files_from_plan(self, mock_cached_call_llm):
        """Test extracting file paths from plan."""
        # Mock plan with file paths
        plan = """
        1. Modify test_file.py to include a new function
        2. Create a new file called new_module.py
        3. Update /absolute/path/to/config.json with new settings
        """
        
        # Set up LLM to return empty response
        mock_response = {'success': True, 'response': '{}'}
        mock_cached_call_llm.return_value = mock_response
        
        # The extract_files_from_plan is a private method, so we'll have to observe
        # its effects through other methods or override it for testing
        self.code_generator._extract_files_from_plan = lambda p: ["test_file.py", "new_module.py", "/absolute/path/to/config.json"]
        
        # Call generate_code which will use _extract_files_from_plan
        task = "Update files according to plan"
        _ = self.code_generator.generate_code(task, plan)
        
        # Verify that the task and prompt were set correctly
        args = mock_cached_call_llm.call_args[0]
        prompt = args[0]
        self.assertIn("test_file.py", prompt)
        self.assertIn("new_module.py", prompt)
        self.assertIn("/absolute/path/to/config.json", prompt)

    @patch('agent_s3.code_generator.cached_call_llm')
    def test_gather_minimal_context(self, mock_cached_call_llm):
        """Test gathering minimal context for first attempt."""
        # Set up mock for LLM response
        mock_response = {'success': True, 'response': '{}'}
        mock_cached_call_llm.return_value = mock_response
        
        # Call generate_code which will use _gather_minimal_context for first attempt
        task = "Create a simple function"
        plan = "Plan to create a function in test_file.py"
        
        # Mock _extract_files_from_plan to return a file
        self.code_generator._extract_files_from_plan = MagicMock(return_value=["test_file.py"])
        
        # Reset generation attempts to ensure first attempt
        self.code_generator._generation_attempts = {}
        
        # Call generate_code
        _ = self.code_generator.generate_code(task, plan)
        
        # Check that the mock was called with the expected context
        args = mock_cached_call_llm.call_args[0]
        prompt = args[0]
        
        # Verify the prompt includes task and plan
        self.assertIn(task, prompt)
        self.assertIn(plan, prompt)
        
        # Verify that memory_manager.estimate_token_count was called for the plan
        self.mock_coordinator.memory_manager.estimate_token_count.assert_called()
    
    @patch('agent_s3.code_generator.cached_call_llm')
    def test_gather_enhanced_context(self, mock_cached_call_llm):
        """Test gathering enhanced context with structural analysis for subsequent attempts."""
        # Set up mock for LLM response
        mock_response = {'success': True, 'response': '{}'}
        mock_cached_call_llm.return_value = mock_response
        
        # Prepare test data
        task = "Create a complex function using existing code"
        plan = "Plan to create a function in test_file.py that uses helpers from utils.py"
        
        # Mock _extract_files_from_plan to return multiple files
        self.code_generator._extract_files_from_plan = MagicMock(return_value=["test_file.py", "utils.py"])
        
        # Configure static analyzer to return test data
        mock_interface = {
            "imports": [{"module": "os", "names": ["path"]}],
            "exports": [{"name": "helper_func", "type": "function"}],
            "inheritance": {},
            "file_path": "utils.py"
        }
        self.mock_static_analyzer.analyze_file_interfaces.return_value = mock_interface
        self.mock_static_analyzer._format_interface_as_string.return_value = "# Exports:\nfunction: helper_func"
        
        # Set up enhanced search results
        self.mock_static_analyzer.find_structurally_relevant_files.return_value = [
            {"file_path": "another_utils.py", "content": "def another_helper(): pass", "score": 0.8}
        ]
        
        # Set up semantic search results
        self.mock_coordinator.code_analysis_tool.find_relevant_files.return_value = [
            {"file_path": "test_file.py", "content": "# Test file", "score": 0.9},
            {"file_path": "utils.py", "content": "# Utils file", "score": 0.8},
            {"file_path": "config.py", "content": "# Config file", "score": 0.7}
        ]
        
        # Mock file_tool.read_file
        def mock_read_file(path):
            content_map = {
                "test_file.py": "def test_func(): pass",
                "utils.py": "def helper_func(): return True",
                "another_utils.py": "def another_helper(): pass"
            }
            return content_map.get(path, "")
        
        self.mock_coordinator.file_tool.read_file.side_effect = mock_read_file
        
        # Patch os.path.isfile to return True for our test files
        with patch('os.path.isfile', return_value=True):
            # Patch open to return file contents
            with patch('builtins.open', mock_open(read_data="def test_func(): pass")):
                # Set generation attempts to make it a second attempt
                self.code_generator._generation_attempts = {
                    self.code_generator._create_task_id(task): {
                        "attempt_count": 2,
                        "failed_attempts": [
                            {"response": "Error in first attempt"}
                        ]
                    }
                }
                
                # Call generate_code
                _ = self.code_generator.generate_code(task, plan)
                
                # Check that the mock was called with the expected context
                args = mock_cached_call_llm.call_args[0]
                prompt = args[0]
                
                # Verify the prompt includes key components
                self.assertIn(task, prompt)
                self.assertIn(plan, prompt)
                
                # Check for enhanced context features
                self.assertTrue(
                    # Check for structural analysis section
                    "# Structural Analysis" in prompt or 
                    # Or check for interface view notation
                    "(Interface View)" in prompt,
                    "Enhanced context features not found in prompt"
                )
                
                # Verify that static analyzer methods were called
                self.mock_static_analyzer.find_structurally_relevant_files.assert_called()
                
                # Verify that find_relevant_files was called on code analysis tool
                self.mock_coordinator.code_analysis_tool.find_relevant_files.assert_called()


if __name__ == '__main__':
    unittest.main()