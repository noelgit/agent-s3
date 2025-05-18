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
            file_history_analyzer = FileHistoryAnalyzer(git_tool=git_tool_instance, config=self.config, scratchpad=self.scratchpad)
            # Store git_tool for later use
            self.git_tool = git_tool_instance
            self.context_manager.initialize_tools(
                tech_stack_detector=tech_stack_detector,
                code_analysis_tool=code_analysis_tool,
                file_history_analyzer=file_history_analyzer,
                file_tool=file_tool
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
            self.git_tool = file_history_analyzer.git_tool
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
            
            # Initialize file history analyzer
            self.file_history_analyzer = FileHistoryAnalyzer(
                git_tool=self.git_tool,
                config=self.config,
                scratchpad=self.scratchpad
            )
            
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
            # The PrePlanningManager class is no longer used
            
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

    def _regenerate_pre_planning_with_modifications(self, original_results: Dict[str, Any], modification_text: str) -> Dict[str, Any]:
        """Regenerate pre-planning results based on user modifications.

        Directly uses the implementation from pre_planner_json_enforced module.

        Args:
            original_results: The original pre-planning results
            modification_text: The user's modification text

        Returns:
            Modified pre-planning results
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="pre_planning",
            operation="regenerate_with_modifications",
            inputs={"modification_text": modification_text}
        ):
            from agent_s3.pre_planner_json_enforced import regenerate_pre_planning_with_modifications
            return regenerate_pre_planning_with_modifications(
                self.router_agent,
                original_results,
                modification_text
            )
    
    def run_task(self, task: str, pre_planning_input: Dict[str, Any] = None, from_design: bool = False):
        """Run a task based on the request text or pre-planning input.

        The core workflow is:
        1. Pre-planning: Generate feature groups from task description using pre_planner_json_enforced
           (or use provided pre_planning_input if coming from design phase)
        2. Validation: Validate the pre-planning output structure and content
        3. User Handoff: Present pre-planning results to user for approval or modification
        4. Signature Normalization: Normalize signatures and IDs for consistency
        5. Feature Group Processing: Process each feature group to create consolidated plans
        6. Plan Approval: User approves, rejects, or modifies consolidated plans
        7. Code Generation: Generate code for approved plans
        8. Validation Loop: Validate, debug, and refine implementations
        9. Finalization: Commit changes if successful

        This method orchestrates the entire workflow from initial request to completed implementation.
        Each phase has specific validation steps and user interaction points to ensure quality and
        alignment with user intentions.

        Args:
            task: The original task description or design objective
            pre_planning_input: Optional pre-planning data from design phase
            from_design: Flag indicating if the task is coming from design phase
        """
        # Use the main try-except with error handler for the entire task execution
        # This will provide consistent error handling and logging for the entire task
        try:
            # Initialize task tracking
            self.current_task_description = task
            self.current_task_id = self.task_state_manager.create_new_task_id()
            
            # Log different message based on source
            if from_design:
                self.scratchpad.log("Coordinator", f"Starting implementation of design {self.current_task_id}: {task[:50]}...")
                # Enhanced tracking for design-sourced tasks
                design_file = pre_planning_input.get("design_file", "design.txt") if pre_planning_input else "design.txt"
                self.progress_tracker.update_progress({
                    "phase": "pre_planner", 
                    "status": "started", 
                    "task_id": self.current_task_id,
                    "from_design": True,
                    "design_file": design_file,
                    "request_text": task  # Use task as request_text for consistency
                })
            else:
                self.scratchpad.log("Coordinator", f"Starting task {self.current_task_id}: {task[:50]}...")
            planning = PlanningWorkflow(self)
            approved_consolidated_plans = planning.execute(task, pre_planning_input, from_design)

            implementation = ImplementationWorkflow(self)
            all_changes_applied_successfully, task_overall_success = implementation.execute(approved_consolidated_plans)

            # --- PHASE 8: Finalization - Commit changes ---
            if task_overall_success and all_changes_applied_successfully:
                self.scratchpad.log("Coordinator", "Implementation loop completed. Proceeding to finalize task.")
                print("\n✅ Implementation complete. Finalizing task...")
                self._finalize_task(all_changes_applied_successfully)
            elif all_changes_applied_successfully:
                self.scratchpad.log("Coordinator", "Implementation loop completed with partial success. Some groups failed.", level=LogLevel.WARNING)
                print("\n⚠")
                self._finalize_task(all_changes_applied_successfully)
            else:
                self.scratchpad.log("Coordinator", "Implementation failed for all approved feature groups.", level=LogLevel.ERROR)
                print("\n❌ Task implementation failed. No changes will be finalized.")
                self.progress_tracker.update_progress({"phase": "finalizing", "status": "failed", "error": "Implementation failed"})
                
        except Exception as e:
            # Global exception handler for the task execution
            # Use the error handler for consistent error handling across the entire task
            error_context = self.error_handler.handle_exception(
                exc=e,
                phase="global",
                operation="run_task",
                level=logging.CRITICAL,
                reraise=False,
                inputs={"request_text": task}
            )
            
            error_msg = f"Unexpected error during task execution: {str(e)}"
            self.scratchpad.log("Coordinator", error_msg, level=LogLevel.CRITICAL)
            self.scratchpad.log("Coordinator", traceback.format_exc(), level=LogLevel.CRITICAL)
            print(f"\n❌ CRITICAL ERROR: {error_msg}")
            print("Task aborted due to an unexpected error.")
            self.progress_tracker.update_progress({
                "phase": "error",
                "status": "failed",
                "error": error_msg,
                "traceback": traceback.format_exc()
            })

    def process_change_request(self, request_text: str, skip_planning: bool = False) -> None:
        """Facade for processing a change request through the workflow stack.

        If ``skip_planning`` is False the request text is treated as a new task
        description and passed to :func:`run_task`. When ``skip_planning`` is
        True the text is assumed to already contain a plan and the implementation
        workflow is invoked directly.

        Args:
            request_text: The feature request or plan text.
            skip_planning: Whether to bypass planning and jump straight to
                implementation.
        """
        try:
            self.scratchpad.log("Coordinator", f"Processing change request: {request_text[:50]}")
            if skip_planning:
                implementation = ImplementationWorkflow(self)
                implementation.execute([{"plan": request_text}])
            else:
                self.run_task(request_text)

            keywords = set(self._extract_keywords_from_task(request_text))
            if {"deploy", "deployment"} & keywords:
                self.execute_deployment()
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="process_change_request",
                level=logging.ERROR
            )

    def _planning_workflow(self, task: str, pre_planning_input: Dict[str, Any] | None = None, from_design: bool = False) -> List[Dict[str, Any]]:
        """Execute planning phases and return approved consolidated plans."""
        with self.error_handler.error_context(
            phase="planning",
            operation="planning_workflow",
            inputs={"task": task}
        ):
            self.progress_tracker.update_progress({"phase": "pre_planning", "status": "started"})

            context = self._prepare_context(task)

            if pre_planning_input is not None:
                pre_plan_data = pre_planning_input
            else:
                from agent_s3.pre_planner_json_enforced import pre_planning_workflow
                success, pre_plan_data = pre_planning_workflow(self.router_agent, task, context=context)
                if not success:
                    raise PlanningError("Pre-planning failed")

            # Static validation of the pre-planning structure
            from agent_s3.tools.plan_validator import validate_pre_plan
            self._validate_pre_planning_data(pre_plan_data)
            validate_pre_plan(pre_plan_data, context_registry=self.context_registry)

            complexity_score = pre_plan_data.get("complexity_score", 0)
            is_complex = pre_plan_data.get("is_complex", False) or complexity_score >= self.config.config.get("complexity_threshold", 7)

            if is_complex:
                self.scratchpad.log("Coordinator", f"Task assessed as complex (Score: {complexity_score})")
                decision = self.prompt_moderator.ask_ternary_question("How would you like to proceed?")
                if decision == "modify":
                    self.scratchpad.log("Coordinator", "User chose to refine the request.")
                    return []
                if decision == "no":
                    self.scratchpad.log("Coordinator", "User cancelled the complex task.")
                    return []

            decision, modification = self._present_pre_planning_results_to_user(pre_plan_data)
            while decision == "modify":
                pre_plan_data = self._regenerate_pre_planning_with_modifications(pre_plan_data, modification)
                decision, modification = self._present_pre_planning_results_to_user(pre_plan_data)

            if decision == "no":
                self.scratchpad.log("Coordinator", "User terminated the workflow at pre-planning handoff.", level=LogLevel.WARNING)
                return []

            self.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "started"})
            fg_result = self.feature_group_processor.process_pre_planning_output(pre_plan_data, task)
            self.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "completed"})

            if not fg_result.get("success"):
                self.scratchpad.log("Coordinator", f"Feature group processing failed: {fg_result.get('error')}", level=LogLevel.ERROR)
                return []

            approved_plans: List[Dict[str, Any]] = []
            for fg_data in fg_result.get("feature_group_results", {}).values():
                if not fg_data.get("success"):
                    self.scratchpad.log(
                        "Coordinator",
                        f"Feature group {fg_data.get('feature_group', {}).get('group_name')} processing failed: {fg_data.get('error')}",
                        level=LogLevel.WARNING,
                    )
                    continue

                plan = fg_data.get("consolidated_plan", {})
                decision, mod_text = self.feature_group_processor.present_consolidated_plan_to_user(plan)
                while decision == "modify":
                    plan = self.feature_group_processor.update_plan_with_modifications(plan, mod_text)
                    decision, mod_text = self.feature_group_processor.present_consolidated_plan_to_user(plan)
                if decision == "yes":
                    approved_plans.append(plan)

            return approved_plans

    def _implementation_workflow(self, approved_plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run implementation loop for approved plans."""
        with self.error_handler.error_context(
            phase="implementation",
            operation="implementation_workflow",
        ):
            all_changes: Dict[str, str] = {}
            overall_success = True

            max_attempts = self.config.config.get("max_attempts", 3)

            for plan in approved_plans:
                plan_id = plan.get("plan_id")
                group_name = plan.get("group_name", "group")
                plan_success = False

                while True:
                    attempt = 0
                    while attempt < max_attempts and not plan_success:
                        attempt += 1
                        self.progress_tracker.update_progress({
                            "phase": "generation",
                            "status": "started",
                            "attempt": attempt,
                            "plan_id": plan_id,
                        })

                        self.scratchpad.log(
                            "Coordinator",
                            f"Generating code for {group_name} (attempt {attempt})",
                        )

                        changes = self.code_generator.generate_code(plan)
                        if not changes:
                            continue

                        if not self._apply_changes_and_manage_dependencies(changes):
                            continue

                        validation = self._run_validation_phase()
                        if validation.get("success"):
                            all_changes.update(changes)
                            plan_success = True
                            break

                        if hasattr(self, "debugging_manager") and self.debugging_manager:
                            debug_res = self.debugging_manager.handle_error(
                                error_message=validation.get("output", ""),
                                traceback_text=validation.get("output", ""),
                            )
                            if debug_res.get("success"):
                                dbg_changes = debug_res.get("changes", {})
                                if dbg_changes:
                                    self._apply_changes_and_manage_dependencies(dbg_changes)
                                    changes.update(dbg_changes)
                                validation = self._run_validation_phase()
                                if validation.get("success"):
                                    all_changes.update(changes)
                                    plan_success = True
                                    break

                    self.progress_tracker.update_progress({
                        "phase": "generation",
                        "status": "completed",
                        "plan_id": plan_id,
                        "success": plan_success,
                    })

                    if plan_success:
                        break

                    self.scratchpad.log(
                        "Coordinator",
                        f"Implementation for {group_name} failed after {max_attempts} attempts",
                        level=LogLevel.WARNING,
                    )

                    if hasattr(self, "prompt_moderator") and self.prompt_moderator:
                        guidance = self.prompt_moderator.request_debugging_guidance(group_name, max_attempts)
                        if guidance:
                            plan = self.feature_group_processor.update_plan_with_modifications(plan, guidance)
                            self.scratchpad.log(
                                "Coordinator",
                                "Engineer provided modifications; retrying implementation",
                            )
                            continue

                    overall_success = False
                    break

            return all_changes, overall_success

    def _run_validation_phase(self) -> Dict[str, Any]:
        """Runs the validation phase and returns the result.

        This performs a series of validation checks on the implemented code:
        1. Database integrity (if database configurations exist)
        2. Code linting
        3. Type checking
        4. Test execution
        5. Static test type verification

        Returns:
            Dictionary containing:
            - success (bool): True if all validations passed
            - failed_step (str): Which validation step failed (if any)
            - output (str): Output/error message from validation
            - metadata (dict): Additional validation metadata
        """
        # Use the error handler for consistent error handling during validation
        with self.error_handler.error_context(phase="validation_run", operation="full_validation"):
            validation_result = {
                "success": False,
                "failed_step": None,
                "output": "",
                "metadata": {},
                "timestamp": datetime.now().isoformat()
            }
            self.progress_tracker.update_progress({"phase": "validation_run", "status": "started"}) # Distinct phase name
            self.scratchpad.log("Coordinator", "Running validation: database integrity, lint, type-check, tests...")

            # Validate database integrity if database configurations exist
            with self.error_handler.error_context(phase="validation_run", operation="database_validation"):
                if hasattr(self, 'database_manager') and self.database_manager:
                    try:
                        db_configs = self.config.config.get("databases", {})
                        if db_configs:
                            self.scratchpad.log("Coordinator", "Validating database integrity...")
                            for db_name in db_configs:
                                test_result = self.database_manager.setup_database(db_name)
                                if not test_result.get("success", False):
                                    error_msg = test_result.get("error", "Unknown database error")
                                    self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "database", "error": error_msg})
                                    validation_result["failed_step"] = "database"
                                    validation_result["output"] = error_msg
                                    validation_result["metadata"]["db_name"] = db_name
                                    return validation_result
                                if hasattr(self.database_manager.database_tool, 'get_schema_info'):
                                    self.database_manager.database_tool.get_schema_info(db_name)
                                self.scratchpad.log("Coordinator", f"Database {db_name} schema validated successfully")
                    except Exception as e:
                        # Handle database validation errors through error handler
                        error_context = self.error_handler.handle_exception(
                            exc=e,
                            phase="validation_run",
                            operation="database_validation",
                            level=logging.ERROR,
                            reraise=False
                        )
                        validation_result["failed_step"] = "database"
                        validation_result["output"] = f"Database validation error: {str(e)}"
                        return validation_result

            # Lint
            with self.error_handler.error_context(phase="validation_run", operation="lint"):
                self.scratchpad.log("Coordinator", "Running linter...")
                lint_cmd = "flake8 ."  # Example, could be configurable
                lint_code, lint_out = self.bash_tool.run_command(lint_cmd, timeout=120)
                validation_result["metadata"]["lint_exit_code"] = lint_code

                if lint_code != 0:
                    msg = f"Linting failed:\n{lint_out}"
                    self.scratchpad.log("Coordinator", msg, level=LogLevel.WARNING)
                    self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "lint", "error": msg})
                    validation_result["failed_step"] = "lint"
                    validation_result["output"] = msg
                    return validation_result

            # Type-check
            with self.error_handler.error_context(phase="validation_run", operation="type_check"):
                self.scratchpad.log("Coordinator", "Running type checker...")
                type_cmd = "mypy ."  # Example, could be configurable
                type_code, type_out = self.bash_tool.run_command(type_cmd, timeout=120)
                validation_result["metadata"]["type_check_exit_code"] = type_code

                if type_code != 0:
                    # Mypy often returns non-zero for type errors, treat as warnings for now unless critical
                    if "error:" in type_out: # Treat actual errors as failures
                        msg = f"Type checking failed:\n{type_out}"
                        self.scratchpad.log("Coordinator", msg, level=LogLevel.ERROR)
                        self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "type_check", "error": msg})
                        validation_result["failed_step"] = "type_check"
                        validation_result["output"] = msg
                        return validation_result
                    else:
                        msg = f"Type checking found issues (warnings):\n{type_out}"
                        self.scratchpad.log("Coordinator", msg, level=LogLevel.WARNING)
                        validation_result["metadata"]["type_check_warnings"] = True
                        # Continue despite type warnings for now

            # Run tests (Execution)
            with self.error_handler.error_context(phase="validation_run", operation="test_execution"):
                self.scratchpad.log("Coordinator", "Executing tests...")
                # This should call a method to run tests, likely on test_runner_tool or test_frameworks
                test_res = self.test_frameworks.run_tests() if hasattr(self.test_frameworks, 'run_tests') else {'success': True, 'coverage': 0}
                validation_result["metadata"]["test_coverage"] = test_res.get('coverage', 0)

                if not test_res.get("success"):
                    msg = f"Test execution failed:\n{test_res.get('output')}"
                    self.scratchpad.log("Coordinator", msg, level=LogLevel.ERROR)
                    self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "tests", "error": msg})
                    validation_result["failed_step"] = "tests"
                    validation_result["output"] = msg
                    return validation_result
                else:
                    self.scratchpad.log("Coordinator", f"Tests passed. Coverage: {test_res.get('coverage', 0):.1f}%")

            # Static Test Type Verification (using TestCritic)
            with self.error_handler.error_context(phase="validation_run", operation="test_critic"):
                if hasattr(self, 'test_critic') and self.test_critic:
                    try:
                        # Static analysis of test types
                        # Handle the case where test_critic might have different methods available
                        if hasattr(self.test_critic, 'validate_test_coverage'):
                            critic_result = self.test_critic.validate_test_coverage()
                        elif hasattr(self.test_critic, 'critique_tests'):
                            # Fall back to critique_tests method if available
                            critic_result = self.test_critic.critique_tests({}, {})
                        else:
                            self.scratchpad.log("Coordinator", "TestCritic has no validate_test_coverage or critique_tests method", level=LogLevel.WARNING)
                            critic_result = None

                        if critic_result and isinstance(critic_result, dict):
                            validation_result["metadata"]["test_critic_result"] = critic_result

                            # Only fail validation if critical issues are found
                            if not critic_result.get("is_valid", True) and critic_result.get("severity", "") == "critical":
                                msg = f"Test critic found critical issues: {critic_result.get('message', 'Unknown issue')}"
                                self.scratchpad.log("Coordinator", msg, level=LogLevel.ERROR)
                                self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "test_critic", "error": msg})
                                validation_result["failed_step"] = "test_critic"
                                validation_result["output"] = msg
                                return validation_result
                    except Exception as e:
                        # Handle test critic errors through error handler but don't fail validation
                        error_context = self.error_handler.handle_exception(
                            exc=e,
                            phase="validation_run",
                            operation="test_critic",
                            level=logging.WARNING,
                            reraise=False
                        )
                        validation_result["metadata"]["test_critic_error"] = str(e)

            # All validations passed
            self.progress_tracker.update_progress({"phase": "validation_run", "status": "completed"})
            validation_result["success"] = True
            validation_result["output"] = "All checks passed"
            return validation_result

    def _apply_changes_and_manage_dependencies(self, changes: Dict[str, str]) -> bool:
        """Apply generated code changes to files and install any new dependencies."""
        # Use the error handler for consistent error handling during change application
        with self.error_handler.error_context(
            phase="apply_changes", 
            operation="apply_and_manage_dependencies"
        ):
            try:
                # Track SQL script files that need to be executed
                sql_scripts = []
                
                for filepath, content in changes.items():
                    dirpath = os.path.dirname(filepath)
                    if dirpath:
                        os.makedirs(dirpath, exist_ok=True)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.scratchpad.log("Coordinator", f"Wrote file: {filepath}")
                    
                    # Check if the file is a SQL script
                    if filepath.endswith('.sql'):
                        sql_scripts.append(filepath)
                
                # Install dependencies if requirements.txt changed
                if os.path.exists('requirements.txt'):
                    self.scratchpad.log("Coordinator", "Installing dependencies...")
                    exit_code, _ = self.bash_tool.run_command("pip install -r requirements.txt", timeout=300)
                    self.scratchpad.log("Coordinator", f"Dependency installation result: exit_code={exit_code}")
                
                # Execute SQL scripts if any and database manager is available
                if sql_scripts and hasattr(self, 'database_manager') and self.database_manager:
                    self.scratchpad.log("Coordinator", "Executing database scripts...")
                    db_configs = self.config.config.get("databases", {})

                    if db_configs:
                        for script_path in sql_scripts:
                            # Determine target database from script path or content
                            target_db = self._determine_target_database(script_path, db_configs)
                            if target_db:
                                self.scratchpad.log("Coordinator", f"Executing SQL script {script_path} on database {target_db}")
                                result = self.database_manager.run_migration(script_path, db_name=target_db)

                                if not result.get("success", False):
                                    error_msg = result.get("error", "Unknown database error")
                                    self.scratchpad.log("Coordinator", f"SQL script execution failed: {error_msg}", level=LogLevel.ERROR)
                                    print(f"Warning: SQL script execution failed: {error_msg}")
                                    # Continue with other changes
                
                return True
            except Exception as e:
                # Handle change application errors through error handler
                error_context = self.error_handler.handle_exception(
                    exc=e,
                    phase="apply_changes",
                    operation="apply_and_manage_dependencies",
                    level=logging.ERROR,
                    reraise=False,
                    variables={"changes_count": len(changes) if changes else 0}
                )
                self.scratchpad.log("Coordinator", f"Error applying changes: {e}", level=LogLevel.ERROR)
                print(f"Error applying changes: {e}")
                return False
    
    def _determine_target_database(self, script_path: str, db_configs: Dict[str, Any]) -> Optional[str]:
        """Determine which database a SQL script is intended for.
        
        Args:
            script_path: Path to the SQL script
            db_configs: Dictionary of database configurations
            
        Returns:
            Database name or None if can't determine
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="database", 
            operation="determine_target_database",
            inputs={"script_path": script_path}
        ):
            # Simple heuristic: check script path or filename for database name
            script_path_lower = script_path.lower()
            
            for db_name in db_configs:
                if db_name.lower() in script_path_lower:
                    return db_name
            
            # If only one database is configured, use it
            if len(db_configs) == 1:
                return list(db_configs.keys())[0]
            
            # Otherwise, try to determine from script content
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    
                    # Check for USE statements or database-specific syntax
                    for db_name, db_config in db_configs.items():
                        db_type = db_config.get("type", "").lower()
                        database = db_config.get("database", "").lower()
                        
                        if db_type and db_type in content:
                            return db_name
                        if database and database in content:
                            return db_name
            except Exception as e:
                # Handle content reading errors through error handler but don't fail the operation
                self.error_handler.handle_exception(
                    exc=e,
                    phase="database", 
                    operation="read_script_content",
                    level=logging.WARNING,
                    reraise=False
                )
            
            # If can't determine, return None
            return None
    
    def _extract_implementation_files_from_plan(self, plan: str) -> List[str]:
        """Extract implementation files from the plan text."""
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="planning", 
            operation="extract_implementation_files"
        ):
            if not plan:
                return []
                
            # Common patterns for file paths in plans
            file_patterns = [
                r'(?:create|modify|update|edit|in|file:)\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
                r'(?:Create|Modify|Update|Edit)\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
                r'(?:create|modify|update|edit|in)\s+file\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
                r'File:\s+`?([^`\s]+\.[a-zA-Z0-9]+)`?',
                r'`([^`\s]+\.[a-zA-Z0-9]+)`',
                r'implementation_file[\"\':].*?[\"\':]([^\"\']+)[\"\':]'
            ]
            
            # Also try to extract files from test specifications section
            test_spec_pattern = r'test_specifications.*?implementation_file.*?[\'"]([^\'"]+)[\'"]'
            
            files = []
            
            # Check for test specifications section
            test_spec_matches = re.findall(test_spec_pattern, plan, re.DOTALL)
            if test_spec_matches:
                files.extend(test_spec_matches)
            
            # Check for general file patterns
            for pattern in file_patterns:
                matches = re.findall(pattern, plan)
                files.extend(matches)
            
            # Remove duplicates and test files
            unique_files = []
            for file in files:
                # Skip test files
                if "test_" in file or "tests/" in file or ".test." in file or ".spec." in file:
                    continue
                    
                # Skip duplicates
                if file not in unique_files:
                    unique_files.append(file)

            # Resolve to absolute paths
            resolved_files = []
            for file_path in unique_files:
                # Check if it's a relative path
                if not os.path.isabs(file_path):
                    # Convert to absolute path
                    abs_path = os.path.join(os.getcwd(), file_path)
                    resolved_files.append(abs_path)
                else:
                    resolved_files.append(file_path)
            
            return resolved_files
    
    def _validate_pre_planning_data(self, pre_plan_data: Dict[str, Any]) -> bool:
        """
        Validate pre-planning data before processing feature groups.

        This performs essential structure checks on the pre-planning data to ensure
        it has the required fields and formats before passing it to the feature
        group processor.

        Args:
            pre_plan_data: Pre-planning data dictionary

        Returns:
            True if valid, False otherwise
        """
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="validation", 
            operation="validate_pre_planning_data"
        ):
            self.scratchpad.log("Coordinator", "Validating pre-planning data structure...")

            # Check basic structure - these are critical checks that must pass
            if not isinstance(pre_plan_data, dict):
                self.scratchpad.log("Coordinator", "Pre-planning data must be a dictionary", level=LogLevel.ERROR)
                return False

            if "feature_groups" not in pre_plan_data:
                self.scratchpad.log("Coordinator", "Pre-planning data missing feature_groups", level=LogLevel.ERROR)
                return False

            if not pre_plan_data["feature_groups"]:
                self.scratchpad.log("Coordinator", "Pre-planning data feature_groups is empty", level=LogLevel.ERROR)
                return False

            if not isinstance(pre_plan_data["feature_groups"], list):
                self.scratchpad.log("Coordinator", "Pre-planning data feature_groups must be a list", level=LogLevel.ERROR)
                return False

            # Run additional context-aware validations
            has_context_manager = hasattr(self, 'context_manager') and self.context_manager
            validation_issues = []

            # Run context validation if available
            if has_context_manager:
                for i, feature_group in enumerate(pre_plan_data["feature_groups"]):
                    if not isinstance(feature_group, dict):
                        self.scratchpad.log("Coordinator", f"Feature group {i} is not a dictionary", level=LogLevel.ERROR)
                        return False

                    try:
                        # See if we can use context manager to validate feature group against context
                        context_validation = self.context_manager.validate_against_context(
                            feature_group,
                            context_type="file_metadata"
                        )

                        if not context_validation.get("valid", True):
                            for issue in context_validation.get("issues", []):
                                validation_issues.append(issue)
                                self.scratchpad.log("Coordinator", issue, level=LogLevel.WARNING)
                    except Exception as e:
                        # Handle validation errors through error handler but don't fail the operation
                        self.error_handler.handle_exception(
                            exc=e,
                            phase="validation", 
                            operation="context_validation",
                            level=logging.WARNING,
                            reraise=False
                        )

            # Report all validation issues but continue with workflow
            if validation_issues:
                self.scratchpad.log("Coordinator",
                                 f"Pre-planning validation issues found: {len(validation_issues)}",
                                 level=LogLevel.WARNING)

                # Log issues to context for later phases
                if has_context_manager:
                    context_data = {
                        "validation_issues": validation_issues,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.context_manager.add_to_context("validation_issues", context_data)

                # Log only a sample of issues to avoid flooding the console
                for issue in validation_issues[:5]:
                    self.scratchpad.log("Coordinator", f"  - {issue}", level=LogLevel.WARNING)

                if len(validation_issues) > 5:
                    self.scratchpad.log("Coordinator", f"  ... and {len(validation_issues) - 5} more issues",
                                      level=LogLevel.WARNING)

            # Validation successful
            return True
        
    def _finalize_task(self, final_changes):
        """Finalize the task: commit, push, and create a pull request if configured."""
        # Use error context manager for consistent error handling
        with self.error_handler.error_context(
            phase="finalizing", 
            operation="finalize_task"
        ):
            self.progress_tracker.update_progress({"phase": "finalizing", "status": "started"})
            self.scratchpad.log("Coordinator", "Finalizing task: committing changes and creating PR if configured...")
            
            # Save database schema metadata if database manager is available
            if hasattr(self, 'database_manager') and self.database_manager:
                try:
                    db_configs = self.config.config.get("databases", {})
                    if db_configs:
                        self.scratchpad.log("Coordinator", "Saving database schema metadata...")
                        schema_metadata = {}
                        
                        for db_name in db_configs:
                            schema_result = None
                            if hasattr(self.database_manager.database_tool, 'get_schema_info'):
                                schema_result = self.database_manager.database_tool.get_schema_info(db_name)
                            if schema_result and schema_result.get("success", False):
                                schema_metadata[db_name] = schema_result.get("schema", {})
                            
                        # Save schema metadata to a file for reference
                        if schema_metadata:
                            os.makedirs("database_metadata", exist_ok=True)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            schema_file = f"database_metadata/schema_{timestamp}.json"
                            with open(schema_file, 'w', encoding='utf-8') as f:
                                json.dump(schema_metadata, f, indent=2)
                            self.scratchpad.log("Coordinator", f"Database schema metadata saved to {schema_file}")
                            
                            # Add database schema file to changes list if it's a dictionary
                            if isinstance(final_changes, dict):
                                final_changes[schema_file] = f"Database schema metadata as of {timestamp}"
                            elif isinstance(final_changes, list):
                                final_changes.append(schema_file)
                except Exception as db_error:
                    # Handle database errors through error handler but don't fail the operation
                    self.error_handler.handle_exception(
                        exc=db_error,
                        phase="finalizing", 
                        operation="save_database_metadata",
                        level=logging.WARNING,
                        reraise=False
                    )
                    # Continue with task finalization despite database metadata error
            
            # Commit changes
            commit_message = f"feat: Implement '{getattr(self, 'current_task_description', 'feature')[:50]}...'"
            file_paths = list(final_changes.keys()) if isinstance(final_changes, dict) else final_changes
            self.git_tool.add_and_commit(file_paths, commit_message)
            self.scratchpad.log("Coordinator", "Changes committed.")

            # Push branch (optional, based on config)
            if self.config.config.get("push_branch", True):
                branch_name = self.git_tool.get_current_branch()
                self.git_tool.push_branch(branch_name)
                self.scratchpad.log("Coordinator", f"Branch '{branch_name}' pushed.")
            else:
                branch_name = self.git_tool.get_current_branch()

            # Create PR (optional, based on config)
            if self.config.config.get("create_pull_request", True) and hasattr(self, "current_issue_url"):
                pr_title = f"Implement: {getattr(self, 'current_task_description', 'feature')}"
                pr_body = f"Implements feature request.\nCloses #{str(self.current_issue_url).split('/')[-1]}"
                
                # Add database schema information to PR description if available
                if hasattr(self, 'database_manager') and self.database_manager:
                    db_configs = self.config.config.get("databases", {})
                    if db_configs:
                        pr_body += "\n\n## Database Changes\n"
                        for db_name in db_configs:
                            pr_body += f"\n### {db_name.capitalize()} Database\n"
                            pr_body += "- Schema metadata saved in database_metadata directory\n"
                
                pr_result = self.git_tool.create_pull_request(pr_title, pr_body, branch_name)
                if pr_result.get("success"):
                    self.scratchpad.log("Coordinator", f"Pull request created: {pr_result.get('url')}")
                    self.progress_tracker.update_progress({"phase": "finalizing", "status": "pr_created", "data": {"url": pr_result.get('url')}})
                else:
                    self.scratchpad.log("Coordinator", f"Failed to create PR: {pr_result.get('error')}", level=LogLevel.WARNING)

            self.progress_tracker.update_progress({"phase": "finalizing", "status": "completed"})
            self.task_state_manager.clear_state(self.current_task_id)
            print("Task completed successfully.")

    # Method removed - functionality consolidated in run_task with from_design=True

    def execute_design(self, design_objective: str) -> Dict[str, Any]:
        """Execute the design workflow.
        
        This is a facade method that delegates to the design manager to create a design document.
        
        Args:
            design_objective: The design objective or requirements
            
        Returns:
            Dictionary with design execution results
        """
        try:
            self.scratchpad.log("Coordinator", f"Starting design process for: {design_objective}")
            
            if not hasattr(self, 'design_manager'):
                return {
                    "success": False,
                    "error": "Design manager not available"
                }
                
            # Start design conversation
            initial_response = self.design_manager.start_design_conversation(design_objective)
            print(initial_response)
            
            # Continue the conversation flow
            is_design_complete = False
            while not is_design_complete:
                user_message = input("Design> ")
                
                if user_message.lower() in ["/exit", "/quit", "/cancel"]:
                    return {
                        "success": False,
                        "cancelled": True
                    }
                
                response, is_design_complete = self.design_manager.continue_conversation(user_message)
                print(response)
            
            # Write design to file
            success, message = self.design_manager.write_design_to_file()
            if not success:
                return {
                    "success": False,
                    "error": message
                }
            
            # Prompt for next steps
            choices = self.design_manager.prompt_for_implementation()
            
            # Return results based on user choices
            return {
                "success": True,
                "design_file": "design.txt",
                "next_action": "implementation" if choices.get("implementation") else 
                              "deployment" if choices.get("deployment") else 
                              None
            }
            
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="execute_design",
                level=logging.ERROR
            )
            return {
                "success": False,
                "error": str(e)
            }

    def execute_deployment(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Execute deployment using the deployment manager."""
        try:
            if not hasattr(self, "deployment_manager"):
                return {"success": False, "error": "Deployment manager not available"}

            result = self.deployment_manager.execute_deployment()
            return result
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="execute_deployment",
                level=logging.ERROR,
            )
            return {"success": False, "error": str(e)}

    def deploy(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Facade used by CommandProcessor to start deployment."""
        return self.execute_deployment(design_file)

    def execute_implementation(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Execute implementation using the implementation manager."""
        try:
            if not hasattr(self, "implementation_manager"):
                return {"success": False, "error": "Implementation manager not available"}

            if not os.path.exists(design_file):
                return {"success": False, "error": f"Design file not found: {design_file}"}

            if hasattr(self, "scratchpad"):
                self.scratchpad.log("Coordinator", f"Starting implementation from {design_file}")

            return self.implementation_manager.start_implementation(design_file)
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="execute_implementation",
                level=logging.ERROR,
            )
            return {"success": False, "error": str(e)}

    def execute_continue(self, continue_type: str = "implementation") -> Dict[str, Any]:
        """Continue a workflow such as implementation or design."""
        try:
            if continue_type == "implementation":
                if not hasattr(self, "implementation_manager"):
                    return {"success": False, "error": "Implementation manager not available"}

                if hasattr(self, "scratchpad"):
                    self.scratchpad.log("Coordinator", "Continuing implementation")

                return self.implementation_manager.continue_implementation()

            return {"success": False, "error": f"Unsupported continuation type: {continue_type}"}
        except Exception as e:
            self.error_handler.handle_exception(
                exc=e,
                operation="execute_continue",
                level=logging.ERROR,
            )
            return {"success": False, "error": str(e)}
