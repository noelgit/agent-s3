"""Tests for the WorkspaceInitializer component."""

import pytest
from unittest.mock import MagicMock, patch

from agent_s3.workspace_initializer import WorkspaceInitializer
from agent_s3.config import Config

class TestWorkspaceInitializer:
    """Tests for the WorkspaceInitializer class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock(spec=Config)
        config.config = {"workspace_path": "."}
        return config

    @pytest.fixture
    def mock_file_tool(self):
        """Create a mock file tool."""
        file_tool = MagicMock()
        file_tool.write_file = MagicMock(return_value=True)
        return file_tool

    @pytest.fixture
    def mock_scratchpad(self):
        """Create a mock scratchpad."""
        scratchpad = MagicMock()
        scratchpad.log = MagicMock()
        return scratchpad

    @pytest.fixture
    def mock_prompt_moderator(self):
        """Create a mock prompt moderator."""
        prompt_moderator = MagicMock()
        prompt_moderator.notify_user = MagicMock()
        return prompt_moderator

    @pytest.fixture
    def workspace_initializer(self, mock_config, mock_file_tool, mock_scratchpad,
         mock_prompt_moderator):        """Create a WorkspaceInitializer instance with mocks."""
        return WorkspaceInitializer(
            config=mock_config,
            file_tool=mock_file_tool,
            scratchpad=mock_scratchpad,
            prompt_moderator=mock_prompt_moderator,
            tech_stack=None
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.mkdir')
    def test_initialize_workspace_creates_directories(self, mock_mkdir, mock_exists,
         workspace_initializer):        """Test that initialize_workspace creates the .github directory."""
        # Setup
        mock_exists.return_value = True  # README exists

        # Exercise
        workspace_initializer.initialize_workspace()

        # Verify
        mock_mkdir.assert_called_with(exist_ok=True)

    def test_initialize_workspace_validates_readme(self, workspace_initializer,
         mock_prompt_moderator):        """Test that initialize_workspace validates README.md."""
        # Setup
        workspace_initializer.readme_file = MagicMock()
        workspace_initializer.readme_file.exists.return_value = False

        # Exercise
        workspace_initializer.initialize_workspace()

        # Verify
        assert workspace_initializer.is_workspace_valid is False
        assert workspace_initializer.validation_failure_reason == "README.md not found"
        mock_prompt_moderator.notify_user.assert_called_once()

    def test_initialize_workspace_creates_personas(self, workspace_initializer, mock_file_tool):
        """Test that initialize_workspace creates personas.md if it doesn't exist."""
        # Setup
        workspace_initializer.readme_file = MagicMock()
        workspace_initializer.readme_file.exists.return_value = True

        personas_path = MagicMock()
        personas_path.exists.return_value = False
        workspace_initializer.workspace_path = MagicMock()
        workspace_initializer.workspace_path.__truediv__.return_value = personas_path

        workspace_initializer.execute_personas_command = MagicMock(return_value="Success")

        # Exercise
        workspace_initializer.initialize_workspace()

        # Verify
        workspace_initializer.execute_personas_command.assert_called_once()

    def test_initialize_workspace_creates_guidelines(self, workspace_initializer, mock_file_tool):
        """Test that initialize_workspace creates copilot-instructions.md if it doesn't exist."""
        # Setup
        workspace_initializer.readme_file = MagicMock()
        workspace_initializer.readme_file.exists.return_value = True

        workspace_initializer.guidelines_file = MagicMock()
        workspace_initializer.guidelines_file.exists.return_value = False

        workspace_initializer.execute_guidelines_command = MagicMock(return_value="Success")

        # Exercise
        workspace_initializer.initialize_workspace()

        # Verify
        workspace_initializer.execute_guidelines_command.assert_called_once()

    def test_initialize_workspace_creates_llm_json(self, workspace_initializer, mock_file_tool):
        """Test that initialize_workspace creates llm.json if it doesn't exist."""
        # Setup
        workspace_initializer.readme_file = MagicMock()
        workspace_initializer.readme_file.exists.return_value = True

        workspace_initializer.llm_json_file = MagicMock()
        workspace_initializer.llm_json_file.exists.return_value = False

        workspace_initializer._ensure_llm_config = MagicMock(return_value=(True, "Success"))

        # Exercise
        workspace_initializer.initialize_workspace()

        # Verify
        workspace_initializer._ensure_llm_config.assert_called_once()

    def test_execute_personas_command(self, workspace_initializer, mock_file_tool):
        """Test that execute_personas_command creates the personas.md file."""
        # Exercise
        result = workspace_initializer.execute_personas_command()

        # Verify
        mock_file_tool.write_file.assert_called_once()
        assert "Successfully created personas.md" in result

    def test_execute_guidelines_command(self, workspace_initializer, mock_file_tool):
        """Test that execute_guidelines_command creates the copilot-instructions.md file."""
        # Exercise
        result = workspace_initializer.execute_guidelines_command()

        # Verify
        mock_file_tool.write_file.assert_called_once()
        assert "Successfully created copilot-instructions.md" in result

    def test_get_default_guidelines(self, workspace_initializer):
        """Test that _get_default_guidelines returns a non-empty string."""
        # Exercise
        guidelines = workspace_initializer._get_default_guidelines()

        # Verify
        assert guidelines
        assert isinstance(guidelines, str)
        assert len(guidelines) > 100  # Basic length check

    def test_get_llm_json_content(self, workspace_initializer):
        """Test that _get_llm_json_content returns a valid JSON string."""
        # Exercise
        llm_json = workspace_initializer._get_llm_json_content()

        # Verify
        assert llm_json
        assert isinstance(llm_json, str)
        assert "[" in llm_json and "]" in llm_json  # Basic JSON check

    def test_enhance_guidelines_with_tech_stack(self, workspace_initializer):
        """Test that _enhance_guidelines_with_tech_stack enhances guidelines with tech stack info."""
        # Setup
        base_guidelines = "# Test Guidelines"
        tech_stack = {
            "languages": [{"name": "Python", "version": "3.10"}],
            "frameworks": [{"name": "Flask", "version": "2.0.1"}]
        }
        workspace_initializer.tech_stack = tech_stack

        # Exercise
        enhanced = workspace_initializer._enhance_guidelines_with_tech_stack(base_guidelines)

        # Verify
        assert enhanced != base_guidelines
        assert "Python" in enhanced
        assert "Flask" in enhanced
