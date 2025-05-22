"""
Comprehensive Debugging System with Chain of Thought Integration.

This module implements a three-tier debugging strategy with CoT-based context
management for effective error resolution.
"""

import os
import re
import json
import time
import logging
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple

from agent_s3.enhanced_scratchpad_manager import (
    EnhancedScratchpadManager,
    Section,
    LogLevel,
)
from agent_s3.planning_helper import generate_plan_via_workflow
from agent_s3.user_config import load_user_config
from agent_s3.tools.error_pattern_learner import ErrorPatternLearner
from agent_s3.llm_utils import cached_call_llm


class ErrorCategory(Enum):
    """Categories of errors for specialized handling."""
    SYNTAX = auto()
    TYPE = auto()
    IMPORT = auto()
    ATTRIBUTE = auto()
    NAME = auto()
    INDEX = auto()
    VALUE = auto()
    RUNTIME = auto()
    MEMORY = auto()
    PERMISSION = auto()
    ASSERTION = auto()
    NETWORK = auto()
    DATABASE = auto()
    UNKNOWN = auto()


class DebuggingPhase(Enum):
    """Phases of debugging process."""
    ANALYSIS = auto()
    QUICK_FIX = auto()
    FULL_DEBUG = auto()
    STRATEGIC_RESTART = auto()


class RestartStrategy(Enum):
    """Strategies for strategic restart."""
    REGENERATE_CODE = auto()
    REDESIGN_PLAN = auto()
    MODIFY_REQUEST = auto()


@dataclass
class ErrorContext:
    """Context information about an error for debugging."""
    message: str
    traceback: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    code_snippet: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: datetime.now().isoformat())
    attempt_number: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = asdict(self)
        result["category"] = self.category.name
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorContext':
        """Create from dictionary representation."""
        category_name = data.get("category", "UNKNOWN")
        try:
            category = ErrorCategory[category_name]
        except (KeyError, TypeError):
            category = ErrorCategory.UNKNOWN
            
        return cls(
            message=data.get("message", ""),
            traceback=data.get("traceback", ""),
            category=category,
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            function_name=data.get("function_name"),
            code_snippet=data.get("code_snippet"),
            variables=data.get("variables", {}),
            occurred_at=data.get("occurred_at", datetime.now().isoformat()),
            attempt_number=data.get("attempt_number", 1),
            metadata=data.get("metadata", {})
        )
    
    def get_summary(self) -> str:
        """Get a concise summary of the error."""
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f" at line {self.line_number}"
                
        return f"{self.category.name} error{location}: {self.message}"


@dataclass
class DebugAttempt:
    """Record of a debugging attempt."""
    error_context: ErrorContext
    phase: DebuggingPhase
    fix_description: str
    code_changes: Dict[str, str]  # file path -> content
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = asdict(self)
        result["error_context"] = self.error_context.to_dict()
        result["phase"] = self.phase.name
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DebugAttempt':
        """Create from dictionary representation."""
        error_data = data.get("error_context", {})
        error_context = ErrorContext.from_dict(error_data)
        
        phase_name = data.get("phase", "ANALYSIS")
        try:
            phase = DebuggingPhase[phase_name]
        except (KeyError, TypeError):
            phase = DebuggingPhase.ANALYSIS
            
        return cls(
            error_context=error_context,
            phase=phase,
            fix_description=data.get("fix_description", ""),
            code_changes=data.get("code_changes", {}),
            success=data.get("success", False),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            duration_seconds=data.get("duration_seconds", 0.0),
            reasoning=data.get("reasoning", ""),
            metadata=data.get("metadata", {})
        )


class DebuggingManager:
    """
    Manages the comprehensive debugging process with three-tier strategy 
    and Chain of Thought integration.
    """
    
    # Constants for debugging configuration
    MAX_GENERATOR_ATTEMPTS = 2  # Tier 1: Quick fixes
    MAX_DEBUGGER_ATTEMPTS = 3   # Tier 2: Full debugging
    MAX_RESTART_ATTEMPTS = 2    # Tier 3: Strategic restart
    
    def __init__(self, coordinator, enhanced_scratchpad: EnhancedScratchpadManager):
        """
        Initialize the debugging manager.
        
        Args:
            coordinator: The coordinator instance
            enhanced_scratchpad: Enhanced scratchpad manager for CoT logging
        """
        self.coordinator = coordinator
        self.scratchpad = enhanced_scratchpad
        
        # Access to tools via coordinator
        self.llm = coordinator.llm if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        self.code_generator = coordinator.code_generator if coordinator else None
        self.error_context_manager = coordinator.error_context_manager if coordinator else None

        # Set up the logger
        self.logger = logging.getLogger("debugging_manager")

        # Initialize debugging state
        self.current_error: Optional[ErrorContext] = None
        self.current_phase = DebuggingPhase.ANALYSIS
        self.attempt_count = 0
        self.generator_attempts = 0
        self.debugger_attempts = 0
        self.restart_attempts = 0

        # Track diagnostics for generation issues
        self.generation_issue_log: Dict[str, List[Dict[str, Any]]] = {}
        
        # Track debugging history
        self.debug_history: List[DebugAttempt] = []

        # Pattern databases for error categorization
        self._initialize_error_patterns()

        # ML-based error pattern learner for cross-project sharing
        self.pattern_learner = ErrorPatternLearner()

        # Per-user customization of debugging limits
        user_cfg = load_user_config()
        self.MAX_GENERATOR_ATTEMPTS = int(
            user_cfg.get("max_quick_fix_attempts", self.MAX_GENERATOR_ATTEMPTS)
        )
        self.MAX_DEBUGGER_ATTEMPTS = int(
            user_cfg.get("max_full_debug_attempts", self.MAX_DEBUGGER_ATTEMPTS)
        )
        self.MAX_RESTART_ATTEMPTS = int(
            user_cfg.get("max_restart_attempts", self.MAX_RESTART_ATTEMPTS)
        )
        
    def _initialize_error_patterns(self):
        """Initialize pattern databases for error categorization."""
        self.error_patterns = {
            ErrorCategory.SYNTAX: [
                r"SyntaxError",
                r"IndentationError",
                r"unexpected token",
                r"invalid syntax",
                r"unexpected indent",
                r"expected an indented block"
            ],
            ErrorCategory.TYPE: [
                r"TypeError",
                r"unsupported operand type",
                r"not subscriptable",
                r"has no attribute",
                r"not a function",
                r"expected .* to be a",
                r"can't convert .* to"
            ],
            ErrorCategory.IMPORT: [
                r"ImportError",
                r"ModuleNotFoundError",
                r"No module named",
                r"cannot import name",
                r"cannot find module"
            ],
            ErrorCategory.ATTRIBUTE: [
                r"AttributeError",
                r"has no attribute",
                r"object has no attribute"
            ],
            ErrorCategory.NAME: [
                r"NameError",
                r"name .* is not defined",
                r"undefined variable",
                r"ReferenceError"
            ],
            ErrorCategory.INDEX: [
                r"IndexError",
                r"out of range",
                r"list index out of range",
                r"array index out of bounds"
            ],
            ErrorCategory.VALUE: [
                r"ValueError",
                r"invalid literal",
                r"could not convert",
                r"invalid value",
                r"value .* is not a valid"
            ],
            ErrorCategory.RUNTIME: [
                r"RuntimeError",
                r"RecursionError",
                r"maximum recursion depth exceeded",
                r"stack overflow"
            ],
            ErrorCategory.MEMORY: [
                r"MemoryError",
                r"out of memory",
                r"memory allocation failed",
                r"cannot allocate"
            ],
            ErrorCategory.PERMISSION: [
                r"PermissionError",
                r"Permission denied",
                r"Access is denied",
                r"not permitted"
            ],
            ErrorCategory.ASSERTION: [
                r"AssertionError",
                r"Assertion failed",
                r"Expected .* but got"
            ],
            ErrorCategory.NETWORK: [
                r"ConnectionError",
                r"ConnectionRefusedError",
                r"ConnectionResetError",
                r"TimeoutError",
                r"Connection refused",
                r"Network is unreachable",
                r"Connection timed out"
            ],
            ErrorCategory.DATABASE: [
                r"DatabaseError",
                r"OperationalError",
                r"IntegrityError",
                r"database is locked",
                r"constraint failed",
                r"syntax error in SQL",
                r"no such table"
            ]
        }
        
    def handle_error(self, 
                    error_message: str, 
                    traceback_text: str, 
                    file_path: Optional[str] = None,
                    line_number: Optional[int] = None,
                    function_name: Optional[str] = None,
                    code_snippet: Optional[str] = None,
                    variables: Optional[Dict[str, Any]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle an error based on the three-tier debugging strategy.
        
        Args:
            error_message: The error message
            traceback_text: The error traceback
            file_path: Optional file path where the error occurred
            line_number: Optional line number where the error occurred
            function_name: Optional function name where the error occurred
            code_snippet: Optional code snippet around the error
            variables: Optional dictionary of variable values at error time
            metadata: Optional additional metadata
            
        Returns:
            Results of debugging attempt
        """
        # Process test-specific structured information if this is a test failure
        test_failure_info = self._process_test_failure_data(metadata)
        
        # Create error context with test-specific information if available
        error_context = self._create_error_context(
            error_message, 
            traceback_text, 
            file_path or test_failure_info.get("test_file"),
            line_number or test_failure_info.get("line_number"),
            function_name, 
            code_snippet,
            variables or test_failure_info.get("variables", {}),
            {**metadata, **test_failure_info} if test_failure_info else metadata
        )
        
        # Check if this might be a test issue rather than an implementation issue
        if test_failure_info and test_failure_info.get("possible_bad_test", False):
            self.scratchpad.start_section(Section.WARNING, "DebuggingManager")
            self.scratchpad.log(
                role="DebuggingManager",
                message="Warning: This test failure might indicate an issue with the test itself rather than the implementation.",
                level=LogLevel.WARNING,
                section=Section.WARNING,
                metadata={"failure_category": test_failure_info.get("failure_category", "UNKNOWN")}
            )
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Test: {test_failure_info.get('test_name', 'Unknown')}, File: {test_failure_info.get('test_file', 'Unknown')}",
                level=LogLevel.WARNING,
                section=Section.WARNING
            )
            
            # Add specific reasons why the test might be problematic
            if test_failure_info.get("failure_category") == "ATTRIBUTE_ERROR":
                self.scratchpad.log(
                    role="DebuggingManager",
                    message="The test appears to be looking for an attribute that doesn't exist, possibly with an unconventional name.",
                    level=LogLevel.WARNING,
                    section=Section.WARNING
                )
            elif test_failure_info.get("expected") and test_failure_info.get("actual"):
                expected = test_failure_info.get("expected", "")
                actual = test_failure_info.get("actual", "")
                if expected and actual and (
                    actual.strip().replace(" ", "") == expected.strip().replace(" ", "") or
                    actual.strip().lower() == expected.strip().lower()
                ):
                    self.scratchpad.log(
                        role="DebuggingManager",
                        message="The expected and actual values differ only in formatting or capitalization.",
                        level=LogLevel.WARNING,
                        section=Section.WARNING
                    )
            
            self.scratchpad.end_section(Section.WARNING)
            
            # Add flag to error context
            error_context.metadata["possible_test_issue"] = True
        
        # Log error in enhanced scratchpad
        self.scratchpad.start_section(Section.ERROR, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Handling error: {error_context.get_summary()}",
            level=LogLevel.ERROR,
            section=Section.ERROR,
            metadata=error_context.to_dict()
        )
        
        # Log detailed test failure information if available
        if test_failure_info:
            failure_category = test_failure_info.get("failure_category", "UNKNOWN")
            test_name = test_failure_info.get("test_name", "Unknown")
            test_file = test_failure_info.get("test_file", "Unknown")
            
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Test Failure Details: {failure_category} in test {test_name} ({test_file})",
                level=LogLevel.ERROR,
                section=Section.ERROR
            )
            
            if "expected" in test_failure_info and "actual" in test_failure_info:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Expected: {test_failure_info['expected']}, Actual: {test_failure_info['actual']}",
                    level=LogLevel.ERROR,
                    section=Section.ERROR
                )
        
        # Determine if this is a continuation of an existing error
        if self.current_error and self._is_similar_error(error_context, self.current_error):
            # Update attempt count for this error
            error_context.attempt_number = self.current_error.attempt_number + 1
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Continuing with error (attempt {error_context.attempt_number})",
                level=LogLevel.INFO,
                section=Section.ERROR
            )
        else:
            # Reset counters for new error
            self.generator_attempts = 0
            self.debugger_attempts = 0
            self.restart_attempts = 0
            self.scratchpad.log(
                role="DebuggingManager",
                message="New error detected, starting tier 1 (generator quick fix)",
                level=LogLevel.INFO,
                section=Section.ERROR
            )
            
        # Update current error
        self.current_error = error_context
        self.attempt_count += 1
        
        # For test failures that might be test issues, consider different debugging strategy
        if test_failure_info and test_failure_info.get("possible_bad_test", False):
            # For potential test issues, prefer full debugging over quick fixes
            if self.debugger_attempts < self.MAX_DEBUGGER_ATTEMPTS:
                self.current_phase = DebuggingPhase.FULL_DEBUG
                self.debugger_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Potential test issue detected. Using tier 2 (full debug) - attempt {self.debugger_attempts}/{self.MAX_DEBUGGER_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = self._execute_full_debugging(error_context)
            else:
                # For persistent test issues, use strategic restart
                self.current_phase = DebuggingPhase.STRATEGIC_RESTART
                self.restart_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Potential test issue not resolved. Using tier 3 (strategic restart) - attempt {self.restart_attempts}/{self.MAX_RESTART_ATTEMPTS}",
                    level=LogLevel.WARNING,
                    section=Section.ERROR
                )
                result = self._execute_strategic_restart(error_context)
        else:
            # Standard debugging flow for normal errors
            if self.generator_attempts < self.MAX_GENERATOR_ATTEMPTS:
                # Tier 1: Generator quick fix
                self.current_phase = DebuggingPhase.QUICK_FIX
                self.generator_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 1 (quick fix) - attempt {self.generator_attempts}/{self.MAX_GENERATOR_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = self._execute_generator_quick_fix(error_context)
                
            elif self.debugger_attempts < self.MAX_DEBUGGER_ATTEMPTS:
                # Tier 2: Full debugging with CoT
                self.current_phase = DebuggingPhase.FULL_DEBUG
                self.debugger_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 2 (full debug) - attempt {self.debugger_attempts}/{self.MAX_DEBUGGER_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = self._execute_full_debugging(error_context)
                
            else:
                # Tier 3: Strategic restart
                self.current_phase = DebuggingPhase.STRATEGIC_RESTART
                self.restart_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 3 (strategic restart) - attempt {self.restart_attempts}/{self.MAX_RESTART_ATTEMPTS}",
                    level=LogLevel.WARNING,
                    section=Section.ERROR
                )
                result = self._execute_strategic_restart(error_context)
            
        # Record debug attempt
        debug_attempt = DebugAttempt(
            error_context=error_context,
            phase=self.current_phase,
            fix_description=result.get("description", ""),
            code_changes=result.get("changes", {}),
            success=result.get("success", False),
            reasoning=result.get("reasoning", ""),
            metadata=result.get("metadata", {})
        )
        self.debug_history.append(debug_attempt)
        
        # If successful, reset counters
        if result.get("success", False):
            self.current_error = None
            self.generator_attempts = 0
            self.debugger_attempts = 0
            self.restart_attempts = 0
            
        # End error section
        self.scratchpad.end_section(Section.ERROR)
        
        return result
        
    def _process_test_failure_data(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract and process test failure information from metadata.
        
        Args:
            metadata: Optional metadata that may contain test failure information
            
        Returns:
            Dictionary with processed test failure data, or empty dict if not a test failure
        """
        if not metadata:
            return {}
            
        # Check if this is a test failure
        if "failed_step" in metadata and metadata["failed_step"] == "tests":
            # The metadata might already contain structured failure info
            if "failure_info" in metadata:
                # Return the first (primary) failure if it's a list
                if isinstance(metadata["failure_info"], list) and metadata["failure_info"]:
                    return metadata["failure_info"][0]
                # Return as is if it's already a dictionary
                elif isinstance(metadata["failure_info"], dict):
                    return metadata["failure_info"]
                    
        # Additional test-failure specific fields to extract
        test_failure_fields = {
            "test_name", "test_file", "test_class", "line_number", 
            "expected", "actual", "assertion", "traceback",
            "failure_category", "possible_bad_test", "variables"
        }
        
        # Extract any test failure fields directly from metadata
        extracted_data = {}
        for field_name in test_failure_fields:
            if field_name in metadata:
                extracted_data[field_name] = metadata[field_name]
                
        return extracted_data
    
    def _create_error_context(self,
                             error_message: str, 
                             traceback_text: str, 
                             file_path: Optional[str] = None,
                             line_number: Optional[int] = None,
                             function_name: Optional[str] = None,
                             code_snippet: Optional[str] = None,
                             variables: Optional[Dict[str, Any]] = None,
                             metadata: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """Create error context with category detection."""
        # Categorize the error
        category = self._categorize_error(error_message, traceback_text)
        
        # Enhance with context from error_context_manager if available
        if not code_snippet and self.error_context_manager and file_path and line_number:
            try:
                context = self.error_context_manager.get_context_for_error(
                    file_path, line_number, error_message
                )
                if context:
                    code_snippet = context.get("code_snippet")
                    if not variables:
                        variables = context.get("variables", {})
            except Exception as e:
                self.logger.warning(f"Error getting additional context: {e}")
        
        # Create the error context
        context = ErrorContext(
            message=error_message,
            traceback=traceback_text,
            category=category,
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            code_snippet=code_snippet,
            variables=variables or {},
            metadata=metadata or {}
        )

        # Update ML learner with the categorized error
        try:
            self.pattern_learner.update(error_message, context.category.name)
        except Exception:
            pass

        return context
    
    def _categorize_error(self, error_message: str, traceback_text: str) -> ErrorCategory:
        """Categorize the error based on patterns."""
        combined_text = f"{error_message}\n{traceback_text}".lower()
        
        # Check each category's patterns
        for category, patterns in self.error_patterns.items():
            for pattern in patterns:
                if re.search(pattern.lower(), combined_text):
                    return category

        # Fallback to ML-based prediction
        prediction = self.pattern_learner.predict(error_message)
        if prediction and prediction in ErrorCategory.__members__:
            return ErrorCategory[prediction]

        # No match found
        return ErrorCategory.UNKNOWN
    
    def _is_similar_error(self, error1: ErrorContext, error2: ErrorContext) -> bool:
        """Determine if two errors are similar enough to be considered the same issue."""
        # If categories differ, not similar
        if error1.category != error2.category:
            return False
            
        # If file paths differ, not similar
        if error1.file_path != error2.file_path:
            return False
            
        # For line numbers, allow some proximity
        if error1.line_number is not None and error2.line_number is not None:
            line_diff = abs(error1.line_number - error2.line_number)
            if line_diff > 5:  # Allow 5 lines of difference
                return False
                
        # Compare error messages for similarity
        similarity = self._text_similarity(error1.message, error2.message)
        return similarity > 0.7  # 70% similarity threshold
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        if not text1 or not text2:
            return 0.0
            
        # Use SequenceMatcher for string similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _execute_generator_quick_fix(self, error_context: ErrorContext) -> Dict[str, Any]:
        """
        Execute a quick fix using the code generator.
        
        Tier 1: Minimal context, focused on simple issues like syntax errors.
        
        Args:
            error_context: The error context to debug
            
        Returns:
            Results of the debugging attempt
        """
        start_time = time.time()
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing generator quick fix",
            level=LogLevel.INFO,
            section=Section.DEBUGGING
        )
        
        # Check if we have a file to fix
        if not error_context.file_path or not os.path.exists(error_context.file_path):
            return {
                "success": False,
                "description": "Cannot execute quick fix: missing or invalid file path",
                "reasoning": "Generator quick fix requires a valid file path to modify."
            }
            
        # Read the file content
        try:
            file_content = self.file_tool.read_file(error_context.file_path)
            if not file_content:
                return {
                    "success": False,
                    "description": "Cannot execute quick fix: unable to read file",
                    "reasoning": "Failed to read file contents for quick fix."
                }
        except Exception as e:
            return {
                "success": False,
                "description": f"Cannot execute quick fix: error reading file: {e}",
                "reasoning": "Failed to read file contents for quick fix."
            }
            
        # Prepare the quick fix prompt
        prompt = self._create_quick_fix_prompt(error_context, file_content)
        
        # Start reasoning section in scratchpad
        self.scratchpad.start_section(Section.REASONING, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message="Generator Quick Fix Reasoning",
            level=LogLevel.INFO,
            section=Section.REASONING
        )
        
        # Call LLM for quick fix
        try:
            result = cached_call_llm(prompt, self.llm, **self.coordinator.config.config)
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Generator quick fix failed: {error_msg}",
                    level=LogLevel.ERROR,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": f"Quick fix failed: {error_msg}",
                    "reasoning": "LLM call failed during quick fix attempt."
                }
                
            response = result.get('response', '')
            
            # Log reasoning
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Generator reasoning:\n{response}",
                level=LogLevel.INFO,
                section=Section.REASONING
            )
            
            # Extract the fixed code
            fixed_code = self._extract_code_from_response(response)
            if not fixed_code:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message="Could not extract fixed code from response",
                    level=LogLevel.WARNING,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": "Quick fix failed: could not extract fixed code",
                    "reasoning": response
                }
                
            # Extract reasoning
            reasoning = self._extract_reasoning_from_response(response)
            
            # End reasoning section
            self.scratchpad.end_section(Section.REASONING)
            
            # Apply the fix
            try:
                self.file_tool.write_file(error_context.file_path, fixed_code)
                
                # Calculate duration
                duration = time.time() - start_time
                
                return {
                    "success": True,
                    "description": f"Applied quick fix to {os.path.basename(error_context.file_path)}",
                    "reasoning": reasoning,
                    "changes": {error_context.file_path: fixed_code},
                    "duration_seconds": duration,
                    "metadata": {
                        "tier": "generator_quick_fix",
                        "attempt": self.generator_attempts,
                        "modified_files": [error_context.file_path]
                    }
                }
            except Exception as e:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Error applying quick fix: {e}",
                    level=LogLevel.ERROR
                )
                return {
                    "success": False,
                    "description": f"Error applying quick fix: {e}",
                    "reasoning": reasoning,
                    "changes": {error_context.file_path: fixed_code}
                }
                
        except Exception as e:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Error during generator quick fix: {e}",
                level=LogLevel.ERROR,
                section=Section.REASONING
            )
            self.scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": f"Quick fix error: {e}",
                "reasoning": "Exception occurred during quick fix attempt."
            }
    
    def _execute_full_debugging(self, error_context: ErrorContext) -> Dict[str, Any]:
        """
        Execute full debugging with Chain of Thought context.
        
        Tier 2: Comprehensive analysis with historical context.
        
        Args:
            error_context: The error context to debug
            
        Returns:
            Results of the debugging attempt
        """
        start_time = time.time()
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing full debugging with CoT",
            level=LogLevel.INFO,
            section=Section.DEBUGGING
        )
        
        # Check if we have a file to fix
        if not error_context.file_path or not os.path.exists(error_context.file_path):
            return {
                "success": False,
                "description": "Cannot execute debugging: missing or invalid file path",
                "reasoning": "Full debugging requires a valid file path to modify."
            }
            
        # Read the file content
        try:
            file_content = self.file_tool.read_file(error_context.file_path)
            if not file_content:
                return {
                    "success": False,
                    "description": "Cannot execute debugging: unable to read file",
                    "reasoning": "Failed to read file contents for debugging."
                }
        except Exception as e:
            return {
                "success": False,
                "description": f"Cannot execute debugging: error reading file: {e}",
                "reasoning": "Failed to read file contents for debugging."
            }
            
        # Get related files based on imports or references
        related_files = self._get_related_files(error_context.file_path, file_content)
        
        # Extract Chain of Thought context relevant to this error
        cot_context = self.scratchpad.extract_cot_for_debugging(
            error_context.message + "\n" + error_context.traceback,
            max_entries=5
        )
        
        # Prepare the full debugging prompt with CoT context
        prompt = self._create_full_debugging_prompt(
            error_context, 
            file_content,
            related_files,
            cot_context
        )
        
        # Start reasoning section in scratchpad
        self.scratchpad.start_section(Section.REASONING, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message="Full Debugging Reasoning",
            level=LogLevel.INFO,
            section=Section.REASONING
        )
        
        # Call LLM for debugging
        try:
            result = cached_call_llm(prompt, self.llm, **self.coordinator.config.config)
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Full debugging failed: {error_msg}",
                    level=LogLevel.ERROR,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": f"Debugging failed: {error_msg}",
                    "reasoning": "LLM call failed during debugging attempt."
                }
                
            response = result.get('response', '')
            
            # Log reasoning
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Debugging reasoning:\n{response}",
                level=LogLevel.INFO,
                section=Section.REASONING
            )
            
            # Extract fixes for all files
            fixes = self._extract_multi_file_fixes(response)
            if not fixes:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message="Could not extract file fixes from response",
                    level=LogLevel.WARNING,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": "Debugging failed: could not extract fixes",
                    "reasoning": response
                }
                
            # Extract reasoning
            reasoning = self._extract_reasoning_from_response(response)
            
            # End reasoning section
            self.scratchpad.end_section(Section.REASONING)
            
            # Apply the fixes
            try:
                for file_path, content in fixes.items():
                    # Validate file path - must exist or be in expected directories
                    if not os.path.exists(file_path) and not self._is_safe_new_file(file_path):
                        self.scratchpad.log(
                            role="DebuggingManager",
                            message=f"Skipping invalid file path: {file_path}",
                            level=LogLevel.WARNING
                        )
                        continue
                    
                    self.file_tool.write_file(file_path, content)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Return success if we applied at least one fix
                if fixes:
                    return {
                        "success": True,
                        "description": f"Applied fixes to {len(fixes)} files",
                        "reasoning": reasoning,
                        "changes": fixes,
                        "duration_seconds": duration,
                        "metadata": {
                            "tier": "full_debugging",
                            "attempt": self.debugger_attempts,
                            "modified_files": list(fixes.keys())
                        }
                    }
                else:
                    return {
                        "success": False,
                        "description": "No valid fixes found to apply",
                        "reasoning": reasoning
                    }
            except Exception as e:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Error applying debugging fixes: {e}",
                    level=LogLevel.ERROR
                )
                return {
                    "success": False,
                    "description": f"Error applying debugging fixes: {e}",
                    "reasoning": reasoning,
                    "changes": fixes
                }
                
        except Exception as e:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Error during full debugging: {e}",
                level=LogLevel.ERROR,
                section=Section.REASONING
            )
            self.scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": f"Debugging error: {e}",
                "reasoning": "Exception occurred during debugging attempt."
            }
    
    def _execute_strategic_restart(self, error_context: ErrorContext) -> Dict[str, Any]:
        """
        Execute strategic restart when other debugging tiers fail.
        
        Tier 3: More extensive changes, preserving error context.
        
        Args:
            error_context: The error context to debug
            
        Returns:
            Results of the restart attempt
        """
        # For metrics collection in child methods
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing strategic restart",
            level=LogLevel.WARNING,
            section=Section.DEBUGGING
        )
        
        # Start decision reasoning section in scratchpad
        self.scratchpad.start_section(Section.DECISION, "DebuggingManager")
        
        # Determine restart strategy
        strategy, reasoning = self._determine_restart_strategy(error_context)
        
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Selected restart strategy: {strategy.name}\nReasoning: {reasoning}",
            level=LogLevel.INFO,
            section=Section.DECISION
        )
        
        self.scratchpad.end_section(Section.DECISION)
        
        # Execute the selected strategy
        if strategy == RestartStrategy.REGENERATE_CODE:
            return self._execute_code_regeneration(error_context)
        elif strategy == RestartStrategy.REDESIGN_PLAN:
            return self._execute_plan_redesign(error_context)
        else:  # MODIFY_REQUEST
            return self._execute_request_modification(error_context)
    
    def _determine_restart_strategy(self, error_context: ErrorContext) -> Tuple[RestartStrategy, str]:
        """Determine the most appropriate restart strategy for the error."""
        # Default strategy
        strategy = RestartStrategy.REGENERATE_CODE
        
        # Gather context for decision
        error_history = [attempt for attempt in self.debug_history 
                        if attempt.error_context.category == error_context.category]
        
        # If we have previous similar errors after regenerating code, escalate
        regenerate_attempts = [a for a in error_history 
                              if a.metadata.get("restart_strategy") == RestartStrategy.REGENERATE_CODE.name]
        
        if regenerate_attempts:
            strategy = RestartStrategy.REDESIGN_PLAN
            reasoning = "Previous code regeneration attempts failed to resolve similar errors."
        else:
            reasoning = "Initial restart strategy is to regenerate code while keeping the plan."
            
        # If we have previous similar errors after redesigning plan, escalate further
        redesign_attempts = [a for a in error_history 
                            if a.metadata.get("restart_strategy") == RestartStrategy.REDESIGN_PLAN.name]
        
        if redesign_attempts:
            strategy = RestartStrategy.MODIFY_REQUEST
            reasoning = "Both code regeneration and plan redesign failed to resolve similar errors."
            
        # Consider error category in decision
        if error_context.category in [ErrorCategory.SYNTAX, ErrorCategory.TYPE, 
                                     ErrorCategory.NAME, ErrorCategory.ATTRIBUTE]:
            # These are likely implementation issues, favor code regeneration
            if strategy == RestartStrategy.MODIFY_REQUEST:
                strategy = RestartStrategy.REDESIGN_PLAN
                reasoning += " However, the error type suggests an implementation issue rather than a fundamental request problem."
        elif error_context.category in [ErrorCategory.PERMISSION, ErrorCategory.NETWORK, 
                                      ErrorCategory.DATABASE, ErrorCategory.MEMORY]:
            # These may be environmental/system issues, consider modifying request
            if strategy == RestartStrategy.REGENERATE_CODE:
                strategy = RestartStrategy.REDESIGN_PLAN
                reasoning += " The error type suggests a potential architectural or environmental issue that may require plan changes."
            
        return strategy, reasoning
    
    def _execute_code_regeneration(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute code regeneration strategy."""
        # Track start time for duration calculation
        strategy_start_time = time.time()
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing code regeneration strategy",
            level=LogLevel.INFO,
            section=Section.DEBUGGING
        )
        
        # We need the current plan and task
        if not hasattr(self.coordinator, 'current_plan') or not self.coordinator.current_plan:
            return {
                "success": False,
                "description": "Cannot regenerate code: no current plan available",
                "reasoning": "Code regeneration requires access to the current plan."
            }
            
        try:
            # Use code generator to regenerate implementation
            # First, prepare error context for code generator
            error_summary = f"Error ({error_context.category.name}): {error_context.message}"
            
            # Add to plan context
            plan_with_error = self.coordinator.current_plan + f"\n\nPrevious implementation error:\n{error_summary}\n"
            if error_context.traceback:
                plan_with_error += f"Traceback:\n{error_context.traceback}\n"
                
            # Generate new code
            result = self.code_generator.generate_code(
                self.coordinator.current_task,
                plan_with_error,
                self.coordinator.tech_stack,
                max_token_count=None  # Use default token count
            )
            
            if not result or not result.get("success", False):
                return {
                    "success": False,
                    "description": "Code regeneration failed",
                    "reasoning": "Failed to generate new code implementation."
                }
                
            # Extract generated files
            generated_files = result.get("files", {})
            
            # Apply the generated files
            for file_path, content in generated_files.items():
                self.file_tool.write_file(file_path, content)
                
            # Calculate duration
            duration = time.time() - strategy_start_time
                
            return {
                "success": True,
                "description": f"Regenerated code for {len(generated_files)} files",
                "reasoning": "Complete code regeneration based on the existing plan.",
                "changes": generated_files,
                "duration_seconds": duration,
                "metadata": {
                    "tier": "strategic_restart",
                    "restart_strategy": RestartStrategy.REGENERATE_CODE.name,
                    "modified_files": list(generated_files.keys())
                }
            }
            
        except Exception as e:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Error during code regeneration: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Code regeneration error: {e}",
                "reasoning": "Exception occurred during code regeneration."
            }
    
    def _execute_plan_redesign(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute plan redesign strategy."""
        # Track start time for duration calculation
        strategy_start_time = time.time()
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing plan redesign strategy",
            level=LogLevel.WARNING,
            section=Section.DEBUGGING
        )
        
        # We need the original task
        if not hasattr(self.coordinator, 'current_task') or not self.coordinator.current_task:
            return {
                "success": False,
                "description": "Cannot redesign plan: no current task available",
                "reasoning": "Plan redesign requires access to the current task."
            }
            
        try:
            # Create a new plan with awareness of the error
            error_summary = f"Error ({error_context.category.name}): {error_context.message}"
            
            # Use the new sequential planning workflow with error context
            plan_result = generate_plan_via_workflow(
                self.coordinator, 
                self.coordinator.current_task,
                context={"error_context": error_summary}
            )
            
            if not plan_result or not plan_result.get("success", False):
                return {
                    "success": False,
                    "description": "Plan redesign failed",
                    "reasoning": "Failed to generate a new plan."
                }
                
            # Get the new plan
            new_plan = plan_result.get("plan", "")
            if not new_plan:
                return {
                    "success": False,
                    "description": "Plan redesign failed - empty plan",
                    "reasoning": "Generated plan was empty."
                }
                
            # Update coordinator's current plan
            self.coordinator.current_plan = new_plan
            
            # Generate code based on new plan
            code_result = self.code_generator.generate_code(
                self.coordinator.current_task,
                new_plan,
                self.coordinator.tech_stack,
                max_token_count=None  # Use default token count
            )
            
            if not code_result or not code_result.get("success", False):
                return {
                    "success": False,
                    "description": "Code generation after plan redesign failed",
                    "reasoning": "Failed to generate code based on new plan."
                }
                
            # Extract generated files
            generated_files = code_result.get("files", {})
            
            # Apply the generated files
            for file_path, content in generated_files.items():
                self.file_tool.write_file(file_path, content)
                
            # Calculate duration
            duration = time.time() - strategy_start_time
                
            return {
                "success": True,
                "description": f"Redesigned plan and generated {len(generated_files)} files",
                "reasoning": "Complete plan redesign and code regeneration.",
                "changes": generated_files,
                "duration_seconds": duration,
                "metadata": {
                    "tier": "strategic_restart",
                    "restart_strategy": RestartStrategy.REDESIGN_PLAN.name,
                    "modified_files": list(generated_files.keys()),
                    "new_plan": new_plan
                }
            }
            
        except Exception as e:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Error during plan redesign: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Plan redesign error: {e}",
                "reasoning": "Exception occurred during plan redesign."
            }
    
    def _execute_request_modification(self, error_context: ErrorContext) -> Dict[str, Any]:
        """Execute request modification strategy."""
        # Track start time for duration calculation
        strategy_start_time = time.time()
        
        self.scratchpad.log(
            role="DebuggingManager",
            message="Executing request modification strategy",
            level=LogLevel.WARNING,
            section=Section.DEBUGGING
        )
        
        # We need the original task
        if not hasattr(self.coordinator, 'current_task') or not self.coordinator.current_task:
            return {
                "success": False,
                "description": "Cannot modify request: no current task available",
                "reasoning": "Request modification requires access to the current task."
            }
            
        try:
            # Start reasoning section for request modification
            self.scratchpad.start_section(Section.REASONING, "DebuggingManager")
            
            # Prepare prompt for request modification
            error_summary = (
                f"Error Category: {error_context.category.name}\n"
                f"Error Message: {error_context.message}\n"
                f"File: {error_context.file_path}\n"
                f"Line: {error_context.line_number}\n"
            )
            
            if error_context.code_snippet:
                error_summary += f"\nCode Snippet:\n{error_context.code_snippet}\n"
                
            if error_context.traceback:
                error_summary += f"\nTraceback:\n{error_context.traceback}\n"
                
            # Add debug history context
            debug_context = "Debug Attempt History:\n"
            for i, attempt in enumerate(self.debug_history[-5:], 1):
                debug_context += f"{i}. {attempt.phase.name} - {attempt.fix_description}\n"
                if attempt.success:
                    debug_context += "   Result: SUCCESS\n"
                else:
                    debug_context += "   Result: FAILED\n"
            
            # Create the prompt
            prompt = f"""
            You are an expert AI assistant tasked with modifying a task request that has repeatedly failed to implement.
            
            Original Task Request:
            {self.coordinator.current_task}
            
            Error Information:
            {error_summary}
            
            {debug_context}
            
            Multiple debugging attempts and strategic restarts have failed to resolve this issue.
            
            Based on the error patterns and debugging history, create a modified version of the original task
            that avoids the problems encountered. Consider:
            
            1. Simplifying requirements that might be causing issues
            2. Suggesting alternative approaches or technologies
            3. Breaking down the task into smaller, more manageable pieces
            4. Addressing any environmental or system constraints revealed by the errors
            5. Clarifying any ambiguities in the original request
            
            Return a JSON object with the following structure:
            {{
                "modified_task": "The revised task request",
                "rationale": "Explanation of the changes made",
                "implementation_steps": ["Step 1", "Step 2", ...]
            }}
            """
            
            # Call LLM for request modification
            result = cached_call_llm(prompt, self.llm, **self.coordinator.config.config)
            
            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Request modification failed: {error_msg}",
                    level=LogLevel.ERROR,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": f"Request modification failed: {error_msg}",
                    "reasoning": "LLM call failed during request modification."
                }
                
            response = result.get('response', '')
            
            # Log reasoning
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Request modification reasoning:\n{response}",
                level=LogLevel.INFO,
                section=Section.REASONING
            )
            
            # Extract JSON from response
            modification_data = self._extract_json_from_response(response)
            if not modification_data:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message="Could not extract JSON from response",
                    level=LogLevel.WARNING,
                    section=Section.REASONING
                )
                self.scratchpad.end_section(Section.REASONING)
                return {
                    "success": False,
                    "description": "Request modification failed: could not extract JSON",
                    "reasoning": response
                }
                
            self.scratchpad.end_section(Section.REASONING)
            
            # Extract the modified task
            modified_task = modification_data.get("modified_task", "")
            rationale = modification_data.get("rationale", "")
            steps = modification_data.get("implementation_steps", [])
            
            if not modified_task:
                return {
                    "success": False,
                    "description": "Request modification failed: no modified task",
                    "reasoning": rationale
                }
                
            # Run the modified task through the full pipeline
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Starting execution of modified task:\n{modified_task}",
                level=LogLevel.INFO
            )
            
            # Store original values
            original_task = self.coordinator.current_task
            original_plan = getattr(self.coordinator, 'current_plan', None)
            
            # Update current task
            self.coordinator.current_task = modified_task
            
            try:
                # Generate a new plan using the sequential planning workflow
                plan_result = generate_plan_via_workflow(
                    self.coordinator, 
                    modified_task
                )
                
                if not plan_result or not plan_result.get("success", False):
                    # Restore original values
                    self.coordinator.current_task = original_task
                    if original_plan:
                        self.coordinator.current_plan = original_plan
                        
                    return {
                        "success": False,
                        "description": "Modified request planning failed",
                        "reasoning": f"Failed to generate a plan for the modified task. Rationale: {rationale}"
                    }
                    
                # Get the new plan
                new_plan = plan_result.get("plan", "")
                self.coordinator.current_plan = new_plan
                
                # Generate code based on new plan
                code_result = self.code_generator.generate_code(
                    modified_task,
                    new_plan,
                    self.coordinator.tech_stack,
                    max_token_count=None  # Use default token count
                )
                
                if not code_result or not code_result.get("success", False):
                    # Restore original values
                    self.coordinator.current_task = original_task
                    if original_plan:
                        self.coordinator.current_plan = original_plan
                        
                    return {
                        "success": False,
                        "description": "Code generation for modified request failed",
                        "reasoning": f"Failed to generate code for the modified task. Rationale: {rationale}"
                    }
                    
                # Extract generated files
                generated_files = code_result.get("files", {})
                
                # Apply the generated files
                for file_path, content in generated_files.items():
                    self.file_tool.write_file(file_path, content)
                    
                # Calculate duration
                duration = time.time() - strategy_start_time
                    
                return {
                    "success": True,
                    "description": f"Modified task request and generated {len(generated_files)} files",
                    "reasoning": rationale,
                    "changes": generated_files,
                    "duration_seconds": duration,
                    "metadata": {
                        "tier": "strategic_restart",
                        "restart_strategy": RestartStrategy.MODIFY_REQUEST.name,
                        "modified_files": list(generated_files.keys()),
                        "modified_task": modified_task,
                        "new_plan": new_plan,
                        "implementation_steps": steps
                    }
                }
                
            except Exception as e:
                # Restore original values
                self.coordinator.current_task = original_task
                if original_plan:
                    self.coordinator.current_plan = original_plan
                    
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Error executing modified task: {e}",
                    level=LogLevel.ERROR
                )
                return {
                    "success": False,
                    "description": f"Modified task execution error: {e}",
                    "reasoning": f"Exception occurred during modified task execution. Rationale: {rationale}"
                }
                
        except Exception as e:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Error during request modification: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Request modification error: {e}",
                "reasoning": "Exception occurred during request modification."
            }
    
    def _create_quick_fix_prompt(self, error_context: ErrorContext, file_content: str) -> str:
        """Create a prompt for generator quick fix."""
        error_message = error_context.message
        traceback = error_context.traceback
        file_path = error_context.file_path
        line_number = error_context.line_number or "unknown"
        
        # Tailor prompt based on error category
        category_specific_instructions = {
            ErrorCategory.SYNTAX: "Focus on fixing syntax errors like missing parentheses, brackets, or indentation issues.",
            ErrorCategory.TYPE: "Check for type mismatches, incorrect method calls, or inappropriate operations on the wrong data type.",
            ErrorCategory.IMPORT: "Verify import statements, module names, and package availability.",
            ErrorCategory.ATTRIBUTE: "Check for incorrect attribute or method names, or attributes used on the wrong type of object.",
            ErrorCategory.NAME: "Look for undefined variables, typos in variable names, or scope issues.",
            ErrorCategory.INDEX: "Check for array/list index errors, off-by-one errors, or accessing empty collections.",
            ErrorCategory.VALUE: "Verify input values, format specifiers, or conversion operations."
        }
        
        specific_instructions = category_specific_instructions.get(
            error_context.category, 
            "Analyze the error message and traceback to identify and fix the issue."
        )
        
        # Context snippet
        context_snippet = ""
        if error_context.code_snippet:
            context_snippet = f"\nRelevant code snippet:\n```\n{error_context.code_snippet}\n```\n"
            
        # Test failure specific information
        test_failure_info = ""
        if "possible_test_issue" in error_context.metadata:
            # This is a potential test issue
            test_failure_info += "\nNOTE: This error might be related to an issue in the test itself rather than the implementation code.\n"
            
            # Add details about the failing test
            if "test_name" in error_context.metadata:
                test_name = error_context.metadata.get("test_name", "Unknown")
                test_file = error_context.metadata.get("test_file", "Unknown")
                test_failure_info += f"Failing Test: {test_name} in {test_file}\n"
                
            # Add expected vs actual if available
            if "expected" in error_context.metadata and "actual" in error_context.metadata:
                expected = error_context.metadata.get("expected", "Unknown")
                actual = error_context.metadata.get("actual", "Unknown")
                test_failure_info += f"Expected: {expected}\nActual: {actual}\n"
                
            # Check for common test issues
            if "failure_category" in error_context.metadata:
                failure_category = error_context.metadata.get("failure_category", "UNKNOWN")
                if failure_category == "ATTRIBUTE_ERROR":
                    test_failure_info += "This might be a case where the test is expecting an attribute that doesn't exist or has a different name.\n"
                elif failure_category == "VALUE_MISMATCH":
                    test_failure_info += "This might be a formatting issue or a case where the test has overly specific expectations.\n"
                elif failure_category == "IMPORT_ERROR":
                    test_failure_info += "This might be a missing dependency or incorrectly specified import in the test.\n"
                    
        # Variables context if available
        variables_context = ""
        if error_context.variables:
            variables_context = "\nVariable values at error time:\n"
            for var_name, var_value in error_context.variables.items():
                variables_context += f"- {var_name}: {var_value}\n"
        
        # Create the prompt
        prompt = f"""
        You are an expert code debugger tasked with fixing a {error_context.category.name} error.
        
        File: {file_path}
        Error at line: {line_number}
        Error message: {error_message}
        
        Traceback:
        {traceback}
        {context_snippet}
        {variables_context}
        {test_failure_info}
        
        Instructions:
        {specific_instructions}
        
        Full file content:
        ```
        {file_content}
        ```
        
        Your task is to:
        1. Analyze the error and determine the cause
        2. Fix the issue with minimal changes
        3. Provide a brief explanation of what was wrong and how you fixed it
        
        Return your answer in the following format:
        
        ## Analysis
        <Your analysis of the error>
        
        ## Fix
        ```
        <Full corrected file content>
        ```
        
        ## Explanation
        <Brief explanation of the fix>
        """
        
        return prompt
    
    def _create_full_debugging_prompt(self, 
                                     error_context: ErrorContext, 
                                     file_content: str,
                                     related_files: Dict[str, str],
                                     cot_context: List[Dict[str, Any]]) -> str:
        """Create a prompt for full debugging with CoT context."""
        error_message = error_context.message
        traceback = error_context.traceback
        file_path = error_context.file_path
        line_number = error_context.line_number or "unknown"
        
        # Format variables if available
        variables_section = ""
        if error_context.variables:
            variables_section = "Variable values at error time:\n"
            for var_name, var_value in error_context.variables.items():
                variables_section += f"- {var_name}: {var_value}\n"
        
        # Format related files
        related_files_section = ""
        if related_files:
            related_files_section = "Related files:\n"
            for path, content in related_files.items():
                related_files_section += f"\n{path}:\n```\n{content[:1000]}"
                if len(content) > 1000:
                    related_files_section += f"\n... (truncated, {len(content) - 1000} more chars)"
                related_files_section += "\n```\n"
        
        # Format Chain of Thought context
        cot_section = ""
        if cot_context:
            cot_section = "Previous debugging insights:\n"
            for i, entry in enumerate(cot_context, 1):
                relevance = entry.get("relevance_score", 0.0)
                content = entry.get("content", "")
                cot_section += f"\nInsight {i} (relevance: {relevance:.2f}):\n{content}\n"
        
        # Add attempt information
        attempt_info = f"This is debugging attempt #{error_context.attempt_number} for this error."
        
        # Test failure specific information
        test_failure_section = ""
        if "failure_category" in error_context.metadata or "test_name" in error_context.metadata:
            failure_category = error_context.metadata.get("failure_category", "UNKNOWN")
            test_name = error_context.metadata.get("test_name", "Unknown")
            test_file = error_context.metadata.get("test_file", "Unknown")
            
            test_failure_section += "\n## Test Failure Details\n"
            test_failure_section += f"Failure Category: {failure_category}\n"
            test_failure_section += f"Test: {test_name} in {test_file}\n"
            
            if "assertion" in error_context.metadata:
                test_failure_section += f"Assertion: {error_context.metadata['assertion']}\n"
                
            if "expected" in error_context.metadata and "actual" in error_context.metadata:
                test_failure_section += f"Expected: {error_context.metadata['expected']}\n"
                test_failure_section += f"Actual: {error_context.metadata['actual']}\n"
                
            # Include original test code if available in failure_info
            if "failure_info" in error_context.metadata and isinstance(error_context.metadata["failure_info"], list):
                for failure in error_context.metadata["failure_info"]:
                    if failure.get("test_name") == test_name and "code" in failure:
                        test_failure_section += f"\nTest Code:\n```\n{failure['code']}\n```\n"
                        break
            
            # Include implementation plan for the file if available
            if "file_implementation_plan" in error_context.metadata:
                file_plan = error_context.metadata["file_implementation_plan"]
                test_failure_section += "\n## Implementation Plan for this File\n"
                test_failure_section += f"```json\n{json.dumps(file_plan, indent=2)}\n```\n"
                
            # Include architecture review if available for relevant context
            if "architecture_review" in error_context.metadata and isinstance(error_context.metadata["architecture_review"], dict):
                arch_review = error_context.metadata["architecture_review"]
                logical_gaps = arch_review.get("logical_gaps", [])
                optimizations = arch_review.get("optimization_suggestions", [])
                
                if logical_gaps or optimizations:
                    test_failure_section += "\n## Relevant Architecture Review Points\n"
                    
                    if logical_gaps:
                        test_failure_section += "Logical Gaps Identified:\n"
                        for gap in logical_gaps[:2]:  # Limit to avoid overloading
                            if isinstance(gap, dict):
                                test_failure_section += f"- {gap.get('description', 'Not specified')}\n"
                            else:
                                test_failure_section += f"- {gap}\n"
                    
                    if optimizations:
                        test_failure_section += "Optimization Suggestions:\n"
                        for opt in optimizations[:2]:  # Limit to avoid overloading
                            if isinstance(opt, dict):
                                test_failure_section += f"- {opt.get('description', 'Not specified')}\n"
                            else:
                                test_failure_section += f"- {opt}\n"
                
            # Special guidance for test issues
            if "possible_test_issue" in error_context.metadata and error_context.metadata["possible_test_issue"]:
                test_failure_section += "\n## Potential Test Issue Detected\n"
                test_failure_section += "This failure may indicate a problem with the test rather than the implementation.\n"
                
                if failure_category == "ATTRIBUTE_ERROR":
                    test_failure_section += "- The test might be looking for an attribute that doesn't exist or has a different name\n"
                    test_failure_section += "- Consider whether to adapt the implementation to match the test's expectations or fix the test\n"
                elif failure_category == "VALUE_MISMATCH":
                    test_failure_section += "- The test may have overly rigid expectations about formatting or specific values\n"
                    test_failure_section += "- Check if the actual and expected values are semantically equivalent despite textual differences\n"
                elif failure_category == "IMPORT_ERROR":
                    test_failure_section += "- There might be a missing dependency or incorrect import in the test\n"
                    test_failure_section += "- Verify that all required packages are available and imports have correct paths\n"
        
        # Create the prompt
        prompt = f"""
        You are an expert software debugger with deep knowledge of error patterns and fixes, specializing in test-driven development.
        
        ## Error Information
        - Category: {error_context.category.name}
        - File: {file_path}
        - Line: {line_number}
        - Error message: {error_message}
        - {attempt_info}
        
        ## Traceback
        {traceback}
        
        {variables_section}
        {test_failure_section}
        
        ## File Content
        ```
        {file_content}
        ```
        
        {related_files_section}
        
        {cot_section}
        
        ## Instructions
        1. Carefully analyze the error, focusing on the exact cause
        2. Use the Chain of Thought insights from previous debugging if relevant
        3. Consider all possible fixes, especially those that previous attempts may have missed
        4. Implement the most robust solution, not just a quick fix
        5. You may modify multiple files if necessary to resolve the issue
        6. Explain your reasoning process step by step
        7. If this is a test failure, remember that the human-approved tests are authoritative and your implementation should adapt to pass them

        ## Special Considerations for Test Failures
        - The human-reviewed and approved tests define the required behavior
        - In cases where the test expectations seem unusual, implement code that passes the tests exactly as written
        - Only suggest test modifications if there's a clear technical impossibility (e.g., requesting behavior the language can't support)
        - If you need to adapt code to unusual test expectations, add comments explaining the reason
        
        ## Response Format
        
        ### Step-by-Step Analysis
        <Detailed analysis of the error, considering previous debugging attempts>
        
        ### Root Cause
        <Precise identification of the root cause>
        
        ### Solution Strategy
        <Explanation of your approach to fixing the issue>
        
        ### File Fixes
        For each file that needs changes:
        
        ```filepath:{file_path}
        <Complete fixed file content>
        ```
        
        Add additional files as needed with the same format.
        
        ### Explanation
        <Concise explanation of the changes made and why they fix the issue>
        """
        
        return prompt
    
    def _get_related_files(self, file_path: str, content: str) -> Dict[str, str]:
        """
        Get related files based on imports or references in the content.
        
        Args:
            file_path: Path to the main file
            content: Content of the main file
            
        Returns:
            Dictionary mapping file paths to their content
        """
        related_files = {}
        
        try:
            # Extract imports
            import_pattern = r'(?:import|from)\s+([.\w]+)(?:\s+import|\s*$)'
            matches = re.findall(import_pattern, content)
            
            # Find potential local imports
            for match in matches:
                # Skip standard library imports
                if match in ["os", "sys", "re", "json", "time", "datetime", "logging", 
                           "math", "random", "collections", "itertools", "functools",
                           "pathlib", "typing", "enum", "abc", "io", "glob"]:
                    continue
                
                # Try to find matching Python file
                possible_paths = []
                
                # For relative imports, look relative to current file
                if match.startswith('.'):
                    base_dir = os.path.dirname(file_path)
                    rel_path = match.lstrip('.')
                    rel_path = rel_path.replace('.', os.path.sep)
                    possible_paths.append(os.path.join(base_dir, f"{rel_path}.py"))
                    possible_paths.append(os.path.join(base_dir, rel_path, "__init__.py"))
                else:
                    # For absolute imports, try various patterns
                    components = match.split('.')
                    module_name = components[0]
                    
                    # Check if it's a top-level module in the current project
                    project_root = self._get_project_root(file_path)
                    if project_root:
                        possible_paths.append(os.path.join(project_root, f"{module_name}.py"))
                        possible_paths.append(os.path.join(project_root, module_name, "__init__.py"))
                    
                # Check for references to other files
                file_ref_pattern = r'[\'\"]([.\w/\\-]+\.(py|js|ts|json|yaml|yml))[\'\"]'
                file_matches = re.findall(file_ref_pattern, content)
                
                for file_match, _ in file_matches:
                    base_dir = os.path.dirname(file_path)
                    possible_paths.append(os.path.join(base_dir, file_match))
                
                # Try to load each possible path
                for path in possible_paths:
                    if path not in related_files and os.path.exists(path):
                        try:
                            related_content = self.file_tool.read_file(path)
                            if related_content:
                                related_files[path] = related_content
                                break  # Found a matching file, stop trying other patterns
                        except Exception:
                            pass
            
        except Exception as e:
            self.logger.warning(f"Error getting related files: {e}")
            
        return related_files
    
    def _get_project_root(self, file_path: str) -> Optional[str]:
        """Try to determine the project root directory."""
        try:
            # Start from the directory containing the file
            current_dir = os.path.dirname(os.path.abspath(file_path))
            
            # Walk up the directory tree looking for common project markers
            max_levels = 5  # Limit the search depth
            for _ in range(max_levels):
                # Check for common project markers
                if (os.path.exists(os.path.join(current_dir, "setup.py")) or
                    os.path.exists(os.path.join(current_dir, "pyproject.toml")) or
                    os.path.exists(os.path.join(current_dir, "package.json")) or
                    os.path.exists(os.path.join(current_dir, ".git"))):
                    return current_dir
                
                # Move up one directory
                parent_dir = os.path.dirname(current_dir)
                if parent_dir == current_dir:  # Reached the root
                    break
                current_dir = parent_dir
                
            # If no markers found, default to directory containing the file
            return os.path.dirname(os.path.abspath(file_path))
        except Exception:
            # In case of any errors, fall back to current directory
            return os.getcwd()
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """Extract code from a response."""
        # Look for code blocks with triple backticks
        import re
        pattern = r'```(?:\w*\n|\n)?(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            # Return the largest code block
            return max(matches, key=len)
            
        # No code blocks found, try to extract a file content section
        pattern = r'## Fix\s*\n(.*?)(?:\n##|\Z)'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            # Clean up any remaining markdown
            code = matches[0].strip()
            code = re.sub(r'^```\w*\s*', '', code)
            code = re.sub(r'```\s*$', '', code)
            return code
            
        return None
    
    def _extract_reasoning_from_response(self, response: str) -> str:
        """Extract reasoning from a response."""
        # Look for analysis or explanation sections
        import re
        
        # Try to find Analysis section
        analysis_pattern = r'(?:##\s*Analysis|Step-by-Step Analysis)\s*\n(.*?)(?:\n##|\Z)'
        analysis_matches = re.findall(analysis_pattern, response, re.DOTALL)
        
        # Try to find Explanation section
        explanation_pattern = r'(?:##\s*Explanation)\s*\n(.*?)(?:\n##|\Z)'
        explanation_matches = re.findall(explanation_pattern, response, re.DOTALL)
        
        # Try to find Root Cause section
        cause_pattern = r'(?:##\s*Root Cause)\s*\n(.*?)(?:\n##|\Z)'
        cause_matches = re.findall(cause_pattern, response, re.DOTALL)
        
        # Combine all found sections
        reasoning_parts = []
        
        if analysis_matches:
            reasoning_parts.append(analysis_matches[0].strip())
            
        if cause_matches:
            reasoning_parts.append(f"Root Cause: {cause_matches[0].strip()}")
            
        if explanation_matches:
            reasoning_parts.append(explanation_matches[0].strip())
            
        if reasoning_parts:
            return "\n\n".join(reasoning_parts)
            
        # If no structured sections found, return truncated response
        return response[:500] + ("..." if len(response) > 500 else "")
    
    def _extract_multi_file_fixes(self, response: str) -> Dict[str, str]:
        """Extract multiple file fixes from a response."""
        fixes = {}
        
        # Look for file-specific code blocks with format ```filepath:/path/to/file
        import re
        pattern = r'```filepath:(.*?)\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            for file_path, content in matches:
                fixes[file_path.strip()] = content
                
        # If no structured file fixes found, try to extract a single code block
        if not fixes:
            code = self._extract_code_from_response(response)
            if code and hasattr(self, 'current_error') and self.current_error and self.current_error.file_path:
                fixes[self.current_error.file_path] = code
                
        return fixes
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from a response."""
        import json
        import re
        
        # Look for JSON block
        pattern = r'```(?:json)?\s*\n?(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
                    
        # No JSON block with backticks, try to find JSON objects
        try:
            # Try to find JSON-like structure
            pattern = r'({[\s\S]*})'
            matches = re.findall(pattern, response)
            
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
            
        return None
    
    def _is_safe_new_file(self, file_path: str) -> bool:
        """Check if a file path is in an expected location for new files."""
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)
        
        # Get project root
        project_root = self._get_project_root(self.current_error.file_path if self.current_error else os.getcwd())
        
        # Check if path is within project root
        if not abs_path.startswith(project_root):
            return False
            
        # Check path components for suspicious elements
        for part in abs_path.split(os.path.sep):
            # Skip empty parts
            if not part:
                continue
                
            # Check for hidden directories or files
            if part.startswith('.') and part not in ['.github', '.vscode', '.env']:
                return False
                
            # Check for sensitive directories
            if part.lower() in ['secret', 'secrets', 'password', 'credentials', 'private']:
                return False
                
        # It should be a Python, JavaScript, TypeScript, or config file
        valid_extensions = ['.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.md']
        if not any(file_path.endswith(ext) for ext in valid_extensions):
            return False
            
        return True
            
    def analyze_error(self, 
                 error_message: str, 
                 traceback_text: str, 
                 file_path: Optional[str] = None,
                 line_number: Optional[int] = None,
                 function_name: Optional[str] = None,
                 code_snippet: Optional[str] = None,
                 variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze an error without attempting to fix it.
        
        Args:
            error_message: The error message
            traceback_text: The error traceback
            file_path: Optional file path where the error occurred
            line_number: Optional line number where the error occurred
            function_name: Optional function name where the error occurred
            code_snippet: Optional code snippet around the error
            variables: Optional dictionary of variable values at error time
            
        Returns:
            Analysis results including category, severity, and potential fix approaches
        """
        # Create error context
        error_context = self._create_error_context(
            error_message, 
            traceback_text, 
            file_path,
            line_number,
            function_name, 
            code_snippet,
            variables
        )
        
        # Log analysis in enhanced scratchpad
        self.scratchpad.start_section(Section.ANALYSIS, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Analyzing error: {error_context.get_summary()}",
            level=LogLevel.INFO,
            section=Section.ANALYSIS,
            metadata=error_context.to_dict()
        )
        
        # Determine severity based on error category
        severity = "HIGH" if error_context.category in [
            ErrorCategory.MEMORY, ErrorCategory.PERMISSION, 
            ErrorCategory.NETWORK, ErrorCategory.DATABASE
        ] else "MEDIUM" if error_context.category in [
            ErrorCategory.RUNTIME, ErrorCategory.ASSERTION,
            ErrorCategory.TYPE, ErrorCategory.ATTRIBUTE
        ] else "LOW"
        
        # Determine likely fix approach based on category
        fix_approach = "CODE_FIX" if error_context.category in [
            ErrorCategory.SYNTAX, ErrorCategory.TYPE, 
            ErrorCategory.NAME, ErrorCategory.ATTRIBUTE,
            ErrorCategory.INDEX, ErrorCategory.VALUE
        ] else "ENVIRONMENT_FIX" if error_context.category in [
            ErrorCategory.IMPORT, ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK, ErrorCategory.DATABASE
        ] else "UNKNOWN"
        
        # Prepare recommended tier
        recommended_tier = "QUICK_FIX" if error_context.category in [
            ErrorCategory.SYNTAX, ErrorCategory.NAME
        ] else "FULL_DEBUG" if error_context.category in [
            ErrorCategory.TYPE, ErrorCategory.ATTRIBUTE,
            ErrorCategory.INDEX, ErrorCategory.VALUE,
            ErrorCategory.IMPORT
        ] else "STRATEGIC_RESTART"
        
        # Check for similar errors in history
        similar_errors = []
        for attempt in self.debug_history:
            if self._is_similar_error(error_context, attempt.error_context):
                similar_errors.append({
                    "phase": attempt.phase.name,
                    "fix_description": attempt.fix_description,
                    "success": attempt.success,
                    "timestamp": attempt.timestamp
                })
        
        # Prepare the analysis result
        analysis = {
            "error": {
                "category": error_context.category.name,
                "message": error_message,
                "file_path": file_path,
                "line_number": line_number,
                "function_name": function_name
            },
            "severity": severity,
            "fix_approach": fix_approach,
            "recommended_tier": recommended_tier,
            "similar_errors_found": len(similar_errors),
            "similar_errors": similar_errors,
            "is_likely_fixable": error_context.category not in [
                ErrorCategory.PERMISSION, ErrorCategory.NETWORK, 
                ErrorCategory.UNKNOWN
            ] or len(similar_errors) > 0
        }
        
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Error analysis complete:\n{json.dumps(analysis, indent=2)}",
            level=LogLevel.INFO,
            section=Section.ANALYSIS
        )
        self.scratchpad.end_section(Section.ANALYSIS)
        
        return analysis
    
    def debug_error(self, 
                   error_message: str, 
                   file_path: str, 
                   line_number: Optional[int] = None,
                   traceback_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Simpler facade for handle_error with minimal required parameters.
        
        Args:
            error_message: The error message
            file_path: File path where the error occurred
            line_number: Optional line number where the error occurred
            traceback_text: Optional error traceback (defaults to error_message if not provided)
            
        Returns:
            Results of debugging attempt
        """
        # Use error message as traceback if not provided
        if not traceback_text:
            traceback_text = error_message
            
        return self.handle_error(
            error_message=error_message,
            traceback_text=traceback_text,
            file_path=file_path,
            line_number=line_number
        )
    
    def get_current_error(self) -> Optional[ErrorContext]:
        """
        Get the current error being debugged.
        
        Returns:
            The current error context or None if no active debugging
        """
        return self.current_error
    
    def get_error_history(self, 
                         limit: Optional[int] = None, 
                         filter_category: Optional[ErrorCategory] = None,
                         filter_success: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get the history of debugging attempts with optional filtering.
        
        Args:
            limit: Optional maximum number of entries to return
            filter_category: Optional filter by error category
            filter_success: Optional filter by success status
            
        Returns:
            List of debugging attempts as dictionaries
        """
        history = self.debug_history.copy()
        
        # Apply filters
        if filter_category:
            history = [a for a in history if a.error_context.category == filter_category]
            
        if filter_success is not None:
            history = [a for a in history if a.success == filter_success]
            
        # Convert to dictionaries
        history_dicts = [a.to_dict() for a in history]
        
        # Apply limit if provided
        if limit and limit > 0:
            history_dicts = history_dicts[-limit:]
            
        return history_dicts
    
    def can_debug_error(self, error_message: str, file_path: Optional[str] = None) -> bool:
        """
        Check if an error is debuggable.
        
        Args:
            error_message: The error message
            file_path: Optional file path where the error occurred
            
        Returns:
            True if the error is likely debuggable, False otherwise
        """
        # Create a minimal error context for analysis
        error_context = self._create_error_context(
            error_message, 
            error_message  # Use message as traceback for minimal context
        )
        
        # Check if file exists (if provided)
        file_exists = file_path and os.path.exists(file_path)
        
        # Check if error category is debuggable
        debuggable_category = error_context.category not in [
            ErrorCategory.UNKNOWN, 
            ErrorCategory.PERMISSION
        ]
        
        # Check if we have relevant context
        has_context = bool(file_path) or error_context.category != ErrorCategory.UNKNOWN
        
        # Check if we've successfully debugged similar errors before
        previous_success = any(
            a.success for a in self.debug_history 
            if self._is_similar_error(error_context, a.error_context)
        )
        
        # Error is debuggable if file exists and either:
        # 1. It's a debuggable category and we have context, or
        # 2. We've successfully debugged a similar error before
        return (file_exists and ((debuggable_category and has_context) or previous_success))
    
    def reset(self) -> None:
        """Reset the debugging manager state."""
        self.current_error = None
        self.current_phase = DebuggingPhase.ANALYSIS
        self.attempt_count = 0
        self.generator_attempts = 0
        self.debugger_attempts = 0
        self.restart_attempts = 0
        
    def get_debug_stats(self) -> Dict[str, Any]:
        """Get debugging statistics."""
        stats = {
            "total_attempts": self.attempt_count,
            "errors_by_category": {},
            "success_rate": 0.0,
            "average_attempts_per_error": 0.0,
            "tier_success_rates": {
                "quick_fix": 0.0,
                "full_debug": 0.0,
                "strategic_restart": 0.0
            }
        }
        
        # Skip if no history
        if not self.debug_history:
            return stats
            
        # Calculate error counts by category
        for attempt in self.debug_history:
            category = attempt.error_context.category.name
            if category not in stats["errors_by_category"]:
                stats["errors_by_category"][category] = 0
            stats["errors_by_category"][category] += 1
            
        # Calculate success rate
        successful_attempts = sum(1 for a in self.debug_history if a.success)
        stats["success_rate"] = successful_attempts / len(self.debug_history) if self.debug_history else 0.0
        
        # Calculate average attempts per error
        unique_errors = set()
        for attempt in self.debug_history:
            # Create a unique key for each distinct error
            error_key = (
                attempt.error_context.category,
                attempt.error_context.file_path,
                attempt.error_context.message
            )
            unique_errors.add(error_key)
            
        if unique_errors:
            stats["average_attempts_per_error"] = len(self.debug_history) / len(unique_errors)
            
        # Calculate tier success rates
        for phase_name, phase_count, phase_successes in [
            ("quick_fix", 0, 0),
            ("full_debug", 0, 0),
            ("strategic_restart", 0, 0)
        ]:
            phase_attempts = [a for a in self.debug_history if a.phase.name.lower() == phase_name.lower()]
            if phase_attempts:
                success_count = sum(1 for a in phase_attempts if a.success)
                stats["tier_success_rates"][phase_name] = success_count / len(phase_attempts)
                
        return stats

    def register_generation_issues(self, file_path: str, debug_info: Dict[str, Any]) -> None:
        """Record generation diagnostics for later summarization."""
        if file_path not in self.generation_issue_log:
            self.generation_issue_log[file_path] = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            **debug_info,
        }
        self.generation_issue_log[file_path].append(entry)

        if self.scratchpad:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Recorded generation issues for {file_path}",
                level=LogLevel.INFO,
                section=Section.DEBUGGING,
                metadata={
                    "issue_count": debug_info.get("issue_count"),
                    "categories": debug_info.get("categorized_issues", []),
                },
            )

    def log_diagnostic_result(self) -> None:
        """Summarize recorded generation issues and log them."""
        if not self.generation_issue_log:
            return

        summary: Dict[str, Dict[str, int]] = {}
        for path, entries in self.generation_issue_log.items():
            file_summary: Dict[str, int] = {}
            for info in entries:
                for cat in info.get("categorized_issues", []):
                    file_summary[cat] = file_summary.get(cat, 0) + 1
            summary[path] = file_summary

        if self.scratchpad:
            self.scratchpad.start_section(Section.ANALYSIS, "DebuggingManager")
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Generation diagnostic summary:\n{json.dumps(summary, indent=2)}",
                level=LogLevel.INFO,
                section=Section.ANALYSIS,
            )
            self.scratchpad.end_section(Section.ANALYSIS)

        self.generation_issue_log.clear()
