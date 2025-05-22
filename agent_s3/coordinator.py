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

# Third-party imports
# None required

# Local imports
from agent_s3.config import Config
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager, LogLevel
from agent_s3.implementation_manager import ImplementationManager
from agent_s3.error_handler import ErrorHandler

from agent_s3.feature_group_processor import FeatureGroupProcessor
from agent_s3.file_history_analyzer import FileHistoryAnalyzer
from agent_s3.planner import Planner
from agent_s3.pre_planner_json_enforced import (
    call_pre_planner_with_enforced_json,
    pre_planning_workflow,
)
from agent_s3.progress_tracker import ProgressTracker
from agent_s3.prompt_moderator import PromptModerator
from agent_s3.router_agent import RouterAgent
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

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class CoordinatorConfig:
    """Configuration class to handle Coordinator's many attributes."""
    def __init__(self, config_obj):
        self.config = config_obj
        self.github_token = None
        self.tools = {}
        self.managers = {}
        self.context = {}
        self.state = {}

    def register_tool(self, name: str, tool_instance: Any) -> None:
        """Register a tool instance."""
        self.tools[name] = tool_instance

    def register_manager(self, name: str, manager_instance: Any) -> None:
        """Register a manager instance."""
        self.managers[name] = manager_instance

    def get_tool(self, name: str) -> Any:
        """Get a registered tool instance."""
        return self.tools.get(name)

    def get_manager(self, name: str) -> Any:
        """Get a registered manager instance."""
        return self.managers.get(name)
        
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
            
        self.coordinator_config = CoordinatorConfig(self.config)
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
            self._finalize_initialization()
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="initialization",
                level=logging.ERROR,
                reraise=True
            )
    
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
            )
        )
        self.current_task_id = None

    def _initialize_tools(self) -> None:
        """Initialize all tools and core functionality."""
        # Router agent initialization
        self.router_agent = RouterAgent(config=self.config)
        self.llm = self.router_agent

        # Initialize bash and related tools first so git can reuse the executor
        self.bash_tool = BashTool(
            sandbox=self.config.config.get("sandbox_environment", False),
            host_os_type=self.config.host_os_type
        )
        self.bash_tool.executor = TerminalExecutor(self.config)

        # Initialize file and git tools
        file_tool = FileTool()
        git_tool = GitTool(self.config.github_token, terminal_executor=self.bash_tool.executor)

        # Initialize context management
        self.context_registry = ContextRegistry()
        self.context_manager = ContextManager(
            config=self.config.config.get('context_management', {}))

        # Initialize code analysis
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

        # Initialize memory management
        embedding_client = EmbeddingClient(
            config=self.config.config,
            router_agent=self.router_agent
        )
        memory_manager = MemoryManager(
            config=self.config.config,
            embedding_client=embedding_client,
            file_tool=file_tool,
            llm_client=self.llm
        )

        # Register providers
        self.context_registry.register_provider("context_manager", self.context_manager)
        self.context_registry.register_provider("memory_manager", memory_manager)

        # Store tool references
        self.coordinator_config.register_tool('file_tool', file_tool)
        self.coordinator_config.register_tool('git_tool', git_tool)
        self.coordinator_config.register_tool('code_analysis_tool', code_analysis_tool)
        self.coordinator_config.register_tool('embedding_client', embedding_client)
        self.coordinator_config.register_tool('memory_manager', memory_manager)

        # Initialize remaining tools
        self._initialize_additional_tools(file_tool)

    def _initialize_additional_tools(self, file_tool: FileTool) -> None:
        """Initialize additional tools that depend on core tools."""
        # Database, environment, and AST tools
        self.database_tool = DatabaseTool(config=self.config, bash_tool=self.bash_tool)
        self.env_tool = EnvTool(self.bash_tool)
        self.ast_tool = ASTTool()

        # Test-related tools
        self.test_runner_tool = TestRunnerTool(self.bash_tool)
        self.test_frameworks = TestFrameworks(self)
        self.test_critic = TestCritic(self)

        # Error context management
        self.error_context_manager = ErrorContextManager(
            config=self.config,
            bash_tool=self.bash_tool,
            file_tool=file_tool,
            code_analysis_tool=self.coordinator_config.get_tool('code_analysis_tool'),
            git_tool=self.coordinator_config.get_tool('git_tool'),
            scratchpad=self.scratchpad
        )

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

        # Feature group processor and debugging manager
        self.feature_group_processor = FeatureGroupProcessor(coordinator=self)
        self.debugging_manager = DebuggingManager(
            coordinator=self,
            enhanced_scratchpad=self.scratchpad
        )

        # Initialize core workflow components
        self._initialize_workflow_components()

    def _initialize_workflow_components(self) -> None:
        """Initialize components related to workflow management."""
        memory_manager = self.coordinator_config.get_tool('memory_manager')
        
        self.planner = Planner(
            config=self.config,
            scratchpad=self.scratchpad,
            progress_tracker=self.progress_tracker,
            task_state_manager=self.task_state_manager,
            code_analysis_tool=self.coordinator_config.get_tool('code_analysis_tool'),
            tech_stack_detector=self.tech_stack_detector,
            memory_manager=memory_manager,
            database_tool=self.database_tool,
            test_frameworks=self.test_frameworks
        )

        self.code_generator = CodeGenerator(coordinator=self)
        self.prompt_moderator = PromptModerator(self)

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

    def _finalize_initialization(self) -> None:
        """Finalize the initialization process."""
        # Start background optimization if enabled
        if (self.config.config.get('context_management', {})
                .get('background_enabled', True)):
            self.context_manager._start_background_optimization()

        # Check for interrupted tasks
        if hasattr(self, 'task_resumer') and self.task_resumer:
            self.task_resumer.check_for_interrupted_tasks()

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
            
            # Stop planner observer if it exists
            if hasattr(self, 'planner') and self.planner and hasattr(self.planner, 'stop_observer'):
                self.planner.stop_observer()
            
            # Clean up context management
            if hasattr(self, 'context_manager') and self.context_manager:
                try:
                    self.scratchpad.log("Coordinator", "Stopping context management background optimization")
                    self.context_manager.stop_background_optimization()
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
                self.scratchpad.log("Coordinator", "User approved pre-planning results.")
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
                        # Import the regeneration function from planner_json_enforced
                        from agent_s3.planner_json_enforced import regenerate_consolidated_plan_with_modifications
                        
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
            elif choices.get("deployment"):
                next_action = "deployment"

            return {
                "success": True,
                "design_file": os.path.join(os.getcwd(), "design.txt"),
                "next_action": next_action,
            }

    # ------------------------------------------------------------------
    # Task Execution Workflow
    # ------------------------------------------------------------------

    def process_change_request(self, request_text: str) -> None:
        """Public facade for processing a change request.

        Args:
            request_text: The feature request to process.
        """
        self.run_task(task=request_text)

    def run_task(self, task: str, pre_planning_input: Optional[Dict[str, Any]] = None) -> None:
        """Execute the full planning and implementation workflow for a task."""
        with self.error_handler.error_context(
            phase="run_task",
            operation="run_task",
            inputs={"request_text": task},
        ):
            try:
                plans = self.planning_workflow.execute(task, pre_planning_input)
                if not plans:
                    return
                all_changes, overall_success = self.implementation_workflow.execute(plans)
                if overall_success:
                    self._finalize_task(all_changes)
            except Exception as exc:  # pragma: no cover - safety net
                self.error_handler.handle_exception(
                    exc=exc,
                    phase="run_task",
                    operation="run_task",
                    inputs={"request_text": task},
                    level=logging.ERROR,
                    reraise=False,
                )

    # ------------------------------------------------------------------
    # Internal workflow helpers
    # ------------------------------------------------------------------

    def _planning_workflow(
        self,
        task: str,
        pre_planning_input: Dict[str, Any] | None = None,
        from_design: bool = False,
    ) -> List[Dict[str, Any]]:
        """Run the planning workflow and return approved plans."""
        self.progress_tracker.update_progress({"phase": "pre_planning", "status": "started"})
        mode = self.config.config.get("pre_planning_mode", "enforced_json")

        if mode == "off":
            self.scratchpad.log("Coordinator", "Pre-planning disabled")
            return []

        if pre_planning_input is None:
            if mode == "enforced_json":
                success, pre_plan = call_pre_planner_with_enforced_json(self.router_agent, task)
            else:  # "json"
                success, pre_plan = pre_planning_workflow(
                    self.router_agent,
                    task,
                    max_attempts=2,
                )
            if not success:
                self.scratchpad.log("Coordinator", "Pre-planning failed", level=LogLevel.ERROR)
                return []
        else:
            pre_plan = pre_planning_input

        decision, _ = self._present_pre_planning_results_to_user(pre_plan)
        if decision != "yes":
            if decision == "modify":
                self.scratchpad.log("Coordinator", "User chose to refine the request.")
            elif decision == "no":
                self.scratchpad.log("Coordinator", "User cancelled the complex task.")
            return []

        fg_result = self.feature_group_processor.process_pre_planning_output(pre_plan, task)
        if not fg_result.get("success"):
            self.scratchpad.log(
                "Coordinator",
                f"Feature group processing failed: {fg_result.get('error')}",
                level=LogLevel.ERROR,
            )
            return []

        plans: List[Dict[str, Any]] = []
        for data in fg_result.get("feature_group_results", {}).values():
            consolidated_plan = data.get("consolidated_plan")
            if not consolidated_plan:
                continue
            decision, modification = self.feature_group_processor.present_consolidated_plan_to_user(consolidated_plan)
            if decision == "modify":
                original_plan = json.loads(json.dumps(consolidated_plan))
                consolidated_plan = self.feature_group_processor.update_plan_with_modifications(
                    consolidated_plan, modification
                )
                decision, _ = self.feature_group_processor.present_consolidated_plan_to_user(
                    consolidated_plan, original_plan
                )
            if decision == "yes":
                plans.append(consolidated_plan)

        self.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "completed"})
        return plans

    def _implementation_workflow(self, plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run the implementation workflow for approved plans."""
        all_changes: Dict[str, str] = {}
        git_tool = self.coordinator_config.get_tool('git_tool')
        overall_success = False
        for plan in plans:
            stash_created = False
            if git_tool:
                rc, _ = git_tool.run_git_command(
                    "stash push --keep-index --include-untracked -m 'agent-s3-temp'"
                )
                stash_created = rc == 0

            changes = self.code_generator.generate_code(plan, tech_stack=self.tech_stack)

            if not self._apply_changes_and_manage_dependencies(changes):
                if stash_created and git_tool:
                    git_tool.run_git_command("stash pop --index")
                continue

            validation = self._run_validation_phase()

            if validation.get("success"):
                all_changes.update(changes)
                overall_success = True
                if stash_created and git_tool:
                    git_tool.run_git_command("stash drop")
                continue

            self.debugging_manager.handle_error(
                error_message=f"Validation step '{validation.get('step')}' failed",
                traceback_text=validation.get("output", ""),
                metadata={"plan": plan, "validation_step": validation.get("step")},
            )

            if stash_created and git_tool:
                git_tool.run_git_command("stash pop --index")

        return all_changes, overall_success

    # ------------------------------------------------------------------
    # Supporting helpers (simplified implementations)
    # ------------------------------------------------------------------

    def _apply_changes_and_manage_dependencies(self, changes: Dict[str, str]) -> bool:
        """Apply generated code changes and manage dependencies."""
        try:
            for path, content in changes.items():
                self.file_tool.write_file(path, content)
            return True
        except Exception as exc:  # pragma: no cover - safety net
            self.scratchpad.log("Coordinator", f"Failed applying changes: {exc}", level=LogLevel.ERROR)
            return False

    def _run_validation_phase(self) -> Dict[str, Any]:
        """Run linting, type checking and tests.

        Returns a dictionary with the following keys:
            - ``success``: overall validation success
            - ``step``: failing step (``"lint"``, ``"type_check"``, ``"tests"``, ``"unknown_error"``) if any
            - ``lint_output``: output from the linting command
            - ``type_output``: output from the type checking command
            - ``test_output``: output from running the tests
            - ``coverage``: calculated test coverage when available
        """

        results = {
            "success": True,
            "step": None,
            "lint_output": None,
            "type_output": None,
            "test_output": None,
            "coverage": None,
            "mutation_score": None,
        }
        try:
            db_result = self.database_manager.setup_database()
            if not db_result.get("success", True):
                return {
                    "success": False,
                    "step": "database",
                    "lint_output": None,
                    "type_output": None,
                    "test_output": db_result.get("error"),
                    "coverage": None,
                }

            lint_exit, lint_output = self.bash_tool.run_command("flake8 .", timeout=120)
            results["lint_output"] = lint_output
            if lint_exit != 0:
                results.update({"success": False, "step": "lint"})
                return results

            type_exit, type_output = self.bash_tool.run_command("mypy .", timeout=120)
            results["type_output"] = type_output
            if type_exit != 0:
                results.update({"success": False, "step": "type_check"})
                return results

            test_result = self.run_tests()
            results["test_output"] = test_result.get("output")
            results["coverage"] = test_result.get("coverage")
            if not test_result.get("success"):
                results.update({"success": False, "step": "tests"})
                return results

            # Run mutation testing using TestCritic
            critic_data = self.test_critic.run_analysis()
            mutation_score = critic_data.get("details", {}).get("mutation_score")
            results["mutation_score"] = mutation_score
            threshold_config = self.config.config.get("mutation_score_threshold", 70.0)
            try:
                threshold = float(threshold_config)
            except (TypeError, ValueError):
                self.scratchpad.log(
                    "Coordinator",
                    f"Invalid mutation_score_threshold '{threshold_config}', defaulting to 70.0",
                    level=LogLevel.ERROR,
                )
                threshold = 70.0
            if mutation_score is not None and mutation_score < threshold:
                results.update({"success": False, "step": "mutation"})
                return results
        except Exception as exc:  # pragma: no cover - safety net
            self.scratchpad.log("Coordinator", f"Validation error: {exc}", level=LogLevel.ERROR)
            results.update({"success": False, "step": "unknown_error"})
            return results

        return results

    def run_tests(self) -> Dict[str, Any]:
        """Run project tests using the configured test runner."""
        try:
            self.env_tool.activate_virtual_env()
            self.test_runner_tool.detect_runner()
            success, output = self.test_runner_tool.run_tests()
            coverage = 0.0
            if success and hasattr(self.test_runner_tool, "parse_coverage_report"):
                coverage = self.test_runner_tool.parse_coverage_report()
            return {"success": success, "output": output, "coverage": coverage}
        except Exception as exc:  # pragma: no cover - safety net
            self.scratchpad.log("Coordinator", f"Test execution failed: {exc}", level=LogLevel.ERROR)
            return {"success": False, "output": str(exc), "coverage": 0.0}

    def _finalize_task(self, changes: Dict[str, str]) -> None:
        """Finalize the task after successful validation."""
        self.scratchpad.log("Coordinator", "Task completed successfully")

    # ------------------------------------------------------------------
    # Design to Implementation Helpers
    # ------------------------------------------------------------------

    def start_pre_planning_from_design(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Start pre-planning workflow based on a design file.

        Args:
            design_file: Path to the design file containing feature tasks.

        Returns:
            Dictionary with success flag and number of tasks started.
        """
        if not os.path.exists(design_file):
            self.scratchpad.log("Coordinator", f"Design file not found: {design_file}", level=LogLevel.ERROR)
            return {"success": False, "error": "Design file not found"}

        try:
            with open(design_file, "r") as f:
                design_content = f.read()
        except Exception as e:  # pragma: no cover - basic safety
            self.scratchpad.log("Coordinator", f"Failed to read design file: {e}", level=LogLevel.ERROR)
            return {"success": False, "error": "Failed to read design file"}

        tasks = self._extract_tasks_from_design(design_content)
        if not tasks:
            self.scratchpad.log("Coordinator", "No tasks found in design file", level=LogLevel.ERROR)
            return {"success": False, "error": "No tasks in design file"}

        for task in tasks:
            self.run_task(task=task, pre_planning_input=None)

        return {"success": True, "tasks_started": len(tasks)}

    def _extract_tasks_from_design(self, design_content: str) -> List[str]:
        """Extract task descriptions from the design content."""
        tasks: List[str] = []
        for line in design_content.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r"(\d+(?:\.\d+)*)\.\s+(.*)", line)
            if match:
                tasks.append(match.group(2))
        return tasks

    def execute_implementation(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Delegate to ImplementationManager to start implementation."""
        if not hasattr(self, "implementation_manager"):
            self.implementation_manager = ImplementationManager(self)
        if not os.path.exists(design_file):
            return {"success": False, "error": "Design file not found"}
        return self.implementation_manager.start_implementation(design_file)

    def execute_continue(self, continue_type: str) -> Dict[str, Any]:
        """Delegate continuation based on type."""
        if continue_type != "implementation":
            return {"success": False, "error": "Unsupported continuation type"}
        if not hasattr(self, "implementation_manager"):
            self.implementation_manager = ImplementationManager(self)
        return self.implementation_manager.continue_implementation()
