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
    from agent_s3.scratchpad_manager import ScratchpadManager # Needed for Planner init
    from agent_s3.progress_tracker import ProgressTracker # Needed for Planner init
except ImportError:
    # Add basic stubs if imports fail (e.g., in a restricted environment)
    print("Warning: Could not import full agent_s3 modules for testing. Using stubs.")
    class Planner: pass
    class PromptModerator: pass
    class Config: def __init__(self, path): self.config = {}
    class ScratchpadManager: def log(self, *args): pass
    class ProgressTracker: def update_progress(self, *args): pass


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
        self.mock_coordinator.scratchpad = MagicMock(spec=ScratchpadManager)
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


    def test_create_debate_system_prompt(self):
        """Test the generation of the system prompt for the debate."""
        mock_personas = {
            "Persona A": "Persona A\nDescription A",
            "Persona B": "Persona B\nDescription B"
        }
        prompt = self.planner._create_debate_system_prompt(mock_personas)

        # Basic checks - more detailed checks could validate structure
        self.assertIn("You are an expert software development planner.", prompt)
        self.assertIn("--- Persona A ---", prompt)
        self.assertIn("Description A", prompt)
        self.assertIn("--- Persona B ---", prompt)
        self.assertIn("Description B", prompt)
        self.assertIn("INSTRUCTIONS:", prompt)
        self.assertIn("`discussion`: A single string", prompt)
        self.assertIn("`plan`: A string containing the detailed", prompt)
        self.assertIn("Example JSON Output Structure:", prompt)
        self.assertIn("```json", prompt) # Check for example format hint


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
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "Error: Failed to parse debate response into discussion and plan. Response: {\"discussion\": \"...\", \"plan\": \"..."...")


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


    @patch.object(Planner, 'generate_plan') # Mock generate_plan within the class
    def test_confirm_plan_user_approves(self, mock_generate_plan):
        """Test the confirmation flow when the user approves ('yes')."""
        initial_plan_data = {"discussion": "Discuss", "plan": "Plan v1"}
        original_request = "Test request"

        # Configure mock moderator to return 'yes'
        self.mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "yes"

        decision, final_plan = self.planner.confirm_and_potentially_modify_plan(
            initial_plan_data, original_request
        )

        # Assertions
        self.assertEqual(decision, "yes")
        self.assertEqual(final_plan, initial_plan_data)
        self.mock_coordinator.prompt_moderator.display_discussion_and_plan.assert_called_once_with("Discuss", "Plan v1")
        self.mock_coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with("Create a GitHub issue for this plan?")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "User approved plan for GitHub issue creation.")
        mock_generate_plan.assert_not_called() # Should not regenerate


    @patch.object(Planner, 'generate_plan')
    def test_confirm_plan_user_rejects(self, mock_generate_plan):
        """Test the confirmation flow when the user rejects ('no')."""
        initial_plan_data = {"discussion": "Discuss", "plan": "Plan v1"}
        original_request = "Test request"

        # Configure mock moderator to return 'no'
        self.mock_coordinator.prompt_moderator.ask_ternary_question.return_value = "no"

        decision, final_plan = self.planner.confirm_and_potentially_modify_plan(
            initial_plan_data, original_request
        )

        # Assertions
        self.assertEqual(decision, "no")
        self.assertIsNone(final_plan) # Should return None for plan data on rejection
        self.mock_coordinator.prompt_moderator.display_discussion_and_plan.assert_called_once_with("Discuss", "Plan v1")
        self.mock_coordinator.prompt_moderator.ask_ternary_question.assert_called_once_with("Create a GitHub issue for this plan?")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "User rejected plan. Aborting.")
        self.mock_coordinator.prompt_moderator.notify_user.assert_called_with("Plan rejected. No further actions will be taken.", level="info")
        mock_generate_plan.assert_not_called() # Should not regenerate


    @patch.object(Planner, 'generate_plan')
    def test_confirm_plan_user_modifies_then_approves(self, mock_generate_plan):
        """Test the flow: modify -> regenerate -> approve."""
        initial_plan_data = {"discussion": "Discuss v1", "plan": "Plan v1"}
        modified_plan_data = {"discussion": "Discuss v2", "plan": "Plan v2"}
        original_request = "Test request"
        modifications = "Make it better"

        # Configure mock moderator: first 'modify', then 'yes'
        self.mock_coordinator.prompt_moderator.ask_ternary_question.side_effect = ["modify", "yes"]
        # Configure mock moderator to return modification text
        self.mock_coordinator.prompt_moderator.ask_for_modification.return_value = modifications
        # Configure mock generate_plan to return the modified plan on the second call
        mock_generate_plan.return_value = (modified_plan_data, "Summary v2", {})

        decision, final_plan = self.planner.confirm_and_potentially_modify_plan(
            initial_plan_data, original_request
        )

        # Assertions
        self.assertEqual(decision, "yes") # Final decision is 'yes'
        self.assertEqual(final_plan, modified_plan_data) # Final plan is the modified one

        # Check calls
        self.assertEqual(self.mock_coordinator.prompt_moderator.display_discussion_and_plan.call_count, 2)
        self.mock_coordinator.prompt_moderator.display_discussion_and_plan.assert_any_call("Discuss v1", "Plan v1")
        self.mock_coordinator.prompt_moderator.display_discussion_and_plan.assert_any_call("Discuss v2", "Plan v2")

        self.assertEqual(self.mock_coordinator.prompt_moderator.ask_ternary_question.call_count, 2)
        self.mock_coordinator.prompt_moderator.ask_for_modification.assert_called_once_with("Please describe the changes you'd like to make to the plan:")

        # Check generate_plan was called once with modification context
        mock_generate_plan.assert_called_once()
        call_args = mock_generate_plan.call_args[0]
        self.assertIn(original_request, call_args[0])
        self.assertIn(modifications, call_args[0])
        self.assertIn("Previous Plan:\nPlan v1", call_args[0])

        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "User chose to modify the plan.")
        self.mock_coordinator.prompt_moderator.notify_user.assert_any_call("Re-generating plan based on your modifications...", level="info")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "User approved plan for GitHub issue creation.")


    @patch.object(Planner, 'generate_plan')
    def test_confirm_plan_user_modifies_regenerate_fails(self, mock_generate_plan):
        """Test the flow: modify -> regenerate fails -> re-prompt with original -> approve."""
        initial_plan_data = {"discussion": "Discuss v1", "plan": "Plan v1"}
        original_request = "Test request"
        modifications = "Make it better"

        # Configure mock moderator: first 'modify', then 'yes' on the second prompt
        self.mock_coordinator.prompt_moderator.ask_ternary_question.side_effect = ["modify", "yes"]
        self.mock_coordinator.prompt_moderator.ask_for_modification.return_value = modifications
        # Configure mock generate_plan to return None (failure)
        mock_generate_plan.return_value = (None, None, {})

        decision, final_plan = self.planner.confirm_and_potentially_modify_plan(
            initial_plan_data, original_request
        )

        # Assertions
        self.assertEqual(decision, "yes") # Final decision is 'yes'
        # IMPORTANT: Since regeneration failed, the user approves the *original* plan
        self.assertEqual(final_plan, initial_plan_data)

        # Check calls
        # Display should be called twice, both times with the *initial* plan data
        self.assertEqual(self.mock_coordinator.prompt_moderator.display_discussion_and_plan.call_count, 2)
        self.mock_coordinator.prompt_moderator.display_discussion_and_plan.assert_called_with("Discuss v1", "Plan v1") # Both calls show v1

        self.assertEqual(self.mock_coordinator.prompt_moderator.ask_ternary_question.call_count, 2)
        self.mock_coordinator.prompt_moderator.ask_for_modification.assert_called_once()

        # Check generate_plan was called once
        mock_generate_plan.assert_called_once()

        # Check notifications
        self.mock_coordinator.prompt_moderator.notify_user.assert_any_call("Re-generating plan based on your modifications...", level="info")
        self.mock_coordinator.prompt_moderator.notify_user.assert_any_call("Failed to regenerate the plan with modifications. Please review the previous plan again.", level="error")
        self.mock_coordinator.scratchpad.log.assert_any_call("Planner", "User approved plan for GitHub issue creation.")


# Add more tests as needed, e.g., for _gather_context, _generate_summary, retry logic

if __name__ == '__main__':
    unittest.main()

