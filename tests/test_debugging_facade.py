"""
Unit tests for the DebuggingManager facade methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_s3.debugging_manager import (
    ErrorCategory, DebuggingPhase, ErrorContext, DebugAttempt, DebuggingManager
)
from agent_s3.enhanced_scratchpad_manager import (
    EnhancedScratchpadManager, Section
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


class TestDebuggingFacadeMethods:
    """Test the facade methods in the DebuggingManager class."""
    
    def test_analyze_error(self, debugging_manager, mock_scratchpad):
        """Test analyzing an error without attempting to fix it."""
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
            
            # Analyze the error
            analysis = debugging_manager.analyze_error(
                error_message="SyntaxError: invalid syntax",
                traceback_text="SyntaxError: invalid syntax",
                file_path="/test/file.py",
                line_number=10
            )
            
            # Verify error context was created
            mock_create_error.assert_called_once_with(
                "SyntaxError: invalid syntax",
                "SyntaxError: invalid syntax",
                "/test/file.py",
                10,
                None,
                None,
                None
            )
            
            # Verify scratchpad section was started and ended
            mock_scratchpad.start_section.assert_called_with(Section.ANALYSIS, "DebuggingManager")
            mock_scratchpad.end_section.assert_called_with(Section.ANALYSIS)
            
            # Check analysis result structure
            assert "error" in analysis
            assert "severity" in analysis
            assert "fix_approach" in analysis
            assert "recommended_tier" in analysis
            assert "similar_errors_found" in analysis
            assert "is_likely_fixable" in analysis
            
            # Check specific values for syntax error
            assert analysis["error"]["category"] == "SYNTAX"
            assert analysis["severity"] == "LOW"  # Syntax errors are low severity
            assert analysis["fix_approach"] == "CODE_FIX"
            assert analysis["recommended_tier"] == "QUICK_FIX"
            assert analysis["is_likely_fixable"] is True
    
    def test_debug_error_facade(self, debugging_manager):
        """Test the simple debug_error facade method."""
        with patch.object(debugging_manager, 'handle_error') as mock_handle_error:
            mock_handle_error.return_value = {
                "success": True,
                "description": "Fixed syntax error"
            }
            
            # Call debug_error
            result = debugging_manager.debug_error(
                error_message="SyntaxError: invalid syntax",
                file_path="/test/file.py",
                line_number=10
            )
            
            # Verify handle_error was called with correct arguments
            mock_handle_error.assert_called_once_with(
                error_message="SyntaxError: invalid syntax",
                traceback_text="SyntaxError: invalid syntax",  # Should use error_message as traceback
                file_path="/test/file.py",
                line_number=10
            )
            
            # Verify result is passed through
            assert result["success"] is True
            assert result["description"] == "Fixed syntax error"
            
            # Test with explicit traceback_text
            debugging_manager.debug_error(
                error_message="SyntaxError: invalid syntax",
                file_path="/test/file.py",
                line_number=10,
                traceback_text="Detailed traceback text"
            )
            
            # Should be called with explicit traceback text
            mock_handle_error.assert_called_with(
                error_message="SyntaxError: invalid syntax",
                traceback_text="Detailed traceback text",
                file_path="/test/file.py",
                line_number=10
            )
    
    def test_get_current_error(self, debugging_manager):
        """Test getting the current error being debugged."""
        # No current error
        assert debugging_manager.get_current_error() is None
        
        # Set a current error
        error_context = ErrorContext(
            message="Test error message",
            traceback="Test traceback"
        )
        debugging_manager.current_error = error_context
        
        # Get current error
        assert debugging_manager.get_current_error() == error_context
    
    def test_get_error_history(self, debugging_manager):
        """Test getting the history of debugging attempts with filtering."""
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
                success=True
            )
        ]
        
        # Get all history
        history = debugging_manager.get_error_history()
        assert len(history) == 3
        
        # Get limited history
        history = debugging_manager.get_error_history(limit=2)
        assert len(history) == 2
        assert history[1]["error_context"]["category"] == "TYPE"
        assert history[1]["phase"] == "STRATEGIC_RESTART"
        
        # Filter by category
        history = debugging_manager.get_error_history(filter_category=ErrorCategory.SYNTAX)
        assert len(history) == 1
        assert history[0]["error_context"]["category"] == "SYNTAX"
        
        # Filter by success
        history = debugging_manager.get_error_history(filter_success=True)
        assert len(history) == 2
        assert all(item["success"] for item in history)
        
        # Combine filters
        history = debugging_manager.get_error_history(
            filter_category=ErrorCategory.TYPE,
            filter_success=True
        )
        assert len(history) == 1
        assert history[0]["error_context"]["category"] == "TYPE"
        assert history[0]["success"] is True
    
    def test_can_debug_error(self, debugging_manager):
        """Test checking if an error is debuggable."""
        with patch.object(debugging_manager, '_create_error_context') as mock_create_error, \
             patch('os.path.exists') as mock_exists:
            
            # Setup mock for file existence check
            mock_exists.return_value = True
            
            # Case 1: Debuggable syntax error with file path
            mock_create_error.return_value = ErrorContext(
                message="SyntaxError",
                traceback="",
                category=ErrorCategory.SYNTAX
            )
            
            assert debugging_manager.can_debug_error(
                error_message="SyntaxError",
                file_path="/test/file.py"
            ) is True
            
            # Case 2: Unknown error but file exists
            mock_create_error.return_value = ErrorContext(
                message="Unknown error",
                traceback="",
                category=ErrorCategory.UNKNOWN
            )
            
            assert debugging_manager.can_debug_error(
                error_message="Unknown error",
                file_path="/test/file.py"
            ) is False  # Unknown category without context is not debuggable
            
            # Case 3: Permission error
            mock_create_error.return_value = ErrorContext(
                message="Permission denied",
                traceback="",
                category=ErrorCategory.PERMISSION
            )
            
            assert debugging_manager.can_debug_error(
                error_message="Permission denied",
                file_path="/test/file.py"
            ) is False  # Permission errors are not typically debuggable
            
            # Case 4: File doesn't exist
            mock_exists.return_value = False
            mock_create_error.return_value = ErrorContext(
                message="SyntaxError",
                traceback="",
                category=ErrorCategory.SYNTAX
            )
            
            assert debugging_manager.can_debug_error(
                error_message="SyntaxError",
                file_path="/test/nonexistent.py"
            ) is False  # Can't debug if file doesn't exist
            
            # Case 5: Previous success for similar error makes it debuggable
            mock_exists.return_value = True
            mock_create_error.return_value = ErrorContext(
                message="Permission denied",
                traceback="",
                category=ErrorCategory.PERMISSION
            )
            
            # Add a successful debug attempt for a similar error
            with patch.object(debugging_manager, '_is_similar_error', return_value=True):
                debugging_manager.debug_history = [
                    DebugAttempt(
                        error_context=ErrorContext(
                            message="Permission denied",
                            traceback="",
                            category=ErrorCategory.PERMISSION
                        ),
                        phase=DebuggingPhase.STRATEGIC_RESTART,
                        fix_description="Found workaround",
                        code_changes={},
                        success=True
                    )
                ]
                
                assert debugging_manager.can_debug_error(
                    error_message="Permission denied",
                    file_path="/test/file.py"
                ) is True  # Debuggable because we've fixed similar errors before