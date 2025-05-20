"""Task Manager that orchestrates workflow phases.

Handles planning, prompt generation, issue creation, and execution phases.
"""


import os
import json
import logging
from agent_s3.enhanced_scratchpad_manager import LogLevel
from typing import Optional, List, Tuple, Dict, Any, Union
import traceback
from pathlib import Path
from datetime import datetime
import re

from agent_s3.config import Config
from agent_s3.planner import Planner
from agent_s3.code_generator import CodeGenerator
from agent_s3.prompt_moderator import PromptModerator
from agent_s3.router_agent import RouterAgent
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
from agent_s3.debugging_manager import DebuggingManager
from agent_s3.progress_tracker import ProgressTracker
from agent_s3.task_state_manager import TaskStateManager
from agent_s3.workspace_initializer import WorkspaceInitializer
from agent_s3.tools.bash_tool import BashTool
from agent_s3.tools.database_tool import DatabaseTool
from agent_s3.tools.env_tool import EnvTool
from agent_s3.tools.ast_tool import ASTTool
from agent_s3.tools.test_runner_tool import TestRunnerTool
from agent_s3.tech_stack_detector import TechStackDetector
from agent_s3.file_history_analyzer import FileHistoryAnalyzer
from agent_s3.task_resumer import TaskResumer
from agent_s3.command_processor import CommandProcessor
from agent_s3.workflows import PlanningWorkflow, ImplementationWorkflow
# Import new standardized error handling
from agent_s3.errors import (
    AgentError,
    CoordinationError,
    PlanningError,
    GenerationError,
    JSONPlanningError,
    ErrorCategory,
    ErrorContext
)
from agent_s3.error_handler import ErrorHandler


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Coordinator:
    """Coordinates the workflow phases for Agent-S3."""

    def __init__(self, config=None, config_path: str = 'llm.json', github_token: str = None):
        """Initialize the coordinator.

        Args:
            config: Optional pre-loaded configuration object (takes precedence over config_path)
            config_path: Path to the configuration file (used if config is not provided)
            github_token: Optional GitHub OAuth token for API access
        """
        # Initialize error handler for coordinator
        self.error_handler = ErrorHandler(
            component="Coordinator",
            logger=logger,
            reraise=False,  # Don't re-raise exceptions by default in coordinator
            transform_exceptions=True,  # Transform standard exceptions to AgentError types
            default_phase="initialization"
        )
        
        try:
            # Initialize configuration
            if config is not None:
                self.config = config
            else:
                self.config = Config(config_path)
                self.config.load()
                
            # Set GitHub token if provided
            if github_token is not None:
                self.config.github_token = github_token
            
            # Initialize logging components
            self.scratchpad = EnhancedScratchpadManager(self.config)
            self.progress_tracker = ProgressTracker(self.config)
            
            # Initialize tools
            self._initialize_tools()
            
            # Initialize task state management
            self.task_state_manager = TaskStateManager(
                base_dir=os.path.join(os.path.dirname(self.config.get_log_file_path("development")), "task_snapshots")
            )
            self.current_task_id = None
            
            # Initialize specialized components
            self._initialize_specialized_components()
            
            # Register additional planning phases
            if hasattr(self.progress_tracker, 'register_semantic_validation_phase'):
                self.progress_tracker.register_semantic_validation_phase()

            # Initialize command processor
            from agent_s3.command_processor import CommandProcessor
            self.command_processor = CommandProcessor(self)

            # Check for interrupted tasks to resume
            if hasattr(self, 'task_resumer') and self.task_resumer:
                self.task_resumer.check_for_interrupted_tasks()

            # Log initialization
            self.scratchpad.log("Coordinator", "Initialized Agent-S3 coordinator")
            if not self.progress_tracker.get_latest_progress():
                self.progress_tracker.update_progress({"phase": "initialization", "status": "pending"})
        except Exception as e:
            # Use the error handler for consistent error handling
            self.error_handler.handle_exception(
                exc=e,
                operation="initialization",
                level=logging.ERROR,
                reraise=True  # Re-raise during initialization to prevent partial initialization
            )
    
    def _initialize_tools(self):
        """Initialize all tool instances."""
        try:
            # Initialize router agent before other tools
            self.router_agent = RouterAgent(config=self.config)
            self.llm = self.router_agent

            # Set up context registry and context manager
            from agent_s3.tools.context_management.context_registry import ContextRegistry
            from agent_s3.tools.context_management.context_manager import ContextManager
            self.context_registry = ContextRegistry()
            self.context_manager = ContextManager(config=self.config.config.get('context_management', {}))

            # Initialize core tools for context manager
            from agent_s3.tools.code_analysis_tool import CodeAnalysisTool
            from agent_s3.tools.file_tool import FileTool
            file_tool = FileTool()
            code_analysis_tool = CodeAnalysisTool(coordinator=self, file_tool=file_tool)
            tech_stack_detector = TechStackDetector(config=self.config, file_tool=file_tool, scratchpad=self.scratchpad)
            from agent_s3.tools.git_tool import GitTool
            # Create a GitTool instance to be shared
            git_tool_instance = GitTool(self.config.github_token)
            self.file_history_analyzer = FileHistoryAnalyzer(
                git_tool=git_tool_instance,
                config=self.config,
                scratchpad=self.scratchpad,
            )
            # Store git_tool for later use
            self.git_tool = git_tool_instance
            self.context_manager.initialize_tools(
                tech_stack_detector=tech_stack_detector,
                code_analysis_tool=code_analysis_tool,
                file_history_analyzer=self.file_history_analyzer,
                file_tool=file_tool,
            )
            self.context_registry.register_provider("context_manager", self.context_manager)

            # Initialize memory manager and register
            from agent_s3.tools.memory_manager import MemoryManager
            from agent_s3.tools.embedding_client import EmbeddingClient
            embedding_client = EmbeddingClient(config=self.config.config, router_agent=self.router_agent)
            memory_manager = MemoryManager(
                config=self.config.config,
                embedding_client=embedding_client,
                file_tool=file_tool,
                llm_client=self.llm
            )
            self.context_registry.register_provider("memory_manager", memory_manager)

            # Start background optimization if enabled
            if self.config.config.get('context_management', {}).get('background_enabled', True):
                self.context_manager._start_background_optimization()

            # Store references for backward compatibility (to be removed after migration)
            self.file_tool = file_tool
            self.memory_manager = memory_manager
            self.embedding_client = embedding_client
            self.git_tool = self.file_history_analyzer.git_tool
            self.bash_tool = BashTool(sandbox=self.config.config.get("sandbox_environment", False), host_os_type=self.config.host_os_type)
            self.database_tool = DatabaseTool(config=self.config, bash_tool=self.bash_tool)
            self.env_tool = EnvTool(self.bash_tool)
            self.ast_tool = ASTTool()
            self.test_runner_tool = TestRunnerTool(self.bash_tool)
            from agent_s3.tools.test_frameworks import TestFrameworks
            self.test_frameworks = TestFrameworks(self)
            from agent_s3.tools.test_critic import TestCritic  # Updated integrated implementation
            self.test_critic = TestCritic(self)
            # TestPlanner has been removed as it's been superseded by feature group workflow
            from agent_s3.tools.error_context_manager import ErrorContextManager
            self.error_context_manager = ErrorContextManager(
                config=self.config,
                bash_tool=self.bash_tool,
                file_tool=self.file_tool,
                code_analysis_tool=code_analysis_tool,
                git_tool=self.git_tool,
                scratchpad=self.scratchpad
            )
        except Exception as e:
            # Use the error handler for consistent error handling
            self.error_handler.handle_exception(
                exc=e,
                phase="initialization",
                operation="initialize_tools",
                level=logging.ERROR,
                reraise=True  # Re-raise during initialization to prevent partial initialization
            )
    
    def _initialize_specialized_components(self):
        """Initialize specialized components using the tools."""
        try:
            # Initialize tech stack detector
            self.tech_stack_detector = TechStackDetector(
                config=self.config,
                file_tool=self.file_tool,
                scratchpad=self.scratchpad
            )
            self.tech_stack = self.tech_stack_detector.detect_tech_stack()
            
            # Initialize workspace initializer
            self.workspace_initializer = WorkspaceInitializer(
                config=self.config,
                file_tool=self.file_tool,
                scratchpad=self.scratchpad,
                prompt_moderator=None,  # Will be set after PromptModerator is initialized
                tech_stack=self.tech_stack
            )
            
            # Initialize feature group processor
            from agent_s3.feature_group_processor import FeatureGroupProcessor
            self.feature_group_processor = FeatureGroupProcessor(coordinator=self)
            
            # Initialize debugging manager
            self.debugging_manager = DebuggingManager(
                coordinator=self,
                enhanced_scratchpad=self.scratchpad
            )
            
            # Initialize planner and related components
            self.planner = Planner(
                config=self.config,
                scratchpad=self.scratchpad,
                progress_tracker=self.progress_tracker,
                task_state_manager=self.task_state_manager,
                code_analysis_tool=getattr(self, 'code_analysis_tool', None),
                tech_stack_detector=self.tech_stack_detector,
                memory_manager=self.memory_manager,
                database_tool=self.database_tool,
                test_frameworks=self.test_frameworks
            )
            
            # Initialize design, implementation, and deployment managers
            from agent_s3.design_manager import DesignManager
            from agent_s3.implementation_manager import ImplementationManager
            from agent_s3.deployment_manager import DeploymentManager
            from agent_s3.database_manager import DatabaseManager
            
            self.design_manager = DesignManager(self)
            self.implementation_manager = ImplementationManager(self)
            self.deployment_manager = DeploymentManager(self)
            self.database_manager = DatabaseManager(self)
            # Initialize code generator
            self.code_generator = CodeGenerator(coordinator=self)
            # Initialize prompt moderator
            self.prompt_moderator = PromptModerator(self)
            
            # Now that we have the prompt moderator, update the workspace initializer
            self.workspace_initializer.prompt_moderator = self.prompt_moderator
            
            # Pre-planning functionality has been moved to pre_planner_json_enforced.py
            
            # Initialize task resumer
            self.task_resumer = TaskResumer(
                coordinator=self,
                task_state_manager=self.task_state_manager,
                scratchpad=self.scratchpad,
                progress_tracker=self.progress_tracker
            )
        except Exception as e:
            # Use the error handler for consistent error handling
            self.error_handler.handle_exception(
                exc=e,
                phase="initialization",
                operation="initialize_specialized_components",
                level=logging.ERROR,
                reraise=True  # Re-raise during initialization to prevent partial initialization
            )

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
            if hasattr(self, 'memory_manager') and self.memory_manager and hasattr(self.memory_manager, '_save_memory'):
                self.memory_manager._save_memory()
            
            # Save embedding client state
            if hasattr(self, 'embedding_client') and self.embedding_client and hasattr(self.embedding_client, '_save_state'):
                self.embedding_client._save_state()   
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
                tech_stack_snapshot = self.get_current_context_snapshot(context_type="tech_stack")
                if tech_stack_snapshot: context.update(tech_stack_snapshot)
                project_structure_snapshot = self.get_current_context_snapshot(context_type="project_structure")
                if project_structure_snapshot: context.update(project_structure_snapshot)
                deps_snapshot = self.get_current_context_snapshot(context_type="dependencies")
                if deps_snapshot: context.update(deps_snapshot)
                
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
    
    def _present_pre_planning_results_to_user(self, pre_planning_results: Dict[str, Any]) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Present the pre-planning results to the user and get their decision (yes/no/modify)."""
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
                return decision, pre_planning_results
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
            return "no",

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
                if self.design_manager.detect_design_completion():
                    break
                try:
                    user_input = input()
                except (KeyboardInterrupt, EOFError):
                    return {"success": False, "cancelled": True}
                try:
                    response, _ = self.design_manager.continue_conversation(user_input)
                    if response:
                        print(response)
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
