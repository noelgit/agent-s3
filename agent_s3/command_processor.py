"""Command Processor component for Agent-S3.

Processes and dispatches CLI commands to appropriate handlers.
"""

import os
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union, Callable

class CommandProcessor:
    """Processes and dispatches CLI commands to appropriate handlers."""

    def __init__(self, coordinator):
        """Initialize the CommandProcessor.

        Args:
            coordinator: Coordinator instance for accessing other components
        """
        self.coordinator = coordinator

        # Initialize command map
        self.command_map = {
            "init": self.execute_init_command,
            "plan": self.execute_plan_command,
            "generate": self.execute_generate_command,
            "test": self.execute_test_command,
            "debug": self.execute_debug_command,
            "terminal": self.execute_terminal_command,
            "personas": self.execute_personas_command,
            "guidelines": self.execute_guidelines_command,
            "design": self.execute_design_command,
            "implement": self.execute_implement_command,
            "continue": self.execute_continue_command,
            "deploy": self.execute_deploy_command,
            "help": self.execute_help_command,
            "config": self.execute_config_command,
            "reload-llm-config": self.execute_reload_llm_config_command,
            "explain": self.execute_explain_command,
            "request": self.execute_request_command,
            "tasks": self.execute_tasks_command,
            "clear": self.execute_clear_command,
            "db": self.execute_db_command,
        }
    
    def process_command(self, command: str, args: str = "") -> str:
        """Process a command with optional arguments.
        
        Args:
            command: Command name
            args: Optional command arguments
        
        Returns:
            Command result message
        """
        # Strip leading slash if present (for compatibility with /command syntax)
        if command.startswith('/'):
            command = command[1:]
        
        # Normalize to lowercase
        command = command.lower()
        
        # Log command execution
        self._log(f"Processing command: {command} with args: {args}")
        
        # Check if command exists in the map
        if command in self.command_map:
            try:
                # Execute command handler
                return self.command_map[command](args)
            except Exception as e:
                error_msg = f"Error executing command '{command}': {e}"
                self._log(error_msg, level="error")
                return error_msg
        else:
            return f"Unknown command: {command}. Type /help for available commands."
    
    def execute_init_command(self, args: str) -> str:
        """Execute the init command to initialize workspace.
        
        Args:
            args: Command arguments (unused)
            
        Returns:
            Command result message
        """
        self._log("Initializing workspace...")
        
        try:
            # Delegate to workspace_initializer if available, otherwise use coordinator
            if hasattr(self.coordinator, 'workspace_initializer'):
                success = self.coordinator.workspace_initializer.initialize_workspace()
            else:
                success = self.coordinator.initialize_workspace()
            
            if success:
                return "Workspace initialized successfully."
            else:
                return "Workspace initialization completed with warnings. Some features may be limited."
        except Exception as e:
            error_msg = f"Workspace initialization failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_plan_command(self, args: str) -> str:
        """Execute the plan command to generate a development plan.
        
        Args:
            args: Plan text/description
            
        Returns:
            Command result message
        """
        if not args.strip():
            return "Please provide a plan description."
        
        self._log(f"Generating plan for: {args}")
        
        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "plan",
                    "status": "started",
                    "input": args,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Generate plan
            if hasattr(self.coordinator, 'generate_plan'):
                plan = self.coordinator.generate_plan(args)
            elif hasattr(self.coordinator, 'planner') and hasattr(self.coordinator.planner, 'generate_plan'):
                plan = self.coordinator.planner.generate_plan(args)
            else:
                return "Plan generation not available."
            
            # Write plan to file
            plan_path = Path("plan.txt")
            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(plan)
            
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "plan",
                    "status": "completed",
                    "input": args,
                    "timestamp": datetime.now().isoformat()
                })
            
            return f"Plan generated and saved to {plan_path}"
        except Exception as e:
            error_msg = f"Plan generation failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "plan",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg
    
    def execute_generate_command(self, args: str) -> str:
        """Execute the generate command to generate code from a plan.
        
        Args:
            args: Optional arguments (unused, plan is read from plan.txt)
            
        Returns:
            Command result message
        """
        plan_file = Path("plan.txt")
        if not plan_file.exists():
            return "plan.txt not found. Please run /plan first."
        
        try:
            plan_text = plan_file.read_text(encoding="utf-8").strip()
            if not plan_text:
                return "plan.txt is empty. Please run /plan first."
            
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "generate",
                    "status": "started",
                    "timestamp": datetime.now().isoformat()
                })
            
            self._log("Executing code generation from plan.txt...")
            print("Executing code generation and workflow from plan.txt...")
            
            # Execute code generation
            if hasattr(self.coordinator, 'execute_generate'):
                self.coordinator.execute_generate()
            elif hasattr(self.coordinator, 'process_change_request'):
                self.coordinator.process_change_request(plan_text, skip_planning=True)
            else:
                return "Code generation functionality not available."
            
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "generate",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat()
                })
            
            return "Code generation completed."
        except Exception as e:
            error_msg = f"Code generation failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "generate",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg
    
    def execute_test_command(self, args: str) -> str:
        """Execute the test command to run tests.
        
        Args:
            args: Optional test filter arguments
            
        Returns:
            Command result message
        """
        print("Running all tests in the codebase...")
        self._log("Running tests...")
        
        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "test",
                    "status": "started",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Run tests
            if hasattr(self.coordinator, 'run_tests_all'):
                self.coordinator.run_tests_all()
            elif hasattr(self.coordinator, 'bash_tool'):
                test_cmd = "pytest --maxfail=1 --disable-warnings -q"
                if args:
                    test_cmd += f" {args}"
                    
                result = self.coordinator.bash_tool.run_command(test_cmd, timeout=120)
                print(result[1])
                
                # Update progress tracking
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "test",
                        "status": "completed" if result[0] == 0 else "failed",
                        "output": result[1],
                        "timestamp": datetime.now().isoformat()
                    })
                
                return "Tests completed." if result[0] == 0 else "Tests failed."
            else:
                return "Test execution functionality not available."
        except Exception as e:
            error_msg = f"Test execution failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "test",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg
    
    def execute_debug_command(self, args: str) -> str:
        """Execute the debug command to debug last test failure.
        
        Args:
            args: Optional arguments (unused)
            
        Returns:
            Command result message
        """
        print("Debugging last test failure...")
        self._log("Debugging last test failure...")
        
        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "debug",
                    "status": "started",
                    "timestamp": datetime.now().isoformat()
                })
            
            # Debug last test
            if hasattr(self.coordinator, 'debug_last_test'):
                self.coordinator.debug_last_test()
                
                # Update progress tracking
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "debug",
                        "status": "completed",
                        "timestamp": datetime.now().isoformat()
                    })
                
                return "Debugging completed."
            else:
                return "Debugging functionality not available."
        except Exception as e:
            error_msg = f"Debugging failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "debug",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg
    
    def execute_terminal_command(self, args: str) -> str:
        """Execute a terminal command.
        
        Args:
            args: Terminal command to execute
            
        Returns:
            Command result message
        """
        if not args.strip():
            return "Please provide a terminal command to execute."
        
        print(f"[TerminalExecutor] Executing: {args}")
        self._log(f"Executing terminal command: {args}")
        
        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "terminal",
                    "status": "started",
                    "command": args,
                    "timestamp": datetime.now().isoformat()
                })
            
            # Execute terminal command
            if hasattr(self.coordinator, 'execute_terminal_command'):
                self.coordinator.execute_terminal_command(args)
                return "Command executed."
            elif hasattr(self.coordinator, 'bash_tool'):
                result = self.coordinator.bash_tool.run_command(args, timeout=120)
                print(result[1])
                
                # Update progress tracking
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "terminal",
                        "status": "completed",
                        "command": args,
                        "output": result[1],
                        "timestamp": datetime.now().isoformat()
                    })
                
                return "Command executed."
            else:
                return "Terminal command execution functionality not available."
        except Exception as e:
            error_msg = f"Terminal command execution failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "terminal",
                    "status": "failed",
                    "command": args,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg
    
    def execute_personas_command(self, args: str) -> str:
        """Execute the personas command to create/update personas.md.
        
        Args:
            args: Optional arguments (unused)
            
        Returns:
            Command result message
        """
        self._log("Creating/updating personas.md...")
        
        try:
            # Execute personas command
            if hasattr(self.coordinator, 'workspace_initializer'):
                result = self.coordinator.workspace_initializer.execute_personas_command()
            elif hasattr(self.coordinator, 'execute_personas_command'):
                result = self.coordinator.execute_personas_command()
            else:
                return "Personas management functionality not available."
            
            return result
        except Exception as e:
            error_msg = f"Personas management failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_guidelines_command(self, args: str) -> str:
        """Execute the guidelines command to create/update copilot-instructions.md.
        
        Args:
            args: Optional arguments (unused)
            
        Returns:
            Command result message
        """
        self._log("Creating/updating copilot-instructions.md...")
        
        try:
            # Execute guidelines command
            if hasattr(self.coordinator, 'workspace_initializer'):
                result = self.coordinator.workspace_initializer.execute_guidelines_command()
            elif hasattr(self.coordinator, 'execute_guidelines_command'):
                result = self.coordinator.execute_guidelines_command()
            else:
                return "Guidelines management functionality not available."
            
            return result
        except Exception as e:
            error_msg = f"Guidelines management failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_design_command(self, args: str) -> str:
        """Execute the design command to create a design document.
        
        This command initiates the design workflow through the coordinator's execute_design facade.
        After the design is completed, it can automatically transition to implementation or deployment
        based on user preferences captured during the design process.
        
        Args:
            args: Design objective
            
        Returns:
            Command result message
        """
        if not args.strip():
            return "Please provide a design objective."
        
        self._log(f"Starting design process for: {args}")
        
        try:
            # Check if the coordinator supports the design workflow
            if hasattr(self.coordinator, 'execute_design'):
                # Execute the design workflow through the coordinator
                result = self.coordinator.execute_design(args.strip())
                
                # Handle errors and cancellations
                if not result.get("success", False):
                    if result.get("cancelled", False):
                        return "Design process cancelled by user."
                    else:
                        return f"Design process failed: {result.get('error', 'Unknown error')}"
                
                # Process next actions based on user choices during design
                next_action = result.get("next_action")
                if next_action == "implementation":
                    # Auto-execute implementation if that was the user's choice
                    return f"Design process completed. Starting implementation of design.txt...\n{self.execute_implement_command('')}"
                elif next_action == "deployment":
                    # Auto-execute deployment if that was the user's choice
                    return f"Design process completed. Starting deployment of design.txt...\n{self.execute_deploy_command('')}"
                else:
                    return "Design process completed successfully. Design saved to design.txt"
            else:
                return "Design functionality not available in this workspace."
        except Exception as e:
            error_msg = f"Design process failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_implement_command(self, args: str) -> str:
        """Execute the implement command to implement a design.
        
        Args:
            args: Optional design file path (defaults to design.txt)
            
        Returns:
            Command result message
        """
        design_file = args.strip() if args.strip() else "design.txt"
        if not Path(design_file).exists():
            return f"{design_file} not found. Please run /design first."
        
        self._log(f"Starting implementation from design: {design_file}")
        
        try:
            # Execute implementation command using the coordinator's execute_implementation method
            if hasattr(self.coordinator, 'execute_implementation'):
                result = self.coordinator.execute_implementation(design_file)
                
                if not result.get("success", False):
                    return f"Implementation failed: {result.get('error', 'Unknown error')}"
                
                # Format successful implementation result
                if result.get("next_task"):
                    return f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}"
                else:
                    return result.get("message", "Implementation completed successfully.")
                
            # Fallback to direct implementation manager access if available
            elif hasattr(self.coordinator, 'implementation_manager') and hasattr(self.coordinator.implementation_manager, 'start_implementation'):
                result = self.coordinator.implementation_manager.start_implementation(design_file)
                
                if not result.get("success", False):
                    return f"Implementation failed: {result.get('error', 'Unknown error')}"
                
                # Format successful implementation result
                if result.get("next_pending"):
                    next_task = result.get("next_pending", {}).get("description", "unknown task")
                    next_id = result.get("next_pending", {}).get("id", "")
                    return f"Task {result.get('task_id')} completed. Next task: {next_id} - {next_task}"
                else:
                    return "All implementation tasks completed."
            else:
                return "Implementation functionality not available."
        except Exception as e:
            error_msg = f"Implementation failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_continue_command(self, args: str) -> str:
        """Execute the continue command to continue implementation or other processes.
        
        Args:
            args: Optional continuation type ('implementation', 'design', etc.)
            
        Returns:
            Command result message
        """
        # Determine continuation type
        continue_type = args.strip().lower() if args.strip() else "implementation"
        self._log(f"Continuing {continue_type}...")
        
        try:
            # Execute continue command using the coordinator's execute_continue method
            if hasattr(self.coordinator, 'execute_continue'):
                result = self.coordinator.execute_continue(continue_type)
                
                if not result.get("success", False):
                    return f"Continuation failed: {result.get('error', 'Unknown error')}"
                
                # Handle implementation-specific result formatting
                if continue_type == "implementation":
                    # Check if there are more tasks
                    if result.get("next_task"):
                        return f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}"
                    else:
                        # All tasks completed
                        return result.get("message", "All implementation tasks completed.")
                elif continue_type == "design":
                    # Design continuation just restarts the design process
                    return "Design process restarted."
                else:
                    return result.get("message", f"{continue_type.capitalize()} continuation completed.")
                
            # Fallback to direct implementation manager access if available
            elif continue_type == "implementation" and hasattr(self.coordinator, 'implementation_manager') and hasattr(self.coordinator.implementation_manager, 'continue_implementation'):
                result = self.coordinator.implementation_manager.continue_implementation()
                
                if not result.get("success", False):
                    return f"Implementation continuation failed: {result.get('error', 'Unknown error')}"
                
                # Check if there are more tasks
                if result.get("next_pending"):
                    next_task = result.get("next_pending", {}).get("description", "unknown task")
                    next_id = result.get("next_pending", {}).get("id", "")
                    return f"Task {result.get('task_id')} completed. Next task: {next_id} - {next_task}"
                else:
                    # All tasks completed
                    return "All implementation tasks completed."
            else:
                return f"{continue_type.capitalize()} continuation functionality not available."
        except Exception as e:
            error_msg = f"Continuation operation failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_deploy_command(self, args: str) -> str:
        """Execute the deploy command to deploy an application.
        
        Args:
            args: Optional design file path (defaults to design.txt)
            
        Returns:
            Command result message
        """
        design_file = args.strip() if args.strip() else "design.txt"
        if not Path(design_file).exists():
            return f"{design_file} not found. Please run /design first."
        
        self._log(f"Starting deployment process for design: {design_file}")
        
        try:
            # Execute deployment command using the coordinator's execute_deployment method
            if hasattr(self.coordinator, 'execute_deployment'):
                result = self.coordinator.execute_deployment(design_file)
                
                if not result.get("success", False):
                    if result.get("cancelled", False):
                        return "Deployment process cancelled by user."
                    else:
                        return f"Deployment failed: {result.get('error', 'Unknown error')}"
                
                # Format successful deployment result
                access_url = result.get("access_url")
                env_file = result.get("env_file")
                message = result.get("message", "Deployment completed successfully.")
                
                response = f"{message}"
                if access_url:
                    response += f"\nApplication is accessible at: {access_url}"
                if env_file:
                    response += f"\nEnvironment variables saved to: {env_file}"
                
                return response
                
            # Fallback to direct deployment manager access if available
            elif hasattr(self.coordinator, 'deployment_manager') and hasattr(self.coordinator.deployment_manager, 'start_deployment_conversation'):
                # Start deployment conversation directly
                initial_response = self.coordinator.deployment_manager.start_deployment_conversation(design_file)
                print(initial_response)
                
                # Continue the conversation flow
                is_deployment_ready = False
                while not is_deployment_ready:
                    user_message = input("Deployment> ")
                    
                    if user_message.lower() in ["/exit", "/quit", "/cancel"]:
                        return "Deployment process cancelled by user."
                    
                    # Check for direct deployment command
                    if user_message.lower() == "/start-deployment":
                        is_deployment_ready = True
                        continue
                    
                    # Continue conversation
                    response, is_deployment_ready = self.coordinator.deployment_manager.continue_deployment_conversation(user_message)
                    print(response)
                
                # Execute deployment
                result = self.coordinator.deployment_manager.execute_deployment()
                
                if not result.get("success", False):
                    return f"Deployment failed: {result.get('error', 'Unknown error')}"
                
                # Format successful deployment result
                access_url = result.get("access_url")
                env_file = result.get("env_file")
                message = result.get("message", "Deployment completed successfully.")
                
                response = f"{message}"
                if access_url:
                    response += f"\nApplication is accessible at: {access_url}"
                if env_file:
                    response += f"\nEnvironment variables saved to: {env_file}"
                
                return response
            else:
                return "Deployment functionality not available."
        except Exception as e:
            error_msg = f"Deployment failed: {e}"
            self._log(error_msg, level="error")
            return error_msg
    
    def execute_help_command(self, args: str) -> str:
        """Execute the help command to show available commands.

        Args:
            args: Optional command name for specific help

        Returns:
            Help message
        """
        if args.strip():
            # Show help for specific command
            command = args.strip().lower()
            if command.startswith('/'):
                command = command[1:]

            help_msgs = {
                "init": "Initialize workspace with essential files (personas.md, guidelines, etc.)",
                "plan": "Generate a development plan from a request description",
                "generate": "Generate code from plan.txt",
                "test": "Run all tests in the codebase",
                "debug": "Debug last test failure",
                "terminal": "Execute a terminal command",
                "personas": "Create/update personas.md with default content",
                "guidelines": "Create/update copilot-instructions.md with default content",
                "design": "Create a design document based on a design objective",
                "implement": "Implement a design from design.txt",
                "continue": "Continue implementation from where it left off",
                "deploy": "Deploy an application based on a design",
                "help": "Show available commands or help for a specific command",
                "config": "Show current configuration",
                "reload-llm-config": "Reload LLM configuration",
                "explain": "Explain the last LLM interaction",
                "request": "Process a full change request (plan + execution)",
                "tasks": "List active tasks that can be resumed",
                "clear": "Clear a specific task state",
                "db": "Database operations (schema, query, test, etc.)"
            }

            if command in help_msgs:
                return f"/{command}: {help_msgs[command]}"
            else:
                return f"Unknown command: {command}. Type /help for available commands."
        else:
            # Show all available commands
            help_text = """Available commands:
/init: Initialize workspace
/plan <description>: Generate a development plan
/generate: Generate code from plan.txt
/test [filter]: Run tests (optional filter)
/debug: Debug last test failure
/terminal <command>: Execute terminal command
/personas: Create/update personas.md
/guidelines: Create/update copilot-instructions.md
/design <objective>: Create a design document
/implement: Implement a design from design.txt
/continue: Continue implementation
/deploy [design_file]: Deploy an application
/config: Show current configuration
/reload-llm-config: Reload LLM configuration
/explain: Explain the last LLM interaction
/request <prompt>: Full change request (plan + execution)
/tasks: List active tasks that can be resumed
/clear <task_id>: Clear a specific task state
/db <command>: Database operations (schema, query, test, etc.)
/help [command]: Show available commands

Type /help <command> for more information on a specific command."""
            return help_text
    
    def execute_config_command(self, args: str) -> str:
        """Execute the config command to show current configuration.

        Args:
            args: Optional arguments (unused)

        Returns:
            Command result message
        """
        self._log("Displaying current configuration...")

        try:
            result = "Current configuration:\n"
            for key, value in self.coordinator.config.config.items():
                if key in ["openrouter_key", "github_token", "api_key"]:
                    # Mask sensitive values
                    result += f"  {key}: {'*' * 10}\n"
                else:
                    result += f"  {key}: {value}\n"
            return result
        except Exception as e:
            error_msg = f"Error getting configuration: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_reload_llm_config_command(self, args: str) -> str:
        """Execute the reload-llm-config command to reload the LLM configuration.

        Args:
            args: Optional arguments (unused)

        Returns:
            Command result message
        """
        self._log("Reloading LLM configuration...")

        try:
            from agent_s3.router_agent import RouterAgent
            router = RouterAgent()
            router.reload_config()
            return "LLM configuration reloaded successfully."
        except Exception as e:
            error_msg = f"Failed to reload LLM configuration: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_explain_command(self, args: str) -> str:
        """Execute the explain command to explain the last LLM interaction.

        Args:
            args: Optional arguments (unused)

        Returns:
            Command result message
        """
        self._log("Explaining the last LLM interaction with context...")

        try:
            # Gather context: tech stack and code snippets
            context = self.coordinator._gather_context() if hasattr(self.coordinator, '_gather_context') else {}
            self.coordinator.explain_last_llm_interaction(context)
            return ""  # Return empty string as output is already printed by the explain method
        except Exception as e:
            error_msg = f"Error explaining last LLM interaction: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_request_command(self, args: str) -> str:
        """Execute the request command to process a full change request.

        Args:
            args: The change request text

        Returns:
            Command result message
        """
        if not args.strip():
            return "Usage: /request <your feature request>"

        request_text = args.strip()
        self._log(f"Processing full change request: {request_text}")

        try:
            self.coordinator.process_change_request(request_text)
            return ""  # Return empty string as output is handled by process_change_request
        except Exception as e:
            error_msg = f"Error processing change request: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_tasks_command(self, args: str) -> str:
        """Execute the tasks command to list active tasks that can be resumed.

        Args:
            args: Optional arguments (unused)

        Returns:
            Command result message
        """
        self._log("Listing active tasks...")

        try:
            # List active tasks that can be resumed
            active_tasks = self.coordinator.task_state_manager.get_active_tasks()
            if not active_tasks:
                return "No active tasks found to resume."

            result = "\nActive tasks that can be resumed:\n"
            for i, task in enumerate(active_tasks, start=1):
                task_id = task.get('task_id', 'Unknown')
                phase = task.get('phase', 'Unknown')
                timestamp = task.get('last_updated', 'Unknown')
                request = task.get('request_text', 'Unknown')
                result += f"{i}. [{task_id[:8]}] Phase: {phase}, Request: {request[:60]}...\n"
                result += f"   Last updated: {timestamp}\n"

            # Show instructions for resuming
            result += "\nTo resume a task, use:\n"
            result += "/continue <task_id>  - where <task_id> is one of the IDs shown above\n"
            result += "Example: /continue " + active_tasks[0].get('task_id', 'task_id')[:8]

            return result
        except Exception as e:
            error_msg = f"Error listing tasks: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_clear_command(self, args: str) -> str:
        """Execute the clear command to clear a specific task state.

        Args:
            args: Task ID to clear

        Returns:
            Command result message
        """
        if not args.strip():
            return "Usage: /clear <task_id>\nUse '/tasks' to see available task IDs"

        task_id = args.strip()
        self._log(f"Clearing task state for ID: {task_id}")

        try:
            # Look for tasks that match the provided ID (or prefix)
            active_tasks = self.coordinator.task_state_manager.get_active_tasks()
            matching_tasks = [t for t in active_tasks if t.get('task_id', '').startswith(task_id)]

            if matching_tasks:
                # Use the first matching task
                matched_task = matching_tasks[0]
                matched_id = matched_task.get('task_id')

                # Prompt for confirmation
                from agent_s3.prompt_moderator import PromptModerator
                prompt_moderator = getattr(self.coordinator, 'prompt_moderator', None) or PromptModerator(self.coordinator)

                confirm = prompt_moderator.ask_yes_no_question(f"Are you sure you want to clear task {matched_id}?")
                if confirm:
                    success = self.coordinator.task_state_manager.clear_state(matched_id)
                    if success:
                        return f"Task {matched_id} successfully cleared."
                    else:
                        return f"Failed to clear task {matched_id}."
                else:
                    return "Operation canceled."
            else:
                return f"No tasks found matching ID: {task_id}\nUse '/tasks' to see available task IDs."
        except Exception as e:
            error_msg = f"Error clearing task: {e}"
            self._log(error_msg, level="error")
            return error_msg

    def execute_db_command(self, args: str) -> str:
        """Execute the db command for database operations.

        Args:
            args: Database command and parameters

        Returns:
            Command result message
        """
        if not hasattr(self.coordinator, 'database_tool') or not self.coordinator.database_tool:
            return "Database tool is not available."

        # Parse db_command from args
        parts = args.split(maxsplit=1)
        db_command = parts[0] if parts else "help"
        db_args = parts[1] if len(parts) > 1 else ""

        self._log(f"Executing database command: {db_command} {db_args}")

        try:
            # Delegate to specialized DB command handlers
            db_command_map = {
                "help": self._db_help_command,
                "list": self._db_list_command,
                "schema": self._db_schema_command,
                "test": self._db_test_command,
                "query": self._db_query_command,
                "script": self._db_script_command,
                "explain": self._db_explain_command
            }

            if db_command in db_command_map:
                return db_command_map[db_command](db_args)
            else:
                return f"Unknown database command: {db_command}\nUse '/db help' to see available commands"
        except Exception as e:
            error_msg = f"Error executing database command: {e}"
            self._log(error_msg, level="error")
            return error_msg

    # Database command handlers
    def _db_help_command(self, args: str) -> str:
        help_text = "\nDatabase Tool Commands:\n"
        help_text += "  /db list                  - List configured databases\n"
        help_text += "  /db schema [db_name]      - Show database schema information\n"
        help_text += "  /db test [db_name]        - Test database connection\n"
        help_text += "  /db query <db_name> <sql> - Execute a SQL query\n"
        help_text += "  /db script <db_name> <file> - Execute a SQL script file\n"
        help_text += "  /db explain <db_name> <sql> - Explain query execution plan\n"
        return help_text

    def _db_list_command(self, args: str) -> str:
        # List configured databases
        db_configs = self.coordinator.config.config.get("databases", {})
        if not db_configs:
            return "No databases configured."

        result = "\nConfigured Databases:\n"
        for db_name, config in db_configs.items():
            db_type = config.get("type", "unknown")
            if db_type == "sqlite":
                db_path = config.get("path", "unknown")
                result += f"  {db_name} ({db_type}): {db_path}\n"
            else:
                host = config.get("host", "localhost")
                database = config.get("database", "unknown")
                result += f"  {db_name} ({db_type}): {database} on {host}\n"
        return result

    def _db_schema_command(self, args: str) -> str:
        # Show database schema
        db_name = args.strip() if args.strip() else None

        result = ""
        if not db_name:
            # List all database schemas
            db_configs = self.coordinator.config.config.get("databases", {})
            for db_name in db_configs:
                result += f"\n=== Schema for {db_name} database ===\n"
                schema_result = self.coordinator.database_tool.get_schema_info(db_name)
                if schema_result.get("success", False):
                    schema = schema_result.get("schema", {})
                    for table, columns in schema.items():
                        result += f"\nTable: {table}\n"
                        for col in columns:
                            nullable = "NULL" if col.get("is_nullable") else "NOT NULL"
                            result += f"  {col.get('column_name')}: {col.get('data_type')} {nullable}\n"
                else:
                    result += f"Error: {schema_result.get('error', 'Unknown error')}\n"
        else:
            # Show schema for specific database
            schema_result = self.coordinator.database_tool.get_schema_info(db_name)
            if schema_result.get("success", False):
                schema = schema_result.get("schema", {})
                for table, columns in schema.items():
                    result += f"\nTable: {table}\n"
                    for col in columns:
                        nullable = "NULL" if col.get("is_nullable") else "NOT NULL"
                        result += f"  {col.get('column_name')}: {col.get('data_type')} {nullable}\n"
            else:
                result += f"Error: {schema_result.get('error', 'Unknown error')}\n"
        return result

    def _db_test_command(self, args: str) -> str:
        # Test database connection
        db_name = args.strip() if args.strip() else None

        result = ""
        if not db_name:
            # Test all database connections
            db_configs = self.coordinator.config.config.get("databases", {})
            for db_name in db_configs:
                result += f"Testing connection to {db_name}...\n"
                test_result = self.coordinator.database_tool.test_connection(db_name)
                if test_result.get("success", False):
                    result += f"  Success: {test_result.get('message', 'Connection successful')}\n"
                else:
                    result += f"  Failed: {test_result.get('error', 'Unknown error')}\n"
        else:
            # Test specific database connection
            test_result = self.coordinator.database_tool.test_connection(db_name)
            if test_result.get("success", False):
                result += f"Connection to {db_name} successful: {test_result.get('message', 'Connection successful')}\n"
            else:
                result += f"Connection to {db_name} failed: {test_result.get('error', 'Unknown error')}\n"
        return result

    def _db_query_command(self, args: str) -> str:
        # Execute a query
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /db query <db_name> <sql>"

        db_name = parts[0]
        sql = parts[1]

        result = f"Executing query on {db_name}...\n"
        query_result = self.coordinator.database_tool.execute_query(sql, db_name=db_name)
        if query_result.get("success", False):
            result += "\nQuery Results:\n"
            results = query_result.get("results", [])
            if results:
                # Print header
                headers = results[0].keys()
                header_line = " | ".join(headers)
                result += header_line + "\n"
                result += "-" * len(header_line) + "\n"

                # Print rows
                for row in results:
                    result += " | ".join(str(row.get(h, "")) for h in headers) + "\n"

                result += f"\n{len(results)} rows returned in {query_result.get('duration_ms', 0):.2f} ms\n"
            else:
                result += "No results returned\n"
        else:
            result += f"Query failed: {query_result.get('error', 'Unknown error')}\n"
        return result

    def _db_script_command(self, args: str) -> str:
        # Execute a script file
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /db script <db_name> <file>"

        db_name = parts[0]
        script_path = parts[1]

        if not os.path.exists(script_path):
            return f"Script file not found: {script_path}"

        result = f"Executing script on {db_name}...\n"
        script_result = self.coordinator.database_tool.execute_script(script_path, db_name=db_name)
        if script_result.get("success", False):
            result += f"Script executed successfully: {script_result.get('queries_executed', 0)} queries executed\n"
        else:
            result += f"Script execution failed: {script_result.get('error', 'Unknown error')}\n"
        return result

    def _db_explain_command(self, args: str) -> str:
        # Explain query plan
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /db explain <db_name> <sql>"

        db_name = parts[0]
        sql = parts[1]

        result = f"Explaining query on {db_name}...\n"
        explain_result = self.coordinator.database_tool.explain_query(sql, db_name=db_name)
        if explain_result.get("success", False):
            result += "\nQuery Execution Plan:\n"
            plan = explain_result.get("plan", [])
            if plan:
                for step in plan:
                    result += json.dumps(step, indent=2) + "\n"
            else:
                result += "No execution plan returned\n"
        else:
            result += f"Explain failed: {explain_result.get('error', 'Unknown error')}\n"
        return result

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the coordinator's scratchpad or default logger.

        Args:
            message: The message to log
            level: The log level (info, warning, error) or LogLevel enum
        """
        # Use coordinator's _log method if available
        if hasattr(self.coordinator, '_log'):
            self.coordinator._log(message, level=level)
        # Otherwise handle directly
        elif hasattr(self.coordinator, 'scratchpad') and self.coordinator.scratchpad:
            # Import LogLevel if not already in scope
            from agent_s3.enhanced_scratchpad_manager import LogLevel

            # Convert string level to LogLevel enum if needed
            log_level = level
            if isinstance(level, str):
                level_map = {
                    "debug": LogLevel.DEBUG,
                    "info": LogLevel.INFO,
                    "warning": LogLevel.WARNING,
                    "warn": LogLevel.WARNING,
                    "error": LogLevel.ERROR,
                    "critical": LogLevel.CRITICAL
                }
                log_level = level_map.get(level.lower(), LogLevel.INFO)

            self.coordinator.scratchpad.log("CommandProcessor", message, level=log_level)
        else:
            # Fall back to standard logging
            if isinstance(level, str):
                if level.lower() == "error":
                    logging.error(message)
                elif level.lower() == "warning":
                    logging.warning(message)
                else:
                    logging.info(message)
            else:
                # Map LogLevel enum to logging levels if needed
                from agent_s3.enhanced_scratchpad_manager import LogLevel
                log_map = {
                    LogLevel.DEBUG: logging.debug,
                    LogLevel.INFO: logging.info,
                    LogLevel.WARNING: logging.warning,
                    LogLevel.ERROR: logging.error,
                    LogLevel.CRITICAL: logging.critical
                }
                log_func = log_map.get(level, logging.info)
                log_func(message)