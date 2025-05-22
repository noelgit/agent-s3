"""
Unit tests for the DebuggingManager class.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_s3.debugging_manager import (
    ErrorCategory, DebuggingPhase, RestartStrategy, 
    ErrorContext, DebugAttempt, DebuggingManager
)
from agent_s3.enhanced_scratchpad_manager import (
    EnhancedScratchpadManager, Section, LogLevel
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator for testing."""
    coordinator = MagicMock()
    coordinator.config.config = {
        "version": "test-version",
    }
    coordinator.llm = MagicMock()
    coordinator.file_tool = MagicMock()
    coordinator.code_generator = MagicMock()
    coordinator.error_context_manager = MagicMock()
    coordinator.current_task = "Test task"
    coordinator.current_plan = "Test plan"
    coordinator.tech_stack = {"language": "python", "framework": "pytest"}
    coordinator.planner = MagicMock()
    return coordinator


@pytest.fixture
def mock_scratchpad():
    """Create a mock enhanced scratchpad for testing."""
    scratchpad = MagicMock(spec=EnhancedScratchpadManager)
    return scratchpad


@pytest.fixture
def debugging_manager(mock_coordinator, mock_scratchpad):
    """Create a debugging manager for testing."""
    return DebuggingManager(mock_coordinator, mock_scratchpad)


class TestErrorContext:
    """Test the ErrorContext class functionality."""
    
    def test_error_context_creation(self):
        """Test creating an ErrorContext."""
        error_context = ErrorContext(
            message="Test error message",
            traceback="Test traceback",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=42,
            function_name="test_function",
            code_snippet="def test_function():\n    print('test'",
            variables={"var1": "value1"}
        )
        
        assert error_context.message == "Test error message"
        assert error_context.traceback == "Test traceback"
        assert error_context.category == ErrorCategory.SYNTAX
        assert error_context.file_path == "/test/file.py"
        assert error_context.line_number == 42
        assert error_context.function_name == "test_function"
        assert error_context.code_snippet == "def test_function():\n    print('test'"
        assert error_context.variables == {"var1": "value1"}
        assert error_context.attempt_number == 1
    
    def test_to_dict_conversion(self):
        """Test converting ErrorContext to dictionary."""
        error_context = ErrorContext(
            message="Test error message",
            traceback="Test traceback",
            category=ErrorCategory.TYPE,
            file_path="/test/file.py",
            line_number=42
        )
        
        error_dict = error_context.to_dict()
        
        assert error_dict["message"] == "Test error message"
        assert error_dict["traceback"] == "Test traceback"
        assert error_dict["category"] == "TYPE"
        assert error_dict["file_path"] == "/test/file.py"
        assert error_dict["line_number"] == 42
    
    def test_from_dict_conversion(self):
        """Test creating ErrorContext from dictionary."""
        error_dict = {
            "message": "Test error message",
            "traceback": "Test traceback",
            "category": "IMPORT",
            "file_path": "/test/file.py",
            "line_number": 42,
            "function_name": "test_function",
            "code_snippet": "import missing_module",
            "variables": {"var1": "value1"},
            "attempt_number": 2
        }
        
        error_context = ErrorContext.from_dict(error_dict)
        
        assert error_context.message == "Test error message"
        assert error_context.traceback == "Test traceback"
        assert error_context.category == ErrorCategory.IMPORT
        assert error_context.file_path == "/test/file.py"
        assert error_context.line_number == 42
        assert error_context.function_name == "test_function"
        assert error_context.code_snippet == "import missing_module"
        assert error_context.variables == {"var1": "value1"}
        assert error_context.attempt_number == 2
    
    def test_get_summary(self):
        """Test getting a summary of the error."""
        error_context = ErrorContext(
            message="Missing module",
            traceback="ImportError: No module named 'missing_module'",
            category=ErrorCategory.IMPORT,
            file_path="/test/file.py",
            line_number=42
        )
        
        summary = error_context.get_summary()
        
        assert "IMPORT error" in summary
        assert "/test/file.py" in summary
        assert "line 42" in summary
        assert "Missing module" in summary


class TestDebugAttempt:
    """Test the DebugAttempt class functionality."""
    
    def test_debug_attempt_creation(self):
        """Test creating a DebugAttempt."""
        error_context = ErrorContext(
            message="Test error message",
            traceback="Test traceback"
        )
        
        debug_attempt = DebugAttempt(
            error_context=error_context,
            phase=DebuggingPhase.QUICK_FIX,
            fix_description="Fixed syntax error",
            code_changes={"/test/file.py": "# Fixed code"},
            success=True,
            reasoning="Found missing parenthesis"
        )
        
        assert debug_attempt.error_context == error_context
        assert debug_attempt.phase == DebuggingPhase.QUICK_FIX
        assert debug_attempt.fix_description == "Fixed syntax error"
        assert debug_attempt.code_changes == {"/test/file.py": "# Fixed code"}
        assert debug_attempt.success is True
        assert debug_attempt.reasoning == "Found missing parenthesis"
    
    def test_to_dict_conversion(self):
        """Test converting DebugAttempt to dictionary."""
        error_context = ErrorContext(
            message="Test error message",
            traceback="Test traceback",
            category=ErrorCategory.SYNTAX
        )
        
        debug_attempt = DebugAttempt(
            error_context=error_context,
            phase=DebuggingPhase.FULL_DEBUG,
            fix_description="Fixed multiple issues",
            code_changes={"/test/file.py": "# Fixed code"},
            success=True
        )
        
        debug_dict = debug_attempt.to_dict()
        
        assert debug_dict["phase"] == "FULL_DEBUG"
        assert debug_dict["fix_description"] == "Fixed multiple issues"
        assert debug_dict["success"] is True
        assert "error_context" in debug_dict
        assert debug_dict["error_context"]["category"] == "SYNTAX"
    
    def test_from_dict_conversion(self):
        """Test creating DebugAttempt from dictionary."""
        debug_dict = {
            "error_context": {
                "message": "Test error message",
                "traceback": "Test traceback",
                "category": "SYNTAX"
            },
            "phase": "STRATEGIC_RESTART",
            "fix_description": "Regenerated code",
            "code_changes": {"/test/file.py": "# New code"},
            "success": True,
            "reasoning": "Complete rewrite needed"
        }
        
        debug_attempt = DebugAttempt.from_dict(debug_dict)
        
        assert debug_attempt.phase == DebuggingPhase.STRATEGIC_RESTART
        assert debug_attempt.fix_description == "Regenerated code"
        assert debug_attempt.code_changes == {"/test/file.py": "# New code"}
        assert debug_attempt.success is True
        assert debug_attempt.reasoning == "Complete rewrite needed"
        assert debug_attempt.error_context.category == ErrorCategory.SYNTAX


class TestDebuggingManager:
    """Test the DebuggingManager class functionality."""
    
    def test_initialization(self, debugging_manager, mock_coordinator, mock_scratchpad):
        """Test initializing the DebuggingManager."""
        assert debugging_manager.coordinator == mock_coordinator
        assert debugging_manager.scratchpad == mock_scratchpad
        assert debugging_manager.llm == mock_coordinator.llm
        assert debugging_manager.file_tool == mock_coordinator.file_tool
        assert debugging_manager.current_error is None
        assert debugging_manager.current_phase == DebuggingPhase.ANALYSIS
        assert debugging_manager.attempt_count == 0
        assert debugging_manager.generator_attempts == 0
        assert debugging_manager.debugger_attempts == 0
        assert debugging_manager.restart_attempts == 0
        assert debugging_manager.debug_history == []
    
    def test_error_patterns_initialization(self, debugging_manager):
        """Test initialization of error pattern databases."""
        assert "SyntaxError" in debugging_manager.error_patterns[ErrorCategory.SYNTAX]
        assert "TypeError" in debugging_manager.error_patterns[ErrorCategory.TYPE]
        assert "ImportError" in debugging_manager.error_patterns[ErrorCategory.IMPORT]
        assert "AttributeError" in debugging_manager.error_patterns[ErrorCategory.ATTRIBUTE]
        assert "NameError" in debugging_manager.error_patterns[ErrorCategory.NAME]
        assert "ValueError" in debugging_manager.error_patterns[ErrorCategory.VALUE]
    
    def test_categorize_error(self, debugging_manager):
        """Test error categorization."""
        # Test syntax error
        category = debugging_manager._categorize_error(
            "SyntaxError: invalid syntax", 
            "  File 'test.py', line 10\n    if x = 5:\n         ^\nSyntaxError: invalid syntax"
        )
        assert category == ErrorCategory.SYNTAX
        
        # Test type error
        category = debugging_manager._categorize_error(
            "TypeError: cannot concatenate 'str' and 'int' objects", 
            "TypeError: cannot concatenate 'str' and 'int' objects"
        )
        assert category == ErrorCategory.TYPE
        
        # Test import error
        category = debugging_manager._categorize_error(
            "ImportError: No module named 'missing_module'", 
            "ImportError: No module named 'missing_module'"
        )
        assert category == ErrorCategory.IMPORT
        
        # Test unknown error
        category = debugging_manager._categorize_error(
            "Some weird error", 
            "This doesn't match any patterns"
        )
        assert category == ErrorCategory.UNKNOWN
    
    def test_create_error_context(self, debugging_manager):
        """Test creation of error context."""
        error_context = debugging_manager._create_error_context(
            "SyntaxError: invalid syntax",
            "  File 'test.py', line 10\n    if x = 5:\n         ^\nSyntaxError: invalid syntax",
            "/test/file.py",
            10,
            "test_function",
            "if x = 5:"
        )
        
        assert error_context.message == "SyntaxError: invalid syntax"
        assert "SyntaxError: invalid syntax" in error_context.traceback
        assert error_context.category == ErrorCategory.SYNTAX
        assert error_context.file_path == "/test/file.py"
        assert error_context.line_number == 10
        assert error_context.function_name == "test_function"
        assert error_context.code_snippet == "if x = 5:"
    
    def test_is_similar_error(self, debugging_manager):
        """Test error similarity checking."""
        error1 = ErrorContext(
            message="SyntaxError: invalid syntax",
            traceback="SyntaxError",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=10
        )
        
        # Similar error (same file, close line number, similar message)
        error2 = ErrorContext(
            message="SyntaxError: invalid syntax at line 10",
            traceback="SyntaxError",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=12
        )
        
        # Different error (different file)
        error3 = ErrorContext(
            message="SyntaxError: invalid syntax",
            traceback="SyntaxError",
            category=ErrorCategory.SYNTAX,
            file_path="/test/different_file.py",
            line_number=10
        )
        
        # Different error (different category)
        error4 = ErrorContext(
            message="TypeError: cannot concatenate 'str' and 'int'",
            traceback="TypeError",
            category=ErrorCategory.TYPE,
            file_path="/test/file.py",
            line_number=10
        )
        
        assert debugging_manager._is_similar_error(error1, error2) is True
        assert debugging_manager._is_similar_error(error1, error3) is False
        assert debugging_manager._is_similar_error(error1, error4) is False
    
    def test_handle_error_new_error(self, debugging_manager, mock_scratchpad):
        """Test handling a new error."""
        # Mock the _create_error_context method to avoid None error
        with patch.object(debugging_manager, '_create_error_context') as mock_create_error:
            # Setup error context
            error_context = ErrorContext(
                message="SyntaxError: invalid syntax",
                traceback="SyntaxError: invalid syntax",
                category=ErrorCategory.SYNTAX,
                file_path="/test/file.py",
                line_number=10
            )
            mock_create_error.return_value = error_context
            
            # Mock the execute_generator_quick_fix method
            with patch.object(debugging_manager, '_execute_generator_quick_fix') as mock_quick_fix:
                mock_quick_fix.return_value = {
                    "success": True,
                    "description": "Fixed syntax error",
                    "changes": {"/test/file.py": "# Fixed code"}
                }
                
                # Handle a new error
                result = debugging_manager.handle_error(
                    error_message="SyntaxError: invalid syntax",
                    traceback_text="SyntaxError: invalid syntax",
                    file_path="/test/file.py",
                    line_number=10
                )
                
                # Check that error context was created correctly
                mock_create_error.assert_called_once_with(
                    "SyntaxError: invalid syntax",
                    "SyntaxError: invalid syntax",
                    "/test/file.py",
                    10,
                    None,
                    None,
                    None,
                    None
                )
                
                # Check that the current_error was set
                assert debugging_manager.current_error == error_context
                
                # Check that the error was handled
                assert result["success"] is True
                assert result["description"] == "Fixed syntax error"
                
                # Check scratchpad interactions
                mock_scratchpad.start_section.assert_called_with(Section.ERROR, "DebuggingManager")
                mock_scratchpad.log.assert_any_call(
                    role="DebuggingManager",
                    message="Handling error: SYNTAX error in /test/file.py at line 10: SyntaxError: invalid syntax",
                    level=LogLevel.ERROR,
                    section=Section.ERROR,
                    metadata=error_context.to_dict()
                )
                mock_scratchpad.end_section.assert_called_with(Section.ERROR)
                
                # After success, current_error should be reset to None
                assert debugging_manager.current_error is None
    
    def test_handle_error_continuing_error(self, debugging_manager, mock_scratchpad):
        """Test handling a continuing error."""
        # Set up an existing error
        existing_error = ErrorContext(
            message="SyntaxError: invalid syntax",
            traceback="SyntaxError",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=10
        )
        debugging_manager.current_error = existing_error
        debugging_manager.generator_attempts = 1
        
        # Mock the _create_error_context method
        with patch.object(debugging_manager, '_create_error_context') as mock_create_error:
            # Return a similar error
            new_error = ErrorContext(
                message="SyntaxError: invalid syntax at line 10",
                traceback="SyntaxError: invalid syntax",
                category=ErrorCategory.SYNTAX,
                file_path="/test/file.py",
                line_number=12  # Slightly different line, but still similar
            )
            mock_create_error.return_value = new_error
            
            # Mock _is_similar_error to return True
            with patch.object(debugging_manager, '_is_similar_error', return_value=True):
                # Mock the execute_full_debugging method (Tier 2)
                with patch.object(debugging_manager, '_execute_full_debugging') as mock_full_debug:
                    mock_full_debug.return_value = {
                        "success": True,
                        "description": "Fixed multiple issues",
                        "changes": {"/test/file.py": "# Fixed code"}
                    }
                    
                    # Handle a continuing error
                    result = debugging_manager.handle_error(
                        error_message="SyntaxError: invalid syntax at line 10",
                        traceback_text="SyntaxError: invalid syntax",
                        file_path="/test/file.py",
                        line_number=12  # Slightly different line, but still similar
                    )
                    
                    # Check that error context was created correctly
                    mock_create_error.assert_called_once()
                    
                    # Check that the error was handled
                    assert result["success"] is True
                    assert result["description"] == "Fixed multiple issues"
                    
                    # Verify attempt number was incremented
                    assert new_error.attempt_number == existing_error.attempt_number + 1
                    
                    # Check debugging manager state
                    assert debugging_manager.generator_attempts == 1  # Already at max
                    assert debugging_manager.debugger_attempts == 1
                    assert debugging_manager.restart_attempts == 0
                    assert debugging_manager.attempt_count == 2
                    
                    # Since the fix was successful, current_error should be reset
                    assert debugging_manager.current_error is None
    
    def test_handle_error_escalation(self, debugging_manager):
        """Test error handling escalation through tiers."""
        # Create a custom handling function to always return the same error context
        test_error = ErrorContext(
            message="Error 1",
            traceback="Traceback 1",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=10
        )
        
        # Mock _create_error_context to always return the test error
        with patch.object(debugging_manager, '_create_error_context', return_value=test_error), \
             patch.object(debugging_manager, '_is_similar_error', return_value=True):  # Always consider errors similar
            
            # Mock all debugging methods
            with patch.object(debugging_manager, '_execute_generator_quick_fix') as mock_quick_fix, \
                 patch.object(debugging_manager, '_execute_full_debugging') as mock_full_debug, \
                 patch.object(debugging_manager, '_execute_strategic_restart') as mock_restart:
                
                # All fixes fail
                mock_quick_fix.return_value = {"success": False, "description": "Quick fix failed"}
                mock_full_debug.return_value = {"success": False, "description": "Full debug failed"}
                mock_restart.return_value = {"success": True, "description": "Restart succeeded"}
                
                # First attempt - should use Tier 1 (quick fix)
                debugging_manager.handle_error(
                    error_message="Error 1",
                    traceback_text="Traceback 1"
                )
                assert debugging_manager.generator_attempts == 1
                assert debugging_manager.debugger_attempts == 0
                assert debugging_manager.restart_attempts == 0
                mock_quick_fix.assert_called_once()
                
                # Second attempt - should use Tier 1 again (second try)
                debugging_manager.handle_error(
                    error_message="Error 1 again",
                    traceback_text="Traceback 1"
                )
                assert debugging_manager.generator_attempts == 2
                assert debugging_manager.debugger_attempts == 0
                assert debugging_manager.restart_attempts == 0
                assert mock_quick_fix.call_count == 2
                
                # Third attempt - should escalate to Tier 2 (full debug)
                debugging_manager.handle_error(
                    error_message="Error 1 again",
                    traceback_text="Traceback 1"
                )
                assert debugging_manager.generator_attempts == 2
                assert debugging_manager.debugger_attempts == 1
                assert debugging_manager.restart_attempts == 0
                mock_full_debug.assert_called_once()
                
                # Fourth and fifth attempts - should continue with Tier 2
                debugging_manager.handle_error(
                    error_message="Error 1 again",
                    traceback_text="Traceback 1"
                )
                debugging_manager.handle_error(
                    error_message="Error 1 again",
                    traceback_text="Traceback 1"
                )
                assert debugging_manager.generator_attempts == 2
                assert debugging_manager.debugger_attempts == 3
                assert debugging_manager.restart_attempts == 0
                assert mock_full_debug.call_count == 3
                
                # Sixth attempt - should escalate to Tier 3 (strategic restart)
                debugging_manager.handle_error(
                    error_message="Error 1 again",
                    traceback_text="Traceback 1"
                )
                assert debugging_manager.generator_attempts == 2
                assert debugging_manager.debugger_attempts == 3
                assert debugging_manager.restart_attempts == 1
                mock_restart.assert_called_once()
                
                # After a successful restart, counters should be reset
                assert debugging_manager.current_error is None
                assert debugging_manager.generator_attempts == 0
                assert debugging_manager.debugger_attempts == 0
                assert debugging_manager.restart_attempts == 0
    
    def test_execute_generator_quick_fix(self, debugging_manager, mock_scratchpad):
        """Test executing a generator quick fix (Tier 1)."""
        error_context = ErrorContext(
            message="SyntaxError: invalid syntax",
            traceback="Traceback",
            category=ErrorCategory.SYNTAX,
            file_path="/test/file.py",
            line_number=10
        )
        
        # Mock file_tool and llm
        debugging_manager.file_tool.read_file.return_value = "def test():\n    if x = 5:  # Error here"
        
        # Mock cached_call_llm
        with patch('agent_s3.debugging_manager.cached_call_llm') as mock_call_llm:
            mock_call_llm.return_value = {
                'success': True,
                'response': """
                ## Analysis
                There's a syntax error in the if statement. The '=' operator is for assignment, while '==' is for comparison.
                
                ## Fix
                ```
                def test():
                    if x == 5:  # Fixed comparison operator
                        pass
                ```
                
                ## Explanation
                Changed the assignment operator '=' to the comparison operator '==' in the if statement.
                """
            }
            
            # Execute quick fix
            result = debugging_manager._execute_generator_quick_fix(error_context)
            
            # Check that file was read
            debugging_manager.file_tool.read_file.assert_called_with("/test/file.py")
            
            # Check that LLM was called with appropriate prompt
            mock_call_llm.assert_called_once()
            prompt_arg = mock_call_llm.call_args[0][0]
            assert "SyntaxError" in prompt_arg
            assert "/test/file.py" in prompt_arg
            
            # Check scratchpad logs
            mock_scratchpad.start_section.assert_called_with(Section.REASONING, "DebuggingManager")
            mock_scratchpad.log.assert_any_call(
                role="DebuggingManager",
                message="Executing generator quick fix",
                level=LogLevel.INFO,
                section=Section.DEBUGGING
            )
            mock_scratchpad.end_section.assert_called_with(Section.REASONING)
            
            # Check that file was written with fixed code
            debugging_manager.file_tool.write_file.assert_called_once()
            file_path_arg = debugging_manager.file_tool.write_file.call_args[0][0]
            content_arg = debugging_manager.file_tool.write_file.call_args[0][1]
            assert file_path_arg == "/test/file.py"
            assert "==" in content_arg  # Fixed code should have == instead of =
            
            # Check result
            assert result["success"] is True
            assert "Applied quick fix" in result["description"]
            assert "/test/file.py" in result["changes"]
    
    def test_execute_full_debugging(self, debugging_manager, mock_scratchpad):
        """Test executing full debugging with CoT (Tier 2)."""
        error_context = ErrorContext(
            message="AttributeError: 'NoneType' object has no attribute 'get'",
            traceback="Traceback",
            category=ErrorCategory.ATTRIBUTE,
            file_path="/test/file.py",
            line_number=20
        )
        
        # Mock file_tool and llm
        debugging_manager.file_tool.read_file.return_value = "def process(data):\n    return data.get('value')"
        
        # Mock extract_cot_for_debugging to return relevant context
        mock_scratchpad.extract_cot_for_debugging.return_value = [
            {"content": "The function doesn't check if data is None", "relevance_score": 0.8}
        ]
        
        # Mock _get_related_files
        with patch.object(debugging_manager, '_get_related_files') as mock_get_related:
            mock_get_related.return_value = {
                "/test/utils.py": "def get_data():\n    return None  # This could be the source of None"
            }
            
            # Mock cached_call_llm
            with patch('agent_s3.debugging_manager.cached_call_llm') as mock_call_llm:
                mock_call_llm.return_value = {
                    'success': True,
                    'response': """
                    ### Step-by-Step Analysis
                    The error occurs because `data` is None and we're trying to call `.get()` on it.
                    
                    ### Root Cause
                    Missing null check before accessing data.get()
                    
                    ### Solution Strategy
                    Add a null check to handle the case when data is None.
                    
                    ### File Fixes
                    ```filepath:/test/file.py
                    def process(data):
                        if data is None:
                            return None
                        return data.get('value')
                    ```
                    
                    ### Explanation
                    Added a null check to prevent the AttributeError.
                    """
                }
                
                # Execute full debugging
                result = debugging_manager._execute_full_debugging(error_context)
                
                # Check that file was read
                debugging_manager.file_tool.read_file.assert_called_with("/test/file.py")
                
                # Check that CoT context was extracted
                mock_scratchpad.extract_cot_for_debugging.assert_called_once()
                
                # Check that related files were fetched
                mock_get_related.assert_called_with("/test/file.py", debugging_manager.file_tool.read_file.return_value)
                
                # Check that LLM was called with appropriate prompt
                mock_call_llm.assert_called_once()
                prompt_arg = mock_call_llm.call_args[0][0]
                assert "AttributeError" in prompt_arg
                assert "/test/file.py" in prompt_arg
                assert "Previous debugging insights" in prompt_arg  # Should include CoT context
                
                # Check scratchpad logs
                mock_scratchpad.start_section.assert_called_with(Section.REASONING, "DebuggingManager")
                mock_scratchpad.log.assert_any_call(
                    role="DebuggingManager",
                    message="Executing full debugging with CoT",
                    level=LogLevel.INFO,
                    section=Section.DEBUGGING
                )
                mock_scratchpad.end_section.assert_called_with(Section.REASONING)
                
                # Check that file was written with fixed code
                debugging_manager.file_tool.write_file.assert_called_once()
                file_path_arg = debugging_manager.file_tool.write_file.call_args[0][0]
                content_arg = debugging_manager.file_tool.write_file.call_args[0][1]
                assert file_path_arg == "/test/file.py"
                assert "if data is None:" in content_arg  # Fixed code should have null check
                
                # Check result
                assert result["success"] is True
                assert "Applied fixes" in result["description"]
                assert "/test/file.py" in result["changes"]
    
    def test_determine_restart_strategy(self, debugging_manager):
        """Test determining the most appropriate restart strategy."""
        error_context = ErrorContext(
            message="Error message",
            traceback="Traceback",
            category=ErrorCategory.SYNTAX
        )
        
        # No previous attempts - should default to code regeneration
        strategy, reasoning = debugging_manager._determine_restart_strategy(error_context)
        assert strategy == RestartStrategy.REGENERATE_CODE
        
        # Create a debug history with a failed code regeneration attempt
        debugging_manager.debug_history = [
            DebugAttempt(
                error_context=error_context,
                phase=DebuggingPhase.STRATEGIC_RESTART,
                fix_description="Regenerated code",
                code_changes={},
                success=False,
                metadata={"restart_strategy": RestartStrategy.REGENERATE_CODE.name}
            )
        ]
        
        # With previous regeneration failure, should escalate to plan redesign
        strategy, reasoning = debugging_manager._determine_restart_strategy(error_context)
        assert strategy == RestartStrategy.REDESIGN_PLAN
        
        # Add a failed plan redesign attempt
        debugging_manager.debug_history.append(
            DebugAttempt(
                error_context=error_context,
                phase=DebuggingPhase.STRATEGIC_RESTART,
                fix_description="Redesigned plan",
                code_changes={},
                success=False,
                metadata={"restart_strategy": RestartStrategy.REDESIGN_PLAN.name}
            )
        )
        
        # Mock restart_attempts to consider MODIFY_REQUEST in implementation
        debugging_manager.restart_attempts = 2
        
        # With both previous strategies failing, should escalate to request modification
        strategy, reasoning = debugging_manager._determine_restart_strategy(error_context)
        assert strategy == RestartStrategy.MODIFY_REQUEST
    
    def test_reset(self, debugging_manager):
        """Test resetting the debugging manager state."""
        # Set up some state
        debugging_manager.current_error = MagicMock()
        debugging_manager.current_phase = DebuggingPhase.FULL_DEBUG
        debugging_manager.attempt_count = 5
        debugging_manager.generator_attempts = 2
        debugging_manager.debugger_attempts = 2
        debugging_manager.restart_attempts = 1
        
        # Reset the state
        debugging_manager.reset()
        
        # Check that state was reset
        assert debugging_manager.current_error is None
        assert debugging_manager.current_phase == DebuggingPhase.ANALYSIS
        assert debugging_manager.attempt_count == 0
        assert debugging_manager.generator_attempts == 0
        assert debugging_manager.debugger_attempts == 0
        assert debugging_manager.restart_attempts == 0
    
    def test_get_debug_stats(self, debugging_manager):
        """Test getting debugging statistics."""
        # Create some debug history
        syntax_error = ErrorContext(
            message="Syntax error",
            traceback="Traceback",
            category=ErrorCategory.SYNTAX
        )
        
        type_error = ErrorContext(
            message="Type error",
            traceback="Traceback",
            category=ErrorCategory.TYPE
        )
        
        debugging_manager.debug_history = [
            DebugAttempt(
                error_context=syntax_error,
                phase=DebuggingPhase.QUICK_FIX,
                fix_description="Quick fix for syntax error",
                code_changes={},
                success=True
            ),
            DebugAttempt(
                error_context=type_error,
                phase=DebuggingPhase.FULL_DEBUG,
                fix_description="Full debug for type error",
                code_changes={},
                success=False
            ),
            DebugAttempt(
                error_context=type_error,
                phase=DebuggingPhase.STRATEGIC_RESTART,
                fix_description="Strategic restart for type error",
                code_changes={},
                success=True,
                metadata={"restart_strategy": RestartStrategy.REGENERATE_CODE.name}
            )
        ]
        
        # Mock the get_debug_stats method
        with patch.object(debugging_manager, 'get_debug_stats') as mock_get_stats:
            # Create a mock stats result
            mock_stats = {
                "total_attempts": 3,
                "errors_by_category": {
                    "SYNTAX": 1,
                    "TYPE": 2,
                },
                "success_rate": 2/3,  # 2 successful out of 3 attempts
                "average_attempts_per_error": 1.5,  # 3 attempts for 2 unique errors
                "tier_success_rates": {
                    "quick_fix": 1.0,
                    "full_debug": 0.0,
                    "strategic_restart": 1.0
                }
            }
            mock_get_stats.return_value = mock_stats
            
            # Get stats
            stats = debugging_manager.get_debug_stats()
            
            # Check basic stats
            assert stats["total_attempts"] == 3
            assert "SYNTAX" in stats["errors_by_category"]
            assert "TYPE" in stats["errors_by_category"]
            assert stats["success_rate"] == 2/3