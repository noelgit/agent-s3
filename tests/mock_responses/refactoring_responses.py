# tests/mock_responses/refactoring_responses.py

REFACTORING_RESPONSES = {
    # Code Organization
    "code_organization": {
        "planning": {
            "create_plan": """
            # Refactoring Plan: Improve Code Organization

            ## Overview
            Refactor the codebase to improve organization, reduce duplication, and follow better design patterns.

            ## Steps
            1. Extract common utility functions into dedicated modules
            2. Implement service layer pattern to separate business logic
            3. Improve error handling with custom exception classes
            4. Standardize logging throughout application

            ## Files to Modify
            - `utils/common.py` - Create utility module
            - `services/data_service.py` - Extract business logic
            - `exceptions.py` - Add custom exception classes
            - `logger.py` - Add centralized logging

            ## Tests to Update
            - Update existing tests to reflect new architecture
            """
        },
        "code_generation": {
            "code": {
                "utils/common.py": '''
                import re
                import json
                import hashlib
                from typing import Dict, Any, List, Optional

                def validate_email(email: str) -> bool:
                    """Validate email format."""
                    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'
                    return bool(re.match(pattern, email))

                def generate_hash(data: str) -> str:
                    """Generate SHA-256 hash of input data."""
                    return hashlib.sha256(data.encode()).hexdigest()

                def safe_get(data: Dict[str, Any], key_path: str, default: Any = None) -> Any:
                    """Safely get a value from a nested dictionary using dot notation."""
                    keys = key_path.split('.')
                    result = data

                    for key in keys:
                        if isinstance(result, dict) and key in result:
                            result = result[key]
                        else:
                            return default

                    return result
                ''',
                "exceptions.py": '''
                class AppException(Exception):
                    """Base exception class for application errors."""

                    def __init__(self, message: str, status_code: int = 500):
                        self.message = message
                        self.status_code = status_code
                        super().__init__(self.message)


                class ValidationError(AppException):
                    """Exception raised for validation errors."""

                    def __init__(self, message: str, field: str = None):
                        self.field = field
                        status_code = 400
                        super().__init__(message, status_code)


                class AuthenticationError(AppException):
                    """Exception raised for authentication errors."""

                    def __init__(self, message: str = "Authentication failed"):
                        status_code = 401
                        super().__init__(message, status_code)


                class AuthorizationError(AppException):
                    """Exception raised for authorization errors."""

                    def __init__(self, message: str = "Not authorized"):
                        status_code = 403
                        super().__init__(message, status_code)


                class ResourceNotFoundError(AppException):
                    """Exception raised when a resource is not found."""

                    def __init__(self, resource_type: str, resource_id: str = None):
                        message = f"{resource_type} not found"
                        if resource_id:
                            message = f"{resource_type} with ID {resource_id} not found"
                        status_code = 404
                        super().__init__(message, status_code)
                ''',
                "logger.py": '''
                import logging
                import sys
                import os
                from datetime import datetime

                # Configure logging
                LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
                LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                LOG_DIR = "logs"

                if not os.path.exists(LOG_DIR):
                    os.makedirs(LOG_DIR)

                def get_logger(name):
                    """Get a configured logger instance."""
                    logger = logging.getLogger(name)

                    # Set level
                    logger.setLevel(getattr(logging, LOG_LEVEL))

                    # Create handlers
                    console_handler = logging.StreamHandler(sys.stdout)
                    file_handler = logging.FileHandler(
                        f"{LOG_DIR}/{datetime.now().strftime('%Y-%m-%d')}.log",
                        encoding="utf-8"
                    )

                    # Set formatters
                    formatter = logging.Formatter(LOG_FORMAT)
                    console_handler.setFormatter(formatter)
                    file_handler.setFormatter(formatter)

                    # Add handlers
                    logger.addHandler(console_handler)
                    logger.addHandler(file_handler)

                    return logger
                '''
            }
        }
    },

    # Performance Optimization
    "performance_optimization": {
        "planning": {
            "create_plan": """
            # Refactoring Plan: Performance Optimization

            ## Overview
            Optimize application performance by improving algorithms, adding caching, and reducing database load.

            ## Steps
            1. Add caching layer for frequently accessed data
            2. Optimize database queries and add indexes
            3. Implement pagination for large result sets
            4. Improve algorithm efficiency in critical paths

            ## Files to Modify
            - `cache/manager.py` - Create caching infrastructure
            - `db/repository.py` - Optimize queries
            - `services/data_service.py` - Add caching
            - `api/handlers.py` - Implement pagination

            ## Performance Targets
            - Reduce API response time by 50%
            - Decrease database load by 30%
            """
        },
        "code_generation": {
            "code": {
                "cache/manager.py": '''
                import json
                import time
                from typing import Any, Dict, Optional, Tuple, Callable

                class CacheManager:
                    """In-memory cache manager with TTL support."""

                    def __init__(self, default_ttl: int = 300):
                        """Initialize cache manager.

                        Args:
                            default_ttl: Default time-to-live in seconds (default: 300)
                        """
                        self.cache: Dict[str, Tuple[Any, float]] = {}
                        self.default_ttl = default_ttl

                    def get(self, key: str) -> Optional[Any]:
                        """Get value from cache if exists and not expired."""
                        if key not in self.cache:
                            return None

                        value, expiry = self.cache[key]
                        if expiry < time.time():
                            # Expired, remove and return None
                            del self.cache[key]
                            return None

                        return value

                    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
                        """Set value in cache with expiry time."""
                        ttl = ttl if ttl is not None else self.default_ttl
                        expiry = time.time() + ttl
                        self.cache[key] = (value, expiry)

                    def delete(self, key: str) -> bool:
                        """Delete key from cache. Returns True if key existed."""
                        if key in self.cache:
                            del self.cache[key]
                            return True
                        return False

                    def clear(self) -> None:
                        """Clear all cache entries."""
                        self.cache.clear()

                    def cached(self, key_prefix: str, ttl: Optional[int] = None) -> Callable:
                        """Decorator for caching function results."""
                        def decorator(func):
                            def wrapper(*args, **kwargs):
                                # Create cache key from function name, args and kwargs
                                key_parts = [key_prefix, func.__name__]

                                # Add stringified args and kwargs
                                if args:
                                    key_parts.append(str(args))
                                if kwargs:
                                    key_parts.append(str(kwargs))

                                cache_key = ":".join(key_parts)

                                # Try to get from cache
                                cached_value = self.get(cache_key)
                                if cached_value is not None:
                                    return cached_value

                                # Not in cache, call function
                                result = func(*args, **kwargs)

                                # Store in cache
                                self.set(cache_key, result, ttl)

                                return result
                            return wrapper
                        return decorator

                # Create global cache instance
                cache = CacheManager()
                '''
            }
        }
    }
}
