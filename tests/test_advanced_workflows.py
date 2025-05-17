"""
Tests for advanced agent workflows including refactoring and debugging tasks.

These tests evaluate the agent's ability to handle complex tasks that involve
understanding existing code, identifying issues, and making targeted improvements.
"""

import os
import pytest
import tempfile
import shutil
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

from agent_s3.coordinator import Coordinator
from tests.mock_responses.llm_responses import (
    REFACTORING_RESPONSES,
    DEBUGGING_RESPONSES
)


@pytest.fixture
def setup_test_files():
    """Create temporary test files that need to be refactored or debugged."""
    # Create a temporary directory for test files
    temp_dir = tempfile.mkdtemp()
    
    # Create test files that need work
    files = {
        # File with performance issues to be optimized
        "data_processor.py": """
        def process_large_dataset(data):
            # Inefficient implementation
            results = []
            for item in data:
                if item.get('value') > 100:
                    # Complex calculation
                    processed = {'id': item.get('id'), 'result': item.get('value') * 2}
                    results.append(processed)
            return results
        
        def get_statistics(data):
            # Calculate statistics inefficiently
            total = 0
            count = 0
            for item in data:
                total += item.get('value', 0)
                count += 1
            
            return {
                'average': total / count if count > 0 else 0,
                'count': count,
                'total': total
            }
        """,
        
        # File with a bug in the authentication system
        "auth_service.py": """
        import time
        
        class AuthService:
            def __init__(self):
                self.tokens = {}
                
            def generate_token(self, user_id):
                token = f"token_{user_id}_{int(time.time())}"
                # Bug: No expiration time is set
                self.tokens[token] = {"user_id": user_id}
                return token
                
            def validate_token(self, token):
                # Bug: No expiration check
                user_data = self.tokens.get(token)
                return user_data
                
            def invalidate_token(self, token):
                if token in self.tokens:
                    del self.tokens[token]
                    return True
                return False
        """
    }
    
    # Write the files
    for filename, content in files.items():
        file_path = os.path.join(temp_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)
    
    yield temp_dir
    
    # Clean up temporary directory
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_coordinator(setup_test_files):
    """Create a mocked coordinator for testing with advanced workflows."""
    # Get path to test files
    test_dir = setup_test_files
    
    # Create patches for key components
    with patch('agent_s3.coordinator.Config') as mock_config_cls, \
         patch('agent_s3.coordinator.EnhancedScratchpadManager') as mock_scratchpad_cls, \
         patch('agent_s3.coordinator.ProgressTracker') as mock_progress_tracker_cls, \
         patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow') as mock_preplan_workflow, \
         patch('agent_s3.pre_planner_json_enforced.regenerate_pre_planning_with_modifications') as mock_regen_preplan, \
         patch('agent_s3.coordinator.Planner') as mock_planner_cls, \
         patch('agent_s3.coordinator.CodeGenerator') as mock_code_generator_cls, \
         patch('agent_s3.coordinator.PromptModerator') as mock_prompt_moderator_cls, \
         patch('agent_s3.coordinator.TaskStateManager') as mock_task_state_manager_cls, \
         patch('agent_s3.coordinator.ErrorContextManager') as mock_error_context_cls, \
         patch('os.path.dirname') as mock_dirname, \
         patch('builtins.open', new_callable=MagicMock), \
         patch('agent_s3.tools.plan_validator.validate_pre_plan') as mock_validate_pre_plan:
        
        # Set up mock config
        mock_config = MagicMock()
        mock_config.config = {
            "max_attempts": 3,
            "complexity_threshold": 100.0,
            "sandbox_environment": False
        }
        mock_config.github_token = "fake-token"
        mock_config.host_os_type = "linux"
        mock_config.get_log_file_path.return_value = f"{test_dir}/logs/development.log"
        
        mock_config_cls.return_value = mock_config
        
        # Set up other mocks
        mock_scratchpad = MagicMock()
        mock_progress_tracker = MagicMock()
        mock_planner = MagicMock()
        mock_code_generator = MagicMock()
        mock_prompt_moderator = MagicMock()
        mock_task_state_manager = MagicMock()
        mock_error_context = MagicMock()
        
        # Set up class return values
        mock_scratchpad_cls.return_value = mock_scratchpad
        mock_progress_tracker_cls.return_value = mock_progress_tracker
        mock_planner_cls.return_value = mock_planner
        mock_code_generator_cls.return_value = mock_code_generator
        mock_prompt_moderator_cls.return_value = mock_prompt_moderator
        mock_task_state_manager_cls.return_value = mock_task_state_manager
        mock_error_context_cls.return_value = mock_error_context
        
        # Make dirname return the test directory
        mock_dirname.return_value = test_dir
        
        # Default pre-planning setup
        default_preplan = {
            "feature_groups": [
                {
                    "group_name": "Group",
                    "group_description": "desc",
                    "features": [
                        {
                            "name": "Feat",
                            "description": "desc",
                            "files_affected": [
                                f"{test_dir}/data_processor.py",
                                f"{test_dir}/auth_service.py",
                            ],
                            "test_requirements": {
                                "unit_tests": [],
                                "integration_tests": [],
                                "property_based_tests": [],
                                "acceptance_tests": [],
                                "test_strategy": {},
                            },
                            "dependencies": {"internal": [], "external": [], "feature_dependencies": []},
                            "risk_assessment": {},
                            "system_design": {},
                        }
                    ],
                    "risk_assessment": {},
                    "dependencies": {},
                }
            ],
            "complexity_score": 65.0,
        }
        mock_preplan_workflow.return_value = (True, default_preplan)
        mock_regen_preplan.return_value = default_preplan
        mock_validate_pre_plan.return_value = (True, {})
        
        # Create coordinator with mocks
        coordinator = Coordinator(config=mock_config)
        
        # Patch file operations
        coordinator._apply_changes_and_manage_dependencies = MagicMock(return_value=True)
        coordinator._run_validation_phase = MagicMock(return_value=(True, "validation", "All checks passed"))
        coordinator._finalize_task = MagicMock(return_value={"status": "completed"})
        
        # Return coordinator with its mocks
        yield coordinator, {
            'scratchpad': mock_scratchpad,
            'progress_tracker': mock_progress_tracker,
            'pre_plan_workflow': mock_preplan_workflow,
            'regen_pre_plan': mock_regen_preplan,
            'planner': mock_planner,
            'code_generator': mock_code_generator,
            'prompt_moderator': mock_prompt_moderator,
            'task_state_manager': mock_task_state_manager,
            'error_context': mock_error_context,
            'test_dir': test_dir
        }


class TestRefactoringWorkflows:
    """Tests for refactoring workflows."""
    
    def test_performance_optimization(self, mock_coordinator):
        """Test refactoring code for performance optimization."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for performance optimization
        mock_responses = REFACTORING_RESPONSES["performance_optimization"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Target file in the test directory
        test_dir = mocks['test_dir']
        target_file = f"{test_dir}/data_processor.py"
        plan = mocks['pre_plan_workflow'].return_value[1]
        plan['feature_groups'][0]['features'][0]['files_affected'] = [target_file]
        mocks['pre_plan_workflow'].return_value = (True, plan)
        
        # Execute task
        task_description = "Optimize the data processing code for better performance"
        result = coordinator.execute_task(task_description, {
            "impacted_files": [target_file],
            "performance_issues": True,
            "optimization_target": "speed"
        })
        
        # Verify results
        assert result["success"] is True
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert result["phases"]["implementation"]["success"]
        
        # Verify mocks were called correctly
        mocks['planner'].create_plan.assert_called_once()
        mocks['code_generator'].generate_code.assert_called_once()
        
        # Verify the context was used
        context_arg = mocks['planner'].create_plan.call_args[0][0]
        assert "performance" in context_arg or "performance" in str(mocks['planner'].create_plan.call_args)
    
    def test_code_organization_refactoring(self, mock_coordinator):
        """Test refactoring code for better organization."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for code organization refactoring
        mock_responses = REFACTORING_RESPONSES["code_organization"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Execute task
        task_description = "Refactor the code to improve organization and reduce duplication"
        result = coordinator.execute_task(task_description)
        
        # Verify results
        assert result["success"] is True
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert result["phases"]["implementation"]["success"]
        
        # Verify specific refactoring outputs
        assert "utils/common.py" in result["changes"]
        assert "exceptions.py" in result["changes"]


class TestDebuggingWorkflows:
    """Tests for debugging workflows."""
    
    def test_auth_bug_debugging(self, mock_coordinator):
        """Test debugging an authentication bug."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for auth bug debugging
        mock_responses = DEBUGGING_RESPONSES["auth_bug"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Target file in the test directory
        test_dir = mocks['test_dir']
        target_file = f"{test_dir}/auth_service.py"
        plan = mocks['pre_plan_workflow'].return_value[1]
        plan['feature_groups'][0]['features'][0]['files_affected'] = [target_file]
        mocks['pre_plan_workflow'].return_value = (True, plan)
        
        # Set up error context for debugging
        mocks['error_context'].collect_error_context.return_value = {
            "parsed_error": {
                "file_paths": [target_file],
                "line_numbers": [12],
                "error_message": "Token validation fails to check expiration",
                "error_type": "LogicError",
                "stack_trace": "No stack trace available"
            },
            "code_snippets": [
                {
                    "file_path": target_file,
                    "start_line": 10,
                    "end_line": 15,
                    "content": "def validate_token(self, token):\n    # Bug: No expiration check\n    user_data = self.tokens.get(token)\n    return user_data"
                }
            ],
            "analysis": "The token validation function does not check if the token has expired"
        }
        
        # Execute task
        task_description = "Debug authentication token issue: tokens are not expiring"
        result = coordinator.execute_task(task_description, {
            "bug_description": "Authentication tokens never expire",
            "impacted_files": [target_file],
            "error_category": "authentication"
        })
        
        # Verify results
        assert result["success"] is True
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert result["phases"]["implementation"]["success"]
        
        # Verify debugging approach
        assert mocks['error_context'].collect_error_context.call_count >= 1
        
        # Verify the fix addresses token expiration
        auth_token_file = [k for k in result["changes"].keys() if "auth" in k.lower()]
        assert len(auth_token_file) > 0
    
    def test_database_connection_debugging(self, mock_coordinator):
        """Test debugging database connection leaks."""
        coordinator, mocks = mock_coordinator
        
        # Set up mocks for database connection debugging
        mock_responses = DEBUGGING_RESPONSES["db_connection_bug"]
        mocks['planner'].create_plan.return_value = mock_responses["planning"]["create_plan"]
        mocks['code_generator'].generate_code.return_value = {"code": mock_responses["code_generation"]["code"]}
        
        # Execute task with context
        task_description = "Fix database connection leaks causing performance degradation"
        result = coordinator.execute_task(task_description, {
            "bug_description": "Database connections are not being properly closed, leading to connection pool exhaustion",
            "symptoms": "Performance degradation over time, eventual timeouts",
            "error_category": "database"
        })
        
        # Verify results
        assert result["success"] is True
        assert "phases" in result
        assert "planning" in result["phases"]
        assert "implementation" in result["phases"]
        
        # Verify output includes database connection management files
        assert "db/connection.py" in result["changes"]
        assert "db/pool_monitor.py" in result["changes"]


class TestMultiStepDebugging:
    """Tests for complex multi-step debugging workflows."""
    
    def test_complex_debugging_scenario(self, mock_coordinator):
        """Test a complex debugging scenario with multiple steps."""
        coordinator, mocks = mock_coordinator
        
        # We'll use debugging responses but customize them
        mock_responses = DEBUGGING_RESPONSES["auth_bug"]
        
        # Modify to include multiple files
        custom_plan = """
        # Debugging Plan: Fix System-Wide Authentication Issues
        
        ## Overview
        Address multiple issues in the authentication system including token expiration,
        session handling, and password validation.
        
        ## Root Cause Analysis
        1. Token validation doesn't check expiration
        2. Session cleanup is not performed properly
        3. Password validation has security vulnerabilities
        
        ## Steps
        1. Fix token validation with proper expiration checks
        2. Implement session timeout and cleanup
        3. Strengthen password validation
        4. Add comprehensive tests for all fixes
        
        ## Files to Modify
        - `auth_service.py` - Fix token validation
        - `session_manager.py` - Add session cleanup
        - `password_validator.py` - Strengthen validation
        - `tests/test_auth.py` - Add comprehensive tests
        """
        
        # Set up custom mock responses
        mocks['planner'].create_plan.return_value = custom_plan
        
        # Simulate multiple generation attempts with refinement
        mocks['code_generator'].generate_code.side_effect = [
            # First attempt - incomplete fix
            {"code": {"auth_service.py": "# Partial fix that doesn't address all issues"}},
            
            # Second attempt - complete fix
            {"code": {
                "auth_service.py": mock_responses["code_generation"]["code"]["auth/token.py"],
                "session_manager.py": """
                class SessionManager:
                    def __init__(self):
                        self.sessions = {}
                        self.cleanup_threshold = 3600  # 1 hour
                    
                    def create_session(self, user_id):
                        session_id = f"session_{user_id}_{int(time.time())}"
                        self.sessions[session_id] = {
                            "user_id": user_id,
                            "created_at": time.time(),
                            "last_activity": time.time()
                        }
                        return session_id
                    
                    def update_activity(self, session_id):
                        if session_id in self.sessions:
                            self.sessions[session_id]["last_activity"] = time.time()
                            return True
                        return False
                    
                    def cleanup_expired_sessions(self):
                        now = time.time()
                        expired = []
                        
                        for session_id, data in self.sessions.items():
                            if now - data["last_activity"] > self.cleanup_threshold:
                                expired.append(session_id)
                        
                        for session_id in expired:
                            del self.sessions[session_id]
                        
                        return len(expired)
                """,
                "password_validator.py": """
                import re
                
                def validate_password(password, min_length=8, require_special=True):
                    # Check length
                    if len(password) < min_length:
                        return False, f"Password must be at least {min_length} characters long"
                    
                    # Check for uppercase
                    if not re.search(r'[A-Z]', password):
                        return False, "Password must contain at least one uppercase letter"
                    
                    # Check for lowercase
                    if not re.search(r'[a-z]', password):
                        return False, "Password must contain at least one lowercase letter"
                    
                    # Check for digits
                    if not re.search(r'\\d', password):
                        return False, "Password must contain at least one digit"
                    
                    # Check for special characters
                    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                        return False, "Password must contain at least one special character"
                    
                    return True, "Password is valid"
                """
            }}
        ]
        
        # Set up to fail validation on first attempt, succeed on second
        coordinator._run_validation_phase = MagicMock(side_effect=[
            (False, "tests", "Tests failed: Authentication still has security issues"),
            (True, "validation", "All checks passed")
        ])
        
        # Execute task
        task_description = "Fix multiple issues in the authentication system"
        result = coordinator.execute_task(task_description, {
            "security_audit": True,
            "priority": "high",
            "issues": [
                "Token expiration not checked",
                "Sessions never timeout",
                "Weak password validation"
            ]
        })
        
        # Verify results
        assert result["success"] is True
        assert "phases" in result
        assert "implementation" in result["phases"]
        assert len(result["phases"]["implementation"]["attempts"]) == 2
        
        # Verify first attempt failed
        assert not result["phases"]["implementation"]["attempts"][0]["validation"]["success"]
        
        # Verify second attempt succeeded
        assert result["phases"]["implementation"]["attempts"][1]["validation"]["success"]
        
        # Verify all fixes are in place
        assert "auth_service.py" in result["changes"]
        assert "session_manager.py" in result["changes"]
        assert "password_validator.py" in result["changes"]


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])