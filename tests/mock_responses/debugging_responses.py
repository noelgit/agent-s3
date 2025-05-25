# tests/mock_responses/debugging_responses.py

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

                def create_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None)
                     -> str:                    """Create a new JWT token."""
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
