# tests/mock_responses/multi_step_responses.py

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

                    def collect_from_api(self, endpoint: str, params: Optional[Dict[str,
                         Any]] = None) -> List[Dict[str, Any]]:                        """Collect data from an API endpoint.

                        Args:
                            endpoint: API endpoint to collect from
                            params: Optional query parameters

                        Returns:
                            List of data records
                        """
                        url = f"{self.base_url}/{endpoint}" if self.base_url else endpoint
                        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

                        logger.info("%s", Collecting data from: {url})

                        try:
                            response = requests.get(url, headers=headers, params=params)
                            response.raise_for_status()

                            data = response.json()
                            logger.info("%s", Collected {len(data)} records from {url})

                            return data
                        except requests.RequestException as e:
                            logger.error("%s", Error collecting from API: {str(e)})
                            return []

                    def collect_from_file(self, file_path: str) -> List[Dict[str, Any]]:
                        """Collect data from a local file.

                        Args:
                            file_path: Path to the data file

                        Returns:
                            List of data records
                        """
                        logger.info("%s", Reading data from file: {file_path})

                        try:
                            with open(file_path, "r") as f:
                                if file_path.endswith(".json"):
                                    data = json.load(f)
                                else:
                                    # Assume CSV with header row
                                    import csv
                                    reader = csv.DictReader(f)
                                    data = list(reader)

                            logger.info("%s", Read {len(data)} records from {file_path})
                            return data
                        except Exception as e:
                            logger.error("%s", Error reading file: {str(e)})
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
                                logger.warning("%s", Unknown operation: {operation_type}, skipping)
                                continue

                            # Get transformation function and apply it
                            transform_func = self.transformations[operation_type]
                            df = transform_func(df, **op.get("params", {}))

                            logger.info("%s", Applied {operation_type} transformation)

                        # Convert back to records
                        return df.to_dict(orient="records")

                    def register_transformation(self, name: str, function: Callable) -> None:
                        """Register a custom transformation function.

                        Args:
                            name: Name of the transformation
                            function: Transformation function that takes a DataFrame and returns DataFrame
                        """
                        self.transformations[name] = function
                        logger.info("%s", Registered custom transformation: {name})

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
