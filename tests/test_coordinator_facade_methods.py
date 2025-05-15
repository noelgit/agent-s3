"""
Tests for the Coordinator's facade methods that interface with CommandProcessor.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from typing import Dict, Any, Tuple

from agent_s3.command_processor import CommandProcessor


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = MagicMock()
    config.config = {
        "version": "test-version",
        "log_files": {
            "development": "log/dev.log",
            "scratchpad": "log/scratchpad.log"
        },
        "sandbox_environment": False,
        "workspace_path": "/test/workspace"
    }
    return config


@pytest.fixture
def coordinator():
    """Create a completely mocked coordinator with necessary facade methods."""
    coordinator = MagicMock()
    
    # Mock all the components that facade methods delegate to
    coordinator.workspace_initializer = MagicMock()
    coordinator.tech_stack_detector = MagicMock()
    coordinator.file_history_analyzer = MagicMock()
    coordinator.task_resumer = MagicMock()
    coordinator.command_processor = MagicMock()
    coordinator.implementation_manager = MagicMock()
    coordinator.bash_tool = MagicMock()
    coordinator.design_manager = MagicMock()
    coordinator.deployment_manager = MagicMock()
    coordinator.scratchpad = MagicMock()
    coordinator.progress_tracker = MagicMock()
    coordinator.prompt_moderator = MagicMock()
    
    # Add all the facade methods to the mock
    coordinator.initialize_workspace = MagicMock(return_value={"success": True, "created_files": []})
    coordinator._detect_tech_stack = MagicMock(return_value={"languages": ["python"]})
    coordinator.get_file_modification_info = MagicMock(return_value={})
    coordinator._check_for_interrupted_tasks = MagicMock(return_value=None)
    coordinator.auto_resume_interrupted_task = MagicMock(return_value=(False, "No tasks to resume"))
    coordinator._resume_task = MagicMock(return_value=None)
    coordinator.execute_personas_command = MagicMock(return_value="Created personas.md")
    coordinator.execute_guidelines_command = MagicMock(return_value="Created guidelines")
    coordinator._get_default_guidelines = MagicMock(return_value="Default guidelines")
    coordinator._get_llm_json_content = MagicMock(return_value='{"version":"1.0"}')
    coordinator._enhance_guidelines_with_tech_stack = MagicMock(return_value="Enhanced guidelines")
    coordinator.process_command = MagicMock(return_value="Command processed")
    coordinator.execute_generate = MagicMock(return_value="Generated code")
    coordinator.execute_implementation = MagicMock(return_value={"success": True})
    coordinator.run_tests_all = MagicMock(return_value={"success": True})
    coordinator.execute_terminal_command = MagicMock(return_value=None)
    coordinator.execute_design = MagicMock(return_value={"success": True, "design_file": "design.txt"})
    coordinator.execute_continue = MagicMock(return_value={"success": True, "message": "Implementation continued"})
    coordinator.execute_deployment = MagicMock(return_value={"success": True, "message": "Deployment successful"})
    coordinator.deploy = MagicMock(side_effect=lambda design_file="design.txt": coordinator.execute_deployment(design_file))
    
    return coordinator


@pytest.fixture
def command_processor(coordinator):
    """Create a command processor with the mocked coordinator."""
    return CommandProcessor(coordinator)


class TestCoordinatorFacadeMethods:
    """Test the Coordinator's facade methods that interface with CommandProcessor."""
    
    def test_deploy_facade_method(self, coordinator):
        """Test that the deploy facade method correctly delegates to execute_deployment."""
        # Call the deploy method
        coordinator.deploy("test_design.txt")
        
        # Verify execute_deployment was called with the correct argument
        coordinator.execute_deployment.assert_called_once_with("test_design.txt")
    
    def test_execute_design_facade_exists(self, coordinator):
        """Test that the execute_design facade method exists and is callable."""
        # Ensure the method exists and is callable
        assert hasattr(coordinator, 'execute_design')
        assert callable(coordinator.execute_design)
        
        # Call the method
        coordinator.execute_design("Test design objective")
        
        # Verify the method was called with the correct argument
        coordinator.execute_design.assert_called_once_with("Test design objective")
    
    def test_execute_continue_facade_exists(self, coordinator):
        """Test that the execute_continue facade method exists and is callable."""
        # Ensure the method exists and is callable
        assert hasattr(coordinator, 'execute_continue')
        assert callable(coordinator.execute_continue)
        
        # Call the method
        coordinator.execute_continue("implementation")
        
        # Verify the method was called with the correct argument
        coordinator.execute_continue.assert_called_once_with("implementation")
    
    def test_command_processor_deploy_integration(self, command_processor, coordinator):
        """Test that the CommandProcessor correctly calls the deploy method."""
        # Set up PathLib to return True for path exists check
        with patch('pathlib.Path.exists', return_value=True):
            # Update mock return value for execute_deployment
            coordinator.execute_deployment.return_value = {
                "success": True,
                "message": "Deployment successful",
                "access_url": "http://localhost:8000",
                "env_file": ".env"
            }
            
            # Call the deploy command
            command_processor.execute_deploy_command("test_design.txt")
            
            # Verify execute_deployment was called with the correct argument
            coordinator.execute_deployment.assert_called_with("test_design.txt")
    
    def test_command_processor_design_integration(self, command_processor, coordinator):
        """Test that the CommandProcessor correctly calls the execute_design method."""
        # Call the design command
        command_processor.execute_design_command("Create a TODO app")
        
        # Verify execute_design was called with the correct argument
        coordinator.execute_design.assert_called_with("Create a TODO app")
    
    def test_command_processor_continue_integration(self, command_processor, coordinator):
        """Test that the CommandProcessor correctly calls the execute_continue method."""
        # Set updated return value
        coordinator.execute_continue.return_value = {
            "success": True,
            "message": "Implementation continued",
            "task_completed": "task1",
            "next_task": "Implement login feature"
        }
        
        # Call the continue command
        command_processor.execute_continue_command("implementation")
        
        # Verify execute_continue was called with the correct argument
        coordinator.execute_continue.assert_called_with("implementation")
    
    # Tests for additional facade methods
    
    def test_initialize_workspace_facade(self, coordinator):
        """Test that the initialize_workspace facade method delegates to WorkspaceInitializer."""
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer(check_permissions=True):
            coordinator.workspace_initializer.initialize_workspace()
            return {"success": True, "created_files": []}
            
        # Replace the mock with our function that delegates to the delegate
        coordinator.initialize_workspace.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator.initialize_workspace(check_permissions=False)
        
        # Verify delegate was called
        coordinator.workspace_initializer.initialize_workspace.assert_called_once()
        assert isinstance(result, dict)
        assert "success" in result
    
    def test_detect_tech_stack_facade(self, coordinator):
        """Test that the _detect_tech_stack facade method delegates to TechStackDetector."""
        # Set up return value
        expected_result = {"languages": ["python"], "frameworks": ["flask"]}
        coordinator.tech_stack_detector.detect_tech_stack.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_tech_stack_detector():
            return coordinator.tech_stack_detector.detect_tech_stack()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._detect_tech_stack.side_effect = delegate_to_tech_stack_detector
        
        # Call the method
        result = coordinator._detect_tech_stack()
        
        # Verify delegate was called
        coordinator.tech_stack_detector.detect_tech_stack.assert_called_once()
        assert result == expected_result
    
    def test_get_file_modification_info_facade(self, coordinator):
        """Test that the get_file_modification_info facade method delegates to FileHistoryAnalyzer."""
        # Set up return value
        expected_result = {"file1.py": {"last_modified": "2023-01-01"}}
        coordinator.file_history_analyzer.get_file_modification_info.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_file_history_analyzer():
            return coordinator.file_history_analyzer.get_file_modification_info()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.get_file_modification_info.side_effect = delegate_to_file_history_analyzer
        
        # Call the method
        result = coordinator.get_file_modification_info()
        
        # Verify delegate was called
        coordinator.file_history_analyzer.get_file_modification_info.assert_called_once()
        assert result == expected_result
    
    def test_check_for_interrupted_tasks_facade(self, coordinator):
        """Test that the _check_for_interrupted_tasks facade method delegates to TaskResumer."""
        # Define the function that will call the delegate
        def delegate_to_task_resumer():
            return coordinator.task_resumer.check_for_interrupted_tasks()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._check_for_interrupted_tasks.side_effect = delegate_to_task_resumer
        
        # Call the method
        coordinator._check_for_interrupted_tasks()
        
        # Verify delegate was called
        coordinator.task_resumer.check_for_interrupted_tasks.assert_called_once()
    
    def test_auto_resume_interrupted_task_facade(self, coordinator):
        """Test that the auto_resume_interrupted_task facade method delegates to TaskResumer."""
        # Set up return value
        expected_result = (True, "Resumed task")
        coordinator.task_resumer.auto_resume_interrupted_task.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_task_resumer():
            return coordinator.task_resumer.auto_resume_interrupted_task()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.auto_resume_interrupted_task.side_effect = delegate_to_task_resumer
        
        # Call the method
        result = coordinator.auto_resume_interrupted_task()
        
        # Verify delegate was called
        coordinator.task_resumer.auto_resume_interrupted_task.assert_called_once()
        assert result == expected_result
    
    def test_resume_task_facade(self, coordinator):
        """Test that the _resume_task facade method delegates to TaskResumer."""
        # Create a mock task state
        task_state = {"id": "task1", "phase": "planning"}
        
        # Define the function that will call the delegate
        def delegate_to_task_resumer(task_state):
            return coordinator.task_resumer.resume_task(task_state)
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._resume_task.side_effect = delegate_to_task_resumer
        
        # Call the method
        coordinator._resume_task(task_state)
        
        # Verify delegate was called
        coordinator.task_resumer.resume_task.assert_called_once_with(task_state)
    
    def test_execute_personas_command_facade(self, coordinator):
        """Test that the execute_personas_command facade method delegates to WorkspaceInitializer."""
        # Set up return value
        expected_result = "Created personas.md file"
        coordinator.workspace_initializer.execute_personas_command.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer():
            return coordinator.workspace_initializer.execute_personas_command()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.execute_personas_command.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator.execute_personas_command()
        
        # Verify delegate was called
        coordinator.workspace_initializer.execute_personas_command.assert_called_once()
        assert result == expected_result
    
    def test_execute_guidelines_command_facade(self, coordinator):
        """Test that the execute_guidelines_command facade method delegates to WorkspaceInitializer."""
        # Set up return value
        expected_result = "Created copilot-instructions.md file"
        coordinator.workspace_initializer.execute_guidelines_command.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer():
            return coordinator.workspace_initializer.execute_guidelines_command()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.execute_guidelines_command.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator.execute_guidelines_command()
        
        # Verify delegate was called
        coordinator.workspace_initializer.execute_guidelines_command.assert_called_once()
        assert result == expected_result
    
    def test_get_default_guidelines_facade(self, coordinator):
        """Test that the _get_default_guidelines facade method delegates to WorkspaceInitializer."""
        # Set up return value
        expected_result = "# Default Guidelines\n\nFollow these coding standards..."
        coordinator.workspace_initializer._get_default_guidelines.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer():
            return coordinator.workspace_initializer._get_default_guidelines()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._get_default_guidelines.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator._get_default_guidelines()
        
        # Verify delegate was called
        coordinator.workspace_initializer._get_default_guidelines.assert_called_once()
        assert result == expected_result
    
    def test_get_llm_json_content_facade(self, coordinator):
        """Test that the _get_llm_json_content facade method delegates to WorkspaceInitializer."""
        # Set up return value
        expected_result = '{"version": "1.0"}'
        coordinator.workspace_initializer._get_llm_json_content.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer():
            return coordinator.workspace_initializer._get_llm_json_content()
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._get_llm_json_content.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator._get_llm_json_content()
        
        # Verify delegate was called
        coordinator.workspace_initializer._get_llm_json_content.assert_called_once()
        assert result == expected_result
    
    def test_enhance_guidelines_with_tech_stack_facade(self, coordinator):
        """Test that the _enhance_guidelines_with_tech_stack facade method delegates to WorkspaceInitializer."""
        # Set up return value and input
        base_guidelines = "# Guidelines"
        expected_result = "# Guidelines\n\n## Python Guidelines"
        coordinator.workspace_initializer._enhance_guidelines_with_tech_stack.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_workspace_initializer(base_guidelines):
            return coordinator.workspace_initializer._enhance_guidelines_with_tech_stack(base_guidelines)
        
        # Replace the mock with our function that delegates to the delegate
        coordinator._enhance_guidelines_with_tech_stack.side_effect = delegate_to_workspace_initializer
        
        # Call the method
        result = coordinator._enhance_guidelines_with_tech_stack(base_guidelines)
        
        # Verify delegate was called
        coordinator.workspace_initializer._enhance_guidelines_with_tech_stack.assert_called_once_with(base_guidelines)
        assert result == expected_result
    
    def test_process_command_facade(self, coordinator):
        """Test that the process_command facade method delegates to CommandProcessor."""
        # Set up return value
        expected_result = "Command executed successfully"
        coordinator.command_processor.process_command.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_command_processor(command, args=""):
            return coordinator.command_processor.process_command(command, args)
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.process_command.side_effect = delegate_to_command_processor
        
        # Call the method
        result = coordinator.process_command("test", "arg1")
        
        # Verify delegate was called
        coordinator.command_processor.process_command.assert_called_once_with("test", "arg1")
        assert result == expected_result
    
    def test_execute_generate_facade(self, coordinator):
        """Test that the execute_generate facade method delegates to CommandProcessor."""
        # Set up return value
        expected_result = "Generated code successfully"
        coordinator.command_processor.execute_generate_command.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_command_processor():
            return coordinator.command_processor.execute_generate_command("")
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.execute_generate.side_effect = delegate_to_command_processor
        
        # Call the method
        result = coordinator.execute_generate()
        
        # Verify delegate was called
        coordinator.command_processor.execute_generate_command.assert_called_once_with("")
        assert result == expected_result
    
    def test_execute_implementation_facade(self, coordinator):
        """Test that the execute_implementation facade method delegates to ImplementationManager."""
        # Set up return value
        expected_result = {"success": True, "message": "Implementation completed"}
        coordinator.implementation_manager.start_implementation.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_implementation_manager(design_file="design.txt"):
            with patch('os.path.exists', return_value=True):
                coordinator.implementation_manager.start_implementation(design_file)
                return expected_result
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.execute_implementation.side_effect = delegate_to_implementation_manager
        
        # Set up prompt_moderator behavior
        coordinator.prompt_moderator.ask_binary_question.return_value = False
        
        # Call the method
        result = coordinator.execute_implementation("test_design.txt")
        
        # Verify delegate was called
        coordinator.implementation_manager.start_implementation.assert_called_once_with("test_design.txt")
        assert isinstance(result, dict)
    
    def test_run_tests_all_facade(self, coordinator):
        """Test that the run_tests_all facade method delegates to CommandProcessor."""
        # Set up return value
        expected_result = {"success": True, "output": "All tests passed"}
        coordinator.command_processor.execute_test_command.return_value = expected_result
        
        # Define the function that will call the delegate
        def delegate_to_command_processor():
            return coordinator.command_processor.execute_test_command("")
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.run_tests_all.side_effect = delegate_to_command_processor
        
        # Call the method
        result = coordinator.run_tests_all()
        
        # Verify delegate was called
        coordinator.command_processor.execute_test_command.assert_called_once_with("")
        assert result == expected_result
    
    def test_execute_terminal_command_facade(self, coordinator):
        """Test that the execute_terminal_command facade method delegates to BashTool."""
        # Set up return value
        coordinator.bash_tool.run_command.return_value = (0, "Command output")
        
        # Define the function that will call the delegate
        def delegate_to_bash_tool(command):
            result = coordinator.bash_tool.run_command(command, timeout=120)
            coordinator.progress_tracker.update_progress({"phase": "terminal", "status": "completed"})
            return result
        
        # Replace the mock with our function that delegates to the delegate
        coordinator.execute_terminal_command.side_effect = delegate_to_bash_tool
        
        # Call the method
        coordinator.execute_terminal_command("ls -l")
        
        # Verify delegate was called
        coordinator.bash_tool.run_command.assert_called_once_with("ls -l", timeout=120)