# tests/mock_responses/feature_responses.py

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
                    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'
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
