"""
Centralized error handling module for Agent-S3.

This module defines a consistent hierarchy of exceptions, error categorization,
and utilities for error handling across the entire agent_s3 system.
"""

import enum
import logging
import os
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Enumeration of error categories for consistent classification."""
    
    # Code-related errors
    SYNTAX = "syntax_error"
    TYPE = "type_error"
    IMPORT = "import_error"
    ATTRIBUTE = "attribute_error"
    NAME = "name_error"
    INDEX = "index_error"
    VALUE = "value_error"
    ASSERTION = "assertion_error"
    
    # Runtime and system errors
    RUNTIME = "runtime_error"
    MEMORY = "memory_error"
    PERMISSION = "permission_error"
    
    # Infrastructure errors
    NETWORK = "network_error"
    DATABASE = "database_error"
    
    # Agent-S3 specific errors
    PLANNING = "planning_error"
    GENERATION = "generation_error"
    VALIDATION = "validation_error"
    SCHEMA = "schema_error"
    COORDINATION = "coordination_error"
    DEBUGGING = "debugging_error"
    AUTHENTICATION = "authentication_error"
    
    # Default
    UNKNOWN = "unknown_error"


@dataclass
class ErrorContext:
    """
    Structured context for error information to facilitate debugging.
    
    This class captures detailed context about where, when, and how an error occurred.
    """
    
    # Error identification
    error_type: str
    error_message: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Location information
    file_path: Optional[str] = None
    function_name: Optional[str] = None
    line_number: Optional[int] = None
    stacktrace: str = field(default_factory=str)
    
    # Additional context
    component: Optional[str] = None
    phase: Optional[str] = None
    operation: Optional[str] = None
    
    # Contextual data (e.g., input values, parameters)
    variables: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[str, Any] = field(default_factory=dict)
    
    # For tracking error handling progress
    attempt_number: int = 0
    recovery_attempted: bool = False
    recovery_strategy: Optional[str] = None
    
    def __post_init__(self):
        """Ensure stacktrace is populated if not provided."""
        if not self.stacktrace:
            self.stacktrace = traceback.format_exc()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error context to a dictionary for serialization."""
        result = {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "timestamp": self.timestamp.isoformat(),
        }
        
        # Add optional fields if they exist
        for field_name in ["file_path", "function_name", "line_number", "stacktrace",
                          "component", "phase", "operation"]:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        
        # Add dictionary fields if they are not empty
        for field_name in ["variables", "inputs"]:
            value = getattr(self, field_name)
            if value:
                result[field_name] = value
        
        # Add recovery information
        result["attempt_number"] = self.attempt_number
        result["recovery_attempted"] = self.recovery_attempted
        if self.recovery_strategy:
            result["recovery_strategy"] = self.recovery_strategy
            
        return result


# Base exception for all Agent-S3 errors
class AgentError(Exception):
    """Base exception for all Agent-S3 specific errors."""
    
    def __init__(
        self, 
        message: str, 
        context: Optional[ErrorContext] = None,
        **kwargs
    ):
        super().__init__(message)
        
        # Create or update error context
        if context is None:
            # Extract information from traceback
            tb = traceback.extract_tb(traceback.exc_info()[2])
            frame = tb[-1] if tb else None
            
            self.context = ErrorContext(
                error_type=self.__class__.__name__,
                error_message=message,
                category=self._get_default_category(),
                file_path=frame.filename if frame else None,
                line_number=frame.lineno if frame else None,
                function_name=frame.name if frame else None,
                **kwargs
            )
        else:
            self.context = context
            
            # Update error context if needed
            if not self.context.error_type:
                self.context.error_type = self.__class__.__name__
            if not self.context.error_message:
                self.context.error_message = message
            if self.context.category == ErrorCategory.UNKNOWN:
                self.context.category = self._get_default_category()
    
    def _get_default_category(self) -> ErrorCategory:
        """Return the default error category for this exception type."""
        return ErrorCategory.UNKNOWN
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the exception to a dictionary for serialization."""
        return self.context.to_dict()


# Planning-related exceptions
class PlanningError(AgentError):
    """Base exception for errors during the planning phase."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.PLANNING


class PrePlanningError(PlanningError):
    """Exception for errors during the pre-planning phase."""
    pass


class JSONPlanningError(PlanningError):
    """Exception for errors related to JSON planning."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.SCHEMA


class PlanValidationError(PlanningError):
    """Exception for plan validation failures."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.VALIDATION


# Generation-related exceptions
class GenerationError(AgentError):
    """Base exception for errors during code generation."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.GENERATION


class CodeValidationError(GenerationError):
    """Exception for code validation failures."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.VALIDATION


# System-related exceptions
class CoordinationError(AgentError):
    """Exception for errors in the coordination of tasks across components."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.COORDINATION


class AuthenticationError(AgentError):
    """Exception for authentication and authorization failures."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.AUTHENTICATION


class NetworkError(AgentError):
    """Exception for network-related errors."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.NETWORK


class DatabaseError(AgentError):
    """Exception for database-related errors."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.DATABASE


# Debugging-related exceptions
class DebuggingError(AgentError):
    """Exception for errors during debugging."""
    
    def _get_default_category(self) -> ErrorCategory:
        return ErrorCategory.DEBUGGING


# Utility functions for error handling
def categorize_exception(exc: Exception) -> ErrorCategory:
    """
    Categorize an exception into an ErrorCategory based on its type.
    
    Args:
        exc: The exception to categorize
        
    Returns:
        An ErrorCategory value
    """
    # Map Python's built-in exceptions to our categories
    exc_type = type(exc).__name__
    
    # Define mapping of exception types to categories
    category_mapping = {
        # Python built-in exceptions
        "SyntaxError": ErrorCategory.SYNTAX,
        "IndentationError": ErrorCategory.SYNTAX,
        "TabError": ErrorCategory.SYNTAX,
        "TypeError": ErrorCategory.TYPE,
        "ImportError": ErrorCategory.IMPORT,
        "ModuleNotFoundError": ErrorCategory.IMPORT,
        "AttributeError": ErrorCategory.ATTRIBUTE,
        "NameError": ErrorCategory.NAME,
        "UnboundLocalError": ErrorCategory.NAME,
        "IndexError": ErrorCategory.INDEX,
        "KeyError": ErrorCategory.INDEX,
        "ValueError": ErrorCategory.VALUE,
        "AssertionError": ErrorCategory.ASSERTION,
        "RuntimeError": ErrorCategory.RUNTIME,
        "RecursionError": ErrorCategory.RUNTIME,
        "MemoryError": ErrorCategory.MEMORY,
        "PermissionError": ErrorCategory.PERMISSION,
        "OSError": ErrorCategory.PERMISSION,
        "ConnectionError": ErrorCategory.NETWORK,
        "TimeoutError": ErrorCategory.NETWORK,
        
        # Agent-S3 custom exceptions
        "PlanningError": ErrorCategory.PLANNING,
        "PrePlanningError": ErrorCategory.PLANNING,
        "JSONPlanningError": ErrorCategory.SCHEMA,
        "PlanValidationError": ErrorCategory.VALIDATION,
        "GenerationError": ErrorCategory.GENERATION,
        "CodeValidationError": ErrorCategory.VALIDATION,
        "CoordinationError": ErrorCategory.COORDINATION,
        "AuthenticationError": ErrorCategory.AUTHENTICATION,
        "DebuggingError": ErrorCategory.DEBUGGING,
    }
    
    return category_mapping.get(exc_type, ErrorCategory.UNKNOWN)


def create_error_context(
    exc: Exception,
    component: Optional[str] = None,
    phase: Optional[str] = None,
    operation: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    inputs: Optional[Dict[str, Any]] = None
) -> ErrorContext:
    """
    Create an ErrorContext object from an exception.
    
    Args:
        exc: The exception to create context from
        component: The component where the error occurred
        phase: The phase of processing where the error occurred
        operation: The specific operation that was being performed
        variables: Dictionary of variables relevant to the error
        inputs: Dictionary of input values relevant to the error
        
    Returns:
        An ErrorContext object with details about the error
    """
    # Get traceback information
    tb = traceback.extract_tb(traceback.exc_info()[2])
    frame = tb[-1] if tb else None
    
    # Create error context
    return ErrorContext(
        error_type=type(exc).__name__,
        error_message=str(exc),
        category=categorize_exception(exc),
        file_path=frame.filename if frame else None,
        line_number=frame.lineno if frame else None,
        function_name=frame.name if frame else None,
        stacktrace=traceback.format_exc(),
        component=component,
        phase=phase,
        operation=operation,
        variables=variables or {},
        inputs=inputs or {}
    )


def extract_syntax_error_info(error_message: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Extract file path, line number, and error description from a syntax error message.
    
    Args:
        error_message: The full error message
        
    Returns:
        Tuple of (file_path, line_number, error_description)
    """
    # Patterns to match different syntax error formats
    patterns = [
        # Standard Python syntax error: "file.py", line 10, ...
        r'"([^"]+)",\s+line\s+(\d+).*:\s*(.*)',
        # Alternative format: File "file.py", line 10, ...
        r'File\s+"([^"]+)",\s+line\s+(\d+).*:\s*(.*)',
        # Just line number: line 10, ...
        r'line\s+(\d+).*:\s*(.*)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_message)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return groups[0], int(groups[1]), groups[2]
            elif len(groups) == 2:
                return None, int(groups[0]), groups[1]
    
    return None, None, error_message


def log_exception(
    exc: Exception,
    logger: logging.Logger,
    component: Optional[str] = None,
    phase: Optional[str] = None,
    operation: Optional[str] = None,
    level: int = logging.ERROR,
    reraise: bool = False
) -> ErrorContext:
    """
    Log an exception with consistent formatting and create an ErrorContext.
    
    Args:
        exc: The exception to log
        logger: The logger to use
        component: The component where the error occurred
        phase: The phase of processing where the error occurred
        operation: The specific operation that was being performed
        level: The logging level to use
        reraise: Whether to re-raise the exception after logging
        
    Returns:
        An ErrorContext object with details about the error
        
    Raises:
        The original exception if reraise is True
    """
    # Create error context
    error_context = create_error_context(
        exc=exc,
        component=component,
        phase=phase,
        operation=operation
    )
    
    # Format log message
    log_message = f"{error_context.category.value.upper()}: {error_context.error_message}"
    if component:
        log_message = f"[{component}] {log_message}"
    if phase:
        log_message = f"[{phase}] {log_message}"
    if operation:
        log_message = f"[{operation}] {log_message}"
    
    # Log the error
    logger.log(level, log_message, exc_info=True)
    
    # Re-raise if requested
    if reraise:
        raise
        
    return error_context


# Error pattern matching utilities
@dataclass
class ErrorPattern:
    """Definition of a pattern to match specific error types."""
    
    category: ErrorCategory
    pattern: Pattern[str]
    description: str
    

# Common error patterns to detect
ERROR_PATTERNS = [
    # Syntax errors
    ErrorPattern(
        category=ErrorCategory.SYNTAX,
        pattern=re.compile(r'SyntaxError: (.*)', re.IGNORECASE),
        description="Python syntax error"
    ),
    ErrorPattern(
        category=ErrorCategory.SYNTAX,
        pattern=re.compile(r'IndentationError: (.*)', re.IGNORECASE),
        description="Python indentation error"
    ),
    
    # Type errors
    ErrorPattern(
        category=ErrorCategory.TYPE,
        pattern=re.compile(r'TypeError: (.*)', re.IGNORECASE),
        description="Python type error"
    ),
    ErrorPattern(
        category=ErrorCategory.TYPE,
        pattern=re.compile(r'incompatible type[s]?', re.IGNORECASE),
        description="Type compatibility error"
    ),
    
    # Import errors
    ErrorPattern(
        category=ErrorCategory.IMPORT,
        pattern=re.compile(r'ImportError: (.*)', re.IGNORECASE),
        description="Python import error"
    ),
    ErrorPattern(
        category=ErrorCategory.IMPORT,
        pattern=re.compile(r'ModuleNotFoundError: (.*)', re.IGNORECASE),
        description="Module not found"
    ),
    
    # Name/attribute errors
    ErrorPattern(
        category=ErrorCategory.NAME,
        pattern=re.compile(r'NameError: (.*)', re.IGNORECASE),
        description="Undefined name"
    ),
    ErrorPattern(
        category=ErrorCategory.ATTRIBUTE,
        pattern=re.compile(r'AttributeError: (.*)', re.IGNORECASE),
        description="Attribute error"
    ),
    
    # Schema and validation errors
    ErrorPattern(
        category=ErrorCategory.SCHEMA,
        pattern=re.compile(r'(JSON|Schema) (error|invalid)', re.IGNORECASE),
        description="Schema validation error"
    ),
    
    # Network errors
    ErrorPattern(
        category=ErrorCategory.NETWORK,
        pattern=re.compile(r'ConnectionError: (.*)', re.IGNORECASE),
        description="Network connection error"
    ),
    ErrorPattern(
        category=ErrorCategory.NETWORK,
        pattern=re.compile(r'Timeout(Error)?: (.*)', re.IGNORECASE),
        description="Network timeout"
    ),
]


def categorize_error_message(error_message: str) -> Tuple[ErrorCategory, str]:
    """
    Categorize an error message into an ErrorCategory based on its content.
    
    Args:
        error_message: The error message to categorize
        
    Returns:
        Tuple of (ErrorCategory, description)
    """
    for pattern in ERROR_PATTERNS:
        if pattern.pattern.search(error_message):
            return pattern.category, pattern.description
    
    return ErrorCategory.UNKNOWN, "Unknown error"
