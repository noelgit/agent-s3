"""
Mock LLM responses for different task types and scenarios.

This module contains realistic mock responses for different types of tasks
that the agent can handle, including:
- Standard feature implementation
- Refactoring operations
- Debugging tasks
- Multi-stage complex tasks
- Edge cases and error scenarios
"""

# Feature Implementation Responses
FEATURE_IMPLEMENTATION_RESPONSES = {
    # API Feature
    "api_endpoint": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Add User API Endpoint
            
            ## Overview
            Add a new REST API endpoint for user management with CRUD operations.
            
            ## Steps
            1. Create model for user data
            2. Implement API endpoint handlers
            3. Set up routes and middleware
            4. Add validation
            5. Write tests
            
            ## Files to Modify
            - `api/models.py` - Add User model
            - `api/routes.py` - Add user routes
            - `api/handlers.py` - Implement handlers
            - `api/validation.py` - Add validation
            - `tests/test_user_api.py` - Add tests
            
            ## Dependencies
            - None (using existing framework)
            """
        },
        "code_generation": {
            "code": {
                "api/models.py": """
                class User:
                    def __init__(self, id=None, name=None, email=None, created_at=None):
                        self.id = id
                        self.name = name
                        self.email = email
                        self.created_at = created_at
                    
                    def to_dict(self):
                        return {
                            'id': self.id,
                            'name': self.name,
                            'email': self.email,
                            'created_at': self.created_at
                        }
                    
                    @classmethod
                    def from_dict(cls, data):
                        return cls(
                            id=data.get('id'),
                            name=data.get('name'),
                            email=data.get('email'),
                            created_at=data.get('created_at')
                        )
                """,
                "api/routes.py": """
                from api.handlers import UserHandler

                def setup_routes(app):
                    handler = UserHandler()
                    
                    app.add_route('/users', handler.get_users, methods=['GET'])
                    app.add_route('/users/{user_id}', handler.get_user, methods=['GET'])
                    app.add_route('/users', handler.create_user, methods=['POST'])
                    app.add_route('/users/{user_id}', handler.update_user, methods=['PUT'])
                    app.add_route('/users/{user_id}', handler.delete_user, methods=['DELETE'])
                """,
                "api/handlers.py": """
                import json
                from api.models import User
                from api.validation import validate_user

                class UserHandler:
                    def __init__(self):
                        self.users = {}  # In-memory store for demo
                    
                    async def get_users(self, request):
                        return json.dumps([user.to_dict() for user in self.users.values()])
                    
                    async def get_user(self, request, user_id):
                        user = self.users.get(user_id)
                        if not user:
                            return {"error": "User not found"}, 404
                        return json.dumps(user.to_dict())
                    
                    async def create_user(self, request):
                        data = await request.json()
                        validation_errors = validate_user(data)
                        
                        if validation_errors:
                            return {"errors": validation_errors}, 400
                        
                        user = User.from_dict(data)
                        self.users[user.id] = user
                        return json.dumps(user.to_dict()), 201
                    
                    async def update_user(self, request, user_id):
                        data = await request.json()
                        validation_errors = validate_user(data)
                        
                        if validation_errors:
                            return {"errors": validation_errors}, 400
                        
                        if user_id not in self.users:
                            return {"error": "User not found"}, 404
                        
                        user = User.from_dict(data)
                        self.users[user_id] = user
                        return json.dumps(user.to_dict())
                    
                    async def delete_user(self, request, user_id):
                        if user_id not in self.users:
                            return {"error": "User not found"}, 404
                        
                        del self.users[user_id]
                        return "", 204
                """,
                "api/validation.py": """
                import re

                def validate_email(email):
                    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
                    return bool(re.match(pattern, email))

                def validate_user(user_data):
                    errors = []
                    
                    if not user_data.get('name'):
                        errors.append("Name is required")
                    
                    if not user_data.get('email'):
                        errors.append("Email is required")
                    elif not validate_email(user_data.get('email')):
                        errors.append("Email format is invalid")
                    
                    return errors
                """,
                "tests/test_user_api.py": """
                import json
                import pytest
                from api.models import User
                from api.handlers import UserHandler

                @pytest.fixture
                def handler():
                    return UserHandler()

                async def test_create_user(handler):
                    # Test user creation
                    user_data = {
                        'id': '1',
                        'name': 'Test User',
                        'email': 'test@example.com'
                    }
                    
                    # Mock request
                    class MockRequest:
                        async def json(self):
                            return user_data
                    
                    response, status = await handler.create_user(MockRequest())
                    assert status == 201
                    
                    # Verify user was created
                    response, status = await handler.get_user(None, '1')
                    assert status == 200
                    assert json.loads(response)['name'] == 'Test User'
                """
            }
        }
    },
    
    # Database Feature
    "database_integration": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Add Database Integration
            
            ## Overview
            Add support for PostgreSQL database with ORM using SQLAlchemy.
            
            ## Steps
            1. Set up database connection
            2. Create SQLAlchemy models
            3. Implement data access layer
            4. Add migrations support
            5. Update existing code to use database
            
            ## Files to Modify
            - `db/connection.py` - Database connection setup
            - `db/models.py` - SQLAlchemy models
            - `db/migrations.py` - Migration utilities
            - `db/repository.py` - Data access layer
            
            ## Dependencies
            - sqlalchemy - ORM framework
            - alembic - Database migrations
            - psycopg2 - PostgreSQL adapter
            """
        },
        "code_generation": {
            "code": {
                "db/connection.py": """
                from sqlalchemy import create_engine
                from sqlalchemy.ext.declarative import declarative_base
                from sqlalchemy.orm import sessionmaker

                DATABASE_URL = "postgresql://user:password@localhost/dbname"

                engine = create_engine(DATABASE_URL)
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                Base = declarative_base()

                def get_db():
                    db = SessionLocal()
                    try:
                        yield db
                    finally:
                        db.close()
                """,
                "db/models.py": """
                from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
                from sqlalchemy.orm import relationship
                from datetime import datetime
                from db.connection import Base

                class User(Base):
                    __tablename__ = "users"

                    id = Column(Integer, primary_key=True, index=True)
                    username = Column(String, unique=True, index=True)
                    email = Column(String, unique=True, index=True)
                    hashed_password = Column(String)
                    created_at = Column(DateTime, default=datetime.utcnow)
                    is_active = Column(Boolean, default=True)
                    
                    items = relationship("Item", back_populates="owner")


                class Item(Base):
                    __tablename__ = "items"

                    id = Column(Integer, primary_key=True, index=True)
                    title = Column(String, index=True)
                    description = Column(String)
                    owner_id = Column(Integer, ForeignKey("users.id"))
                    
                    owner = relationship("User", back_populates="items")
                """,
                "db/repository.py": """
                from sqlalchemy.orm import Session
                from db.models import User, Item

                class UserRepository:
                    def __init__(self, db: Session):
                        self.db = db
                    
                    def get_user(self, user_id: int):
                        return self.db.query(User).filter(User.id == user_id).first()
                    
                    def get_user_by_email(self, email: str):
                        return self.db.query(User).filter(User.email == email).first()
                    
                    def get_users(self, skip: int = 0, limit: int = 100):
                        return self.db.query(User).offset(skip).limit(limit).all()
                    
                    def create_user(self, username: str, email: str, hashed_password: str):
                        db_user = User(username=username, email=email, hashed_password=hashed_password)
                        self.db.add(db_user)
                        self.db.commit()
                        self.db.refresh(db_user)
                        return db_user

                class ItemRepository:
                    def __init__(self, db: Session):
                        self.db = db
                    
                    def get_items(self, skip: int = 0, limit: int = 100):
                        return self.db.query(Item).offset(skip).limit(limit).all()
                    
                    def create_user_item(self, item: dict, user_id: int):
                        db_item = Item(**item, owner_id=user_id)
                        self.db.add(db_item)
                        self.db.commit()
                        self.db.refresh(db_item)
                        return db_item
                """,
                "db/migrations.py": """
                import os
                import sys
                from logging.config import fileConfig

                from sqlalchemy import engine_from_config
                from sqlalchemy import pool

                from alembic import context
                from db.models import Base
                from db.connection import DATABASE_URL

                # this is the Alembic Config object
                config = context.config

                # set database url
                config.set_main_option("sqlalchemy.url", DATABASE_URL)

                # add model's MetaData object for autogenerate support
                target_metadata = Base.metadata

                def run_migrations():
                    '''Run migrations in 'online' mode.'''
                    connectable = engine_from_config(
                        config.get_section(config.config_ini_section),
                        prefix="sqlalchemy.",
                        poolclass=pool.NullPool,
                    )

                    with connectable.connect() as connection:
                        context.configure(
                            connection=connection, 
                            target_metadata=target_metadata
                        )

                        with context.begin_transaction():
                            context.run_migrations()
                """
            }
        }
    }
}

# Refactoring Responses
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
                    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
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

# Debugging Responses
DEBUGGING_RESPONSES = {
    # Authentication Bug
    "auth_bug": {
        "planning": {
            "create_plan": """
            # Debugging Plan: Fix Authentication Token Expiration
            
            ## Overview
            Debug and fix issue where authentication tokens are not properly expiring.
            
            ## Root Cause Analysis
            The token validation logic does not properly check the expiration claim in the JWT.
            
            ## Steps
            1. Review token generation and validation code
            2. Fix token validation to properly check expiration
            3. Add tests for token expiration
            4. Update any affected components
            
            ## Files to Modify
            - `auth/token.py` - Fix token validation
            - `tests/test_auth.py` - Add expiration tests
            """
        },
        "code_generation": {
            "code": {
                "auth/token.py": '''
                import jwt
                import time
                from datetime import datetime, timedelta
                from typing import Dict, Any, Optional

                # Configuration
                SECRET_KEY = "your-secret-key"  # Should be in environment variables
                ALGORITHM = "HS256"
                ACCESS_TOKEN_EXPIRE_MINUTES = 30

                def create_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
                    """Create a new JWT token."""
                    to_encode = data.copy()
                    
                    # Set expiration
                    if expires_delta:
                        expire = datetime.utcnow() + expires_delta
                    else:
                        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                    
                    to_encode.update({"exp": expire})
                    
                    # Create token
                    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
                    return encoded_jwt

                def decode_token(token: str) -> Optional[Dict[str, Any]]:
                    """Decode and validate a JWT token.
                    
                    Returns:
                        Dict containing token claims if valid, None otherwise
                    """
                    try:
                        # Fix: Add explicit verification of expiration
                        payload = jwt.decode(
                            token, 
                            SECRET_KEY, 
                            algorithms=[ALGORITHM],
                            options={"verify_exp": True}  # Explicitly verify expiration
                        )
                        return payload
                    except jwt.ExpiredSignatureError:
                        # Token has expired
                        return None
                    except jwt.InvalidTokenError:
                        # Token is invalid
                        return None

                def is_token_expired(token: str) -> bool:
                    """Check if a token is expired without raising exceptions."""
                    try:
                        payload = jwt.decode(
                            token, 
                            SECRET_KEY, 
                            algorithms=[ALGORITHM],
                            options={"verify_exp": False}  # Don't verify expiration yet
                        )
                        
                        # Manually check expiration
                        if "exp" in payload:
                            expiration = datetime.fromtimestamp(payload["exp"])
                            return datetime.utcnow() > expiration
                        
                        # No expiration claim, consider expired
                        return True
                    except:
                        # Any decode error means the token is invalid
                        return True
                """,
                "tests/test_auth.py": """
                import pytest
                import time
                from datetime import timedelta
                from auth.token import create_token, decode_token, is_token_expired

                def test_token_expiration():
                    # Create token that expires in 2 seconds
                    token = create_token(
                        {"sub": "test"}, 
                        expires_delta=timedelta(seconds=2)
                    )
                    
                    # Token should be valid initially
                    payload = decode_token(token)
                    assert payload is not None
                    assert payload["sub"] == "test"
                    
                    # Wait for token to expire
                    time.sleep(3)
                    
                    # Token should now be expired
                    payload = decode_token(token)
                    assert payload is None
                    
                    # Check with is_token_expired
                    assert is_token_expired(token) is True

                def test_is_token_expired():
                    # Test with valid token
                    valid_token = create_token(
                        {"sub": "test"}, 
                        expires_delta=timedelta(minutes=10)
                    )
                    assert is_token_expired(valid_token) is False
                    
                    # Test with expired token
                    expired_token = create_token(
                        {"sub": "test"}, 
                        expires_delta=timedelta(seconds=-10)  # Already expired
                    )
                    assert is_token_expired(expired_token) is True
                    
                    # Test with invalid token
                    invalid_token = "invalid.token.string"
                    assert is_token_expired(invalid_token) is True
                '''
            }
        }
    },
    
    # Database Connection Bug
    "db_connection_bug": {
        "planning": {
            "create_plan": """
            # Debugging Plan: Fix Database Connection Leaks
            
            ## Overview
            Address issues with database connection leaks causing performance degradation over time.
            
            ## Root Cause Analysis
            Database connections aren't being properly closed in error cases, leading to connection pool exhaustion.
            
            ## Steps
            1. Identify connection management code
            2. Implement proper connection handling with context managers
            3. Add connection pool monitoring
            4. Add stress tests for connection management
            
            ## Files to Modify
            - `db/connection.py` - Fix connection handling
            - `db/pool_monitor.py` - Add monitoring
            - `tests/test_db_connections.py` - Add stress tests
            """
        },
        "code_generation": {
            "code": {
                "db/connection.py": '''
                import contextlib
                import logging
                from typing import Generator, Any
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker, Session
                from sqlalchemy.pool import QueuePool
                from sqlalchemy.ext.declarative import declarative_base

                # Configuration
                DATABASE_URL = "postgresql://user:password@localhost/dbname"
                MAX_OVERFLOW = 10
                POOL_SIZE = 20
                POOL_TIMEOUT = 30
                POOL_RECYCLE = 1800  # 30 minutes

                # Setup logging
                logger = logging.getLogger(__name__)

                # Create engine with connection pooling
                engine = create_engine(
                    DATABASE_URL,
                    poolclass=QueuePool,
                    pool_size=POOL_SIZE,
                    max_overflow=MAX_OVERFLOW,
                    pool_timeout=POOL_TIMEOUT,
                    pool_recycle=POOL_RECYCLE
                )

                # Create session factory
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

                # Create base class for declarative models
                Base = declarative_base()

                @contextlib.contextmanager
                def get_db_connection() -> Generator[Any, None, None]:
                    """Get a database connection from the pool.
                    
                    This context manager ensures that connections are always returned to the pool,
                    even in the case of exceptions.
                    """
                    connection = engine.connect()
                    try:
                        yield connection
                    finally:
                        connection.close()

                @contextlib.contextmanager
                def get_db_session() -> Generator[Session, None, None]:
                    """Get a database session.
                    
                    This context manager ensures that sessions are always closed properly,
                    and transactions are committed or rolled back as appropriate.
                    """
                    session = SessionLocal()
                    try:
                        yield session
                        session.commit()
                    except Exception:
                        session.rollback()
                        raise
                    finally:
                        session.close()

                def get_db() -> Generator[Session, None, None]:
                    """Get DB session for dependency injection."""
                    with get_db_session() as session:
                        yield session

                def get_connection_pool_info() -> dict:
                    """Get information about the current connection pool state."""
                    return {
                        "size": engine.pool.size(),
                        "checkedin": engine.pool.checkedin(),
                        "checkedout": engine.pool.checkedout(),
                        "overflow": engine.pool.overflow(),
                        "checkedout_overflow": engine.pool.overflow(),
                    }
                ''',
                "db/pool_monitor.py": '''
                import time
                import logging
                import threading
                from typing import Optional
                from db.connection import get_connection_pool_info

                logger = logging.getLogger(__name__)

                class PoolMonitor:
                    """Monitor database connection pool and log statistics."""
                    
                    def __init__(self, interval: int = 60):
                        """Initialize the pool monitor.
                        
                        Args:
                            interval: Monitoring interval in seconds
                        """
                        self.interval = interval
                        self.running = False
                        self.thread: Optional[threading.Thread] = None
                    
                    def start(self) -> None:
                        """Start monitoring thread."""
                        if self.running:
                            return
                        
                        self.running = True
                        self.thread = threading.Thread(
                            target=self._monitor_loop,
                            daemon=True
                        )
                        self.thread.start()
                        logger.info("Database pool monitoring started")
                    
                    def stop(self) -> None:
                        """Stop monitoring thread."""
                        self.running = False
                        if self.thread:
                            self.thread.join(timeout=5)
                            self.thread = None
                        logger.info("Database pool monitoring stopped")
                    
                    def _monitor_loop(self) -> None:
                        """Main monitoring loop."""
                        while self.running:
                            try:
                                stats = get_connection_pool_info()
                                
                                # Log current pool state
                                logger.info(
                                    "DB Pool Stats: size=%d, checkedin=%d, checkedout=%d, overflow=%d",
                                    stats["size"],
                                    stats["checkedin"],
                                    stats["checkedout"],
                                    stats["overflow"]
                                )
                                
                                # Check for potential issues
                                if stats["checkedout"] > stats["size"] * 0.8:
                                    logger.warning(
                                        "DB pool near capacity: %d/%d connections used",
                                        stats["checkedout"],
                                        stats["size"]
                                    )
                                
                                if stats["overflow"] > 0:
                                    logger.warning(
                                        "DB pool overflow active: %d overflow connections",
                                        stats["overflow"]
                                    )
                            except Exception as e:
                                logger.error("Error monitoring DB pool: %s", str(e))
                            
                            # Sleep until next interval
                            time.sleep(self.interval)

                # Create singleton instance
                monitor = PoolMonitor()
                '''
            }
        }
    }
}

# Multi-Step Task Responses
MULTI_STEP_RESPONSES = {
    # Data Pipeline
    "data_pipeline": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Data Processing Pipeline
            
            ## Overview
            Create a data processing pipeline with collection, transformation, and visualization components.
            
            ## Steps
            1. Create data collector module
            2. Implement data transformation engine
            3. Add data storage layer
            4. Create visualization module
            5. Implement pipeline coordinator
            
            ## Files to Create
            - `pipeline/collector.py` - Data collection module
            - `pipeline/transformer.py` - Data transformation module
            - `pipeline/storage.py` - Data storage module
            - `pipeline/visualizer.py` - Data visualization module 
            - `pipeline/coordinator.py` - Pipeline coordination
            
            ## Dependencies
            - pandas - Data manipulation
            - matplotlib - Visualization
            - requests - Data collection
            """
        },
        "code_generation": {
            "code": {
                "pipeline/collector.py": '''
                import json
                import logging
                import requests
                from typing import Dict, List, Any, Optional

                logger = logging.getLogger(__name__)

                class DataCollector:
                    """Component for collecting data from various sources."""
                    
                    def __init__(self, config: Optional[Dict[str, Any]] = None):
                        """Initialize the data collector.
                        
                        Args:
                            config: Optional configuration dictionary
                        """
                        self.config = config or {}
                        self.api_key = self.config.get("api_key")
                        self.base_url = self.config.get("base_url")
                    
                    def collect_from_api(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                        """Collect data from an API endpoint.
                        
                        Args:
                            endpoint: API endpoint to collect from
                            params: Optional query parameters
                        
                        Returns:
                            List of data records
                        """
                        url = f"{self.base_url}/{endpoint}" if self.base_url else endpoint
                        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                        
                        logger.info(f"Collecting data from: {url}")
                        
                        try:
                            response = requests.get(url, headers=headers, params=params)
                            response.raise_for_status()
                            
                            data = response.json()
                            logger.info(f"Collected {len(data)} records from {url}")
                            
                            return data
                        except requests.RequestException as e:
                            logger.error(f"Error collecting from API: {str(e)}")
                            return []
                    
                    def collect_from_file(self, file_path: str) -> List[Dict[str, Any]]:
                        """Collect data from a local file.
                        
                        Args:
                            file_path: Path to the data file
                        
                        Returns:
                            List of data records
                        """
                        logger.info(f"Reading data from file: {file_path}")
                        
                        try:
                            with open(file_path, "r") as f:
                                if file_path.endswith(".json"):
                                    data = json.load(f)
                                else:
                                    # Assume CSV with header row
                                    import csv
                                    reader = csv.DictReader(f)
                                    data = list(reader)
                            
                            logger.info(f"Read {len(data)} records from {file_path}")
                            return data
                        except Exception as e:
                            logger.error(f"Error reading file: {str(e)}")
                            return []
                ''',
                "pipeline/transformer.py": '''
                import logging
                import pandas as pd
                from typing import Dict, List, Any, Callable, Optional, Union

                logger = logging.getLogger(__name__)

                class DataTransformer:
                    """Component for transforming and cleaning data."""
                    
                    def __init__(self):
                        """Initialize the data transformer."""
                        # Register built-in transformations
                        self.transformations = {
                            "clean_nulls": self._clean_null_values,
                            "normalize": self._normalize_values,
                            "filter_outliers": self._filter_outliers
                        }
                    
                    def transform(
                        self, 
                        data: List[Dict[str, Any]], 
                        operations: List[Dict[str, Any]]
                    ) -> List[Dict[str, Any]]:
                        """Apply a series of transformations to data.
                        
                        Args:
                            data: List of data records
                            operations: Transformation operations to apply
                        
                        Returns:
                            Transformed data
                        """
                        if not data:
                            return []
                        
                        # Convert to DataFrame for easier manipulation
                        df = pd.DataFrame(data)
                        
                        # Apply each operation in sequence
                        for op in operations:
                            operation_type = op.get("type")
                            if not operation_type:
                                logger.warning("Missing operation type, skipping")
                                continue
                            
                            if operation_type not in self.transformations:
                                logger.warning(f"Unknown operation: {operation_type}, skipping")
                                continue
                            
                            # Get transformation function and apply it
                            transform_func = self.transformations[operation_type]
                            df = transform_func(df, **op.get("params", {}))
                            
                            logger.info(f"Applied {operation_type} transformation")
                        
                        # Convert back to records
                        return df.to_dict(orient="records")
                    
                    def register_transformation(self, name: str, function: Callable) -> None:
                        """Register a custom transformation function.
                        
                        Args:
                            name: Name of the transformation
                            function: Transformation function that takes a DataFrame and returns DataFrame
                        """
                        self.transformations[name] = function
                        logger.info(f"Registered custom transformation: {name}")
                    
                    def _clean_null_values(
                        self, 
                        df: pd.DataFrame, 
                        strategy: str = "drop",
                        columns: Optional[List[str]] = None
                    ) -> pd.DataFrame:
                        """Clean null values in the dataset.
                        
                        Args:
                            df: Input DataFrame
                            strategy: Strategy to handle nulls ('drop', 'fill_mean', 'fill_median', 'fill_zero')
                            columns: Specific columns to clean (None for all)
                        
                        Returns:
                            Cleaned DataFrame
                        """
                        if strategy == "drop":
                            if columns:
                                return df.dropna(subset=columns)
                            return df.dropna()
                        
                        target_cols = columns or df.columns
                        
                        if strategy == "fill_zero":
                            return df.fillna({col: 0 for col in target_cols if col in df.columns})
                        
                        if strategy == "fill_mean":
                            for col in target_cols:
                                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                                    df[col] = df[col].fillna(df[col].mean())
                            return df
                        
                        if strategy == "fill_median":
                            for col in target_cols:
                                if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                                    df[col] = df[col].fillna(df[col].median())
                            return df
                        
                        return df
                    
                    def _normalize_values(
                        self, 
                        df: pd.DataFrame, 
                        columns: List[str],
                        method: str = "minmax"
                    ) -> pd.DataFrame:
                        """Normalize values in specified columns.
                        
                        Args:
                            df: Input DataFrame
                            columns: Columns to normalize
                            method: Normalization method ('minmax', 'zscore')
                        
                        Returns:
                            DataFrame with normalized values
                        """
                        for col in columns:
                            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                                continue
                                
                            if method == "minmax":
                                min_val = df[col].min()
                                max_val = df[col].max()
                                df[col] = (df[col] - min_val) / (max_val - min_val)
                            
                            elif method == "zscore":
                                mean = df[col].mean()
                                std = df[col].std()
                                if std > 0:
                                    df[col] = (df[col] - mean) / std
                        
                        return df
                    
                    def _filter_outliers(
                        self, 
                        df: pd.DataFrame, 
                        columns: List[str],
                        threshold: float = 3.0,
                        method: str = "zscore"
                    ) -> pd.DataFrame:
                        """Filter outliers from the dataset.
                        
                        Args:
                            df: Input DataFrame
                            columns: Columns to check for outliers
                            threshold: Outlier threshold
                            method: Method for outlier detection ('zscore', 'iqr')
                        
                        Returns:
                            DataFrame with outliers removed
                        """
                        for col in columns:
                            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                                continue
                                
                            if method == "zscore":
                                # Z-score method
                                z = (df[col] - df[col].mean()) / df[col].std()
                                df = df[abs(z) < threshold]
                            
                            elif method == "iqr":
                                # IQR method
                                Q1 = df[col].quantile(0.25)
                                Q3 = df[col].quantile(0.75)
                                IQR = Q3 - Q1
                                df = df[~((df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR)))]
                        
                        return df
                '''
            }
        }
    },
    
    # Authentication System
    "auth_system": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Authentication System
            
            ## Overview
            Create a complete authentication system with registration, login, password reset, and session management.
            
            ## Steps
            1. Design user model and database schema
            2. Implement secure password hashing
            3. Create authentication routes and handlers
            4. Implement JWT token management
            5. Add password reset functionality
            6. Create session management
            7. Add unit and integration tests
            
            ## Files to Create
            - `auth/models.py` - User model definition
            - `auth/password.py` - Password hashing and verification
            - `auth/tokens.py` - JWT token generation and validation
            - `auth/routes.py` - Authentication API routes
            - `auth/email.py` - Email services for password reset
            - `auth/session.py` - Session management
            - `tests/test_auth.py` - Authentication tests
            
            ## Dependencies
            - bcrypt - Password hashing
            - pyjwt - JWT token management
            - email-validator - Email validation
            """
        },
        "code_generation": {
            "code": {
                "auth/models.py": '''
                from sqlalchemy import Column, Integer, String, Boolean, DateTime
                from sqlalchemy.ext.declarative import declarative_base
                from datetime import datetime
                from typing import Dict, Any, Optional

                Base = declarative_base()

                class User(Base):
                    """User model for authentication."""
                    
                    __tablename__ = "users"
                    
                    id = Column(Integer, primary_key=True, index=True)
                    email = Column(String, unique=True, index=True, nullable=False)
                    username = Column(String, unique=True, index=True, nullable=False)
                    hashed_password = Column(String, nullable=False)
                    is_active = Column(Boolean, default=True)
                    is_verified = Column(Boolean, default=False)
                    created_at = Column(DateTime, default=datetime.utcnow)
                    last_login = Column(DateTime, nullable=True)
                    
                    def to_dict(self) -> Dict[str, Any]:
                        """Convert user to dictionary."""
                        return {
                            "id": self.id,
                            "email": self.email,
                            "username": self.username,
                            "is_active": self.is_active,
                            "is_verified": self.is_verified,
                            "created_at": self.created_at.isoformat() if self.created_at else None,
                            "last_login": self.last_login.isoformat() if self.last_login else None
                        }
                    
                    @classmethod
                    def from_dict(cls, data: Dict[str, Any]) -> "User":
                        """Create user instance from dictionary."""
                        user = cls(
                            email=data.get("email"),
                            username=data.get("username"),
                            hashed_password=data.get("hashed_password"),
                            is_active=data.get("is_active", True),
                            is_verified=data.get("is_verified", False)
                        )
                        
                        if "id" in data:
                            user.id = data["id"]
                            
                        if "created_at" in data and data["created_at"]:
                            user.created_at = datetime.fromisoformat(data["created_at"])
                            
                        if "last_login" in data and data["last_login"]:
                            user.last_login = datetime.fromisoformat(data["last_login"])
                            
                        return user
                ''',
                "auth/password.py": '''
                import bcrypt
                import re
                from typing import Tuple

                # Password validation regex patterns
                PATTERNS = {
                    "length": r".{8,}",  # At least 8 characters
                    "uppercase": r"[A-Z]",  # At least one uppercase letter
                    "lowercase": r"[a-z]",  # At least one lowercase letter
                    "digit": r"\\d",  # At least one digit
                    "special": r"[!@#$%^&*(),.?\":{}|<>]"  # At least one special character
                }

                def hash_password(password: str) -> str:
                    """Hash password using bcrypt.
                    
                    Args:
                        password: Plain text password
                        
                    Returns:
                        Hashed password
                    """
                    password_bytes = password.encode('utf-8')
                    salt = bcrypt.gensalt()
                    hashed = bcrypt.hashpw(password_bytes, salt)
                    return hashed.decode('utf-8')

                def verify_password(plain_password: str, hashed_password: str) -> bool:
                    """Verify password against hash.
                    
                    Args:
                        plain_password: Plain text password to verify
                        hashed_password: Hashed password to check against
                        
                    Returns:
                        True if password matches, False otherwise
                    """
                    plain_password_bytes = plain_password.encode('utf-8')
                    hashed_password_bytes = hashed_password.encode('utf-8')
                    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)

                def validate_password(password: str) -> Tuple[bool, str]:
                    """Validate password strength.
                    
                    Args:
                        password: Password to validate
                        
                    Returns:
                        Tuple of (valid, reason)
                    """
                    if not re.search(PATTERNS["length"], password):
                        return False, "Password must be at least 8 characters long"
                    
                    if not re.search(PATTERNS["uppercase"], password):
                        return False, "Password must contain at least one uppercase letter"
                    
                    if not re.search(PATTERNS["lowercase"], password):
                        return False, "Password must contain at least one lowercase letter"
                    
                    if not re.search(PATTERNS["digit"], password):
                        return False, "Password must contain at least one digit"
                    
                    if not re.search(PATTERNS["special"], password):
                        return False, "Password must contain at least one special character"
                    
                    return True, ""
                '''
            }
        }
    }
}

# Edge Case Responses
EDGE_CASE_RESPONSES = {
    # Empty Implementation
    "empty_implementation": {
        "planning": {
            "create_plan": """
            # No Implementation Required
            
            ## Overview
            After analyzing the request, no implementation is required because the requested functionality already exists.
            
            ## Explanation
            The requested feature already exists in the codebase. The desired functionality is provided by the module at `utils/existing.py`.
            
            ## Recommendation
            Use the existing implementation instead of creating a new one. Here's an example of how to use it:
            
            ```python
            from utils.existing import feature_function
            
            result = feature_function(param1, param2)
            ```
            """
        },
        "code_generation": {
            "code": {}  # No code needed
        }
    },
    
    # Partial Implementation
    "partial_implementation": {
        "planning": {
            "create_plan": """
            # Partial Implementation Plan: Add CSV Export Feature
            
            ## Overview
            Implement CSV export for the data report feature. Part of the functionality already exists.
            
            ## What Already Exists
            The `export.py` module already contains functionality for exporting data to JSON and XML.
            
            ## What's Missing
            The CSV export function needs to be added to complete the export functionality.
            
            ## Files to Modify
            - `utils/export.py` - Add CSV export function
            - `tests/test_export.py` - Add tests for CSV export
            
            ## Implementation Notes
            Use the existing `_prepare_data` helper function for data preparation before export.
            """
        },
        "code_generation": {
            "code": {
                "utils/export.py": '''
                def export_to_csv(data, filepath, delimiter=','):
                    """Export data to CSV file.
                    
                    Args:
                        data: List of dictionaries to export
                        filepath: Path to save the CSV file
                        delimiter: CSV delimiter character
                    
                    Returns:
                        True if export successful, False otherwise
                    """
                    if not data:
                        return False
                        
                    # Prepare data using existing helper
                    prepared_data = _prepare_data(data)
                    
                    try:
                        import csv
                        
                        # Get fieldnames from the first row
                        fieldnames = list(prepared_data[0].keys())
                        
                        with open(filepath, 'w', newline='') as csvfile:
                            writer = csv.DictWriter(
                                csvfile, 
                                fieldnames=fieldnames,
                                delimiter=delimiter
                            )
                            
                            # Write header and rows
                            writer.writeheader()
                            writer.writerows(prepared_data)
                            
                        return True
                    except Exception as e:
                        logger.error(f"CSV export error: {str(e)}")
                        return False
                '''
            }
        }
    }
}

# Consolidated Mock Responses
MOCK_RESPONSES = {
    "feature_implementation": FEATURE_IMPLEMENTATION_RESPONSES,
    "refactoring": REFACTORING_RESPONSES,
    "debugging": DEBUGGING_RESPONSES,
    "multi_step": MULTI_STEP_RESPONSES,
    "edge_case": EDGE_CASE_RESPONSES
}
