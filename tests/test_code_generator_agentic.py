"""Tests for the agentic code generator."""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.code_generator import CodeGenerator
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
from agent_s3.config import Config # Added import
from agent_s3.llm_utils import LLMUtils # Added import
from agent_s3.tools.file_tool import FileTools # Corrected import
from agent_s3.tools.bash_tool import BashTools # Corrected import
from agent_s3.router_agent import RouterAgent # Added import


class TestCodeGeneratorAgentic:
    """Test suite for the agentic CodeGenerator."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.config = MagicMock(spec=Config) # Added
        coordinator.llm_utils = MagicMock(spec=LLMUtils) # Added
        coordinator.file_tool = MagicMock(spec=FileTools) # Changed spec
        coordinator.bash_tool = MagicMock(spec=BashTools) # Changed spec
        coordinator.router_agent = MagicMock(spec=RouterAgent) # Changed spec
        coordinator.scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        return coordinator

    def test_extract_files_from_plan(self, mock_coordinator):
        """Test extracting files from an implementation plan."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        implementation_plan = {
            "file1.py": [
                {"function": "func1", "description": "test"}
            ],
            "file2.py": [
                {"function": "func2", "description": "test2"}
            ]
        }

        # Act
        result = code_generator._extract_files_from_plan(implementation_plan)

        # Assert
        assert len(result) == 2
        assert result[0][0] == "file1.py"
        assert result[1][0] == "file2.py"
        assert result[0][1][0]["function"] == "func1"
        assert result[1][1][0]["function"] == "func2"

    def test_prepare_file_context(self, mock_coordinator):
        """Test preparing context for a file."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py"
        implementation_details = [
            {"function": "test_func", "description": "A test function", "imports": ["datetime", "agent_s3.utils"]}
        ]

        # Mock file reading
        mock_coordinator.file_tool.read_file.return_value = "import datetime\nimport agent_s3.utils\n\ndef existing_func():\n    pass"

        # Mock os.path.exists and os.listdir
        with patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.is_dir', return_value=False), \
             patch('os.listdir', return_value=[]): # os.listdir might still be used by dependencies or older code paths
            # Act
            context = code_generator._prepare_file_context(file_path, implementation_details)

            # Assert
            assert "existing_code" in context
            assert context["existing_code"].startswith("import datetime")
            assert "imports" in context
            assert "datetime" in context["imports"]
            assert "agent_s3.utils" in context["imports"]

    def test_extract_relevant_tests(self, mock_coordinator):
        """Test extracting tests relevant to a specific file."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py" # Keep as string
        tests = {
            "unit_tests": [
                {
                    "file": "tests/test_test_module.py",
                    "test_name": "test_test_module_func",
                    "tested_functions": ["agent_s3.test_module.test_func"], # Corrected path
                    "code": "def test_test_module_func():\n    assert test_func() is True"
                },
                {
                    "file": "tests/test_other_module.py",
                    "test_name": "test_other_func",
                    "tested_functions": ["agent_s3.other_module.other_func"], # Corrected path
                    "code": "def test_other_func():\n    assert other_func() is True"
                }
            ],
            "integration_tests": [
                {
                    "file": "tests/test_integration.py",
                    "test_name": "test_integration",
                    "components_involved": ["agent_s3.test_module", "agent_s3.other_module"], # Corrected paths
                    "code": "def test_integration():\n    assert test_module.test_func() and other_module.other_func()" # Corrected string literal
                }
            ]
        }

        # Act
        relevant_tests = code_generator._extract_relevant_tests(tests, file_path)

        # Assert
        assert len(relevant_tests["unit_tests"]) == 1
        assert relevant_tests["unit_tests"][0]["test_name"] == "test_test_module_func"
        assert len(relevant_tests["integration_tests"]) == 1
        assert relevant_tests["integration_tests"][0]["components_involved"] == ["agent_s3.test_module", "agent_s3.other_module"]

    def test_generate_file(self, mock_coordinator):
        """Test generation of a single file."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py"
        implementation_details = [
            {"function": "test_func", "description": "A test function"}
        ]
        tests = {"unit_tests": []}

        # Mock necessary methods
        code_generator._extract_relevant_tests = MagicMock(return_value={"unit_tests": []})
        code_generator._generate_with_validation = MagicMock(return_value="def test_func():\n    return True") # Corrected string literal
        # Act
        result = code_generator.generate_file(file_path, implementation_details, tests, {})

        # Assert
        assert result == "def test_func():\n    return True"
        code_generator._extract_relevant_tests.assert_called_once()
        code_generator._generate_with_validation.assert_called_once()

    def test_validate_generated_code_valid(self, mock_coordinator):
        """Test validation of valid code."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py"
        valid_code = "def test_func():\n    return True"

        # Mock bash tool response for flake8 and mypy (no errors)
        # Simulate successful run for both flake8 and mypy
        mock_coordinator.bash_tool.run_command.side_effect = [
            (0, "", ""), # flake8 success
            (0, "", "")  # mypy success
        ]


        # Act
        with patch('ast.parse'):  # Mock ast.parse to avoid actual parsing
            is_valid, issues = code_generator._validate_generated_code(file_path, valid_code)

        # Assert
        assert is_valid is True
        assert len(issues) == 0
        # Ensure bash_tool.run_command was called twice (for flake8 and mypy)
        assert mock_coordinator.bash_tool.run_command.call_count == 2


    def test_validate_generated_code_invalid(self, mock_coordinator):
        """Test validation of invalid code."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py"
        invalid_code = "def test_func()\n    \n    return undefined_variable"  # Missing colon and undefined variable
        
        # Simulate flake8 finding an error and mypy finding an error
        mock_coordinator.bash_tool.run_command.side_effect = [
            (1, "E999 SyntaxError: invalid syntax", ""), # flake8 error
            (1, "test_module.py:2: error: Name 'undefined_variable' is not defined", "") # mypy error
        ]

        # Mock ast.parse to raise SyntaxError for the initial parse attempt
        with patch('ast.parse', side_effect=SyntaxError("invalid syntax")):
            # Act
            is_valid, issues = code_generator._validate_generated_code(file_path, invalid_code)

        # Assert
        assert is_valid is False
        assert len(issues) > 0 # Expecting issues from ast.parse, flake8, and mypy
        assert any("SyntaxError: invalid syntax" in issue for issue in issues) # From ast.parse
        assert any("E999 SyntaxError: invalid syntax" in issue for issue in issues) # From flake8
        assert any("Name 'undefined_variable' is not defined" in issue for issue in issues) # From mypy
        # Ensure bash_tool.run_command was called twice (for flake8 and mypy)
        assert mock_coordinator.bash_tool.run_command.call_count == 2


    def test_refine_code(self, mock_coordinator):
        """Test code refinement based on validation issues."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "agent_s3/test_module.py"
        original_code = "def test_func():\n    return undefined_variable"
        validation_issues = ["undefined_variable is not defined"]

        # Mock LLM call for refinement
        mock_coordinator.router_agent.call_llm_by_role.return_value = """```python
def test_func():
    defined_variable = "value"
    return defined_variable
```"""

        # Act
        refined_code = code_generator._refine_code(file_path, original_code, validation_issues)

        # Assert
        assert refined_code is not None
        assert "undefined_variable" not in refined_code
        assert "defined_variable" in refined_code

    def test_generate_code_integration(self, mock_coordinator):
        """Test the complete generate_code method."""
        # Arrange
        code_generator = CodeGenerator(mock_coordinator)

        # Mock methods to control behavior
        code_generator._extract_files_from_plan = MagicMock(return_value=[
            ("file1.py", [{"function": "func1"}]),
            ("file2.py", [{"function": "func2"}])
        ])
        code_generator._prepare_file_context = MagicMock(return_value={})
        code_generator.generate_file = MagicMock(side_effect=["content1", "content2"])

        plan = {
            "implementation_plan": {"file1.py": [], "file2.py": []},
            "tests": {},
            "group_name": "Test Group"
        }

        # Act
        result = code_generator.generate_code(plan)

        # Assert
        assert len(result) == 2
        assert "file1.py" in result
        assert "file2.py" in result
        assert result["file1.py"] == "content1"
        assert result["file2.py"] == "content2"
        assert code_generator.generate_file.call_count == 2

