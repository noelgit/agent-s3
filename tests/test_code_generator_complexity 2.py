"""Tests for the agentic code generator complexity estimation and debugging functionality."""

import os
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.code_generator import CodeGenerator
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager, LogLevel

class TestCodeGeneratorComplexity:
    """Test suite for complexity estimation and debugging in the CodeGenerator."""
    
    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        coordinator.file_tool = MagicMock()
        coordinator.bash_tool = MagicMock()
        coordinator.debugging_manager = MagicMock()
        return coordinator
    
    def test_estimate_file_complexity_empty(self, mock_coordinator):
        """Test complexity estimation with empty implementation details."""
        code_generator = CodeGenerator(mock_coordinator)
        complexity = code_generator._estimate_file_complexity([])
        
        # Base complexity should be returned
        assert complexity == 1.0
    
    def test_estimate_file_complexity_simple(self, mock_coordinator):
        """Test complexity estimation with simple implementation details."""
        code_generator = CodeGenerator(mock_coordinator)
        implementation_details = [
            {
                "function": "simple_func",
                "signature": "def simple_func(a, b):",
                "description": "A simple function that adds two numbers",
                "imports": ["math"]
            }
        ]
        
        complexity = code_generator._estimate_file_complexity(implementation_details)
        
        # Should be slightly higher than base complexity but not much
        assert complexity > 1.0
        assert complexity < 2.0
    
    def test_estimate_file_complexity_complex(self, mock_coordinator):
        """Test complexity estimation with complex implementation details."""
        code_generator = CodeGenerator(mock_coordinator)
        implementation_details = [
            {
                "class": "ComplexProcessor",
                "signature": "class ComplexProcessor:",
                "description": "A class that processes data with multiple threading and optimization",
                "imports": ["threading", "queue", "numpy", "pandas", "scipy", "os", "sys"]
            },
            {
                "function": "process_data",
                "signature": "def process_data(self, data: List[Dict[str, Any]], options: Optional[ProcessingOptions] = None) -> Tuple[np.ndarray, Dict[str, float]]:",
                "description": "Processes data using parallel processing and caching for optimization",
                "imports": []
            },
            {
                "function": "validate_input",
                "signature": "def validate_input(self, data: Any) -> bool:",
                "description": "Validates input data",
                "imports": []
            },
            {
                "function": "transform",
                "signature": "def transform(self, matrix: np.ndarray) -> np.ndarray:",
                "description": "Transforms data using matrix operations",
                "imports": []
            },
            {
                "function": "_internal_helper",
                "signature": "def _internal_helper(self, x: int, y: int) -> int:",
                "description": "Internal helper function",
                "imports": []
            }
        ]
        
        complexity = code_generator._estimate_file_complexity(implementation_details)
        
        # Should be significantly higher due to complexity factors
        assert complexity > 2.0
    
    def test_estimate_file_complexity_test_file(self, mock_coordinator):
        """Test complexity estimation for test files."""
        code_generator = CodeGenerator(mock_coordinator)
        implementation_details = [
            {
                "function": "test_integration",
                "signature": "def test_integration(self):",
                "description": "Integration test for the system with database connections",
                "imports": ["pytest", "unittest.mock"]
            }
        ]
        
        complexity = code_generator._estimate_file_complexity(implementation_details, file_path="tests/test_integration.py")
        
        # Should have higher complexity due to being a test file with integration testing
        assert complexity > 1.5
    
    def test_estimate_file_complexity_with_existing_file(self, mock_coordinator):
        """Test complexity estimation considering existing file content."""
        code_generator = CodeGenerator(mock_coordinator)
        implementation_details = [
            {
                "function": "new_function",
                "signature": "def new_function(x: int) -> int:",
                "description": "A new function to add",
                "imports": []
            }
        ]
        
        # Mock existing file content
        existing_content = """
        class ExistingClass:
            def method1(self):
                pass
                
            def method2(self):
                pass
                
        def existing_function():
            return True
        """
        
        mock_coordinator.file_tool.read_file.return_value = existing_content
        
        with patch('os.path.exists', return_value=True):
            complexity = code_generator._estimate_file_complexity(implementation_details, file_path="module.py")
        
        # Should consider existing code complexity
        assert complexity > 1.3
    
    def test_debug_generation_issue_syntax_error(self, mock_coordinator):
        """Test debugging for syntax errors."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        generated_code = """
def function_with_error()
    print("Missing colon above")
    
def another_function():
    return None
"""
        validation_issues = ["Syntax error: invalid syntax at line 2"]
        
        diagnostics = code_generator._debug_generation_issue(file_path, generated_code, validation_issues)
        
        assert diagnostics["issue_count"] == 1
        assert "syntax" in diagnostics["categorized_issues"]
        assert len(diagnostics["suggested_fixes"]) > 0
        assert "summary" in diagnostics
    
    def test_debug_generation_issue_import_error(self, mock_coordinator):
        """Test debugging for import errors."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        generated_code = """
import missing_module

def function():
    obj = missing_module.Class()
    return obj
"""
        validation_issues = ["No module named 'missing_module'"]
        
        diagnostics = code_generator._debug_generation_issue(file_path, generated_code, validation_issues)
        
        assert "import" in diagnostics["categorized_issues"]
        assert any("missing_module" in fix.get("issue", "") for fix in diagnostics["suggested_fixes"])
    
    def test_debug_generation_issue_undefined_variable(self, mock_coordinator):
        """Test debugging for undefined variables."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        generated_code = """
def function():
    return undefined_variable
"""
        validation_issues = ["name 'undefined_variable' is not defined"]
        
        diagnostics = code_generator._debug_generation_issue(file_path, generated_code, validation_issues)
        
        assert "undefined" in diagnostics["categorized_issues"]
        assert any("undefined_variable" in fix.get("issue", "") for fix in diagnostics["suggested_fixes"])
    
    def test_debug_generation_issue_type_error(self, mock_coordinator):
        """Test debugging for type errors."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        generated_code = """
def function() -> str:
    return 42
"""
        validation_issues = ["Incompatible return value type (got 'int', expected 'str')"]
        
        diagnostics = code_generator._debug_generation_issue(file_path, generated_code, validation_issues)
        
        assert "type" in diagnostics["categorized_issues"]
    
    def test_debug_generation_issue_multiple_issues(self, mock_coordinator):
        """Test debugging for multiple issues of different types."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        generated_code = """
import missing_module

def function()
    x = undefined_variable
    return "string"
"""
        validation_issues = [
            "Syntax error: invalid syntax at line 4",
            "No module named 'missing_module'",
            "name 'undefined_variable' is not defined"
        ]
        
        diagnostics = code_generator._debug_generation_issue(file_path, generated_code, validation_issues)
        
        assert diagnostics["issue_count"] == 3
        assert "syntax" in diagnostics["categorized_issues"]
        assert "import" in diagnostics["categorized_issues"]
        assert "undefined" in diagnostics["categorized_issues"]
        assert len(diagnostics["critical_issues"]) == 3
        assert len(diagnostics["suggested_fixes"]) > 0
    
    def test_debug_generation_issue_integration_with_debugging_manager(self, mock_coordinator):
        """Test integration with debugging manager."""
        code_generator = CodeGenerator(mock_coordinator)
        file_path = "module.py"
        validation_issues = ["Syntax error: invalid syntax"]
        
        diagnostics = code_generator._debug_generation_issue(file_path, "", validation_issues)
        
        # Should have called the debugging manager's methods
        mock_coordinator.debugging_manager.register_generation_issues.assert_called_once_with(file_path, diagnostics)
        mock_coordinator.debugging_manager.log_diagnostic_result.assert_called_once()
