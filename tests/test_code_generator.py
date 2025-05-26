"""Unit tests for the CodeGenerator module."""

import unittest
from unittest.mock import MagicMock
import tempfile

try:
    from agent_s3.code_generator import CodeGenerator
    from agent_s3.debug_utils import DebugUtils
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
        self.assertEqual(self.code_generator.context_manager.coordinator.file_tool, self.mock_coordinator.file_tool)
        self.assertEqual(self.code_generator.context_manager.coordinator.memory_manager, self.mock_coordinator.memory_manager)
        self.assertEqual(self.code_generator.context_manager.coordinator.code_analysis_tool, self.mock_coordinator.code_analysis_tool)

    def test_allocate_token_budget(self):
        """Test token budget allocation for context."""
        # Test with a specific total budget for first attempt
        total_tokens = 4000
        budgets = self.code_generator.context_manager.allocate_token_budget(total_tokens, attempt_num=1)

        # Verify that budgets are reasonable
        self.assertIsInstance(budgets, dict)
        self.assertGreater(budgets.get('code_context', 0), 0)
        self.assertGreater(budgets.get('plan', 0), 0)
        self.assertGreater(budgets.get('task', 0), 0)
        self.assertGreater(budgets.get('tech_stack', 0), 0)

        # Verify that budgets sum to the total
        self.assertEqual(sum(budgets.values()), total_tokens)

        # Test that second attempt gives different allocations
        second_attempt = self.code_generator.context_manager.allocate_token_budget(total_tokens, attempt_num=2)
        self.assertNotEqual(budgets['code_context'], second_attempt['code_context'])

        # Test that third attempt gives even more context allocation
        third_attempt = self.code_generator.context_manager.allocate_token_budget(total_tokens, attempt_num=3)
        self.assertGreater(third_attempt['code_context'], second_attempt['code_context'])

    def test_create_generation_prompt(self):
        """Test _create_generation_prompt generates the expected prompt."""
        task = "Create a test function"
        plan = "The plan is to create a test function"
        budgets = {"task": 100, "plan": 200, "code_context": 300, "tech_stack": 50}

        context = self.code_generator.context_manager.gather_minimal_context(task, plan, {}, budgets)
        prompt = self.code_generator.context_manager.create_generation_prompt(context)

        self.assertIn(task, prompt)
        self.assertIn(plan, prompt)

    def test_extract_files_from_plan(self):
        """Test extracting file paths from an implementation plan."""
        implementation_plan = {
            "file1.py": [{"function": "func1"}],
            "file2.py": [{"function": "func2"}],
        }
        files = self.code_generator._extract_files_from_plan(implementation_plan)
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0][0], "file1.py")
        self.assertEqual(files[1][0], "file2.py")

    def test_gather_minimal_context(self):
        """Test gathering minimal context for first attempt."""
        task = "Create a simple function"
        plan = "Plan to create a function in test_file.py"
        budgets = {"task": 100, "plan": 200, "code_context": 300, "tech_stack": 50}

        context = self.code_generator.context_manager.gather_minimal_context(task, plan, {}, budgets)
        self.assertIn("task", context)
        self.assertEqual(context["task"], task)
        self.assertIn("plan", context)
        self.assertIn(plan, context["plan"])

    def test_gather_enhanced_context(self):
        """Test gathering full context for subsequent attempts."""

        task = "Create a complex function using existing code"
        plan = "Plan to create a function in test_file.py that uses helpers from utils.py"
        budgets = {"task": 100, "plan": 200, "code_context": 300, "tech_stack": 50}

        context = self.code_generator.context_manager.gather_full_context(
            task=task,
            plan=plan,
            tech_stack={},
            token_budgets=budgets,
            failed_attempts=[{"response": "Error in first attempt"}],
        )

        self.assertEqual(context["previous_attempts"][0]["response"], "Error in first attempt")
        self.assertIn(task, context["task"])
        self.assertIn(plan, context["plan"])

    def test_generate_with_validation_applies_debug_fix(self):
        """Ensure debug manager fixes are applied during generation."""
        file_path = "module.py"

        # Mock LLM initial generation response
        self.mock_coordinator.router_agent.call_llm_by_role.return_value = "```python\nbad_code\n```"

        # Validation fails first then succeeds after fix
        self.code_generator.validator.validate_generated_code = MagicMock(side_effect=[(False, ["err"]), (True, [])])

        # Debugging manager provides a fix
        fix = {"analysis": "analysis", "suggested_fixes": [], "fixed_code": "good_code"}
        debug_manager = MagicMock()
        debug_manager.register_generation_issues = MagicMock()
        debug_manager.log_diagnostic_result = MagicMock()
        debug_manager.analyze_issue = MagicMock(return_value=fix)
        self.code_generator.debugging_manager = debug_manager
        self.code_generator.debug_utils = DebugUtils(debug_manager, self.code_generator.scratchpad)

        result = self.code_generator._generate_with_validation(
            file_path,
            "sys",
            "user",
            config=self.mock_coordinator.config.config,
            max_validation_attempts=1,
        )

        self.assertEqual(result, "good_code")
        debug_manager.analyze_issue.assert_called_once()

    def test_generate_with_validation_handles_llm_failure(self):
        """LLM returning None should result in empty code and no validation."""
        file_path = "module.py"

        # LLM fails to return a response
        self.mock_coordinator.router_agent.call_llm_by_role.return_value = None

        # Validator should not be called when generation fails
        self.code_generator.validator.validate_generated_code = MagicMock()

        result = self.code_generator._generate_with_validation(
            file_path, "sys", "user", max_validation_attempts=1
        )

        self.assertEqual(result, "")
        self.code_generator.validator.validate_generated_code.assert_not_called()

if __name__ == '__main__':
    unittest.main()
