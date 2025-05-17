"""
Tests for the centralized error handling system.
"""

import logging
import pytest
from contextlib import contextmanager
from typing import Dict, Optional, Type

from agent_s3.errors import (
    AgentError,
    ErrorCategory,
    ErrorContext,
    PlanningError,
    GenerationError,
    JSONPlanningError,
    categorize_exception,
    create_error_context,
    extract_syntax_error_info,
    log_exception,
    categorize_error_message
)
from agent_s3.error_handler import ErrorHandler, retry


# Helper context manager for asserting exceptions
@contextmanager
def assert_raises_with_context(exc_type: Type[Exception], check_context: bool = True):
    """Assert that an exception is raised and has an error context if it's an AgentError."""
    try:
        yield
        pytest.fail(f"Expected {exc_type.__name__} to be raised")
    except exc_type as e:
        if check_context and isinstance(e, AgentError):
            assert hasattr(e, "context"), f"Expected {exc_type.__name__} to have error context"
            assert isinstance(e.context, ErrorContext), f"Expected context to be an ErrorContext"
        # Re-raise non-matching exceptions
        elif not isinstance(e, exc_type):
            raise


class TestErrorCategories:
    """Tests for error categorization functionality."""
    
    def test_error_category_enum(self):
        """Test that ErrorCategory enum has expected values."""
        assert ErrorCategory.SYNTAX.value == "syntax_error"
        assert ErrorCategory.PLANNING.value == "planning_error"
        assert ErrorCategory.UNKNOWN.value == "unknown_error"
    
    def test_categorize_exception(self):
        """Test exception categorization based on type."""
        syntax_error = SyntaxError("invalid syntax")
        type_error = TypeError("invalid type")
        attribute_error = AttributeError("object has no attribute")
        planning_error = PlanningError("planning failed")
        
        assert categorize_exception(syntax_error) == ErrorCategory.SYNTAX
        assert categorize_exception(type_error) == ErrorCategory.TYPE
        assert categorize_exception(attribute_error) == ErrorCategory.ATTRIBUTE
        assert categorize_exception(planning_error) == ErrorCategory.PLANNING
        assert categorize_exception(Exception("generic")) == ErrorCategory.UNKNOWN
    
    def test_categorize_error_message(self):
        """Test error message categorization based on content."""
        syntax_message = "SyntaxError: invalid syntax at line 10"
        import_message = "ModuleNotFoundError: No module named 'nonexistent'"
        schema_message = "JSON error: invalid format"
        unknown_message = "Something went wrong"
        
        category, _ = categorize_error_message(syntax_message)
        assert category == ErrorCategory.SYNTAX
        
        category, _ = categorize_error_message(import_message)
        assert category == ErrorCategory.IMPORT
        
        category, _ = categorize_error_message(schema_message)
        assert category == ErrorCategory.SCHEMA
        
        category, _ = categorize_error_message(unknown_message)
        assert category == ErrorCategory.UNKNOWN


class TestErrorContext:
    """Tests for ErrorContext class and related utilities."""
    
    def test_error_context_creation(self):
        """Test creating an ErrorContext object."""
        context = ErrorContext(
            error_type="TestError",
            error_message="Test error message",
            category=ErrorCategory.PLANNING,
            file_path="test_file.py",
            line_number=42,
            function_name="test_function",
            component="TestComponent",
            phase="planning",
            operation="test_operation"
        )
        
        assert context.error_type == "TestError"
        assert context.error_message == "Test error message"
        assert context.category == ErrorCategory.PLANNING
        assert context.file_path == "test_file.py"
        assert context.line_number == 42
        assert context.function_name == "test_function"
        assert context.component == "TestComponent"
        assert context.phase == "planning"
        assert context.operation == "test_operation"
    
    def test_error_context_to_dict(self):
        """Test converting ErrorContext to a dictionary."""
        context = ErrorContext(
            error_type="TestError",
            error_message="Test error message",
            category=ErrorCategory.PLANNING
        )
        
        context_dict = context.to_dict()
        assert context_dict["error_type"] == "TestError"
        assert context_dict["error_message"] == "Test error message"
        assert context_dict["category"] == "planning_error"
        assert "timestamp" in context_dict
    
    def test_create_error_context_from_exception(self):
        """Test creating ErrorContext from an exception."""
        try:
            # Raise a test exception
            raise ValueError("Test value error")
        except Exception as e:
            context = create_error_context(
                exc=e,
                component="TestComponent",
                phase="test_phase",
                operation="test_operation"
            )
            
            assert context.error_type == "ValueError"
            assert context.error_message == "Test value error"
            assert context.category == ErrorCategory.VALUE
            assert context.component == "TestComponent"
            assert context.phase == "test_phase"
            assert context.operation == "test_operation"
            assert "test_error_handling.py" in context.file_path
    
    def test_extract_syntax_error_info(self):
        """Test extracting information from syntax error messages."""
        # Test standard format
        file_path, line_number, desc = extract_syntax_error_info(
            '"test_file.py", line 42: invalid syntax'
        )
        assert file_path == "test_file.py"
        assert line_number == 42
        assert desc == "invalid syntax"
        
        # Test alternative format
        file_path, line_number, desc = extract_syntax_error_info(
            'File "test_file.py", line 42: invalid syntax'
        )
        assert file_path == "test_file.py"
        assert line_number == 42
        assert desc == "invalid syntax"
        
        # Test line-only format
        file_path, line_number, desc = extract_syntax_error_info(
            'line 42: invalid syntax'
        )
        assert file_path is None
        assert line_number == 42
        assert desc == "invalid syntax"
        
        # Test unrecognized format
        file_path, line_number, desc = extract_syntax_error_info(
            'Syntax error in test_file.py'
        )
        assert file_path is None
        assert line_number is None
        assert desc == 'Syntax error in test_file.py'


class TestAgentExceptions:
    """Tests for AgentError and its subclasses."""
    
    def test_agent_error_creation(self):
        """Test creating an AgentError with and without context."""
        # Create error without context
        error = AgentError("Test agent error")
        assert str(error) == "Test agent error"
        assert hasattr(error, "context")
        assert error.context.error_type == "AgentError"
        assert error.context.error_message == "Test agent error"
        assert error.context.category == ErrorCategory.UNKNOWN
        
        # Create error with context
        context = ErrorContext(
            error_type="CustomError",
            error_message="Custom error message",
            category=ErrorCategory.PLANNING
        )
        error = AgentError("Test agent error", context)
        assert str(error) == "Test agent error"
        assert error.context.error_type == "CustomError"
        assert error.context.error_message == "Custom error message"
        assert error.context.category == ErrorCategory.PLANNING
    
    def test_specialized_exceptions(self):
        """Test specialized exception types with their default categories."""
        planning_error = PlanningError("Planning failed")
        assert planning_error.context.category == ErrorCategory.PLANNING
        
        json_error = JSONPlanningError("Invalid JSON")
        assert json_error.context.category == ErrorCategory.SCHEMA
        
        generation_error = GenerationError("Generation failed")
        assert generation_error.context.category == ErrorCategory.GENERATION
    
    def test_error_to_dict(self):
        """Test converting AgentError to a dictionary."""
        error = PlanningError("Planning failed")
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "PlanningError"
        assert error_dict["error_message"] == "Planning failed"
        assert error_dict["category"] == "planning_error"
        assert "timestamp" in error_dict


class TestErrorHandler:
    """Tests for the ErrorHandler class."""
    
    def setup_method(self):
        """Set up a test error handler and logger."""
        self.test_logger = logging.getLogger("test_error_handler")
        self.handler = ErrorHandler(
            component="TestComponent",
            logger=self.test_logger,
            reraise=False,
            transform_exceptions=True
        )
    
    def test_handle_exception(self):
        """Test handling an exception without re-raising."""
        try:
            raise ValueError("Test value error")
        except Exception as e:
            context = self.handler.handle_exception(
                exc=e,
                phase="test_phase",
                operation="test_operation"
            )
            
            assert context.error_type == "ValueError"
            assert context.component == "TestComponent"
            assert context.phase == "test_phase"
    
    def test_handle_exception_with_reraise(self):
        """Test handling an exception with re-raising."""
        try:
            raise ValueError("Test value error")
        except Exception as e:
            with pytest.raises(AgentError) as exc_info:
                self.handler.handle_exception(
                    exc=e,
                    phase="test_phase",
                    operation="test_operation",
                    reraise=True
                )
            
            assert "Test value error" in str(exc_info.value)
    
    def test_handle_exception_without_transform(self):
        """Test handling an exception without transformation."""
        handler = ErrorHandler(
            component="TestComponent",
            reraise=False,
            transform_exceptions=False
        )
        
        try:
            raise ValueError("Test value error")
        except Exception as e:
            context = handler.handle_exception(
                exc=e,
                phase="test_phase",
                operation="test_operation"
            )
            
            assert context.error_type == "ValueError"
    
    def test_handle_exception_with_transform(self):
        """Test handling an exception with transformation."""
        try:
            raise ValueError("Test value error")
        except Exception as e:
            with pytest.raises(AgentError) as exc_info:
                self.handler.handle_exception(
                    exc=e,
                    phase="test_phase",
                    operation="test_operation",
                    reraise=True
                )
            
            assert isinstance(exc_info.value, AgentError)
            assert not isinstance(exc_info.value, ValueError)
            assert "Test value error" in str(exc_info.value)
    
    def test_exception_decorator(self):
        """Test the exception decorator."""
        # Define a function that raises an exception
        @self.handler.exception_decorator(
            phase="test_phase",
            operation="test_operation",
            default_return="default"
        )
        def failing_function():
            raise ValueError("Test value error")
        
        # The function should return the default value without raising
        result = failing_function()
        assert result == "default"
        
        # Modify the decorator to re-raise
        @self.handler.exception_decorator(
            phase="test_phase",
            operation="test_operation",
            reraise=True
        )
        def failing_function_reraise():
            raise ValueError("Test value error")
        
        # The function should raise an AgentError
        with pytest.raises(AgentError):
            failing_function_reraise()
    
    def test_error_context_manager(self):
        """Test the error context manager."""
        # Without re-raising
        try:
            with self.handler.error_context(
                phase="test_phase",
                operation="test_operation"
            ):
                raise ValueError("Test value error")
        except Exception:
            pytest.fail("Exception should not have been re-raised")
        
        # With re-raising
        with pytest.raises(AgentError):
            with self.handler.error_context(
                phase="test_phase",
                operation="test_operation",
                reraise=True
            ):
                raise ValueError("Test value error")


class TestRetryDecorator:
    """Tests for the retry decorator."""
    
    def test_retry_success_after_failure(self):
        """Test retry succeeding after initial failures."""
        attempts = 0
        
        @retry(max_attempts=3)
        def failing_then_succeeding():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError(f"Failure on attempt {attempts}")
            return "success"
        
        result = failing_then_succeeding()
        assert result == "success"
        assert attempts == 3
    
    def test_retry_all_failures(self):
        """Test retry failing on all attempts."""
        attempts = 0
        
        @retry(max_attempts=3)
        def always_failing():
            nonlocal attempts
            attempts += 1
            raise ValueError(f"Failure on attempt {attempts}")
        
        with pytest.raises(ValueError) as exc_info:
            always_failing()
        
        assert "Failure on attempt 3" in str(exc_info.value)
        assert attempts == 3
    
    def test_retry_specific_exceptions(self):
        """Test retry only for specific exceptions."""
        attempts = 0
        
        @retry(max_attempts=3, exceptions=ValueError)
        def mixed_exceptions():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("Retryable error")
            elif attempts == 2:
                raise TypeError("Non-retryable error")
            return "success"
        
        with pytest.raises(TypeError) as exc_info:
            mixed_exceptions()
        
        assert "Non-retryable error" in str(exc_info.value)
        assert attempts == 2
    
    def test_retry_with_custom_predicate(self):
        """Test retry with custom predicate function."""
        attempts = 0
        
        def should_retry(exc, attempt):
            return isinstance(exc, ValueError) and "retry" in str(exc).lower()
        
        @retry(max_attempts=3, should_retry_func=should_retry)
        def conditional_retry():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ValueError("Please retry this")
            elif attempts == 2:
                raise ValueError("Don't retry this")
            return "success"
        
        with pytest.raises(ValueError) as exc_info:
            conditional_retry()
        
        assert "Don't retry this" in str(exc_info.value)
        assert attempts == 2