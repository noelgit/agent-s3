"""
Unit tests for pre_planner_json_enforced module.

This module contains tests for the canonical pre-planning implementation that provides
robust JSON enforcement, validation, repair, and coordinator integration. The pre_planner_json_enforced
module is the primary implementation used throughout the system for pre-planning.
"""

import json
import logging
import os
import pytest
from unittest.mock import MagicMock, patch

from agent_s3.pre_planner_json_enforced import (
    get_json_system_prompt,
    get_json_user_prompt,
    get_openrouter_json_params,
    validate_json_schema,
    repair_json_structure,
    create_fallback_json,
    integrate_with_coordinator,
    _parse_structured_modifications,
    regenerate_pre_planning_with_modifications,
    JSONValidationError,
    pre_planning_workflow,
)
from agent_s3.json_utils import extract_json_from_text


class TestPrePlannerJsonEnforced:
    """Test class for pre_planner_json_enforced module."""

    def test_get_json_system_prompt(self):
        """Test that system prompt is non-empty and includes critical instructions."""
        prompt = get_json_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert "CRITICAL INSTRUCTION" in prompt
        assert "JSON format" in prompt
        assert "schema" in prompt

    def test_get_json_user_prompt(self):
        """Test that user prompt properly includes task description."""
        task = "Implement a new feature for user authentication"
        prompt = get_json_user_prompt(task)
        assert isinstance(prompt, str)
        assert task in prompt
        assert "structured data" in prompt

    def test_get_openrouter_json_params(self):
        """Test that OpenRouter parameters are correctly configured."""
        params = get_openrouter_json_params()
        assert isinstance(params, dict)
        assert "response_format" in params
        assert params["response_format"]["type"] == "json_object"
        assert params["temperature"] < 0.2  # Low temperature for consistent JSON

    def test_extract_json_from_text_with_code_block(self):
        """Test extracting JSON from markdown code blocks."""
        text = "Here is some JSON:\n```json\n{\"key\": \"value\"}\n```\nMore text."
        json_str = extract_json_from_text(text)
        assert json_str == '{\"key\": \"value\"}'
        
        # Test with code block without language specifier
        text = "Here is some JSON:\n```\n{\"key\": \"value\"}\n```\nMore text."
        json_str = extract_json_from_text(text)
        assert json_str == '{\"key\": \"value\"}'

    def test_extract_json_from_text_direct(self):
        """Test extracting JSON directly from text."""
        text = "Some text {\"key\": \"value\"} more text."
        json_str = extract_json_from_text(text)
        assert json_str == '{\"key\": \"value\"}'

    def test_extract_json_from_text_no_json(self):
        """Test extracting JSON from text with no valid JSON."""
        text = "Some text without any JSON."
        json_str = extract_json_from_text(text)
        assert json_str is None

    def test_validate_json_schema_valid(self):
        """Test schema validation with valid JSON."""
        valid_data = {
            "original_request": "Add user authentication",
            "features": [
                {
                    "name": "User Login",
                    "description": "Implement user login functionality",
                    "files_affected": ["auth.py", "login.py", "templates/login.html"],
                    "test_requirements": {
                        "unit_tests": [
                            {
                                "description": "Validate that create_user normalizes email addresses",
                                "target_element": "create_user",
                                "target_element_id": "create_user_function_id",
                                "inputs": ["user@EXAMPLE.com"],
                                "expected_outcome": "Email is normalized to lowercase"
                            },
                            {
                                "description": "Ensure calculate_discount returns zero for negative input",
                                "target_element": "calculate_discount",
                                "target_element_id": "calculate_discount_function_id",
                                "inputs": ["-10"],
                                "expected_outcome": "Return value is 0"
                            }
                        ],
                        "integration_tests": ["Flow: user signup → email verification → login",
                                             "API: product lookup returns correct pricing for multiple SKUs"],
                        "property_based_tests": [
                            {
                                "description": "Discount calculation should never exceed item price",
                                "target_element": "calculate_discount",
                                "target_element_id": "calculate_discount_function_id",
                                "input_generators": ["Random price values", "Random discount percentages"]
                            }
                        ],
                        "acceptance_tests": [
                            {
                                "given": "a logged-in user with an empty cart",
                                "when": "they add an item priced at $10",
                                "then": "the cart total is $10"
                            }
                        ],
                        "test_strategy": {
                            "coverage_goal": "80% line, 60% branch",
                            "ui_test_approach": "basic snapshot tests via driver"
                        }
                    },
                    "dependencies": {
                        "internal": ["user_model"],
                        "external": ["passlib"]
                    }
                }
            ]
        }
        is_valid, error = validate_json_schema(valid_data)
        assert is_valid is True
        assert error == ""

    def test_validate_json_schema_invalid_missing_key(self):
        """Test schema validation with missing required key."""
        invalid_data = {
            # Missing "original_request"
            "features": [],
            "complexity_score": 50,
            "complexity_breakdown": {}
        }
        is_valid, error = validate_json_schema(invalid_data)
        assert is_valid is False
        assert "Missing required" in error

    def test_validate_json_schema_invalid_type(self):
        """Test schema validation with wrong data type."""
        invalid_data = {
            "original_request": "Add authentication",
            "features": "Not a list",  # Wrong type
            "complexity_score": 50,
            "complexity_breakdown": {}
        }
        is_valid, error = validate_json_schema(invalid_data)
        assert is_valid is False
        assert "should be" in error

    def test_repair_json_structure(self):
        """Test JSON structure repair functionality."""
        # Create partial data with missing fields
        partial_data = {
            "original_request": "Add authentication",
            "features": [
                {
                    "name": "Auth",
                    # Missing fields will be added by repair function
                }
            ]
        }
        
        repaired = repair_json_structure(partial_data)
        
        # Check that missing fields were added
        assert "description" in repaired["features"][0]
        assert "files_affected" in repaired["features"][0]
        assert "test_requirements" in repaired["features"][0]
        assert "dependencies" in repaired["features"][0]
        assert "acceptance_tests" in repaired["features"][0]["test_requirements"]
        assert "test_strategy" in repaired["features"][0]["test_requirements"]
        
        # Validate the repaired structure
        is_valid, _ = validate_json_schema(repaired)
        assert is_valid is True

    def test_create_fallback_json(self):
        """Test fallback JSON creation."""
        request = "Add user authentication"
        fallback = create_fallback_json(request)
        
        assert fallback["original_request"] == request
        assert isinstance(fallback["features"], list)
        assert len(fallback["features"]) > 0
        assert "files_affected" in fallback["features"][0]
        
        # Validate the fallback structure
        is_valid, _ = validate_json_schema(fallback)
        assert is_valid is True

    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    @patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow')
    def test_integrate_with_coordinator(self, mock_workflow, mock_call):
        """Test integration with coordinator."""
        # Setup mock data
        task = "Implement user authentication"
        json_data = {
            "original_request": task,
            "features": [
                {
                    "name": "User Login",
                    "description": "Login functionality",
                    "files_affected": ["auth.py", "login.py", "templates/login.html"],
                    "test_requirements": {
                        "unit_tests": [
                            {
                                "description": "Validate that create_user normalizes email addresses",
                                "target_element": "create_user",
                                "target_element_id": "create_user_function_id",
                                "inputs": ["user@EXAMPLE.com"],
                                "expected_outcome": "Email is normalized to lowercase"
                            },
                            {
                                "description": "Ensure calculate_discount returns zero for negative input",
                                "target_element": "calculate_discount",
                                "target_element_id": "calculate_discount_function_id",
                                "inputs": ["-10"],
                                "expected_outcome": "Return value is 0"
                            }
                        ],
                        "integration_tests": ["Flow: user signup → email verification → login",
                                             "API: product lookup returns correct pricing for multiple SKUs"],
                        "property_based_tests": [
                            {
                                "description": "Discount calculation should never exceed item price",
                                "target_element": "calculate_discount",
                                "target_element_id": "calculate_discount_function_id",
                                "input_generators": ["Random price values", "Random discount percentages"]
                            }
                        ],
                        "acceptance_tests": [
                            {
                                "given": "a logged-in user with an empty cart",
                                "when": "they add an item priced at $10",
                                "then": "the cart total is $10"
                            }
                        ],
                        "test_strategy": {
                            "coverage_goal": "80% line, 60% branch",
                            "ui_test_approach": "basic snapshot tests via driver"
                        }
                    },
                    "dependencies": {
                        "internal": ["user_model"],
                        "external": ["auth_lib"]
                    }
                }
            ]
        }
        mock_workflow.return_value = (True, json_data)

        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.get_current_timestamp.return_value = "2025-01-01T00:00:00"
        mock_coordinator.config = MagicMock()
        mock_coordinator.config.config = {"pre_planning_mode": "json"}
        
        # Call the integration function
        result = integrate_with_coordinator(mock_coordinator, task, max_attempts=4)

        # Verify results
        assert result["success"] is True
        assert result["uses_enforced_json"] is False
        assert result["status"] == "completed"
        assert "test_requirements" in result
        assert "dependencies" in result
        assert "edge_cases" in result
        assert "is_complex" in result
        assert isinstance(result["is_complex"], bool)
        
        # Verify the function called the pre-planner with the right arguments
        # Context dict is passed, only check that the router agent and task are correct
        mock_workflow.assert_called_once()
        mock_call.assert_not_called()
        args, kwargs = mock_workflow.call_args
        assert args[0] == mock_coordinator.router_agent
        assert args[1] == task
        assert kwargs.get("max_attempts") == 4

    @patch('agent_s3.pre_planner_json_enforced.pre_planning_workflow')
    @patch('agent_s3.pre_planner_json_enforced.call_pre_planner_with_enforced_json')
    def test_integrate_with_coordinator_enforced_mode(self, mock_call, mock_workflow):
        """Ensure enforced JSON mode sets the flag correctly."""
        task = "Implement user auth"
        json_data = {"original_request": task, "feature_groups": []}
        mock_call.return_value = (True, json_data)

        coordinator = MagicMock()
        coordinator.get_current_timestamp.return_value = "2025-01-01T00:00:00"
        coordinator.config = MagicMock()
        coordinator.config.config = {"pre_planning_mode": "enforced_json"}

        result = integrate_with_coordinator(coordinator, task)

        assert result["success"] is True
        assert result["uses_enforced_json"] is True
        mock_call.assert_called_once_with(coordinator.router_agent, task)
        mock_workflow.assert_not_called()

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    @patch('agent_s3.pre_planner_json_enforced.get_json_system_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_json_user_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_openrouter_json_params')
    def test_call_pre_planner_with_enforced_json_success(self, mock_params, mock_user_prompt, 
                                                        mock_system_prompt, mock_process):
        """Test successful call to pre-planner with enforced JSON."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_user_prompt.return_value = "User prompt"
        mock_params.return_value = {"temperature": 0.1}
        
        # Setup success response
        json_data = {"original_request": "Test", "features": [], "complexity_score": 50, "complexity_breakdown": {}}
        mock_process.return_value = (True, json_data)
        
        # Setup mock router agent
        mock_agent = MagicMock()
        mock_agent.call_llm_by_role.return_value = "{}"
        
        # Call the function
        success, data = pre_planning_workflow(mock_agent, "Test request")
        
        # Verify results
        assert success is True
        assert data == json_data
        assert mock_agent.call_llm_by_role.call_count == 1  # Only called once due to success

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    @patch('agent_s3.pre_planner_json_enforced.get_json_system_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_json_user_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_openrouter_json_params')
    def test_call_pre_planner_with_enforced_json_retry(self, mock_params, mock_user_prompt, 
                                                       mock_system_prompt, mock_process):
        """Test retry mechanism for pre-planner with enforced JSON."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_user_prompt.return_value = "User prompt"
        mock_params.return_value = {"temperature": 0.1}
        
        # Setup failure then success responses
        json_data = {"original_request": "Test", "features": [], "complexity_score": 50, "complexity_breakdown": {}}
        mock_process.side_effect = [(False, None), (True, json_data)]
        
        # Setup mock router agent
        mock_agent = MagicMock()
        mock_agent.call_llm_by_role.return_value = "{}"
        
        # Call the function
        success, data = pre_planning_workflow(mock_agent, "Test request")
        
        # Verify results
        assert success is True
        assert data == json_data
        assert mock_agent.call_llm_by_role.call_count == 2  # Called twice due to retry

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    @patch('agent_s3.pre_planner_json_enforced.get_json_system_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_json_user_prompt')
    @patch('agent_s3.pre_planner_json_enforced.get_openrouter_json_params')
    @patch('agent_s3.pre_planner_json_enforced.create_fallback_json')
    def test_call_pre_planner_with_enforced_json_fallback(self, mock_fallback, mock_params, 
                                                          mock_user_prompt, mock_system_prompt, 
                                                          mock_process):
        """Test fallback mechanism for pre-planner with enforced JSON."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_user_prompt.return_value = "User prompt"
        mock_params.return_value = {"temperature": 0.1}
        
        # Setup failure responses
        mock_process.return_value = (False, None)
        
        # Setup fallback to raise JSONValidationError
        mock_fallback.side_effect = JSONValidationError("JSON validation failed")
        
        # Setup mock router agent
        mock_agent = MagicMock()
        mock_agent.call_llm_by_role.return_value = "{}"
        
        # Call the function and expect an exception
        with pytest.raises(JSONValidationError):
            pre_planning_workflow(mock_agent, "Test request")
        
        # Verify results
        assert mock_agent.call_llm_by_role.call_count == 2  # Both attempts fail
        mock_fallback.assert_called_once_with("Test request")

    def test_parse_structured_modifications_with_structured_format(self):
        """Test parsing of structured modifications with the STRUCTURED_MODIFICATIONS format."""
        modification_text = """STRUCTURED_MODIFICATIONS:
Modification 1:
  COMPONENT: implementation_plan
  LOCATION: src/database/user_repository.py
  CHANGE_TYPE: add
  DESCRIPTION: Add error handling for database connection failures

Modification 2:
  COMPONENT: tests
  LOCATION: test_user_auth.py
  CHANGE_TYPE: change
  DESCRIPTION: Use mock database connection instead of real one

RAW_INPUT:
COMPONENT: implementation_plan
LOCATION: src/database/user_repository.py
CHANGE_TYPE: add
DESCRIPTION: Add error handling for database connection failures
---
COMPONENT: tests
LOCATION: test_user_auth.py
CHANGE_TYPE: change
DESCRIPTION: Use mock database connection instead of real one
"""
        result = _parse_structured_modifications(modification_text)
        
        assert len(result) == 2
        assert result[0]["COMPONENT"] == "implementation_plan"
        assert result[0]["LOCATION"] == "src/database/user_repository.py"
        assert result[0]["CHANGE_TYPE"] == "add"
        assert result[0]["DESCRIPTION"] == "Add error handling for database connection failures"
        
        assert result[1]["COMPONENT"] == "tests"
        assert result[1]["LOCATION"] == "test_user_auth.py"
        assert result[1]["CHANGE_TYPE"] == "change"
        assert result[1]["DESCRIPTION"] == "Use mock database connection instead of real one"

    def test_parse_structured_modifications_with_raw_format(self):
        """Test parsing of structured modifications with the raw format."""
        modification_text = """COMPONENT: implementation_plan
LOCATION: src/auth/login.py
CHANGE_TYPE: change
DESCRIPTION: Fix password hashing implementation to use stronger algorithm

---

COMPONENT: tests
LOCATION: test_login.py
CHANGE_TYPE: add
DESCRIPTION: Add test case for password reset functionality
"""
        result = _parse_structured_modifications(modification_text)
        
        assert len(result) == 2
        assert result[0]["COMPONENT"] == "implementation_plan"
        assert result[0]["LOCATION"] == "src/auth/login.py"
        assert result[0]["CHANGE_TYPE"] == "change"
        assert result[0]["DESCRIPTION"] == "Fix password hashing implementation to use stronger algorithm"
        
        assert result[1]["COMPONENT"] == "tests"
        assert result[1]["LOCATION"] == "test_login.py"
        assert result[1]["CHANGE_TYPE"] == "add"
        assert result[1]["DESCRIPTION"] == "Add test case for password reset functionality"

    def test_parse_structured_modifications_with_incomplete_data(self):
        """Test parsing of structured modifications with incomplete data."""
        modification_text = """COMPONENT: implementation_plan
CHANGE_TYPE: change
DESCRIPTION: Fix password hashing implementation

---

COMPONENT: tests
LOCATION: test_login.py
DESCRIPTION: Add test case for password reset
"""
        result = _parse_structured_modifications(modification_text)
        
        # Should be empty because both modifications are missing required fields
        assert len(result) == 0

    def test_parse_structured_modifications_with_unstructured_data(self):
        """Test parsing of completely unstructured modifications."""
        modification_text = """Please add error handling for database connections and fix the password hashing algorithm."""
        result = _parse_structured_modifications(modification_text)
        
        # Should be empty because there's no structure
        assert len(result) == 0

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_regenerate_pre_planning_with_structured_modifications(self, mock_process):
        """Test regeneration of pre-planning with structured modifications."""
        # Setup mock router agent
        mock_agent = MagicMock()
        mock_agent.call_llm_by_role.return_value = "{}"
        
        # Setup mock process_response
        json_data = {
            "original_request": "Test request",
            "feature_groups": [{
                "group_name": "Authentication",
                "group_description": "User authentication features",
                "features": [{
                    "name": "User Login",
                    "description": "Updated with error handling",
                    "files_affected": ["auth.py", "login.py"],
                    "test_requirements": {},
                    "dependencies": {},
                    "risk_assessment": {},
                    "system_design": "Updated design with error handling"
                }]
            }]
        }
        mock_process.return_value = (True, json_data)
        
        # Original results
        original_results = {
            "original_request": "Test request",
            "feature_groups": [{
                "group_name": "Authentication",
                "group_description": "User authentication features",
                "features": [{
                    "name": "User Login",
                    "description": "Basic login functionality",
                    "files_affected": ["auth.py", "login.py"],
                    "test_requirements": {},
                    "dependencies": {},
                    "risk_assessment": {},
                    "system_design": "Original design"
                }]
            }]
        }
        
        # Structured modification
        modification_text = """STRUCTURED_MODIFICATIONS:
Modification 1:
  COMPONENT: implementation_plan
  LOCATION: auth.py
  CHANGE_TYPE: change
  DESCRIPTION: Add error handling for connection failures

RAW_INPUT:
COMPONENT: implementation_plan
LOCATION: auth.py
CHANGE_TYPE: change
DESCRIPTION: Add error handling for connection failures
"""
        
        # Call the function
        result = regenerate_pre_planning_with_modifications(mock_agent, original_results, modification_text)
        
        # Verify the LLM was called with structured format in the prompt
        call_args = mock_agent.call_llm_by_role.call_args[1]
        prompt = call_args["user_prompt"]
        
        # Check that the prompt includes structured format information
        assert "Modification Request" in prompt
        assert "COMPONENT: implementation_plan" in prompt
        assert "LOCATION: auth.py" in prompt
        assert "CHANGE_TYPE: change" in prompt
        
        # Verify the result
        assert result == json_data

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_pre_planning_workflow_respects_env_max_clarifications(self, mock_process):
        """Ensure MAX_CLARIFICATION_ROUNDS limits clarification prompts."""
        router = MagicMock()
        router.call_llm_by_role.return_value = "{}"

        mock_process.side_effect = [
            ("question", {"question": "Q1?"}),
            ("question", {"question": "Q2?"}),
            (True, {"original_request": "Task", "features": []})
        ]

        with patch.dict(os.environ, {"MAX_CLARIFICATION_ROUNDS": "1"}), patch('builtins.input', return_value='A1') as mock_input:
            success, data = pre_planning_workflow(router, "Task")

        assert success is True
        assert data == {"original_request": "Task", "features": []}
        assert mock_input.call_count == 1

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_pre_planning_workflow_appends_clarification_to_file(self, mock_process, tmp_path):
        """Ensure clarification round data is appended to the progress log file."""
        router = MagicMock()
        router.call_llm_by_role.return_value = "{}"

        log_file = tmp_path / "progress_log.jsonl"
        logger = logging.getLogger("TestProgressTracker")
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_file, encoding="utf-8")
        logger.addHandler(handler)

        with patch('agent_s3.pre_planner_json_enforced.progress_tracker.logger', logger):
            mock_process.side_effect = [
                ("question", {"question": "Need more info?"}),
                (True, {"original_request": "Task", "features": []})
            ]
            with patch('builtins.input', return_value='Here you go'):
                success, data = pre_planning_workflow(router, "Task")

        assert success is True
        assert data == {"original_request": "Task", "features": []}

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        log_entry = json.loads(lines[0])
        assert log_entry["phase"] == "pre-planning clarification"
        assert log_entry["question"] == "Need more info?"
        assert log_entry["answer"] == "Here you go"

        # Clean up the file handler to avoid ResourceWarning for unclosed files
        logger.removeHandler(handler)
        handler.close()

    @patch('agent_s3.pre_planner_json_enforced.progress_tracker.logger')
    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_pre_planning_workflow_logs_single_clarification(self, mock_process, mock_logger):
        """Ensure a clarification round is logged to progress_log.jsonl."""
        router = MagicMock()
        router.call_llm_by_role.return_value = "{}"

        mock_process.side_effect = [
            ("question", {"question": "Need more info?"}),
            (True, {"original_request": "Task", "features": []})
        ]

        with patch('builtins.input', return_value='Here you go'):
            success, data = pre_planning_workflow(router, "Task")

        assert success is True
        assert data == {"original_request": "Task", "features": []}
        mock_logger.info.assert_called_once()
        log_entry = json.loads(mock_logger.info.call_args[0][0])
        assert log_entry["phase"] == "pre-planning clarification"
        assert log_entry["question"] == "Need more info?"
        assert log_entry["answer"] == "Here you go"

    @patch('agent_s3.pre_planner_json_enforced.progress_tracker.logger')
    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_pre_planning_workflow_logs_multiple_clarifications(self, mock_process, mock_logger):
        """Multiple clarification rounds should each be logged."""
        router = MagicMock()
        router.call_llm_by_role.return_value = "{}"

        mock_process.side_effect = [
            ("question", {"question": "Q1?"}),
            ("question", {"question": "Q2?"}),
            (True, {"original_request": "Task", "features": []})
        ]

        with patch('builtins.input', side_effect=['A1', 'A2']):
            success, data = pre_planning_workflow(router, "Task")

        assert success is True
        assert mock_logger.info.call_count == 2
        first = json.loads(mock_logger.info.call_args_list[0].args[0])
        second = json.loads(mock_logger.info.call_args_list[1].args[0])
        assert first["question"] == "Q1?"
        assert first["answer"] == "A1"
        assert second["question"] == "Q2?"
        assert second["answer"] == "A2"

    @patch('agent_s3.pre_planner_json_enforced.process_response')
    def test_regenerate_pre_planning_with_unstructured_modifications(self, mock_process):
        """Test regeneration of pre-planning with unstructured modifications."""
        # Setup mock router agent
        mock_agent = MagicMock()
        mock_agent.call_llm_by_role.return_value = "{}"
        
        # Setup mock process_response
        json_data = {
            "original_request": "Test request",
            "feature_groups": [{
                "group_name": "Authentication",
                "group_description": "User authentication features",
                "features": [{
                    "name": "User Login",
                    "description": "Updated with better error handling",
                    "files_affected": ["auth.py", "login.py"],
                    "test_requirements": {},
                    "dependencies": {},
                    "risk_assessment": {},
                    "system_design": "Updated design"
                }]
            }]
        }
        mock_process.return_value = (True, json_data)
        
        # Original results
        original_results = {
            "original_request": "Test request",
            "feature_groups": [{
                "group_name": "Authentication",
                "group_description": "User authentication features",
                "features": [{
                    "name": "User Login",
                    "description": "Basic login functionality",
                    "files_affected": ["auth.py", "login.py"],
                    "test_requirements": {},
                    "dependencies": {},
                    "risk_assessment": {},
                    "system_design": "Original design"
                }]
            }]
        }
        
        # Unstructured modification
        modification_text = "Please improve the error handling in the auth system."
        
        # Call the function
        result = regenerate_pre_planning_with_modifications(mock_agent, original_results, modification_text)
        
        # Verify the LLM was called with unstructured format in the prompt
        call_args = mock_agent.call_llm_by_role.call_args[1]
        prompt = call_args["user_prompt"]
        
        # Check that the prompt includes modification text
        assert "Modification Request" in prompt
        assert modification_text in prompt
        
        # Verify the result
        assert result == json_data

