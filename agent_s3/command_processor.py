"""Command Processor component for Agent-S3.

Processes and dispatches CLI commands to appropriate handlers.
"""

import os
import logging
import json
from pathlib import Path
from datetime import datetime


from .planning_helper import generate_plan_via_workflow

class CommandProcessor:
    """Processes and dispatches CLI commands to appropriate handlers."""

    def __init__(self, coordinator):
        """Initialize the CommandProcessor.

        Args:
            coordinator: Coordinator instance for accessing other components
        """
        self.coordinator = coordinator


    def process_command(self, command: str) -> str:
        """Delegate parsing and execution to the CLI dispatcher."""
        from agent_s3.cli.dispatcher import dispatch

        self._log(f"Processing command: {command}")
        return dispatch(self, command)

    def execute_init_command(self, args: str) -> tuple[str, bool]:
        """Execute the init command to initialize workspace.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of command result message and success flag
        """
        self._log("Initializing workspace...")
        initialization_success = False
        result_msg = "Workspace initialization failed."

        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "init",
                    "status": "started",
                    "timestamp": datetime.now().isoformat()
                })

            # Delegate to workspace_initializer if available, otherwise use coordinator
            if hasattr(self.coordinator, 'workspace_initializer'):
                initialization_success = self.coordinator.workspace_initializer.initialize_workspace()
                result_msg = "Workspace initialized successfully."
                
                # Get validation details for better user feedback
                if (
                    hasattr(self.coordinator.workspace_initializer, "validation_failure_reason")
                    and self.coordinator.workspace_initializer.validation_failure_reason
                ):
                    if initialization_success:
                        result_msg += (
                            f" Note: {self.coordinator.workspace_initializer.validation_failure_reason}"
                        )
                    else:
                        result_msg = (
                            "Workspace initialization failed: "
                            f"{self.coordinator.workspace_initializer.validation_failure_reason}"
                        )
            else:
                # Handle coordinator fallback with proper return value parsing
                result = self.coordinator.initialize_workspace()
                
                # Parse dictionary return value correctly
                if isinstance(result, dict):
                    initialization_success = result.get("success", False)
                    is_valid = result.get("is_workspace_valid", False)
                    errors = result.get("errors", [])
                    validation_reason = result.get("validation_failure_reason")
                    
                    if initialization_success and is_valid:
                        result_msg = "Workspace initialized successfully."
                    elif initialization_success and not is_valid:
                        error_details = "; ".join(str(err) for err in errors) if errors else validation_reason or "Unknown validation issues"
                        result_msg = f"Workspace initialization completed with warnings: {error_details}. Some features may be limited."
                    else:
                        error_details = "; ".join(str(err) for err in errors) if errors else "Unknown error"
                        result_msg = f"Workspace initialization failed: {error_details}"
                        initialization_success = False
                else:
                    # Fallback for unexpected return type
                    initialization_success = bool(result)
                    result_msg = "Workspace initialized successfully." if initialization_success else "Workspace initialization failed."

            # After successful initialization, gather codebase context
            if initialization_success:
                self._log("Gathering initial codebase context...")
                if hasattr(self.coordinator, 'gather_initial_code_context'):
                    context_gathering_success = self.coordinator.gather_initial_code_context()
                    if context_gathering_success:
                        self._log("Initial codebase context gathered successfully.")
                        result_msg += " Initial codebase context gathered."
                    else:
                        self._log("Failed to gather initial codebase context.", level="warning")
                        result_msg += " Warning: Failed to gather initial codebase context."
                else:
                    self._log("Coordinator does not have 'gather_initial_code_context' method.", level="warning")
                    result_msg += " Warning: Context gathering feature not available."
            
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "init",
                    "status": "completed" if initialization_success else "failed",
                    "result": result_msg,
                    "timestamp": datetime.now().isoformat()
                })

            return result_msg, initialization_success

        except Exception as e:
            error_msg = f"Workspace initialization failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking with failure
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "init",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg, False

    def execute_plan_command(self, args: str) -> tuple[str, bool]:
        """Execute the plan command to generate a development plan.

        Args:
            args: Plan text/description

        Returns:
            Command result message
        """
        if not args.strip():
            return "Please provide a plan description.", False

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

            # Generate plan using the sequential planning workflow
            plan_result = generate_plan_via_workflow(self.coordinator, args)

            if not plan_result.get("success"):
                error_msg = plan_result.get("error", "Unknown planning error")
                self._log(error_msg, level="error")

                # Update progress tracking with failure
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "plan",
                        "status": "failed",
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    })

                return f"Plan generation failed: {error_msg}", False

            plan_obj = plan_result.get("plan")

            # Convert plan object to string representation
            if isinstance(plan_obj, dict):
                plan = json.dumps(plan_obj, indent=2)
            else:
                plan = str(plan_obj)

            # Write plan to file
            plan_path = Path("plan.txt")
            with open(plan_path, "w", encoding="utf-8") as f:
                f.write(plan)

            # Also save as JSON if possible
            try:
                json_plan_path = Path("plan.json")
                with open(json_plan_path, "w", encoding="utf-8") as f:
                    if isinstance(plan_obj, dict):
                        json.dump(plan_obj, f, indent=2)
                    else:
                        json.dump({"plan": str(plan_obj)}, f, indent=2)
            except Exception as json_err:
                self._log(f"Warning: Could not save plan as JSON: {json_err}", level="warning")

            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "plan",
                    "status": "completed",
                    "input": args,
                    "timestamp": datetime.now().isoformat()
                })

            return f"Plan generated and saved to {plan_path}", True
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

            return error_msg, False

    def execute_test_command(self, args: str) -> tuple[str, bool]:
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
                
                # Update progress tracking for run_tests_all path
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "test",
                        "status": "completed",
                        "output": "Tests executed via run_tests_all",
                        "timestamp": datetime.now().isoformat()
                    })
                
                return "Tests completed.", True
            elif hasattr(self.coordinator, 'bash_tool'):
                test_cmd = "pytest --maxfail=1 --disable-warnings -q"
                if args:
                    # Sanitize args to prevent command injection
                    sanitized_args = self._sanitize_test_args(args.strip())
                    test_cmd += f" {sanitized_args}"

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

                return (
                    "Tests completed." if result[0] == 0 else "Tests failed.",
                    result[0] == 0,
                )
            else:
                return "Test execution functionality not available.", False
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

            return error_msg, False

    def execute_debug_command(self, args: str) -> tuple[str, bool]:
        """Execute the debug command to debug last test failure.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
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

            # Debug last test (canonical behavior)
            if hasattr(self.coordinator, 'debug_last_test'):
                self.coordinator.debug_last_test()
            else:
                return "Debug functionality not available.", False

            # Update progress tracking on success
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "debug",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat()
                })

            return "Debugging completed.", True
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

            return error_msg, False

    def execute_terminal_command(self, args: str) -> tuple[str, bool]:
        """Execute a terminal command.

        Args:
            args: Terminal command to execute

        Returns:
            Tuple of command result message and success flag
        """
        if not args.strip():
            return "Please provide a terminal command to execute.", False

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
                return "Command executed.", True
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

                return "Command executed.", True
            else:
                return "Terminal command execution functionality not available.", False
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

            return error_msg, False


    def execute_guidelines_command(self, args: str) -> tuple[str, bool]:
        """Execute the guidelines command to create/update copilot-instructions.md.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
        """
        self._log("Creating/updating copilot-instructions.md...")

        try:
            # Execute guidelines command
            if hasattr(self.coordinator, 'workspace_initializer'):
                result = self.coordinator.workspace_initializer.execute_guidelines_command()
            elif hasattr(self.coordinator, 'execute_guidelines_command'):
                result = self.coordinator.execute_guidelines_command()
            else:
                return "Guidelines management functionality not available.", False

            return result, True
        except Exception as e:
            error_msg = f"Guidelines management failed: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_design_command(self, args: str) -> tuple[str, bool]:
        """Execute the design command to create a design document.

        This command initiates the design workflow through the coordinator's execute_design facade.
        After the design is completed, it can automatically transition to implementation or deployment
        based on user preferences captured during the design process.

        Args:
            args: Design objective

        Returns:
            Tuple of command result message and success flag
        """
        if not args.strip():
            return "Please provide a design objective.", False

        self._log(f"Starting design process for: {args}")

        try:
            # Update progress tracking
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "design",
                    "status": "started",
                    "objective": args.strip(),
                    "timestamp": datetime.now().isoformat()
                })

            # Check if the coordinator supports the design workflow
            if hasattr(self.coordinator, 'execute_design'):
                # Execute the design workflow through the coordinator
                result = self.coordinator.execute_design(args.strip())

                # Handle errors and cancellations
                if not result.get("success", False):
                    # Update progress tracking for failure
                    if hasattr(self.coordinator, 'progress_tracker'):
                        self.coordinator.progress_tracker.update_progress({
                            "phase": "design",
                            "status": "cancelled" if result.get("cancelled", False) else "failed",
                            "error": result.get('error', 'Unknown error'),
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    if result.get("cancelled", False):
                        return "Design process cancelled by user.", False
                    else:
                        return (
                            f"Design process failed: {result.get('error', 'Unknown error')}",
                            False,
                        )

                # Update progress tracking for success
                if hasattr(self.coordinator, 'progress_tracker'):
                    self.coordinator.progress_tracker.update_progress({
                        "phase": "design",
                        "status": "completed",
                        "next_action": result.get("next_action"),
                        "timestamp": datetime.now().isoformat()
                    })

                # Process next actions based on user choices during design
                next_action = result.get("next_action")
                if next_action == "implementation":
                    return (
                        "Design process completed. Implementation started for design.txt",
                        True,
                    )
                elif next_action == "deployment":
                    return (
                        "Design process completed. Deployment started for design.txt",
                        True,
                    )
                else:
                    return (
                        "Design process completed successfully. Design saved to design.txt",
                        True,
                    )
            else:
                return "Design functionality not available in this workspace.", False
        except Exception as e:
            error_msg = f"Design process failed: {e}"
            self._log(error_msg, level="error")
            
            # Update progress tracking for exception
            if hasattr(self.coordinator, 'progress_tracker'):
                self.coordinator.progress_tracker.update_progress({
                    "phase": "design",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
            
            return error_msg, False

    def execute_design_auto_command(self, args: str) -> tuple[str, bool]:
        """Execute automated design command with implicit approvals."""
        if not args.strip():
            return "Please provide a design objective.", False

        self._log(f"Starting automated design for: {args}")

        try:
            # Update progress tracking when starting
            if hasattr(self.coordinator, "progress_tracker"):
                self.coordinator.progress_tracker.update_progress(
                    {
                        "phase": "design-auto",
                        "status": "started",
                        "objective": args.strip(),
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            if hasattr(self.coordinator, 'execute_design_auto'):
                result = self.coordinator.execute_design_auto(args.strip())
            else:
                return "Automated design not available in this workspace.", False

            if not result.get("success", False):
                # Update progress tracking for failure
                if hasattr(self.coordinator, "progress_tracker"):
                    self.coordinator.progress_tracker.update_progress(
                        {
                            "phase": "design-auto",
                            "status": "failed",
                            "error": result.get("error", "Unknown error"),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                return (
                    f"Design process failed: {result.get('error', 'Unknown error')}",
                    False,
                )

            # Update progress tracking for success
            if hasattr(self.coordinator, "progress_tracker"):
                self.coordinator.progress_tracker.update_progress(
                    {
                        "phase": "design-auto",
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return (
                "Design process completed successfully. Design saved to design.txt",
                True,
            )
        except Exception as e:
            error_msg = f"Design process failed: {e}"
            self._log(error_msg, level="error")
            # Update progress tracking for exception
            if hasattr(self.coordinator, "progress_tracker"):
                self.coordinator.progress_tracker.update_progress(
                    {
                        "phase": "design-auto",
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            return error_msg, False

    def execute_implement_command(self, args: str) -> tuple[str, bool]:
        """Execute the implement command to implement a design.

        Args:
            args: Optional design file path (defaults to design.txt)

        Returns:
            Tuple of command result message and success flag
        """
        design_file = args.strip() if args.strip() else "design.txt"
        if not Path(design_file).exists():
            return f"{design_file} not found. Please run /design first.", False

        self._log(f"Starting implementation from design: {design_file}")

        try:
            # Execute implementation command using the coordinator's execute_implementation method
            if hasattr(self.coordinator, 'execute_implementation'):
                result = self.coordinator.execute_implementation(design_file)

                if not result.get("success", False):
                    return (
                        f"Implementation failed: {result.get('error', 'Unknown error')}",
                        False,
                    )

                # Format successful implementation result
                if result.get("next_task"):
                    return (
                        f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}",
                        True,
                    )
                else:
                    return result.get("message", "Implementation completed successfully."), True

            # Fallback to direct implementation manager access if available
            elif hasattr(self.coordinator, 'implementation_manager') and hasattr(self.coordinator.implementation_manager, 'start_implementation'):
                result = self.coordinator.implementation_manager.start_implementation(design_file)

                if not result.get("success", False):
                    return (
                        f"Implementation failed: {result.get('error', 'Unknown error')}",
                        False,
                    )

                # Format successful implementation result
                if result.get("next_pending"):
                    next_task = result.get("next_pending", {}).get("description", "unknown task")
                    next_id = result.get("next_pending", {}).get("id", "")
                    return (
                        f"Task {result.get('task_id')} completed. Next task: {next_id} - {next_task}",
                        True,
                    )
                else:
                    return "All implementation tasks completed.", True
            else:
                return "Implementation functionality not available.", False
        except Exception as e:
            error_msg = f"Implementation failed: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_continue_command(self, args: str) -> tuple[str, bool]:
        """Execute the continue command to continue implementation or other processes.

        Args:
            args: Optional continuation type ('implementation', 'design', etc.)

        Returns:
            Tuple of command result message and success flag
        """
        # Determine continuation type
        continue_type = args.strip().lower() if args.strip() else "implementation"
        self._log(f"Continuing {continue_type}...")

        try:
            # Execute continue command using the coordinator's execute_continue method
            if hasattr(self.coordinator, 'execute_continue'):
                result = self.coordinator.execute_continue(continue_type)

                if not result.get("success", False):
                    return (
                        f"Continuation failed: {result.get('error', 'Unknown error')}",
                        False,
                    )

                # Handle implementation-specific result formatting
                if continue_type == "implementation":
                    # Check if there are more tasks
                    if result.get("next_task"):
                        return (
                            f"Task {result.get('task_completed')} completed. Next task: {result.get('next_task')}",
                            True,
                        )
                    else:
                        # All tasks completed
                        return result.get("message", "All implementation tasks completed."), True
                elif continue_type == "design":
                    # Design continuation just restarts the design process
                    return "Design process restarted.", True
                else:
                    return result.get(
                        "message", f"{continue_type.capitalize()} continuation completed."), True

            # Fallback to direct implementation manager access if available
            elif continue_type == "implementation" and hasattr(self.coordinator, 'implementation_manager') and hasattr(self.coordinator.implementation_manager, 'continue_implementation'):
                result = self.coordinator.implementation_manager.continue_implementation()

                if not result.get("success", False):
                    return (
                        f"Implementation continuation failed: {result.get('error', 'Unknown error')}",
                        False,
                    )

                # Check if there are more tasks
                if result.get("next_pending"):
                    next_task = result.get("next_pending", {}).get("description", "unknown task")
                    next_id = result.get("next_pending", {}).get("id", "")
                    return (
                        f"Task {result.get('task_id')} completed. Next task: {next_id} - {next_task}",
                        True,
                    )
                else:
                    # All tasks completed
                    return "All implementation tasks completed.", True
            else:
                return f"{continue_type.capitalize()} continuation functionality not available.", False
        except Exception as e:
            error_msg = f"Continuation operation failed: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_deploy_command(self, args: str) -> tuple[str, bool]:
        """Execute the deploy command to deploy an application.

        Args:
            args: Optional design file path (defaults to design.txt)

        Returns:
            Tuple of command result message and success flag
        """
        design_file = args.strip() if args.strip() else "design.txt"
        if not Path(design_file).exists():
            return f"{design_file} not found. Please run /design first.", False

        self._log(f"Starting deployment process for design: {design_file}")

        try:
            # Execute deployment command using the coordinator's execute_deployment method
            if hasattr(self.coordinator, 'execute_deployment'):
                result = self.coordinator.execute_deployment(design_file)

                if not result.get("success", False):
                    if result.get("cancelled", False):
                        return "Deployment process cancelled by user.", False
                    else:
                        return (
                            f"Deployment failed: {result.get('error', 'Unknown error')}",
                            False,
                        )

                # Format successful deployment result
                return self._format_deployment_result(result), True

            # Fallback to direct deployment manager access if available
            elif hasattr(self.coordinator, 'deployment_manager') and hasattr(self.coordinator.deployment_manager, 'start_deployment_conversation'):
                # Start deployment conversation directly
                initial_response = self.coordinator.deployment_manager.start_deployment_conversation(design_file)
                print(initial_response)

                # Continue the conversation flow
                is_deployment_ready = False
                while not is_deployment_ready:
                    try:
                        user_message = input("Deployment> ")
                    except (EOFError, KeyboardInterrupt):
                        return "Deployment process cancelled by user.", False

                    if user_message.lower() in ["/exit", "/quit", "/cancel"]:
                        return "Deployment process cancelled by user.", False

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
                    return (
                        f"Deployment failed: {result.get('error', 'Unknown error')}",
                        False,
                    )

                # Format successful deployment result
                return self._format_deployment_result(result), True
            else:
                return "Deployment functionality not available.", False
        except Exception as e:
            error_msg = f"Deployment failed: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_help_command(self, args: str) -> tuple[str, bool]:
        """Execute the help command - delegates to CLI dispatcher (single source of truth).

        Args:
            args: Optional command name for specific help

        Returns:
            Tuple of help message and success flag
        """
        # Delegate to CLI dispatcher - SINGLE SOURCE OF TRUTH
        from agent_s3.cli.dispatcher import _handle_simple_help_command
        help_text, success = _handle_simple_help_command(args)
        return help_text, success

    def execute_config_command(self, args: str) -> tuple[str, bool]:
        """Execute the config command to show current configuration.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
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
            return result, True
        except Exception as e:
            error_msg = f"Error getting configuration: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_reload_llm_config_command(self, args: str) -> tuple[str, bool]:
        """Execute the reload-llm-config command to reload the LLM configuration.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
        """
        self._log("Reloading LLM configuration...")

        try:
            from agent_s3.router_agent import RouterAgent
            router = RouterAgent()
            router.reload_config()
            return "LLM configuration reloaded successfully.", True
        except Exception as e:
            error_msg = f"Failed to reload LLM configuration: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_explain_command(self, args: str) -> tuple[str, bool]:
        """Execute the explain command to explain the last LLM interaction.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
        """
        self._log("Explaining the last LLM interaction with context...")

        try:
            # Gather context: tech stack and code snippets
            context = self.coordinator._gather_context()
            self.coordinator.explain_last_llm_interaction(context)
            return "", True  # Return empty string as output is already printed by the explain method
        except Exception as e:
            error_msg = f"Error explaining last LLM interaction: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_request_command(self, args: str) -> tuple[str, bool]:
        """Execute the request command to process a full change request.

        Args:
            args: The change request text

        Returns:
            Tuple of command result message and success flag
        """
        if not args.strip():
            return "Usage: /request <your feature request>", False

        request_text = args.strip()
        self._log(f"Processing full change request: {request_text}")

        try:
            self.coordinator.process_change_request(request_text)
            return "", True  # Return empty string as output is handled by process_change_request
        except Exception as e:
            error_msg = f"Error processing change request: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_tasks_command(self, args: str) -> tuple[str, bool]:
        """Execute the tasks command to list active tasks that can be resumed.

        Args:
            args: Optional arguments (unused)

        Returns:
            Tuple of command result message and success flag
        """
        self._log("Listing active tasks...")

        try:
            # List active tasks that can be resumed
            active_tasks = self.coordinator.task_state_manager.get_active_tasks()
            if not active_tasks:
                return "No active tasks found to resume.", True

            result = "\nActive tasks that can be resumed:\n"
            for i, task in enumerate(active_tasks, start=1):
                # Validate task structure and provide safe defaults
                if not isinstance(task, dict):
                    self._log(f"Invalid task format at index {i}: {type(task)}", level="warning")
                    continue
                    
                task_id = task.get('task_id', 'Unknown')
                phase = task.get('phase', 'Unknown')
                timestamp = task.get('last_updated', 'Unknown')
                request = task.get('request_text', 'Unknown')
                
                # Safe string operations with validation
                safe_task_id = str(task_id)[:8] if task_id and task_id != 'Unknown' else 'Unknown'
                safe_request = str(request)[:60] if request and request != 'Unknown' else 'No description'
                
                result += f"{i}. [{safe_task_id}] Phase: {phase}, Request: {safe_request}...\n"
                result += f"   Last updated: {timestamp}\n"

            # Show instructions for resuming with validation
            result += "\nTo resume a task, use:\n"
            result += "/continue <task_id>  - where <task_id> is one of the IDs shown above\n"
            
            # Safe example generation
            if active_tasks and len(active_tasks) > 0:
                first_task = active_tasks[0]
                if isinstance(first_task, dict) and first_task.get('task_id'):
                    example_id = str(first_task.get('task_id'))[:8]
                    result += f"Example: /continue {example_id}"
                else:
                    result += "Example: /continue <task_id>"
            else:
                result += "Example: /continue <task_id>"

            return result, True
        except Exception as e:
            error_msg = f"Error listing tasks: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_clear_command(self, args: str) -> tuple[str, bool]:
        """Execute the clear command to clear a specific task state.

        Args:
            args: Task ID to clear

        Returns:
            Tuple of command result message and success flag
        """
        if not args.strip():
            return "Usage: /clear <task_id>\nUse '/tasks' to see available task IDs", False

        task_id = args.strip()
        self._log(f"Clearing task state for ID: {task_id}")

        try:
            # Look for tasks that match the provided ID (or prefix)
            active_tasks = self.coordinator.task_state_manager.get_active_tasks()
            matching_tasks = [t for t in active_tasks if t.get('task_id', '').startswith(task_id)]

            if matching_tasks:
                # Handle multiple matches - let user choose
                if len(matching_tasks) > 1:
                    match_info = f"Multiple tasks match '{task_id}':\n"
                    for i, task in enumerate(matching_tasks, 1):
                        task_full_id = task.get('task_id', 'Unknown')
                        phase = task.get('phase', 'Unknown')
                        request = task.get('request_text', 'No description')
                        match_info += f"  {i}. {task_full_id} (Phase: {phase}, Request: {request[:40]}...)\n"
                    match_info += "\nPlease specify a more complete task ID to avoid ambiguity."
                    return match_info, False
                
                # Single match - proceed with confirmation
                matched_task = matching_tasks[0]
                matched_id = matched_task.get('task_id')

                # Validate clear_state return type and prompt moderator usage
                from agent_s3.prompt_moderator import PromptModerator
                prompt_moderator = getattr(self.coordinator, 'prompt_moderator', None) or PromptModerator(self.coordinator)

                confirm = prompt_moderator.ask_yes_no_question(f"Are you sure you want to clear task {matched_id}?")
                if confirm:
                    success = self.coordinator.task_state_manager.clear_state(matched_id)
                    # Validate return type
                    if isinstance(success, bool) and success:
                        return f"Task {matched_id} successfully cleared.", True
                    else:
                        return f"Failed to clear task {matched_id}. Result: {success}", False
                else:
                    return "Operation canceled.", False
            else:
                return (
                    f"No tasks found matching ID: {task_id}\nUse '/tasks' to see available task IDs.",
                    False,
                )
        except Exception as e:
            error_msg = f"Error clearing task: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

    def execute_db_command(self, args: str) -> tuple[str, bool]:
        """Execute the db command for database operations.

        Args:
            args: Database command and parameters

        Returns:
            Tuple of command result message and success flag
        """
        if not hasattr(self.coordinator, 'database_manager') or not self.coordinator.database_manager:
            return "Database tool is not available.", False

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
                return db_command_map[db_command](db_args), True
            else:
                return (
                    f"Unknown database command: {db_command}\nUse '/db help' to see available commands",
                    False,
                )
        except Exception as e:
            error_msg = f"Error executing database command: {e}"
            self._log(error_msg, level="error")
            return error_msg, False

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
                schema_result = self.coordinator.database_manager.database_tool.get_schema_info(db_name)
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
            schema_result = self.coordinator.database_manager.database_tool.get_schema_info(db_name)
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
                test_result = self.coordinator.database_manager.setup_database(db_name)
                if test_result.get("success", False):
                    result += f"  Success: {test_result.get('message', 'Connection successful')}\n"
                else:
                    result += f"  Failed: {test_result.get('error', 'Unknown error')}\n"
        else:
            # Test specific database connection
            test_result = self.coordinator.database_manager.setup_database(db_name)
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
        
        # Sanitize SQL to prevent injection
        sanitized_sql, is_safe = self._sanitize_sql_query(sql)
        if not is_safe:
            return "Query rejected for security reasons. Please use only safe read-only queries."

        result = f"Executing query on {db_name}...\n"
        query_result = self.coordinator.database_manager.execute_query(sanitized_sql, db_name=db_name)
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
        script_result = self.coordinator.database_manager.run_migration(script_path, db_name=db_name)
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
        
        # Sanitize SQL to prevent injection
        sanitized_sql, is_safe = self._sanitize_sql_query(sql)
        if not is_safe:
            return "Query rejected for security reasons. Please use only safe read-only queries."

        result = f"Explaining query on {db_name}...\n"
        explain_result = self.coordinator.database_manager.database_tool.explain_query(sanitized_sql, db_name=db_name)
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

    def _sanitize_test_args(self, args: str) -> str:
        """Sanitize test arguments to prevent command injection.
        
        Args:
            args: Raw test arguments
            
        Returns:
            Sanitized arguments safe for pytest execution
        """
        import re
        import shlex
        
        # Split args safely and validate each part
        try:
            # Use shlex to safely parse arguments
            parsed_args = shlex.split(args)
        except ValueError:
            # If parsing fails, treat as unsafe and return empty
            self._log(f"Failed to parse test args safely: {args}", level="warning")
            return ""
        
        sanitized_parts = []
        for arg in parsed_args:
            # Allow only safe pytest arguments and test paths
            if re.match(r'^[a-zA-Z0-9_./:\-]+$', arg) or arg.startswith('-'):
                # Additional validation for pytest flags
                if arg.startswith('-') and not re.match(r'^-[a-zA-Z\-]+$', arg):
                    self._log(f"Potentially unsafe pytest flag: {arg}", level="warning")
                    continue
                sanitized_parts.append(arg)
            else:
                self._log(f"Rejected unsafe test argument: {arg}", level="warning")
        
        return ' '.join(sanitized_parts)

    def _sanitize_sql_query(self, sql: str) -> tuple[str, bool]:
        """Sanitize SQL query to prevent SQL injection.
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Tuple of (sanitized_sql, is_safe)
        """
        import re
        
        # Remove leading/trailing whitespace
        sql = sql.strip()
        
        # Check for obviously dangerous patterns
        dangerous_patterns = [
            r';.*?(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|EXEC|EXECUTE)',
            r'--.*?(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)',
            r'/\*.*?(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE).*?\*/',
            r'xp_cmdshell',
            r'sp_executesql',
            r'UNION.*?SELECT.*?FROM.*?WHERE',
            r';\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE | re.DOTALL):
                self._log(f"Potentially dangerous SQL pattern detected: {pattern}", level="warning")
                return "", False
        
        # For basic safety, only allow SELECT, SHOW, DESCRIBE, EXPLAIN statements
        # and limit to single statements
        if ';' in sql and not sql.strip().endswith(';'):
            self._log("Multiple SQL statements not allowed", level="warning")
            return "", False
        
        # Remove trailing semicolon for consistency
        sql = sql.rstrip(';')
        
        # Only allow safe read-only operations
        safe_prefixes = ['SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN']
        if not any(sql.upper().startswith(prefix) for prefix in safe_prefixes):
            self._log(f"Only read-only queries allowed. Query starts with: {sql[:20]}", level="warning")
            return "", False
        
        return sql, True

    def _format_deployment_result(self, result: dict) -> str:
        """Format deployment result with access URL and environment file info.
        
        Args:
            result: Deployment result dictionary
            
        Returns:
            Formatted result message
        """
        access_url = result.get("access_url")
        env_file = result.get("env_file")
        message = result.get("message", "Deployment completed successfully.")

        response = f"{message}"
        if access_url:
            response += f"\nApplication is accessible at: {access_url}"
        if env_file:
            response += f"\nEnvironment variables saved to: {env_file}"

        return response
