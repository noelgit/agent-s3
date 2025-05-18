"""
System-level integration tests for the Agent-S3 system.

These tests use realistic mock LLM responses to test various workflows 
including feature development, refactoring, debugging, and multi-step tasks.
"""

import os
import json
import pytest
import uuid
from unittest.mock import MagicMock, patch, call
from pathlib import Path
from typing import Dict, Any, List

from agent_s3.coordinator import Coordinator
from agent_s3.config import Config


# Mock LLM responses for different task scenarios
MOCK_LLM_RESPONSES = {
    # Basic feature implementation mock responses
    "feature_implementation": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Add User Authentication Feature
            
            ## Overview
            Implement a basic user authentication system with login, registration, and session management.
            
            ## Steps
            1. Create user model (user.py)
            2. Implement authentication logic (auth.py)
            3. Add API endpoints for auth operations
            4. Implement session management
            5. Add tests for authentication flows
            
            ## Files to Modify
            - `models/user.py` - Create new file for user model
            - `api/auth.py` - Create new file for auth endpoints
            - `services/auth_service.py` - Create new file for auth business logic
            - `tests/test_auth.py` - Create tests for authentication
            
            ## Dependencies
            - bcrypt - Password hashing
            - pyjwt - JWT token management
            """
        },
        "code_generation": {
            "code": {
                "models/user.py": """
                from datetime import datetime
                
                class User:
                    def __init__(self, username, email, password_hash, created_at=None, last_login=None):
                        self.username = username
                        self.email = email
                        self.password_hash = password_hash
                        self.created_at = created_at or datetime.now()
                        self.last_login = last_login
                    
                    def to_dict(self):
                        return {
                            'username': self.username,
                            'email': self.email,
                            'created_at': self.created_at.isoformat(),
                            'last_login': self.last_login.isoformat() if self.last_login else None
                        }
                """
            }
        }
    },
    
    # Refactoring task mock responses
    "refactoring": {
        "planning": {
            "create_plan": """
            # Refactoring Plan: Improve Code Organization
            
            ## Overview
            Refactor the codebase to improve organization, reduce duplication, and follow better design patterns.
            
            ## Steps
            1. Extract common utility functions
            2. Implement service layer pattern
            3. Improve error handling with custom exceptions
            4. Add proper logging
            
            ## Files to Modify
            - `utils/common.py` - Create utility module
            - `services/data_service.py` - Extract data handling logic
            - `exceptions.py` - Add custom exception classes
            - `logger.py` - Add centralized logging
            
            ## Tests
            - Update existing tests to reflect new structure
            - Add tests for new utility functions
            """
        },
        "code_generation": {
            "code": {
                "utils/common.py": """
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
                """
            }
        }
    },
    
    # Debugging task mock responses
    "debugging": {
        "planning": {
            "create_plan": """
            # Debugging Plan: Fix Authentication Token Expiration Issue
            
            ## Overview
            Debug and fix issue where authentication tokens are not properly expiring.
            
            ## Steps
            1. Identify token generation and validation code
            2. Review token expiration implementation
            3. Fix expiration validation
            4. Add tests for token expiration
            
            ## Files to Modify
            - `services/auth_service.py` - Fix token expiration logic
            - `tests/test_auth.py` - Add expiration tests
            
            ## Root Cause Analysis
            The token validation does not properly check the 'exp' claim in the JWT token.
            """
        },
        "code_generation": {
            "code": {
                "services/auth_service.py": """
                import jwt
                import datetime
                from typing import Dict, Any, Optional
                
                JWT_SECRET = "your-secret-key"  # In production, use environment variable
                JWT_ALGORITHM = "HS256"
                TOKEN_EXPIRY = 3600  # 1 hour in seconds
                
                def generate_token(user_id: str) -> str:
                    """Generate a JWT token for a user."""
                    payload = {
                        'user_id': user_id,
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRY),
                        'iat': datetime.datetime.utcnow()
                    }
                    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
                
                def validate_token(token: str) -> Optional[Dict[str, Any]]:
                    """Validate a JWT token and return payload if valid."""
                    try:
                        # Fix: Add verification of exp claim
                        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={'verify_exp': True})
                        return payload
                    except jwt.ExpiredSignatureError:
                        # Handle expired token
                        return None
                    except jwt.InvalidTokenError:
                        # Handle invalid token
                        return None
                """
            }
        }
    },
    
    # Multi-step task mock responses
    "multi_step": {
        "planning": {
            "create_plan": """
            # Implementation Plan: Data Analytics Pipeline
            
            ## Overview
            Create a data processing pipeline with collection, transformation, and visualization components.
            
            ## Steps
            1. Create data collector module
            2. Implement data transformation engine
            3. Add data storage layer
            4. Create visualization module
            5. Implement end-to-end pipeline
            
            ## Files to Create/Modify
            - `pipeline/collector.py` - Data collection
            - `pipeline/transformer.py` - Data transformation
            - `pipeline/storage.py` - Data storage
            - `pipeline/visualizer.py` - Data visualization
            - `pipeline/pipeline.py` - End-to-end pipeline
            - `tests/pipeline/test_*.py` - Tests for each component
            
            ## Dependencies
            - pandas - Data processing
            - matplotlib - Visualization
            - SQLAlchemy - Data storage
            """
        },
        "code_generation": {
            "code": {
                "pipeline/collector.py": """
                import requests
                import json
                import logging
                from typing import Dict, Any, List, Optional
                
                logger = logging.getLogger(__name__)
                
                class DataCollector:
                    def __init__(self, api_url: str, api_key: Optional[str] = None):
                        self.api_url = api_url
                        self.api_key = api_key
                        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    
                    def collect_data(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                        """Collect data from specified API endpoint."""
                        url = f"{self.api_url}/{endpoint}"
                        logger.info(f"Collecting data from {url}")
                        
                        try:
                            response = requests.get(url, headers=self.headers, params=params)
                            response.raise_for_status()
                            return response.json()
                        except requests.RequestException as e:
                            logger.error(f"Error collecting data: {str(e)}")
                            return []
                """
            }
        }
    }
}


@pytest.fixture
def mock_coordinator():
    """Create a mocked Coordinator for testing."""
    # Create patches for key components to allow controlled testing
    with patch('agent_s3.coordinator.Config') as mock_config_cls, \
         patch('agent_s3.coordinator.EnhancedScratchpadManager') as mock_scratchpad_cls, \
         patch('agent_s3.coordinator.ProgressTracker') as mock_progress_tracker_cls, \
         patch('agent_s3.coordinator.TaskStateManager') as mock_task_state_manager_cls, \
         patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_pre_planning_workflow, \
         patch('agent_s3.pre_planner_json_enforced.regenerate_pre_planning_with_modifications') as mock_regen_pre_planning, \
         patch('agent_s3.coordinator.Planner') as mock_planner_cls, \
         patch('agent_s3.coordinator.TestPlanner') as mock_test_planner_cls, \
         patch('agent_s3.coordinator.CodeGenerator') as mock_code_generator_cls, \
         patch('agent_s3.coordinator.PromptModerator') as mock_prompt_moderator_cls, \
         patch('agent_s3.coordinator.os.makedirs') as mock_makedirs, \
         patch('builtins.open', new_callable=MagicMock), \
         patch('agent_s3.coordinator.BashTool') as mock_bash_tool_cls:
        
        # Set up return values for core mocks
        mock_config = MagicMock()
        mock_config.config = {
            "max_attempts": 3,
            "complexity_threshold": 100.0,
            "sandbox_environment": False
        }
        mock_config.github_token = "fake-token"
        mock_config.host_os_type = "linux"
        mock_config.get_log_file_path.return_value = "/path/to/log"
        
        mock_config_cls.return_value = mock_config
        
        mock_scratchpad = MagicMock()
        mock_progress_tracker = MagicMock()
        mock_task_state_manager = MagicMock()
        mock_planner = MagicMock()
        mock_test_planner = MagicMock()
        mock_code_generator = MagicMock()
        mock_prompt_moderator = MagicMock()
        mock_bash_tool = MagicMock()
        
        # Set up return values
        mock_scratchpad_cls.return_value = mock_scratchpad
        mock_progress_tracker_cls.return_value = mock_progress_tracker
        mock_task_state_manager_cls.return_value = mock_task_state_manager
        mock_planner_cls.return_value = mock_planner
        mock_test_planner_cls.return_value = mock_test_planner
        mock_code_generator_cls.return_value = mock_code_generator
        mock_prompt_moderator_cls.return_value = mock_prompt_moderator
        mock_bash_tool_cls.return_value = mock_bash_tool
        
        # Pre-planning default setup
        pre_plan_data = {
            "original_request": "",
            "feature_groups": [{"group_name": "fg", "features": []}],
            "complexity_score": 50.0,
            "complexity_breakdown": {},
            "is_complex": False,
        }
        mock_pre_planning_workflow.return_value = (True, pre_plan_data)
        mock_regen_pre_planning.return_value = pre_plan_data
        
        # Set up run_command for bash tool
        mock_bash_tool.run_command.return_value = (0, "Success output")
        
        # Create the coordinator with mocked components
        coordinator = Coordinator(config=mock_config)
        
        # Patch internal methods that interact with the filesystem
        coordinator._apply_changes_and_manage_dependencies = MagicMock(return_value=True)
        coordinator._run_validation_phase = MagicMock(return_value=(True, "validation", "All checks passed"))
        coordinator._finalize_task = MagicMock(return_value={"status": "completed"})
        
        # Return the coordinator with all its mocks for testing
        yield coordinator, {
            'scratchpad': mock_scratchpad,
            'progress_tracker': mock_progress_tracker,
            'task_state_manager': mock_task_state_manager,
            'pre_planning_workflow': mock_pre_planning_workflow,
            'regenerate_pre_planning_with_modifications': mock_regen_pre_planning,
            'planner': mock_planner,
            'test_planner': mock_test_planner,
            'code_generator': mock_code_generator,
            'prompt_moderator': mock_prompt_moderator,
            'bash_tool': mock_bash_tool
        }


class TestFeatureImplementation:
    """Tests for feature implementation tasks."""
    
    def test_basic_feature_implementation(self, mock_coordinator):
        """Test implementing a basic feature."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for feature implementation
        mock_responses = MOCK_LLM_RESPONSES["feature_implementation"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Run the task
        task_description = "Implement user authentication"
        result = coordinator.execute_task(task_description)
        
        # Verify success
        assert result["success"] is True
        assert "phases" in result
        assert "planning" in result["phases"]
        assert "implementation" in result["phases"]
        
        # Verify correct plan was created
        assert mocks['planner'].create_plan.call_count == 1
        assert mocks['planner'].create_plan.call_args[0][0] == task_description
        
        # Verify code generation was called correctly
        assert mocks['code_generator'].generate_code.call_count == 1
        
        # Verify changes were applied
        assert coordinator._apply_changes_and_manage_dependencies.call_count == 1
        assert coordinator._run_validation_phase.call_count == 1
        
        # Verify task was finalized
        assert coordinator._finalize_task.call_count == 1


class TestRefactoring:
    """Tests for code refactoring tasks."""
    
    def test_code_refactoring(self, mock_coordinator):
        """Test a code refactoring task."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for refactoring task
        mock_responses = MOCK_LLM_RESPONSES["refactoring"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Run the task
        task_description = "Refactor the code to improve organization"
        result = coordinator.execute_task(task_description)
        
        # Verify success
        assert result["success"] is True
        assert "phases" in result
        assert "planning" in result["phases"]
        assert "implementation" in result["phases"]
        
        # Verify planning reflected refactoring approach
        plan = mocks['planner'].create_plan.call_args[0][0]
        assert task_description in plan or task_description in str(mocks['planner'].create_plan.call_args)
        
        # Verify code generation produced refactored code
        assert "utils/common.py" in result["changes"]


class TestDebugging:
    """Tests for debugging tasks."""
    
    def test_debug_auth_issue(self, mock_coordinator):
        """Test debugging an authentication issue."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for debugging task
        mock_responses = MOCK_LLM_RESPONSES["debugging"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Run the task
        task_description = "Debug authentication token expiration"
        result = coordinator.execute_task(task_description)
        
        # Verify success
        assert result["success"] is True
        
        # Verify debugging approach in planning
        debug_plan = mocks['planner'].create_plan.call_args[0][0]
        assert task_description in debug_plan or task_description in str(mocks['planner'].create_plan.call_args)
        
        # Verify bug fix was generated
        assert "services/auth_service.py" in result["changes"]
        
        # Verify changes were validated
        assert coordinator._run_validation_phase.call_count == 1


class TestMultiStepTask:
    """Tests for complex multi-step tasks."""
    
    def test_data_pipeline_implementation(self, mock_coordinator):
        """Test implementing a multi-component data pipeline."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for multi-step task
        mock_responses = MOCK_LLM_RESPONSES["multi_step"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Simulate higher complexity
        pre_plan = mocks['pre_planning_workflow'].return_value[1].copy()
        pre_plan['complexity_score'] = 80.0
        mocks['pre_planning_workflow'].return_value = (True, pre_plan)
        
        # Run the task
        task_description = "Create a data analytics pipeline"
        result = coordinator.execute_task(task_description)
        
        # Verify success
        assert result["success"] is True
        
        # Verify complexity assessment
        pre_planning = result["phases"]["pre_planning"]
        assert pre_planning["complexity_score"] == 80.0
        
        # Verify planned pipeline components
        plan = mocks['planner'].create_plan.call_args[0][0]
        assert task_description in plan or task_description in str(mocks['planner'].create_plan.call_args)
        
        # Verify component implementation
        assert "pipeline/collector.py" in result["changes"]


class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    def test_planning_failure(self, mock_coordinator):
        """Test handling a planning failure."""
        coordinator, mocks = mock_coordinator
        
        # Set up planner to fail
        mocks['planner'].create_plan.side_effect = Exception("Planning error")
        
        # Run the task
        task_description = "Implement feature that will fail planning"
        result = coordinator.execute_task(task_description)
        
        # Verify failure was handled
        assert result["success"] is False
        assert "error" in result
        assert "Planning error" in result["error"]
        assert "planning" in result["phases"]
        assert result["phases"]["planning"]["status"] == "error"
    
    def test_code_generation_failure(self, mock_coordinator):
        """Test handling a code generation failure."""
        coordinator, mocks = mock_coordinator
        
        # Set up successful planning but failed code generation
        mocks['planner'].create_plan.return_value = "Test plan"
        mocks['code_generator'].generate_code.return_value = None
        
        # Run the task
        task_description = "Implement feature with code generation failure"
        result = coordinator.execute_task(task_description)
        
        # Verify failure was handled
        assert result["success"] is False
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert not result["phases"]["implementation"]["success"]
        
    def test_validation_failure(self, mock_coordinator):
        """Test handling a validation failure with recovery attempt."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks
        mocks['planner'].create_plan.return_value = "Test plan"
        mocks['code_generator'].generate_code.return_value = {"code": {"test.py": "print('test')"}}
        
        # First validation fails, second succeeds
        coordinator._run_validation_phase = MagicMock(side_effect=[
            (False, "lint", "Linting error"), 
            (True, "validation", "All checks passed")
        ])
        
        # Set up error context
        coordinator.error_context_manager = MagicMock()
        coordinator.error_context_manager.collect_error_context.return_value = "Error context"
        
        # Run the task
        task_description = "Implement feature with validation issues"
        result = coordinator.execute_task(task_description)
        
        # Verify recovery succeeded
        assert result["success"] is True
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert result["phases"]["implementation"]["success"]
        assert len(result["phases"]["implementation"]["attempts"]) == 2
        assert result["phases"]["implementation"]["attempts"][0]["validation"]["success"] is False
        assert result["phases"]["implementation"]["attempts"][1]["validation"]["success"] is True


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])