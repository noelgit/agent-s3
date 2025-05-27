"""
Common utility functions for Agent-S3.

This module provides shared utilities for retry logic, validation, JSON processing,
and error handling to maintain consistency across the codebase.
"""

import json
import logging
import time
import random
import traceback
from typing import Dict, Any, Optional, Tuple, Callable, List
from functools import wraps

logger = logging.getLogger(__name__)

# Error handling patterns
class AgentError(Exception):
    """Base exception for Agent-S3 errors."""
    pass

class RetryableError(AgentError):
    """Error that can be retried."""
    pass

class ValidationError(AgentError):
    """Error during validation."""
    pass

class ProcessingError(AgentError):
    """Error during processing."""
    pass

# Retry utilities
def exponential_backoff_with_jitter(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate exponential backoff with jitter.
    
    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
    
    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.random() * 0.1 * delay
    return delay + jitter

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[type, ...] = (Exception,),
    logger_instance: Optional[logging.Logger] = None
):
    """Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exception types to retry on
        logger_instance: Logger instance for logging retry attempts
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            log = logger_instance or logger
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        log.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise
                    
                    delay = exponential_backoff_with_jitter(attempt, base_delay, max_delay)
                    log.warning(f"Function {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                    time.sleep(delay)
                except Exception as e:
                    # Non-retryable exception
                    log.error(f"Function {func.__name__} failed with non-retryable error: {e}")
                    raise
            
            # Should never reach here, but just in case
            raise last_exception
        return wrapper
    return decorator

def call_with_retry(
    func: Callable,
    args: Tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: Tuple[type, ...] = (Exception,),
    logger_instance: Optional[logging.Logger] = None
) -> Any:
    """Call function with retry logic.
    
    Args:
        func: Function to call
        args: Positional arguments for function
        kwargs: Keyword arguments for function
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries
        retryable_exceptions: Tuple of exception types to retry on
        logger_instance: Logger instance for logging
    
    Returns:
        Function result
    """
    kwargs = kwargs or {}
    last_exception = None
    log = logger_instance or logger
    
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            if attempt == max_retries:
                log.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                raise
            
            delay = exponential_backoff_with_jitter(attempt, base_delay)
            log.warning(f"Function {func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
            time.sleep(delay)
        except Exception as e:
            log.error(f"Function {func.__name__} failed with non-retryable error: {e}")
            raise
    
    raise last_exception

# JSON processing utilities
def safe_json_loads(text: str, default: Any = None) -> Any:
    """Safely parse JSON text with fallback.
    
    Args:
        text: JSON text to parse
        default: Default value if parsing fails
    
    Returns:
        Parsed JSON or default value
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default

def extract_json_with_patterns(text: str) -> Optional[str]:
    """Extract JSON from text using multiple patterns.
    
    Args:
        text: Text potentially containing JSON
    
    Returns:
        Extracted JSON string or None
    """
    import re
    
    # Try different extraction patterns in order of preference
    patterns = [
        # Code block pattern (most common)
        (r'```json\n(.*?)\n```', "json code block"),
        # Markdown code block without language specifier
        (r'```\n(.*?)\n```', "generic code block"),
        # Direct JSON pattern with optional whitespace
        (r'(\{\s*"[^"]+"\s*:.*\})', "direct JSON pattern"),
        # Broader JSON pattern fallback
        (r'({[\s\S]*})', "general JSON pattern"),
        # XML-like pattern (sometimes LLMs wrap JSON in XML-like tags)
        (r'<json>([\s\S]*?)</json>', "XML-like wrapper"),
        # Array pattern
        (r'(\[[\s\S]*\])', "array pattern")
    ]
    
    for pattern, pattern_name in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            logger.debug(f"Extracted JSON using {pattern_name} pattern")
            return match.group(1).strip()
    
    return None

def repair_json_quotes(text: str) -> str:
    """Repair common JSON quote issues.
    
    Args:
        text: JSON text to repair
    
    Returns:
        Repaired JSON text
    """
    import re
    
    # Replace single quotes with double quotes (but not inside strings)
    # This is a simple approach - could be made more sophisticated
    text = text.replace("'", '"')
    
    # Remove trailing commas before closing brackets/braces
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    return text

def validate_json_structure(data: Any, required_keys: List[str] = None) -> Tuple[bool, List[str]]:
    """Validate JSON structure has required keys.
    
    Args:
        data: Data to validate
        required_keys: List of required top-level keys
    
    Returns:
        Tuple of (is_valid, list_of_missing_keys)
    """
    if not isinstance(data, dict):
        return False, ["Data is not a dictionary"]
    
    if not required_keys:
        return True, []
    
    missing_keys = [key for key in required_keys if key not in data]
    return len(missing_keys) == 0, missing_keys

# Validation utilities
class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, is_valid: bool, issues: List[str] = None, data: Any = None):
        self.is_valid = is_valid
        self.issues = issues or []
        self.data = data
        self.needs_repair = not is_valid and bool(issues)
    
    def add_issue(self, issue: str) -> None:
        """Add a validation issue."""
        self.issues.append(issue)
        self.is_valid = False
        self.needs_repair = True
    
    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """Merge with another validation result."""
        combined_valid = self.is_valid and other.is_valid
        combined_issues = self.issues + other.issues
        return ValidationResult(combined_valid, combined_issues, other.data or self.data)

def validate_feature_group_structure(feature_group: Dict[str, Any]) -> ValidationResult:
    """Validate feature group structure.
    
    Args:
        feature_group: Feature group data to validate
    
    Returns:
        ValidationResult with validation status and issues
    """
    result = ValidationResult(True, [], feature_group)
    
    if not isinstance(feature_group, dict):
        result.add_issue("Feature group must be a dictionary")
        return result
    
    # Check required fields
    required_fields = ["group_name", "features"]
    for field in required_fields:
        if field not in feature_group:
            result.add_issue(f"Missing required field: {field}")
    
    # Validate features
    features = feature_group.get("features", [])
    if not isinstance(features, list):
        result.add_issue("Features must be a list")
    elif not features:
        result.add_issue("Features list cannot be empty")
    else:
        for i, feature in enumerate(features):
            if not isinstance(feature, dict):
                result.add_issue(f"Feature {i} must be a dictionary")
                continue
            
            feature_required = ["name", "description"]
            for field in feature_required:
                if field not in feature:
                    result.add_issue(f"Feature {i} missing required field: {field}")
    
    return result

# Error handling utilities
def handle_error_with_context(
    error: Exception,
    context: str,
    logger_instance: Optional[logging.Logger] = None,
    include_traceback: bool = True
) -> str:
    """Handle error with context information.
    
    Args:
        error: Exception that occurred
        context: Context description
        logger_instance: Logger instance
        include_traceback: Whether to include traceback
    
    Returns:
        Formatted error message
    """
    log = logger_instance or logger
    
    error_msg = f"Error in {context}: {str(error)}"
    
    if include_traceback:
        error_msg += f"\nTraceback: {traceback.format_exc()}"
    
    log.error(error_msg)
    return error_msg

def create_error_response(
    success: bool = False,
    error_message: str = "",
    error_context: str = "",
    data: Any = None,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """Create standardized error response.
    
    Args:
        success: Whether operation was successful
        error_message: Error message
        error_context: Error context
        data: Any associated data
        timestamp: Timestamp (will use current time if not provided)
    
    Returns:
        Standardized error response dictionary
    """
    import datetime
    
    response = {
        "success": success,
        "timestamp": timestamp or datetime.datetime.now().isoformat()
    }
    
    if not success:
        response["error"] = {
            "message": error_message,
            "context": error_context
        }
    
    if data is not None:
        response["data"] = data
    
    return response

# Logging utilities
def log_function_entry_exit(logger_instance: Optional[logging.Logger] = None):
    """Decorator to log function entry and exit.
    
    Args:
        logger_instance: Logger instance to use
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logger_instance or logger
            func_name = func.__name__
            
            log.debug(f"Entering {func_name}")
            try:
                result = func(*args, **kwargs)
                log.debug(f"Exiting {func_name} successfully")
                return result
            except Exception as e:
                log.error(f"Exiting {func_name} with error: {e}")
                raise
        return wrapper
    return decorator

def safe_get_nested(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely get nested dictionary value.
    
    Args:
        data: Dictionary to search
        keys: List of nested keys
        default: Default value if key path not found
    
    Returns:
        Value at key path or default
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current

def merge_dictionaries(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries safely.
    
    Args:
        *dicts: Dictionaries to merge
    
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result