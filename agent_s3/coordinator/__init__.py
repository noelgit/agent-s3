"""Task Manager that orchestrates workflow phases.

Handles planning, prompt generation, issue creation, and execution phases.
"""

# Standard library imports
import json
import logging
import os
import re
import traceback
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Third-party imports
# None required

# Local imports
from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import (
    EnhancedScratchpadManager,
    LogLevel,
    Section,
)
from agent_s3.implementation_manager import ImplementationManager
from agent_s3.error_handler import ErrorHandler

from agent_s3.feature_group_processor import FeatureGroupProcessor
from agent_s3.file_history_analyzer import FileHistoryAnalyzer
from agent_s3.planner_json_enforced import Planner

from agent_s3.progress_tracker import ProgressTracker
from agent_s3.prompt_moderator import PromptModerator
from agent_s3.router_agent import RouterAgent
from agent_s3.design_manager import DesignManager
from agent_s3.task_resumer import TaskResumer
from agent_s3.task_state_manager import TaskStateManager
from agent_s3.tech_stack_detector import TechStackDetector
from agent_s3.workspace_initializer import WorkspaceInitializer

# Tool imports
from agent_s3.tools.ast_tool import ASTTool
from agent_s3.tools.bash_tool import BashTool
from agent_s3.tools.code_analysis_tool import CodeAnalysisTool
from agent_s3.tools.context_management.context_manager import ContextManager
from agent_s3.tools.context_management.context_registry import ContextRegistry
from agent_s3.tools.database_tool import DatabaseTool
from agent_s3.database_manager import DatabaseManager
from agent_s3.tools.embedding_client import EmbeddingClient
from agent_s3.tools.env_tool import EnvTool
from agent_s3.tools.error_context_manager import ErrorContextManager
from agent_s3.tools.file_tool import FileTool
from agent_s3.tools.git_tool import GitTool
from agent_s3.terminal_executor import TerminalExecutor
from agent_s3.tools.memory_manager import MemoryManager
from agent_s3.tools.test_critic import TestCritic
from agent_s3.tools.test_frameworks import TestFrameworks
from agent_s3.tools.test_runner_tool import TestRunnerTool
from agent_s3.workflows import PlanningWorkflow, ImplementationWorkflow
from agent_s3.debugging_manager import DebuggingManager
from agent_s3.code_generator import CodeGenerator
from .registry import CoordinatorRegistry

# Configure module logger. The logging system should be configured by the
# application entry point (e.g. the CLI) before importing this module.
logger = logging.getLogger(__name__)

class Coordinator:
    """Coordinates the workflow phases for Agent-S3."""

    def __init__(self, config=None, config_path: str = 'llm.json', github_token: str = None):
        """Initialize the coordinator.

        Args:
            config: Optional pre-loaded configuration object
            config_path: Path to the configuration file
            github_token: Optional GitHub OAuth token for API access
        """
        # Initialize configuration class to handle attributes
        if config is not None:
            self.config = config
        else:
            self.config = Config(config_path)
            self.config.load()

        self.coordinator_config = CoordinatorRegistry(self.config)
        if github_token is not None:
            self.coordinator_config.github_token = github_token

        # Initialize error handler
        self.error_handler = ErrorHandler(
            component="Coordinator",
            logger=logger,
            reraise=False,
            transform_exceptions=True,
            default_phase="initialization"
        )

        try:
            self._initialize_core_components()
            self._initialize_tools()
            self._initialize_specialized_components()
            self._initialize_communication()  # Add this line
            self._finalize_initialization()
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="initialization",
                level=logging.ERROR,
                reraise=True
            )

        # Lazy-initialized command processor
        self._command_processor = None

    @property
    def command_processor(self):
        """Lazily create and return the CommandProcessor instance."""
        if self._command_processor is None:
            from agent_s3.command_processor import CommandProcessor
            self._command_processor = CommandProcessor(self)
        return self._command_processor

    def _initialize_core_components(self) -> None:
        """Initialize core components and logging."""
        self.scratchpad = EnhancedScratchpadManager(self.config)
        self.progress_tracker = ProgressTracker(self.config)

        if hasattr(self.progress_tracker, 'register_semantic_validation_phase'):
            self.progress_tracker.register_semantic_validation_phase()

        self.task_state_manager = TaskStateManager(
            base_dir=os.path.join(
                os.path.dirname(self.config.get_log_file_path("development")),
                "task_snapshots"
            ),
            error_handler=self.error_handler,
        )
        self.current_task_id = None

    def _initialize_tools(self) -> None:
        """Initialize all tools and core functionality."""
        # Router agent initialization
        self.router_agent = RouterAgent(config=self.config)
        self.llm = self.router_agent

        # Initialize bash and related tools first so git can reuse the executor
        self.bash_tool = BashTool(
            sandbox=True,  # Sandbox always enabled for safety
            host_os_type=self.config.host_os_type
        )
        self.bash_tool.executor = TerminalExecutor(self.config)

        # Initialize file and git tools
        file_tool = FileTool()
        self.file_tool = file_tool
        git_tool = GitTool(self.config.github_token, terminal_executor=self.bash_tool.executor)

        # Initialize context management
        self.context_registry = ContextRegistry()
        self.context_manager = ContextManager(
            config=self.config.config.get('context_management', {}))

        # Initialize memory management first (needed by code analysis tool)
        self.embedding_client = EmbeddingClient(
            config=self.config.config,
            router_agent=self.router_agent
        )
        self.memory_manager = MemoryManager(
            config=self.config.config,
            embedding_client=self.embedding_client,
            file_tool=file_tool,
            llm_client=self.llm
        )

        # Initialize code analysis (depends on embedding_client)
        code_analysis_tool = CodeAnalysisTool(
            coordinator=self,
            file_tool=file_tool
        )

        # Initialize tech stack detection
        self.tech_stack_detector = TechStackDetector(
            config=self.config,
            file_tool=file_tool,
            scratchpad=self.scratchpad
        )

        # Initialize file history analyzer
        self.file_history_analyzer = FileHistoryAnalyzer(
            git_tool=git_tool,
            config=self.config,
            scratchpad=self.scratchpad
        )

        # Set up context manager tools
        self.context_manager.initialize_tools(
            tech_stack_detector=self.tech_stack_detector,
            code_analysis_tool=code_analysis_tool,
            file_history_analyzer=self.file_history_analyzer,
            file_tool=file_tool
        )

        # Register providers
        self.context_registry.register_provider("context_manager", self.context_manager)
        self.context_registry.register_provider("memory_manager", self.memory_manager)

        # Store tool references
        self.coordinator_config.register_tool('file_tool', file_tool)
        self.coordinator_config.register_tool('git_tool', git_tool)
        self.coordinator_config.register_tool('code_analysis_tool', code_analysis_tool)
        self.coordinator_config.register_tool('embedding_client', self.embedding_client)
        self.coordinator_config.register_tool('memory_manager', self.memory_manager)

        # Initialize remaining tools
        self._initialize_additional_tools(file_tool)

    def _initialize_additional_tools(self, file_tool: FileTool) -> None:
        """Initialize additional tools that depend on core tools."""
        # Database, environment, and AST tools
        self.database_tool = DatabaseTool(config=self.config, bash_tool=self.bash_tool)
        self.database_manager = DatabaseManager(coordinator=self, database_tool=self.database_tool)
        self.env_tool = EnvTool(self.bash_tool)
        self.ast_tool = ASTTool()

        # Test-related tools
        self.test_runner_tool = TestRunnerTool(self.bash_tool)
        self.test_frameworks = TestFrameworks(self)
        self.test_critic = TestCritic(self)

        # Error context management
        self.error_context_manager = ErrorContextManager(coordinator=self)

    def _initialize_specialized_components(self) -> None:
        """Initialize specialized components using the tools."""
        # Detect tech stack using existing detector
        self.tech_stack = self.tech_stack_detector.detect_tech_stack()

        # Initialize workspace
        self.workspace_initializer = WorkspaceInitializer(
            config=self.config,
            file_tool=self.coordinator_config.get_tool('file_tool'),
            scratchpad=self.scratchpad,
            tech_stack=self.tech_stack
        )

        # Feature group processor
        self.feature_group_processor = FeatureGroupProcessor(coordinator=self)

        # Implementation manager handles step-by-step execution of design tasks
        self.implementation_manager = ImplementationManager(
            coordinator=self,
            error_handler=self.error_handler,
        )

        # Design manager for interactive design conversations
        self.design_manager = DesignManager(coordinator=self)

        # Initialize core workflow components
        self._initialize_workflow_components()

    def _initialize_workflow_components(self) -> None:
        """Initialize components related to workflow management."""
        memory_manager = self.coordinator_config.get_tool('memory_manager')

        from agent_s3.planner_json_enforced import PlannerConfig
        planner_config = PlannerConfig(
            coordinator=self,
            scratchpad=self.scratchpad,
            tech_stack_detector=self.tech_stack_detector,
            memory_manager=memory_manager,
            database_tool=self.database_tool,
            test_frameworks=self.test_frameworks
        )
        self.planner = Planner(config=planner_config)

        self.code_generator = CodeGenerator(coordinator=self)
        self.prompt_moderator = PromptModerator(self)
        
        # Initialize debugging manager (depends on code_generator)
        self.debugging_manager = DebuggingManager(
            coordinator=self,
            enhanced_scratchpad=self.scratchpad
        )

        # Workflow pipelines
        self.planning_workflow = PlanningWorkflow(self)
        self.implementation_workflow = ImplementationWorkflow(self)

        # Update workspace initializer with prompt moderator
        if hasattr(self, 'workspace_initializer'):
            self.workspace_initializer.prompt_moderator = self.prompt_moderator

        # Task resumption
        self.task_resumer = TaskResumer(
            coordinator=self,
            task_state_manager=self.task_state_manager
        )

        # Initialize workflow orchestrator (lazy import to avoid circular import)
        from .orchestrator import WorkflowOrchestrator
        self.orchestrator = WorkflowOrchestrator(self, self.coordinator_config)

    def _initialize_communication(self) -> None:
        """Initialize communication components like the HTTP server."""
        from agent_s3.communication.http_server import EnhancedHTTPServer

        # Get host, port, and allowed origins from HTTP config, with defaults
        http_config = self.config.config.get('http', {})
        http_host = http_config.get('host', 'localhost')
        http_port = http_config.get('port', 8081)  # Default to 8081 for HTTP
        allowed_origins = http_config.get('allowed_origins', ['*'])
        auth_token = http_config.get('auth_token') or os.getenv('AGENT_S3_AUTH_TOKEN')

        self.http_server = EnhancedHTTPServer(
            host=http_host,
            port=http_port,
            coordinator=self,
            allowed_origins=allowed_origins,
            auth_token=auth_token,
        )
        # Start the server in a separate thread so it doesn't block the coordinator
        self.http_thread = self.http_server.start_in_thread()
        self.scratchpad.log("Coordinator", f"HTTP server starting on http://{http_host}:{http_port}")


    def _finalize_initialization(self) -> None:
        """Finalize the initialization process."""
        # Start background optimization (always enabled)
        self.context_manager._start_background_optimization()

        # Check for interrupted tasks
        if hasattr(self, 'task_resumer') and self.task_resumer:
            self.task_resumer.check_for_interrupted_tasks()

        # GitHub integration handled through existing GitTool

        # Log initialization success
        self.scratchpad.log("Coordinator", "Initialized Agent-S3 coordinator")
        if not self.progress_tracker.get_latest_progress():
            self.progress_tracker.update_progress({
                "phase": "initialization",
                "status": "pending"
            })

    def _extract_keywords_from_task(self, task_description: str) -> List[str]:
        """Extracts keywords from a task description.

        Args:
            task_description: The task description string.

        Returns:
            A list of keywords.
        """
        if not task_description:
            return []
        # Simple keyword extraction: lowercase, split by non-alphanumeric, filter short words and common stop words
        words = re.findall(r'\b\w+\b', task_description.lower())
        # Define a basic list of stop words, can be expanded
        stop_words = {"a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "should",
                      "can", "could", "may", "might", "must", "and", "or", "but", "if",
                      "of", "at", "by", "for", "with", "about", "to", "from", "in", "out",
                      "on", "off", "over", "under", "again", "further", "then", "once",
                      "here", "there", "when", "where", "why", "how", "all", "any", "both",
                      "each", "few", "more", "most", "other", "some", "such", "no", "nor",
                      "not", "only", "own", "same", "so", "than", "too", "very", "s", "t",
                      "just", "don", "shouldve", "now", "d", "ll", "m", "o", "re", "ve", "y",
                      "ain", "aren", "couldn", "didn", "doesn", "hadn", "hasn", "haven",
                      "isn", "ma", "mightn", "mustn", "needn", "shan", "shouldn", "wasn",
                      "weren", "won", "wouldn", "i", "me", "my", "myself", "we", "our",
                      "ours", "ourselves", "you", "your", "yours", "yourself", "yourselves",
                      "he", "him", "his", "himself", "she", "her", "hers", "herself", "it",
                      "its", "itself", "they", "them", "their", "theirs", "themselves",
                      "what", "which", "who", "whom", "this", "that", "these", "those",
                      "am", "create", "update", "delete", "remove", "add", "implement",
                      "make", "ensure", "fix", "refactor", "change", "modify", "develop"}

        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        # Return unique keywords
        return list(set(keywords))

    def shutdown(self):
        """Gracefully shuts down coordinator components."""
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="shutdown",
            operation="shutdown",
            reraise=False  # Don't re-raise exceptions during shutdown
        ):
            self.scratchpad.log("Coordinator", "Shutting down Agent-S3 coordinator...")

            # Stop HTTP server first
            if hasattr(self, 'http_server') and self.http_server:
                try:
                    self.scratchpad.log("Coordinator", "Stopping HTTP server...")
                    self.http_server.stop_sync()
                    self.scratchpad.log("Coordinator", "HTTP server stopped.")
                except Exception as e:
                    self.scratchpad.log("Coordinator", f"Error stopping HTTP server: {e}", level=LogLevel.ERROR)

            # Stop planner observer if it exists
            if hasattr(self, 'planner') and self.planner and hasattr(self.planner, 'stop_observer'):
                self.planner.stop_observer()

            # Clean up context management
            if hasattr(self, 'context_manager') and self.context_manager:
                try:
                    self.scratchpad.log("Coordinator", "Stopping context management background optimization")
                    self.context_manager._stop_background_optimization()
                except Exception as e:
                    self.scratchpad.log("Coordinator", f"Error stopping context management: {e}", level=LogLevel.ERROR)

            # Save memory manager state
            if hasattr(self, 'memory_manager') and self.memory_manager and hasattr(self.memory_manager, 'save_state'):
                self.memory_manager.save_state()

            # Save embedding client state
            if hasattr(self, 'embedding_client') and self.embedding_client and hasattr(self.embedding_client, 'save_state'):
                self.embedding_client.save_state()
            # Close enhanced scratchpad
            if hasattr(self, 'scratchpad') and hasattr(self.scratchpad, 'close'):
                self.scratchpad.close()

            self.scratchpad.log("Coordinator", "Shutdown complete.")

    def get_current_context_snapshot(self, context_type: str = None, query: str = None):
        """Return a copy of the current, background-refined context state."""
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="context",
            operation="get_current_context_snapshot"
        ):
            return self.context_registry.get_current_context_snapshot(context_type=context_type, query=query)

    def _prepare_context(self, task_description: str) -> Dict[str, Any]:
        """Prepare context by gathering all relevant information.

        Uses ContextManager.gather_context with extracted keywords for primary context.
        Also includes snapshots from ContextRegistry for supplementary information.

        Args:
            task_description: The task description to provide context for

        Returns:
            Dictionary with consolidated context information
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="context",
            operation="prepare_context",
            inputs={"task_description": task_description}
        ):
            context = {}
            task_keywords = self._extract_keywords_from_task(task_description)
            self.scratchpad.log("Coordinator", f"Extracted keywords for context preparation: {task_keywords}")

            try:
                # Primary context gathering using ContextManager and keywords
                if self.context_manager:
                    # Determine task type (can be enhanced later)
                    task_type = "planning"  # Default for pre-planning

                    gathered_context_items = self.context_manager.gather_context(
                        task_description=task_description,
                        task_type=task_type,
                        task_keywords=task_keywords,
                        max_tokens=self.config.config.get('context_management', {}).get('max_tokens_for_pre_planning', 4000)
                    )

                    processed_gathered_context = {}
                    for item in gathered_context_items:
                        if item.file_path:
                            key_name = f"file_{item.file_path.replace('/', '_')}"
                            processed_gathered_context[key_name] = {
                                "content": item.content,
                                "type": item.type,
                                "importance": item.importance_score,
                                "token_count": item.token_count,
                                "reason": item.reasoning
                            }
                        elif item.identifier:
                             processed_gathered_context[item.identifier] = {
                                "content": item.content,
                                "type": item.type,
                                "importance": item.importance_score,
                                "token_count": item.token_count,
                                "reason": item.reasoning
                            }
                        else:
                            processed_gathered_context[f"context_item_{len(processed_gathered_context)}"] = {
                                "content": item.content,
                                "type": item.type,
                                "importance": item.importance_score,
                                "token_count": item.token_count,
                                "reason": item.reasoning
                            }
                    context["focused_context"] = processed_gathered_context
                    self.scratchpad.log("Coordinator", f"Focused context gathered with {len(gathered_context_items)} items.")

                # Supplementary context from registry (less focused, more general)
                tech_stack_snapshot = self.get_current_context_snapshot(
                    context_type="tech_stack"
                )
                if tech_stack_snapshot:
                    context.update(tech_stack_snapshot)
                project_structure_snapshot = self.get_current_context_snapshot(
                    context_type="project_structure"
                )
                if project_structure_snapshot:
                    context.update(project_structure_snapshot)
                deps_snapshot = self.get_current_context_snapshot(
                    context_type="dependencies"
                )
                if deps_snapshot:
                    context.update(deps_snapshot)

            except Exception as e:
                self.scratchpad.log("Coordinator", f"Error preparing context: {e}\n{traceback.format_exc()}", level=LogLevel.WARNING)
            return context

    def _gather_context(self) -> Dict[str, Any]:
        """Gather context snippets for explaining the last LLM interaction."""
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="context",
            operation="gather_context",
        ):
            raw_context = self._prepare_context("explain last interaction")
            snippets = {}

            if "tech_stack" in raw_context:
                snippets["tech_stack"] = raw_context["tech_stack"]

            focused = raw_context.get("focused_context", {})
            if focused:
                item_limit = self.config.config.get("llm_explain_context_items_limit", 3)
                snippets["focused_context"] = dict(list(focused.items())[:item_limit])

            return snippets

    def explain_last_llm_interaction(self, context: Dict[str, Any]) -> None:
        """Print a formatted explanation of the last LLM interaction."""
        interaction = self.scratchpad.get_last_llm_interaction()
        if not interaction:
            print("No LLM interaction has been logged yet.")
            return

        print("\n# Last LLM Interaction Explanation\n")
        print(f"Role: {interaction.get('role', 'unknown')}")
        print(f"Status: {interaction.get('status', 'unknown')}")
        print(f"Timestamp: {interaction.get('timestamp', 'unknown')}\n")

        print("## Prompt\n" + interaction.get("prompt", "") + "\n")
        print("## Response\n" + interaction.get("response", "") + "\n")

        if context.get("tech_stack"):
            print("## Tech Stack")
            print(json.dumps(context["tech_stack"], indent=2))
            print()

        focused = context.get("focused_context", {})
        if focused:
            print("## Code Snippets")
            for name, data in focused.items():
                snippet = data.get("content", "")
                print(f"### {name}\n{snippet}\n")

        if interaction.get("error"):
            print("## Error")
            print(interaction.get("error"))

    def debug_last_test(self) -> Optional[str]:
        """Attempt to debug the most recent failing test output."""
        last = self.progress_tracker.get_latest_progress()
        if not last or "output" not in last:
            return None

        self.scratchpad.start_section(Section.DEBUGGING, "Coordinator")
        output = last["output"]
        try:
            context = self.error_context_manager.collect_error_context(
                error_message=output
            )
            attempted, result = self.error_context_manager.attempt_automated_recovery(
                context, context
            )

            if attempted and "failed" not in str(result).lower():
                self.scratchpad.log(
                    "Coordinator",
                    f"Automated recovery succeeded: {result}",
                    level=LogLevel.INFO,
                )

            if not attempted or "failed" in str(result).lower():
                debug_result = self.debugging_manager.handle_error(
                    error_message=output,
                    traceback_text=output,
                    file_path=context.get("parsed_error", {}).get("file_paths", [None])[0],
                    line_number=context.get("parsed_error", {}).get("line_numbers", [None])[0],
                )
                self.scratchpad.log(
                    "Coordinator",
                    f"Advanced debugging completed: {debug_result.get('description')}",
                    level=LogLevel.INFO if debug_result.get("success") else LogLevel.WARNING,
                )
            return None
        except Exception as exc:  # pragma: no cover - defensive
            self.progress_tracker.update_progress({
                "phase": "debug",
                "status": "failed",
                "error": str(exc),
                "timestamp": datetime.now().isoformat(),
            })
            return f"Error during finalization: {exc}"
        finally:
            self.scratchpad.end_section(Section.DEBUGGING)

    # _execute_pre_planning_phase method removed as it's redundant with inline implementation in run_task

    def _present_pre_planning_results_to_user(self, pre_planning_results: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """Present the pre-planning results to the user and get their decision.

        The second return value contains the modification text when the user
        chooses to refine the plan, otherwise ``None``.
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="pre_planning",
            operation="present_results_to_user"
        ):
            display_results = dict(pre_planning_results)
            display_results.pop("test_requirements", None)
            formatted_json = json.dumps(display_results, indent=2)
            self.scratchpad.log("Coordinator", "Pre-planning complete. Review the proposed approach:")
            print("\n" + formatted_json + "\n")
            decision = self.prompt_moderator.ask_ternary_question(
                "Do you want to proceed with this plan, modify it, or cancel?"
            )
            if decision == "yes":
                # Additional confirmation if the task was flagged as complex
                is_complex = pre_planning_results.get("is_complex", False)
                score = pre_planning_results.get("complexity_score", 0)
                threshold = self.config.config.get("complexity_threshold", 0)
                if is_complex or score >= threshold:
                    confirm = self.prompt_moderator.ask_yes_no_question(
                        "This plan is complex. Are you sure you want to continue?"
                    )
                    if not confirm:
                        self.scratchpad.log(
                            "Coordinator",
                            "User cancelled after reviewing complex plan.",
                        )
                        return "no", None

                self.scratchpad.log(
                    "Coordinator", "User approved pre-planning results."
                )
                return decision, None
            elif decision == "no":
                self.scratchpad.log("Coordinator", "User rejected pre-planning results.")
                return decision, None
            else:
                self.scratchpad.log("Coordinator", "User chose to modify pre-planning results.")
                modification = self.prompt_moderator.ask_for_modification(
                    "Please describe your modifications:"
                )
                return "modify", modification

    def plan_approval_loop(self, plan: Dict[str, Any], original_plan: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Run the plan approval loop to get user approval for a plan.
        
        This method presents the plan to the user, handles modifications, validates
        the modified plan, and continues the loop until the user approves or rejects
        the plan or the maximum number of iterations is reached.
        
        Args:
            plan: The plan to approve
            original_plan: Optional original plan for comparison in validation
            
        Returns:
            Tuple of (decision, final_plan)
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="plan_approval",
            operation="plan_approval_loop"
        ):
            self.scratchpad.log("Coordinator", "Starting plan approval loop")

            # Initialize loop variables
            current_plan = plan
            iteration = 0
            max_iterations = self.prompt_moderator.max_plan_iterations

            # Create a static plan checker for validation
            from agent_s3.tools.static_plan_checker import StaticPlanChecker
            plan_checker = StaticPlanChecker(context_registry=self.context_registry)

            while iteration < max_iterations:
                iteration += 1
                self.scratchpad.log("Coordinator", f"Plan approval iteration {iteration}/{max_iterations}")

                # Present the plan to the user
                decision, modification_text = self.prompt_moderator.present_consolidated_plan(current_plan)

                if decision == "yes":
                    self.scratchpad.log("Coordinator", "User approved the plan")
                    return "yes", current_plan
                elif decision == "no":
                    self.scratchpad.log("Coordinator", "User rejected the plan")
                    return "no", current_plan
                elif decision == "modify":
                    self.scratchpad.log("Coordinator", "User chose to modify the plan")

                    # Handle user modification
                    try:
                        # Import the regeneration function from planning module
                        from agent_s3.planning.plan_generation import regenerate_consolidated_plan_with_modifications

                        # Regenerate the plan with modifications
                        modified_plan = regenerate_consolidated_plan_with_modifications(
                            self.router_agent,
                            current_plan,
                            modification_text
                        )

                        # Validate the modified plan
                        is_valid, validation_results = plan_checker.validate_plan(modified_plan, original_plan or current_plan)

                        if is_valid:
                            self.scratchpad.log("Coordinator", "Modified plan validation successful")
                            current_plan = modified_plan
                        else:
                            # Display validation errors
                            critical_errors = validation_results.get("critical", [])
                            if critical_errors:
                                print("\n❌ VALIDATION ERRORS:")
                                for error in critical_errors[:5]:  # Show only first 5 errors
                                    error_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
                                    print(f"  - {error_msg}")

                                # Ask if user wants to proceed anyway
                                proceed_anyway = self.prompt_moderator.ask_yes_no_question(
                                    "The modified plan has validation errors. Do you want to proceed anyway?"
                                )

                                if proceed_anyway:
                                    self.scratchpad.log("Coordinator", "User chose to proceed with invalid plan")
                                    current_plan = modified_plan
                                else:
                                    self.scratchpad.log("Coordinator", "User chose not to proceed with invalid plan")
                                    # Continue with the original plan for this iteration
                            else:
                                # No critical errors, just warnings
                                warnings = validation_results.get("warnings", [])
                                if warnings:
                                    print("\n⚠️ VALIDATION WARNINGS:")
                                    for warning in warnings[:5]:  # Show only first 5 warnings
                                        warning_msg = warning.get("message", str(warning)) if isinstance(warning, dict) else str(warning)
                                        print(f"  - {warning_msg}")

                                # Proceed with the modified plan
                                self.scratchpad.log("Coordinator", "Modified plan has warnings but no critical errors")
                                current_plan = modified_plan
                    except Exception as e:
                        self.error_handler.handle_exception(
                            exc=e,
                            phase="plan_approval",
                            operation="handle_modification",
                            level=logging.ERROR,
                            reraise=False
                        )

                        print(f"\n❌ ERROR: Failed to apply modifications: {str(e)}")

                        # Ask if user wants to try again
                        try_again = self.prompt_moderator.ask_yes_no_question(
                            "Do you want to try modifying the plan again?"
                        )

                        if not try_again:
                            self.scratchpad.log("Coordinator", "User chose not to try modifying again")
                            return "no", current_plan

                # Check if we've reached the maximum number of iterations
                if iteration >= max_iterations:
                    print(f"\n⚠️ Maximum number of modification iterations ({max_iterations}) reached.")

                    # Ask if user wants to proceed with the current plan
                    proceed = self.prompt_moderator.ask_yes_no_question(
                        "Do you want to proceed with the current plan?"
                    )

                    if proceed:
                        self.scratchpad.log("Coordinator", "User chose to proceed after max iterations")
                        return "yes", current_plan
                    else:
                        self.scratchpad.log("Coordinator", "User chose not to proceed after max iterations")
                        return "no", current_plan

            # Default return if loop exits unexpectedly
            return "no", current_plan

    def execute_design(self, objective: str) -> Dict[str, Any]:
        """Orchestrate the interactive design workflow.

        Args:
            objective: The user's design objective.

        Returns:
            Dictionary with success flag, design file path, and next action.
        """
        with self.error_handler.error_context(
            phase="design",
            operation="execute_design",
            inputs={"objective": objective},
        ):
            try:
                response = self.design_manager.start_design_conversation(objective)
                if response:
                    print(response)
            except Exception as e:
                self.scratchpad.log("Coordinator", f"Failed to start design: {e}", level=LogLevel.ERROR)
                return {"success": False, "error": str(e)}

            # Continue conversation until completion
            while True:
                try:
                    user_input = input()
                except (KeyboardInterrupt, EOFError):
                    return {"success": False, "cancelled": True}

                try:
                    response, is_complete = self.design_manager.continue_conversation(user_input)
                    if response:
                        print(response)
                    if is_complete or self.design_manager.detect_design_completion():
                        break
                except Exception as e:
                    self.scratchpad.log(
                        "Coordinator",
                        f"Error during design conversation: {e}",
                        level=LogLevel.ERROR,
                    )
                    return {"success": False, "error": str(e)}

            success, message = self.design_manager.write_design_to_file()
            if not success:
                return {"success": False, "error": message}

            choices = self.design_manager.prompt_for_implementation()
            next_action = None
            if choices.get("implementation"):
                next_action = "implementation"
                if hasattr(self, "start_pre_planning_from_design"):
                    self.start_pre_planning_from_design("design.txt")
            elif choices.get("deployment"):
                next_action = "deployment"

            return {
                "success": True,
                "design_file": os.path.join(os.getcwd(), "design.txt"),
                "next_action": next_action,
            }

    def execute_design_auto(self, objective: str) -> Dict[str, Any]:
        """Run design and planning automatically with all confirmations."""
        original_auto = getattr(self.prompt_moderator, "auto_confirm", False)
        self.prompt_moderator.set_auto_confirm(True)
        try:
            response = self.design_manager.start_design_conversation(objective)
            if response:
                print(response)

            self.design_manager.continue_conversation("/finalize-design")
            success, message = self.design_manager.write_design_to_file()
            if not success:
                return {"success": False, "error": message}

            planning_result = self.start_pre_planning_from_design(
                "design.txt", implement=False
            )
            if not planning_result.get("success", False):
                return planning_result

            return {
                "success": True,
                "design_file": os.path.join(os.getcwd(), "design.txt"),
                "next_action": None,
            }
        finally:
            self.prompt_moderator.set_auto_confirm(original_auto)

    # ------------------------------------------------------------------
    # Task Execution Workflow
    # ------------------------------------------------------------------

    def process_change_request(self, request_text: str) -> None:
        """Public facade for processing a change request.

        Args:
            request_text: The feature request to process.
        """
        self.run_task(task=request_text)


    def run_task(
        self,
        task: str,
        pre_planning_input: Optional[Dict[str, Any]] = None,
        *,
        from_design: bool = False,
        implement: bool = True,
    ) -> None:
        """Delegate task execution to the workflow orchestrator."""
        # Ensure any residual context from previous tasks is cleared
        if hasattr(self, "context_manager") and self.context_manager:
            self.context_manager.clear_context()

        self.orchestrator.run_task(
            task,
            pre_planning_input,
            from_design=from_design,
            implement=implement,
        )

    def execute_implementation(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Delegate execution to the workflow orchestrator."""
        return self.orchestrator.execute_implementation(design_file)

    def execute_continue(self, continue_type: str = "implementation") -> Dict[str, Any]:
        """Delegate continuation to the workflow orchestrator."""
        return self.orchestrator.execute_continue(continue_type)

    def start_pre_planning_from_design(self, design_file: str = "design.txt", *, implement: bool = True) -> Dict[str, Any]:
        """Delegate pre-planning start to the workflow orchestrator."""
        return self.orchestrator.start_pre_planning_from_design(design_file, implement=implement)

    def initialize_workspace(self) -> Dict[str, Any]:
        """Initialize the workspace using the workspace initializer.
        
        Returns:
            Dictionary with success status, validation result, and any errors.
        """
        try:
            # Call the workspace initializer
            is_valid = self.workspace_initializer.initialize_workspace()
            
            # Get validation details
            validation_reason = getattr(self.workspace_initializer, 'validation_failure_reason', None)
            
            result = {
                "success": True,
                "is_workspace_valid": is_valid,
                "created_files": [],  # Could be enhanced to track created files
                "errors": [] if is_valid else [validation_reason] if validation_reason else ["Workspace validation failed"]
            }
            
            # Add validation failure reason if available
            if validation_reason:
                result["validation_failure_reason"] = validation_reason
                
            return result
            
        except PermissionError as e:
            error_msg = str(e)
            self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
            return {
                "success": False,
                "is_workspace_valid": False,
                "created_files": [],
                "errors": [{"type": "permission", "message": error_msg}]
            }
        except Exception as e:
            error_msg = str(e)
            self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
            return {
                "success": False,
                "is_workspace_valid": False,
                "created_files": [],
                "errors": [{"type": "exception", "message": error_msg}]
            }

    def gather_initial_code_context(self) -> bool:
        """Gather initial codebase context for the workspace.
        
        This method triggers the context management system to analyze and index
        the codebase, making it ready for Agent-S3 operations.
        
        Returns:
            bool: True if context gathering succeeded, False otherwise
        """
        try:
            self.scratchpad.log("Coordinator", "Starting initial codebase context gathering")
            
            # Check if context management is available
            if not hasattr(self, 'context_manager') or not self.context_manager:
                self.scratchpad.log("Coordinator", "Context manager not available, skipping context gathering", level=LogLevel.WARNING)
                return False
            
            # Update context with current workspace
            workspace_files = self._discover_workspace_files()
            if workspace_files:
                # Use context manager to gather and optimize context
                context_data = {
                    "code_context": {},
                    "documentation": {},
                    "configuration": {},
                    "metadata": {
                        "workspace_initialized": True,
                        "context_gathering_time": datetime.now().isoformat()
                    }
                }
                
                # Add tech stack detection
                if hasattr(self, 'tech_stack_detector') and self.tech_stack_detector:
                    try:
                        tech_stack_info = self.tech_stack_detector.detect_tech_stack()
                        context_data["tech_stack"] = tech_stack_info
                        self.scratchpad.log("Coordinator", f"Detected tech stack: {tech_stack_info.get('primary_language', 'unknown')}")
                    except Exception as tech_error:
                        self.scratchpad.log("Coordinator", f"Error detecting tech stack: {tech_error}", level=LogLevel.DEBUG)
                
                # Add project structure summary
                try:
                    project_structure = self._analyze_project_structure(workspace_files)
                    context_data["project_structure"] = project_structure
                except Exception as struct_error:
                    self.scratchpad.log("Coordinator", f"Error analyzing project structure: {struct_error}", level=LogLevel.DEBUG)
                
                # Add discovered files to context
                for file_type, files in workspace_files.items():
                    for file_path in files[:10]:  # Limit initial context
                        try:
                            if file_path.stat().st_size < 50000:  # 50KB limit
                                content = file_path.read_text(encoding='utf-8', errors='ignore')
                                relative_path = str(file_path.relative_to(Path.cwd()))
                                
                                if file_type == 'code':
                                    context_data["code_context"][relative_path] = content
                                elif file_type == 'docs':
                                    context_data["documentation"][relative_path] = content
                                elif file_type == 'config':
                                    context_data["configuration"][relative_path] = content
                                    
                        except Exception as file_error:
                            self.scratchpad.log("Coordinator", f"Error reading file {file_path}: {file_error}", level=LogLevel.DEBUG)
                
                # Update context manager with initial context
                self.context_manager.update_context(context_data)
                
                # Trigger initial optimization
                if hasattr(self.context_manager, 'ensure_background_optimization_running'):
                    self.context_manager.ensure_background_optimization_running()
                
                self.scratchpad.log("Coordinator", f"Initial context gathered with {len(context_data['code_context'])} code files")
                return True
            else:
                self.scratchpad.log("Coordinator", "No relevant files found for context gathering")
                return True  # Not an error, just an empty workspace
                
        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error during context gathering: {e}", level=LogLevel.ERROR)
            return False

    def _discover_workspace_files(self) -> Dict[str, list]:
        """Discover files in the workspace for context gathering.
        
        Returns:
            Dict mapping file types to lists of file paths
        """
        try:
            workspace_root = Path.cwd()
            
            # File type mappings
            code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go', '.rs', '.php', '.swift', '.kt'}
            config_extensions = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf'}
            doc_extensions = {'.md', '.rst', '.txt'}
            
            discovered_files = {
                'code': [],
                'config': [],
                'docs': []
            }
            
            # Ignore patterns for file discovery
            ignore_patterns = {
                'node_modules', '.git', '__pycache__', '.mypy_cache', '.pytest_cache',
                'dist', 'build', '.venv', 'venv', '.env', 'coverage_html', '.agent_s3'
            }
            
            # Scan for relevant files
            for file_path in workspace_root.rglob('*'):
                if (file_path.is_file() and 
                    not any(pattern in str(file_path) for pattern in ignore_patterns) and
                    not file_path.name.startswith('.')):
                    
                    if file_path.suffix in code_extensions:
                        discovered_files['code'].append(file_path)
                    elif file_path.suffix in config_extensions:
                        discovered_files['config'].append(file_path)
                    elif file_path.suffix in doc_extensions:
                        discovered_files['docs'].append(file_path)
            
            # Sort by modification time (most recent first) and limit results
            for file_type in discovered_files:
                discovered_files[file_type].sort(key=lambda f: f.stat().st_mtime, reverse=True)
                discovered_files[file_type] = discovered_files[file_type][:20]  # Limit per type
            
            return discovered_files
            
        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error discovering workspace files: {e}", level=LogLevel.WARNING)
            return {}
    
    def _analyze_project_structure(self, workspace_files: Dict[str, list]) -> Dict[str, Any]:
        """Analyze project structure for planning context.
        
        Args:
            workspace_files: Dict mapping file types to lists of file paths
            
        Returns:
            Dict containing project structure analysis
        """
        try:
            structure = {
                "directories": {},
                "file_counts": {},
                "patterns": [],
                "entry_points": []
            }
            
            # Count files by type and directory
            all_files = []
            for file_type, files in workspace_files.items():
                structure["file_counts"][file_type] = len(files)
                all_files.extend(files)
            
            # Analyze directory structure
            directories = set()
            for file_path in all_files:
                parts = file_path.parts[:-1]  # Exclude filename
                for i in range(1, len(parts) + 1):
                    directories.add('/'.join(parts[:i]))
            
            structure["directories"] = {
                "total_dirs": len(directories),
                "main_dirs": sorted(list(directories))[:10]  # Top 10 directories
            }
            
            # Identify common patterns
            patterns = []
            code_files = workspace_files.get('code', [])
            
            # Look for common entry points
            entry_points = []
            for file_path in code_files:
                filename = file_path.name.lower()
                if filename in ['main.py', 'app.py', 'index.js', 'index.ts', 'server.js', 'app.js']:
                    entry_points.append(str(file_path.relative_to(Path.cwd())))
                elif filename == 'package.json' and file_path in workspace_files.get('config', []):
                    try:
                        with open(file_path, 'r') as f:
                            pkg_data = json.loads(f.read())
                            if 'main' in pkg_data:
                                entry_points.append(f"package.json -> {pkg_data['main']}")
                    except (json.JSONDecodeError, IOError, KeyError):
                        pass
            
            structure["entry_points"] = entry_points
            
            # Detect project patterns
            if any('src/' in str(f) for f in code_files):
                patterns.append("src_directory_structure")
            if any('test' in str(f).lower() for f in code_files):
                patterns.append("test_directory_present")
            if 'package.json' in [f.name for f in workspace_files.get('config', [])]:
                patterns.append("npm_project")
            if any(f.name in ['requirements.txt', 'pyproject.toml', 'setup.py'] for f in workspace_files.get('config', [])):
                patterns.append("python_project")
            
            structure["patterns"] = patterns
            
            return structure
            
        except Exception as e:
            self.scratchpad.log("Coordinator", f"Error analyzing project structure: {e}", level=LogLevel.WARNING)
            return {"error": str(e)}

    def get_current_timestamp(self) -> str:
        """Get the current timestamp in ISO format.
        
        Returns:
            ISO formatted timestamp string.
        """
        from datetime import datetime
        return datetime.now().isoformat()

    def _run_validation_phase(self) -> Dict[str, Any]:
        """Delegate validation phase to the workflow orchestrator."""
        return self.orchestrator._run_validation_phase()

    def _run_tests(self) -> Dict[str, Any]:
        """Delegate test execution to the workflow orchestrator."""
        return self.orchestrator._run_tests()

    def _apply_changes_and_manage_dependencies(self, changes: Dict[str, str]) -> bool:
        """Delegate changes application to the workflow orchestrator."""
        return self.orchestrator._apply_changes_and_manage_dependencies(changes)

    def _validate_pre_planning_data(self, data: Any) -> bool:
        """Validate the structure of pre-planning data.
        
        Args:
            data: The pre-planning data to validate
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            ValueError: If data structure is fundamentally invalid
        """
        self.scratchpad.log("Coordinator", "Validating pre-planning data structure...")
        
        # Check if data is a dictionary
        if not isinstance(data, dict):
            raise ValueError("Pre-planning data must be a dictionary")
        
        # Check if feature_groups key exists
        if "feature_groups" not in data:
            raise ValueError("Pre-planning data missing feature_groups")
        
        # Check if feature_groups is a list and not empty
        feature_groups = data["feature_groups"]
        if not isinstance(feature_groups, list):
            raise ValueError("feature_groups must be a list")
        
        if len(feature_groups) == 0:
            raise ValueError("feature_groups is empty")
        
        # Basic validation of feature group structure
        for i, group in enumerate(feature_groups):
            if not isinstance(group, dict):
                raise ValueError(f"Feature group {i} must be a dictionary")
            
            required_keys = ["group_name", "group_description", "features"]
            for key in required_keys:
                if key not in group:
                    raise ValueError(f"Feature group {i} missing required key: {key}")
        
        return True

    # ------------------------------------------------------------------
    # Execution resume helpers
    # ------------------------------------------------------------------

    def _execute_changes_atomically(
        self,
        changes: List[Dict[str, Any]],
        iteration: int,
        *,
        already_applied: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Apply file changes atomically using file and git tools."""
        file_tool = getattr(self, "file_tool", None)
        git_tool = getattr(self, "git_tool", None)
        if file_tool is None:
            raise RuntimeError("File tool not available")

        try:
            for change in changes:
                file_tool.write_file(change.get("path"), change.get("content", ""))
                if git_tool:
                    git_tool.add_file(change.get("path"))
        except Exception as exc:  # pragma: no cover - defensive
            if git_tool:
                git_tool.reset_hard()
            self.scratchpad.log(
                "Coordinator",
                f"Failed to apply changes in iteration {iteration}: {exc}",
                level=LogLevel.ERROR,
            )
            raise

    def _run_tests_after_changes(self, changes: List[Dict[str, Any]], iteration: int) -> Dict[str, Any]:
        """Run project tests after applying changes."""
        self.scratchpad.log(
            "Coordinator",
            f"Running tests after applying changes for iteration {iteration}",
        )
        return self.orchestrator._run_tests()

    def _analyze_test_results(
        self,
        raw_output: str,
        changes: List[Dict[str, Any]],
        iteration: int,
    ) -> Dict[str, Any]:
        """Analyze raw test output for resume workflow."""
        parser = getattr(self.test_runner_tool, "parse_test_output", None)
        if callable(parser):
            return parser(raw_output)
        return {"output": raw_output}

    # ------------------------------------------------------------------
    # Pull request helpers
    # ------------------------------------------------------------------

    def _create_pr_branch(self, branch_name: str, base_branch: str = "main") -> Dict[str, Any]:
        """Create a new branch for the pull request."""
        git_tool = self.coordinator_config.get_tool("git_tool")
        if not git_tool:
            raise RuntimeError("Git tool not available")

        result = git_tool.create_branch(branch_name, source_branch=base_branch)
        if not result.get("success"):
            self.scratchpad.log("Coordinator", result.get("message", "Failed to create branch"), level=LogLevel.ERROR)
            raise RuntimeError(result.get("message", "Failed to create branch"))
        return result

    def _stage_pr_changes(self, files: Optional[List[str]] = None) -> None:
        """Stage changes for commit."""
        git_tool = self.coordinator_config.get_tool("git_tool")
        if not git_tool:
            raise RuntimeError("Git tool not available")

        if files:
            file_list = " ".join([f'\"{f}\"' for f in files])
            git_tool.run_git_command(f"add {file_list}")
        else:
            git_tool.run_git_command("add -A")

    def _commit_pr_changes(self, commit_message: str) -> Dict[str, Any]:
        """Commit staged changes."""
        git_tool = self.coordinator_config.get_tool("git_tool")
        if not git_tool:
            raise RuntimeError("Git tool not available")

        result = git_tool.commit_changes(commit_message, add_all=False)
        if not result.get("success"):
            self.scratchpad.log("Coordinator", result.get("message", "Failed to commit"), level=LogLevel.ERROR)
            raise RuntimeError(result.get("message", "Failed to commit"))
        return result

    def _push_pr_branch(self, branch_name: str) -> Dict[str, Any]:
        """Push the PR branch to the remote."""
        git_tool = self.coordinator_config.get_tool("git_tool")
        if not git_tool:
            raise RuntimeError("Git tool not available")

        result = git_tool.push_changes(branch_name, set_upstream=True)
        if not result.get("success"):
            self.scratchpad.log("Coordinator", result.get("message", "Failed to push"), level=LogLevel.ERROR)
            raise RuntimeError(result.get("message", "Failed to push"))
        return result

    def _submit_pr(
        self,
        branch_name: str,
        pr_title: str,
        pr_body: str,
        base_branch: str = "main",
        draft: bool = False,
    ) -> str:
        """Create the pull request via GitHub API."""
        git_tool = self.coordinator_config.get_tool("git_tool")
        if not git_tool:
            raise RuntimeError("Git tool not available")

        pr_url = git_tool.create_pull_request(
            pr_title,
            pr_body,
            head_branch=branch_name,
            base_branch=base_branch,
            draft=draft,
        )
        if not pr_url:
            self.scratchpad.log("Coordinator", "Failed to create pull request", level=LogLevel.ERROR)
            raise RuntimeError("Failed to create pull request")

        self.scratchpad.log("Coordinator", f"Created PR: {pr_url}")
        return pr_url

    def _create_pr(
        self,
        changes: List[Dict[str, Any]],
        pr_body: str,
        branch_name: Optional[str] = None,
        pr_title: Optional[str] = None,
        base_branch: str = "main",
        draft: bool = False,
    ) -> str:
        """High level helper to create a pull request from changes."""
        if branch_name is None:
            branch_name = f"agent-s3-pr-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if pr_title is None:
            pr_title = "Agent-S3 Automated PR"

        self._create_pr_branch(branch_name, base_branch)
        self._stage_pr_changes()
        self._commit_pr_changes(pr_title)
        self._push_pr_branch(branch_name)
        return self._submit_pr(branch_name, pr_title, pr_body, base_branch, draft)
