"""
Standardized error handling utilities for Agent-S3.

This module provides consistent patterns for error handling, logging,
and recovery across all components of the agent_s3 system.
"""

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, cast

from agent_s3.errors import (
    AgentError,
    ErrorCategory,
    ErrorContext,
    create_error_context,
)

logger = logging.getLogger(__name__)

# Type variables for function decorators
F = TypeVar("F", bound=Callable[..., Any])
R = TypeVar("R")


class ErrorHandler:
    """
    Utility class for standardized error handling across components.

    This class provides methods for consistent error handling, logging,
    and recovery strategies that can be used by any component.
    """

    def __init__(
        self,
        component: str,
        logger: Optional[logging.Logger] = None,
        reraise: bool = True,
        transform_exceptions: bool = False,
        default_phase: Optional[str] = None,
    ):
        """
        Initialize an ErrorHandler for a specific component.

        Args:
            component: The name of the component using this handler
            logger: The logger to use (defaults to module logger)
            reraise: Whether to re-raise exceptions by default
            transform_exceptions: Whether to transform standard exceptions to AgentError
            default_phase: Default phase name to use in error contexts
        """
        self.component = component
        self.logger = logger or logging.getLogger(f"agent_s3.{component}")
        self.reraise = reraise
        self.transform_exceptions = transform_exceptions
        self.default_phase = default_phase

    def handle_exception(
        self,
        exc: Exception,
        phase: Optional[str] = None,
        operation: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        level: int = logging.ERROR,
        reraise: Optional[bool] = None,
        transform: Optional[bool] = None,
    ) -> ErrorContext:
        """
        Handle an exception with consistent logging and optional transformation.

        Args:
            exc: The exception to handle
            phase: The phase where the error occurred (overrides default_phase)
            operation: The specific operation being performed
            variables: Dictionary of variables relevant to the error
            inputs: Dictionary of input values relevant to the error
            level: The logging level to use
            reraise: Whether to re-raise the exception (overrides instance default)
            transform: Whether to transform standard exceptions (overrides instance default)

        Returns:
            An ErrorContext object with details about the error

        Raises:
            AgentError or the original exception, depending on the transform setting
        """
        # Use instance defaults if not specified
        should_reraise = self.reraise if reraise is None else reraise
        should_transform = self.transform_exceptions if transform is None else transform
        phase_name = phase or self.default_phase

        # Create error context
        error_context = create_error_context(
            exc=exc,
            component=self.component,
            phase=phase_name,
            operation=operation,
            variables=variables,
            inputs=inputs,
        )

        # Format log message
        log_message = (
            f"{error_context.category.value.upper()}: {error_context.error_message}"
        )
        if self.component:
            log_message = f"[{self.component}] {log_message}"
        if phase_name:
            log_message = f"[{phase_name}] {log_message}"
        if operation:
            log_message = f"[{operation}] {log_message}"

        # Log the error
        self.logger.log(level, log_message, exc_info=True)

        # Transform exception if requested
        if should_transform and not isinstance(exc, AgentError):
            # Map standard exceptions to our hierarchy
            from agent_s3.errors import (
                PlanningError,
                GenerationError,
                CoordinationError,
                AuthenticationError,
                NetworkError,
                DatabaseError,
                DebuggingError,
            )

            category = error_context.category
            new_exc: Optional[AgentError] = None

            # Create the appropriate exception type
            if category in [
                ErrorCategory.PLANNING,
                ErrorCategory.SCHEMA,
                ErrorCategory.VALIDATION,
            ]:
                new_exc = PlanningError(str(exc), error_context)
            elif category == ErrorCategory.GENERATION:
                new_exc = GenerationError(str(exc), error_context)
            elif category == ErrorCategory.COORDINATION:
                new_exc = CoordinationError(str(exc), error_context)
            elif category == ErrorCategory.AUTHENTICATION:
                new_exc = AuthenticationError(str(exc), error_context)
            elif category == ErrorCategory.NETWORK:
                new_exc = NetworkError(str(exc), error_context)
            elif category == ErrorCategory.DATABASE:
                new_exc = DatabaseError(str(exc), error_context)
            elif category == ErrorCategory.DEBUGGING:
                new_exc = DebuggingError(str(exc), error_context)
            else:
                new_exc = AgentError(str(exc), error_context)

            # Re-raise the transformed exception if requested
            if should_reraise:
                raise new_exc from exc

        # Re-raise the original exception if requested
        elif should_reraise:
            raise

        return error_context

    def exception_decorator(
        self,
        phase: Optional[str] = None,
        operation: Optional[str] = None,
        reraise: Optional[bool] = None,
        transform: Optional[bool] = None,
        default_return: Optional[Any] = None,
    ) -> Callable[[F], F]:
        """
        Decorator for consistent exception handling.

        This decorator wraps a function to provide consistent exception handling,
        logging, and optional transformation of exceptions.

        Args:
            phase: The phase where the function operates
            operation: The specific operation being performed
            reraise: Whether to re-raise exceptions (overrides instance default)
            transform: Whether to transform standard exceptions (overrides instance default)
            default_return: Default value to return on error if not re-raising

        Returns:
            Decorator function that wraps the target function
        """

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    # Extract relevant variables
                    variables = {"args": args, "kwargs": kwargs}

                    # Handle the exception
                    self.handle_exception(
                        exc=exc,
                        phase=phase,
                        operation=operation or func.__name__,
                        variables=variables,
                        reraise=reraise,
                        transform=transform,
                    )

                    # If we get here, the exception wasn't re-raised
                    return default_return

            return cast(F, wrapper)

        return decorator

    @contextmanager
    def error_context(
        self,
        phase: Optional[str] = None,
        operation: Optional[str] = None,
        reraise: Optional[bool] = None,
        transform: Optional[bool] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager for consistent exception handling.

        This context manager provides consistent exception handling,
        logging, and optional transformation of exceptions.

        Args:
            phase: The phase where the operation occurs
            operation: The specific operation being performed
            reraise: Whether to re-raise exceptions (overrides instance default)
            transform: Whether to transform standard exceptions (overrides instance default)
            inputs: Dictionary of input values relevant to the operation
        """
        try:
            yield
        except Exception as exc:
            self.handle_exception(
                exc=exc,
                phase=phase,
                operation=operation,
                inputs=inputs,
                reraise=reraise,
                transform=transform,
            )


# Decorator for retry logic
def retry(
    max_attempts: int = 3,
    exceptions: Union[Type[Exception], List[Type[Exception]]] = Exception,
    logger: Optional[logging.Logger] = None,
    retry_message: str = "Retrying {operation} (attempt {attempt}/{max_attempts})",
    failure_message: str = "All retry attempts failed for {operation}",
    should_retry_func: Optional[Callable[[Exception, int], bool]] = None,
) -> Callable[[F], F]:
    """
    Decorator for retry logic with consistent logging.

    This decorator wraps a function to provide retry logic with
    consistent logging and optional filtering of exceptions.

    Args:
        max_attempts: Maximum number of retry attempts
        exceptions: Exception type(s) to catch for retries
        logger: Logger to use for logging retries
        retry_message: Message to log when retrying
        failure_message: Message to log when all retries fail
        should_retry_func: Function to determine if a retry should be attempted

    Returns:
        Decorator function that adds retry logic to the target function
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            operation = func.__name__

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    # Check if we should retry
                    if should_retry_func:
                        try_again = should_retry_func(exc, attempt)
                    else:
                        try_again = True

                    # Also stop retrying on explicit don't retry messages
                    if not try_again or "don't retry" in str(exc).lower():
                        logger.warning(
                            f"Not retrying {operation} after attempt {attempt} due to exception: {exc}"
                        )
                        break

                    # Check if we have more attempts
                    if attempt < max_attempts:
                        log_message = retry_message.format(
                            operation=operation,
                            attempt=attempt,
                            max_attempts=max_attempts,
                        )
                        logger.warning("%s", {log_message}: {exc})
                    else:
                        log_message = failure_message.format(
                            operation=operation, max_attempts=max_attempts
                        )
                        logger.error("%s", {log_message}: {exc})

            # Re-raise the last exception
            if last_exception:
                raise last_exception

        return cast(F, wrapper)

    return decorator
