"""Unit tests for the Planner module."""

import unittest
import os
import json
from unittest.mock import patch, MagicMock, mock_open

# Ensure agent_s3 is in the path or adjust imports accordingly
# This might require setting PYTHONPATH or modifying sys.path in a test runner setup
try:
    from agent_s3.planner import Planner
    from agent_s3.prompt_moderator import PromptModerator
    from agent_s3.config import Config # Needed for Planner init
    from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager, LogLevel # Needed for Planner init
    from agent_s3.progress_tracker import ProgressTracker # Needed for Planner init
except ImportError:
    # Add basic stubs if imports fail (e.g., in a restricted environment)
    print("Warning: Could not import full agent_s3 modules for testing. Using stubs.")
    class Planner:
        pass
    class PromptModerator:
        pass
    class Config:
        def __init__(self, path):
            self.config = {}
    class EnhancedScratchpadManager:
        def log(self, *args, **kwargs):
            pass
    ScratchpadManager = EnhancedScratchpadManager # Alias for backwards compatibility
    class ProgressTracker:
        def update_progress(self, *args):
            pass


# --- Mock Data ---

MOCK_PERSONAS_CONTENT = """
## Business Development Manager
Focuses on why.

## Expert Coder
Focuses on how.

## Reviewer
Focuses on consistency.

## Validator
Focuses on best practices.
"""

MOCK_LLM_RESPONSE_VALID = json.dumps({
    "discussion": "**BDM:** Why?\n**Coder:** How!",
    "plan": "# Plan\n1. Do this.\n2. Do that."
})

MOCK_LLM_RESPONSE_IN_BLOCK = f"```json\n{MOCK_LLM_RESPONSE_VALID}\n```"

MOCK_LLM_RESPONSE_INVALID_JSON = "{\"discussion\": \"...\", \"plan\": \"..." # Missing closing brace

MOCK_LLM_RESPONSE_MISSING_KEYS = json.dumps({"discuss": "...", "the_plan": "..."})

MOCK_CONFIG_DICT = {
    "max_retries": 1,
    "initial_backoff": 0.1,
    "failure_threshold": 5,
    "cooldown_period": 300,
    "project_root": "." # Assume project root is current dir for tests
}

# --- Test Class ---

class TestPlanner(unittest.TestCase):

    def setUp(self):
        """Set up test environment before each test."""
        # Mock Coordinator and its components
        self.mock_coordinator = MagicMock()
        self.mock_coordinator.config = MagicMock(spec=Config)
        self.mock_coordinator.config.config = MOCK_CONFIG_DICT
        self.mock_coordinator.scratchpad = MagicMock(spec=EnhancedScratchpadManager)
        self.mock_coordinator.progress_tracker = MagicMock(spec=ProgressTracker)
        self.mock_coordinator.prompt_moderator = MagicMock(spec=PromptModerator)
        self.mock_coordinator.code_analysis_tool = MagicMock()
        self.mock_coordinator.file_tool = MagicMock()
        self.mock_coordinator.router = MagicMock() # Mock the RouterAgent used by Planner

        # Patch _load_llm_config to avoid dependency on actual llm.json
        self.patcher_load_llm = patch('agent_s3.planner._load_llm_config', return_value={})
        self.mock_load_llm = self.patcher_load_llm.start()

        # Instantiate Planner with mocked Coordinator
        self.planner = Planner(coordinator=self.mock_coordinator)
        
        # Mock the new components added in our implementation
        self.planner.context_gatherer = MagicMock()
        self.planner.context_gatherer.gather_context.return_value = {}
        
        self.planner.persona_debate_manager = MagicMock()
        self.planner.persona_debate_manager._default_debate_template = "Debate Template"
        self.planner.persona_debate_manager.personas = [{"role": "Expert"}, {"role": "Critic"}]
        
        # Also assign the mocked router to the planner instance directly
        self.planner.router = self.mock_coordinator.router

    def tearDown(self):
        """Clean up after each test."""
        self.patcher_load_llm.stop()
        # Clean up any created files if necessary

    @patch("builtins.open", new_callable=mock_open, read_data=MOCK_PERSONAS_CONTENT)
    @patch("os.path.exists")
    def test_load_personas_success(self, mock_exists, mock_file):
        """Test loading personas successfully from a mock file."""
        # Simulate personas.md exists at the expected project root location
        # The path calculation goes ../ from planner.py, so mock that path.
        expected_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'personas.md'))
        mock_exists.side_effect = lambda path: path == expected_path

        personas = self.planner._load_personas()

        # Assertions
        self.assertEqual(len(personas), 4)
        self.assertIn("Business Development Manager", personas)
        self.assertIn("Expert Coder", personas)
        self.assertIn("Reviewer", personas)
        self.assertIn("Validator", personas)
        self.assertIn("Focuses on why.", personas["Business Development Manager"])
        self.assertIn("Focuses on how.", personas["Expert Coder"])
        mock_exists.assert_called_with(expected_path)
        mock_file.assert_called_once_with(expected_path, "r", encoding='utf-8')
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Successfully loaded 4 personas from " + expected_path)


    @patch("os.path.exists", return_value=False)
    def test_load_personas_not_found(self, mock_exists):
        """Test FileNotFoundError when personas.md is missing."""
        with self.assertRaises(FileNotFoundError):
            self.planner._load_personas()
        # Check logs if desired
        # self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Personas file not found...")


    def test_parse_debate_response_valid_json(self):
        """Test parsing a valid JSON response."""
        result = self.planner._parse_debate_response(MOCK_LLM_RESPONSE_VALID)
        self.assertIsNotNone(result)
        self.assertEqual(result["discussion"], "**BDM:** Why?\n**Coder:** How!")
        self.assertEqual(result["plan"], "# Plan\n1. Do this.\n2. Do that.")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Parsed JSON response directly.")

    def test_parse_debate_response_json_in_block(self):
        """Test parsing a JSON response enclosed in ```json block."""
        result = self.planner._parse_debate_response(MOCK_LLM_RESPONSE_IN_BLOCK)
        self.assertIsNotNone(result)
        self.assertEqual(result["discussion"], "**BDM:** Why?\n**Coder:** How!")
        self.assertEqual(result["plan"], "# Plan\n1. Do this.\n2. Do that.")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Parsed JSON response using ```json block.")


    def test_parse_debate_response_invalid_json(self):
        """Test parsing an invalid JSON response."""
        result = self.planner._parse_debate_response(MOCK_LLM_RESPONSE_INVALID_JSON)
        self.assertIsNone(result)
        self.mock_coordinator.scratchpad.log.assert_any_call(
            "Planner", 'Error: Failed to parse debate response into discussion and plan. Response: {"discussion": "...", "plan": "..."}...'
        )


    def test_parse_debate_response_missing_keys(self):
        """Test parsing JSON that is missing the required keys."""
        result = self.planner._parse_debate_response(MOCK_LLM_RESPONSE_MISSING_KEYS)
        self.assertIsNone(result)
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Warning: Direct JSON parse successful but missing 'discussion' or 'plan' keys.")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Error: Failed to parse debate response into discussion and plan. Response: {\"discuss\": \"...\", \"the_plan\": \"...\"}...")


    def test_parse_debate_response_empty(self):
        """Test parsing an empty response."""
        result = self.planner._parse_debate_response("")
        self.assertIsNone(result)
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Error parsing debate response: Received empty response.")


    # Tests for legacy confirm_and_potentially_modify_plan method have been removed
    # This method was part of the workflow using the simple system prompt, which has been removed


    # Tests for legacy create_plan method with simple system prompt have been removed
    # The create_plan method and related functionality has been removed from planner.py
    # The pre-planner to planner flow now exclusively uses planner_json_enforced.py with the extensive system prompt

if __name__ == '__main__':
    unittest.main()
