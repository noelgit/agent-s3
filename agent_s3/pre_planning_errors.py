"""
Centralized error handling module for pre-planning in Agent-S3.

This module defines a consistent hierarchy of exceptions, error categorization,
and decorators for pre-planning error handling.
"""

from typing import Dict, Any, List, Optional
import logging
import functools

logger = logging.getLogger(__name__)

class AgentS3BaseError(Exception):
    """Base error class for Agent-S3 exceptions."""
    pass

class PrePlanningError(AgentS3BaseError):
    """Base class for pre-planning related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }

class ValidationError(PrePlanningError):
    """Error for validation failures during pre-planning."""
    def __init__(self, message: str, errors: List[str], 
                 validation_results: Optional[Dict[str, Any]] = None):
        details = {
            "errors": errors
        }
        if validation_results:
            details["validation_results"] = validation_results
        super().__init__(message, details)

class SchemaError(PrePlanningError):
    """Error for JSON schema validation failures."""
    def __init__(self, message: str, schema_errors: List[str]):
        super().__init__(message, {"schema_errors": schema_errors})

class RepairError(PrePlanningError):
    """Error when pre-planning data repair fails."""
    def __init__(self, message: str, original_errors: List[str]):
        super().__init__(message, {"original_errors": original_errors})

class ComplexityError(PrePlanningError):
    """Error for task complexity issues."""
    def __init__(self, message: str, complexity_score: float, 
                 complexity_factors: Dict[str, float]):
        super().__init__(message, {
            "complexity_score": complexity_score,
            "complexity_factors": complexity_factors
        })

# Error handling decorator
def handle_pre_planning_errors(func):
    """Decorator for consistent pre-planning error handling."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.error(f"Validation error in {func.__name__}: {e.message}")
            return {
                "success": False,
                "error_type": "validation",
                "message": e.message,
                "details": e.details
            }
        except SchemaError as e:
            logger.error(f"Schema error in {func.__name__}: {e.message}")
            return {
                "success": False,
                "error_type": "schema",
                "message": e.message,
                "details": e.details
            }
        except RepairError as e:
            logger.error(f"Repair error in {func.__name__}: {e.message}")
            return {
                "success": False,
                "error_type": "repair",
                "message": e.message,
                "details": e.details
            }
        except ComplexityError as e:
            logger.error(f"Complexity error in {func.__name__}: {e.message}")
            return {
                "success": False,
                "error_type": "complexity",
                "message": e.message,
                "details": e.details
            }
        except PrePlanningError as e:
            logger.error(f"Pre-planning error in {func.__name__}: {e.message}")
            return {
                "success": False,
                "error_type": "pre_planning",
                "message": e.message,
                "details": e.details
            }
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return {
                "success": False,
                "error_type": "unexpected",
                "message": f"An unexpected error occurred: {str(e)}"
            }
    return wrapper
