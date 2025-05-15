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
            
            self.design_manager = DesignManager(self)
            self.implementation_manager = ImplementationManager(self)
            self.deployment_manager = DeploymentManager(self)
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
    
    def run_task(self, request_text: str):
        """Run a task based on the request text.

        The core workflow is:
        1. Pre-planning: Generate feature groups from task description using pre_planner_json_enforced
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
            request_text: The original task description from the user
        """
        # Use the main try-except with error handler for the entire task execution
        # This will provide consistent error handling and logging for the entire task
        try:
            # Initialize task tracking
            self.current_task_description = request_text
            self.current_task_id = self.task_state_manager.create_new_task_id()
            self.scratchpad.log("Coordinator", f"Starting task {self.current_task_id}: {request_text[:50]}...")
            self.progress_tracker.update_progress({"phase": "pre_planner", "status": "started", "task_id": self.current_task_id})

            # --- PHASE 1: Pre-Planning - Generate feature groups ---
            # Use a more specific error handling context for this phase
            with self.error_handler.error_context(phase="pre_planning", operation="generate_feature_groups"):
                # First, import both base and specialized pre-planner modules to maintain architecture consistency
                from agent_s3.pre_planner import call_pre_planner
                from agent_s3.pre_planner_json_enforced import pre_planning_workflow

                # Collect context for the pre-planner
                context = self._prepare_context(request_text)

                # Call the canonical JSON-enforced pre-planner for robust schema validation
                self.scratchpad.log("Coordinator", "Using JSON-enforced pre-planner for feature group generation")
                success, pre_plan_data = pre_planning_workflow(
                    self.router_agent,
                    request_text,
                    context=context
                )

                # Handle pre-planning failure
                if not success:
                    error_msg = "Pre-planning failed to produce valid output."
                    self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                    print(error_msg)
                    # Raise a specific exception type for consistent handling
                    raise PlanningError(error_msg)

                self.scratchpad.log("Coordinator", "Pre-planning completed successfully.")

            # --- PHASE 2: Validation - Validate pre-planning output ---
            with self.error_handler.error_context(phase="validation", operation="validate_pre_planning"):
                # Validate the pre-planning output structure and content
                self.scratchpad.log("Coordinator", "Validating pre-planning output...")

                # Use the plan validator for comprehensive static validation
                from agent_s3.tools.plan_validator import validate_pre_plan
                plan_valid, validation_results = validate_pre_plan(
                    pre_plan_data,
                    os.getcwd(),
                    self.context_registry
                )

                # Display and handle critical errors
                critical_errors = validation_results.get("critical", [])
                warnings = validation_results.get("warnings", [])

                if critical_errors:
                    for error in critical_errors:
                        self.scratchpad.log("Coordinator", f"Critical validation error: {error}", level=LogLevel.ERROR)
                        print(f"\n❌ CRITICAL ERROR: {error}")

                    proceed_anyway = self.prompt_moderator.ask_yes_no_question(
                        "Critical validation errors were found. Proceed anyway?"
                    )
                    if not proceed_anyway:
                        self.scratchpad.log("Coordinator", "User cancelled due to validation errors.")
                        print("Task cancelled due to validation errors.")
                        return
                    else:
                        self.scratchpad.log("Coordinator", "User chose to proceed despite validation errors.")

                # Display warnings (but continue processing)
                if warnings:
                    self.scratchpad.log("Coordinator", f"Plan validation found {len(warnings)} warnings")
                    for warning in warnings[:3]:  # Show only first 3 warnings
                        print(f"\n⚠️ WARNING: {warning}")
                    if len(warnings) > 3:
                        print(f"... and {len(warnings) - 3} more warnings")

                # Save validation results for reference and debugging
                try:
                    from agent_s3.tools.context_management.checkpoint_manager import save_checkpoint
                    checkpoint_id = save_checkpoint(
                        "pre_planning_validation",
                        validation_results,
                        metadata={"timestamp": datetime.now().isoformat()}
                    )
                    self.scratchpad.log("Coordinator", f"Pre-planning validation checkpoint saved: {checkpoint_id}")
                except Exception as e:
                    # Use the error handler to record this exception without stopping the workflow
                    self.error_handler.handle_exception(
                        exc=e,
                        phase="validation",
                        operation="save_checkpoint",
                        level=logging.WARNING,
                        reraise=False
                    )

            # Interactive handoff loop
            with self.error_handler.error_context(phase="user_interaction", operation="pre_planning_handoff"):
                while True:
                    decision, payload = self._present_pre_planning_results_to_user(pre_plan_data)
                    if decision == "yes":
                        pre_plan_data = payload
                        break
                    elif decision == "no":
                        self.scratchpad.log("Coordinator", "User terminated the workflow at pre-planning handoff.")
                        print("Workflow terminated by user at pre-planning stage.")
                        return
                    elif decision == "modify":
                        modification_text = payload
                        from agent_s3.tools.phase_validator import validate_user_modifications
                        is_valid, error_message = validate_user_modifications(modification_text)
                        if not is_valid:
                            self.scratchpad.log("Coordinator", f"Invalid modification: {error_message}", level=LogLevel.WARNING)
                            print(f"Warning: {error_message}")

                        from agent_s3.pre_planner_json_enforced import regenerate_pre_planning_with_modifications
                        pre_plan_data = regenerate_pre_planning_with_modifications(
                            self.router_agent,
                            pre_plan_data,
                            modification_text
                        )

                        try:
                            from agent_s3.tools.context_management.checkpoint_manager import save_checkpoint
                            checkpoint_id = save_checkpoint(
                                "pre_planning_modified",
                                pre_plan_data,
                                metadata={"modification": modification_text}
                            )
                            self.scratchpad.log("Coordinator", f"Modified pre-planning checkpoint saved: {checkpoint_id}")
                        except Exception as e:
                            # Use the error handler to record this exception without stopping the workflow
                            self.error_handler.handle_exception(
                                exc=e,
                                phase="user_interaction",
                                operation="save_modified_checkpoint",
                                level=logging.WARNING,
                                reraise=False
                            )
                        continue

            # --- PHASE 4: Signature Normalization - Normalize signatures and IDs ---
            self.progress_tracker.update_progress({"phase": "signature_finalization", "status": "started"})
            self.scratchpad.log("Coordinator", "Performing signature and ID finalization to ensure consistent naming and syntax...")

            with self.error_handler.error_context(phase="signature_normalization", operation="normalize_signatures"):
                try:
                    # Run the signature normalization step
                    from agent_s3.signature_normalizer import normalize_pre_plan
                    normalized_pre_plan = normalize_pre_plan(pre_plan_data, os.getcwd(), self.context_registry)

                    # Count the number of normalized elements
                    normalized_count = 0
                    for group in normalized_pre_plan.get("feature_groups", []):
                        for feature in group.get("features", []):
                            normalized_count += len(feature.get("system_design", {}).get("code_elements", []))

                    self.scratchpad.log("Coordinator", f"Successfully normalized signatures and IDs for {normalized_count} code elements")
                    self.progress_tracker.update_progress({"phase": "signature_finalization", "status": "completed", "normalized_count": normalized_count})

                    # Save a checkpoint with the normalized plan
                    try:
                        # Import the checkpoint manager within the try block to handle import errors gracefully
                        from agent_s3.tools.context_management.checkpoint_manager import save_checkpoint
                        checkpoint_id = save_checkpoint(
                            "pre_planning_normalized",
                            normalized_pre_plan,
                            metadata={
                                "normalization_timestamp": datetime.now().isoformat(),
                                "normalized_element_count": normalized_count
                            }
                        )
                        self.scratchpad.log("Coordinator", f"Normalized pre-planning checkpoint saved: {checkpoint_id}")
                    except Exception as e:
                        # Use the error handler to record this exception without stopping the workflow
                        self.error_handler.handle_exception(
                            exc=e,
                            phase="signature_normalization",
                            operation="save_normalized_checkpoint",
                            level=logging.WARNING,
                            reraise=False
                        )

                    # Update pre_plan_data with the normalized version
                    pre_plan_data = normalized_pre_plan

                except Exception as e:
                    # Use the error handler to record this exception without stopping the workflow
                    error_context = self.error_handler.handle_exception(
                        exc=e,
                        phase="signature_normalization",
                        operation="normalize_signatures",
                        level=logging.ERROR,
                        reraise=False
                    )
                    
                    # Log the error but continue with the original pre_plan_data (fail safe)
                    self.scratchpad.log("Coordinator", f"Error during signature and ID finalization: {str(e)}", level=LogLevel.ERROR)
                    self.progress_tracker.update_progress({"phase": "signature_finalization", "status": "error", "error": str(e)})
                    print(f"\n⚠️ WARNING: Could not fully normalize signatures and IDs: {str(e)}")
                    print("Proceeding with original pre-planning data.")

            # --- PHASE 5: Feature Group Processing - Generate consolidated plans ---
            self.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "started"})
            self.scratchpad.log("Coordinator", "Processing feature groups from pre-planning output...")

            with self.error_handler.error_context(phase="feature_group_processing", operation="process_groups"):
                # We've already validated the pre-planning data during the validation phase
                # No need to validate again before processing

                # Process feature groups through the FeatureGroupProcessor
                # The feature_group_processor.process_pre_planning_output method:
                # 1. Extracts feature groups from pre_plan_data
                # 2. Generates architecture reviews for each group
                # 3. Creates consolidated plans with implementation details
                # 4. Returns a result dictionary with processed_groups array
                processing_results = self.feature_group_processor.process_pre_planning_output(pre_plan_data, request_text)

                # Handle processing failures
                if not processing_results.get("success", False):
                    error_msg = processing_results.get("error", "Unknown error")
                    self.scratchpad.log("Coordinator", f"Feature group processing failed: {error_msg}", level=LogLevel.ERROR)
                    print(f"Feature group processing failed: {error_msg}")

                    # Try to generate a recovery plan if debugging manager is available
                    if hasattr(self, 'debugging_manager') and self.debugging_manager:
                        try:
                            recovery_plan = self.debugging_manager.generate_recovery_plan(
                                phase="feature_group_processing",
                                error=error_msg,
                                context={"pre_plan_data": pre_plan_data}
                            )
                            self.scratchpad.log("Coordinator", f"Recovery plan: {recovery_plan.get('description', 'No recovery plan')}")
                            print(f"Recovery plan suggestion: {recovery_plan.get('description', 'No recovery plan')}")
                        except Exception as recovery_error:
                            # Use the error handler to record this exception without stopping the workflow
                            self.error_handler.handle_exception(
                                exc=recovery_error, 
                                phase="feature_group_processing", 
                                operation="generate_recovery_plan",
                                level=logging.ERROR,
                                reraise=False
                            )
                    # Raise a specific exception type for consistent handling
                    raise PlanningError(f"Feature group processing failed: {error_msg}")

                # Get the processed feature groups from the results
                # The feature group processor returns these as a list of either:
                # 1. Consolidated plan dictionaries (when successful)
                # 2. Error dictionaries with error messages (when processing failed for a group)
                processed_groups = processing_results.get("processed_groups", [])
                if not processed_groups:
                    error_msg = "No processed groups returned from feature group processor"
                    self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                    print("No feature groups were processed successfully. Cannot proceed.")
                    # Raise a specific exception type for consistent handling
                    raise PlanningError(error_msg)

                self.scratchpad.log("Coordinator", f"Processed {len(processed_groups)} feature groups.")

            # --- PHASE 6: Plan Approval - Get user approval for consolidated plans ---
            with self.error_handler.error_context(phase="plan_approval", operation="get_user_approval"):
                approved_consolidated_plans = []
                for group_plan in processed_groups:
                    # Check if this is a successful plan or an error entry
                    if "error" not in group_plan:
                        feature_group_name = group_plan.get('group_name', 'Unknown')
                        self.scratchpad.log("Coordinator", f"Processing consolidated plan for feature group: {feature_group_name}")

                        # Present consolidated plan to user for approval
                        if group_plan:
                            decision, modification_text = self.feature_group_processor.present_consolidated_plan_to_user(group_plan)
                            if decision == "yes":
                                self.scratchpad.log("Coordinator", f"User accepted the plan for feature group: {feature_group_name}")
                                approved_consolidated_plans.append(group_plan)
                            elif decision == "no":
                                self.scratchpad.log("Coordinator", f"User rejected the plan for feature group: {feature_group_name}")
                                print(f"Implementation of feature group '{feature_group_name}' cancelled.")
                                continue
                            elif decision == "modify":
                                self.scratchpad.log("Coordinator", f"User requested modifications for feature group: {feature_group_name}")
                                updated_plan = self.feature_group_processor.update_plan_with_modifications(
                                    group_plan, modification_text
                                )
                                has_critical_issues = False
                                if "revalidation_status" in updated_plan and not updated_plan["revalidation_status"].get("is_valid", True):
                                    has_critical_issues = True
                                    issues = updated_plan["revalidation_status"].get("issues_found", [])
                                    issues_str = ", ".join(issues) if isinstance(issues, list) else str(issues)
                                    self.scratchpad.log("Coordinator",
                                                     f"Re-validation failed for modified plan: {issues_str}",
                                                     level=LogLevel.WARNING)
                                    proceed_anyway = self.prompt_moderator.ask_yes_no_question(
                                        "Re-validation has found critical issues with your modifications. Proceed anyway?"
                                    )
                                    if not proceed_anyway:
                                        self.scratchpad.log("Coordinator", "User decided not to proceed with invalid plan")
                                        print("Implementation canceled due to validation issues.")
                                        continue
                                    else:
                                        self.scratchpad.log("Coordinator",
                                                         "User chose to proceed despite validation issues",
                                                         level=LogLevel.WARNING)
                                        # Add warning to additional_considerations if they exist
                                        if "architecture_review" in updated_plan and "additional_considerations" in updated_plan["architecture_review"]:
                                            # Make sure it's a list before appending
                                            if isinstance(updated_plan["architecture_review"]["additional_considerations"], list):
                                                updated_plan["architecture_review"]["additional_considerations"].append(
                                                    "WARNING: Implementation proceeded despite validation issues"
                                                )

                                self.scratchpad.log("Coordinator",
                                                 f"Plan updated with user modifications for feature group: {feature_group_name}" +
                                                 (" (with validation warnings)" if has_critical_issues else ""))
                                approved_consolidated_plans.append(updated_plan)
                        else:
                            self.scratchpad.log("Coordinator", f"No consolidated plan available for feature group: {feature_group_name}", level=LogLevel.WARNING)
                    else:
                        # Handle error entries in the processed_groups array
                        error_msg = group_plan.get('error', 'Unknown error')
                        error_group = group_plan.get('group_name', 'Unknown group')
                        self.scratchpad.log("Coordinator", f"Feature group {error_group} processing failed: {error_msg}", level=LogLevel.WARNING)
                self.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "completed"})
                print(f"Successfully processed {len(processed_groups)} feature groups.")

            # --- PHASE 7: Implementation - Code generation, validation, and debugging ---
            if not approved_consolidated_plans:
                self.scratchpad.log("Coordinator", "No approved plans to implement.")
                print("No approved plans available for implementation.")
                self.progress_tracker.update_progress({"phase": "implementation_loop", "status": "skipped"})
                return

            self.progress_tracker.update_progress({"phase": "implementation_loop", "status": "started"})
            all_changes_applied_successfully = {} # Store successful changes {filepath: content}
            task_overall_success = True

            for plan_index, consolidated_plan in enumerate(approved_consolidated_plans):
                with self.error_handler.error_context(
                    phase="implementation_loop", 
                    operation=f"implement_plan_{plan_index}"
                ):
                    group_name = consolidated_plan.get("group_name", f"Approved Plan {plan_index+1}")
                    plan_id = consolidated_plan.get("plan_id", f"plan_{plan_index+1}")
                    self.scratchpad.log("Coordinator", f"Starting implementation loop for: {group_name} (Plan ID: {plan_id})")
                    print(f"\n--- Implementing Feature Group: {group_name} ---")
                    self.progress_tracker.update_progress({"phase": "implementation", "status": "started", "group": group_name})

                    max_debug_attempts = self.config.config.get('max_debug_attempts', 3) # Get max attempts from config
                    debug_attempt = 0
                    implementation_successful = False
                    last_generated_code = {} # Keep track of the code for this group iteration

                    while debug_attempt < max_debug_attempts:
                        debug_attempt += 1
                        self.scratchpad.log("Coordinator", f"Implementation/Debug Attempt {debug_attempt}/{max_debug_attempts} for {group_name}")
                        print(f"Attempt {debug_attempt}/{max_debug_attempts} for {group_name}...")

                        # 1. Generate Code (or use previous attempt's code if debugging)
                        if debug_attempt == 1: # Only generate code on the first attempt
                            self.progress_tracker.update_progress({
                                "phase": "code_generation", 
                                "status": "started", 
                                "group": group_name, 
                                "attempt": debug_attempt
                            })
                            self.scratchpad.log("Coordinator", f"Generating code for {group_name}")
                            
                            with self.error_handler.error_context(
                                phase="code_generation", 
                                operation=f"generate_{group_name}"
                            ):
                                generated_code = self.code_generator.generate_code(
                                    plan=consolidated_plan,
                                    tech_stack=self.tech_stack # Pass tech stack if available
                                )
                                
                            self.progress_tracker.update_progress({
                                "phase": "code_generation", 
                                "status": "completed" if generated_code else "failed", 
                                "group": group_name
                            })

                            if not generated_code:
                                error_msg = f"Code generation failed for {group_name} on attempt {debug_attempt}."
                                self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                                print(f"❌ ERROR: Code generation failed for {group_name}. Skipping this group.")
                                task_overall_success = False
                                break # Exit the debug loop for this feature group

                            last_generated_code = generated_code
                        else:
                            # Use the code generated in the *previous* failed attempt for subsequent debug tries
                            self.scratchpad.log("Coordinator", f"Using code from previous attempt for debug attempt {debug_attempt}")
                            # The changes were applied in the previous iteration's debugging step

                        # 2. Apply Code Changes
                        self.progress_tracker.update_progress({
                            "phase": "apply_changes", 
                            "status": "started", 
                            "group": group_name, 
                            "attempt": debug_attempt
                        })
                        self.scratchpad.log("Coordinator", f"Applying changes for {group_name}")
                        
                        with self.error_handler.error_context(
                            phase="apply_changes", 
                            operation=f"apply_changes_{group_name}"
                        ):
                            apply_success = self._apply_changes_and_manage_dependencies(last_generated_code)
                            
                        self.progress_tracker.update_progress({
                            "phase": "apply_changes", 
                            "status": "completed" if apply_success else "failed", 
                            "group": group_name
                        })

                        if not apply_success:
                            error_msg = f"Failed to apply generated code changes for {group_name}."
                            self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                            print(f"❌ ERROR: Failed to apply code changes for {group_name}. Debugging may be needed or skipping.")
                            task_overall_success = False
                            # Decide if we should retry or break. Let's break for now on apply failure.
                            break

                        # 3. Run Validation Phase (Lint, Type Check, Test Execution)
                        self.progress_tracker.update_progress({
                            "phase": "validation", 
                            "status": "started", 
                            "group": group_name, 
                            "attempt": debug_attempt
                        })
                        self.scratchpad.log("Coordinator", f"Running validation for {group_name}")
                        
                        with self.error_handler.error_context(
                            phase="validation", 
                            operation=f"validate_{group_name}"
                        ):
                            validation_result = self._run_validation_phase()
                            
                        validation_passed = validation_result.get("success", False)
                        error_step = validation_result.get("failed_step", "unknown")
                        validation_output = validation_result.get("output", "No validation output available")

                        self.progress_tracker.update_progress({
                            "phase": "validation",
                            "status": "completed" if validation_passed else "failed",
                            "group": group_name,
                            **(validation_result.get("metadata", {}))
                        })

                        if validation_passed:
                            self.scratchpad.log("Coordinator", f"Validation successful for {group_name} on attempt {debug_attempt}")
                            print(f"✅ Validation successful for {group_name}.")
                            implementation_successful = True
                            # Store the successful code
                            all_changes_applied_successfully.update(last_generated_code)
                            break # Exit the debug loop for this feature group

                        # 4. Validation Failed - Trigger Debugging
                        else:
                            self.scratchpad.log("Coordinator", 
                                f"Validation failed for {group_name} at step '{error_step}'. Output:\n{validation_output}", 
                                level=LogLevel.WARNING
                            )
                            print(f"⚠️ Validation failed for {group_name} at step '{error_step}'. Attempting to debug...")

                            self.progress_tracker.update_progress({
                                "phase": "debugging", 
                                "status": "started", 
                                "group": group_name, 
                                "attempt": debug_attempt
                            })
                            # Extract error details for the debugging manager
                            # Basic extraction, DebuggingManager might parse more details internally
                            error_message = validation_output
                            traceback_text = validation_output # Use full output as traceback for context
                            # Try to find a file path in the output
                            file_path_match = re.search(r"(\S+\.(?:py|js|ts|jsx|tsx))\S*", validation_output) # Basic pattern
                            failed_file = file_path_match.group(1) if file_path_match else None

                            with self.error_handler.error_context(
                                phase="debugging", 
                                operation=f"debug_{group_name}"
                            ):
                                debug_result = self.debugging_manager.handle_error(
                                    error_message=error_message,
                                    traceback_text=traceback_text,
                                    file_path=failed_file,
                                    # line_number, function_name etc. could be extracted if validation provides them
                                    metadata={
                                        "failed_step": error_step, 
                                        "group_name": group_name, 
                                        "attempt": debug_attempt
                                    }
                                )

                            self.progress_tracker.update_progress({
                                "phase": "debugging", 
                                "status": "completed" if debug_result.get("success") else "failed", 
                                "group": group_name
                            })

                            if debug_result.get("success", False):
                                self.scratchpad.log("Coordinator", f"Debugging successful for {group_name}. Applying fixes and re-validating.")
                                print(f"🛠️ Debugging applied fixes for '{error_step}'. Re-validating...")
                                # Apply the fixes suggested by the debugger
                                fixes = debug_result.get("changes", {})
                                if fixes:
                                    # Update last_generated_code with the fixes for the next loop iteration's apply step
                                    last_generated_code.update(fixes)
                                else:
                                    self.scratchpad.log("Coordinator", 
                                        f"Debugging reported success but provided no changes for {group_name}. Retrying validation.", 
                                        level=LogLevel.WARNING
                                    )
                                # Continue to the next iteration of the while loop to re-apply and re-validate
                            else:
                                error_msg = f"Debugging failed for {group_name} on attempt {debug_attempt}: {debug_result.get('description')}"
                                self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                                print(f"❌ Debugging failed for {group_name}: {debug_result.get('description')}")
                                task_overall_success = False
                                break # Exit the debug loop for this feature group

                    # End of debug loop for this feature group
                    if not implementation_successful:
                        error_msg = f"Failed to implement feature group {group_name} after {max_debug_attempts} attempts."
                        self.scratchpad.log("Coordinator", error_msg, level=LogLevel.ERROR)
                        print(f"❌ Failed to implement feature group {group_name} after {max_debug_attempts} attempts.")
                        task_overall_success = False
                        # Optionally: Offer to skip or abort entire task here
                    else:
                        self.progress_tracker.update_progress({
                            "phase": "implementation", 
                            "status": "completed", 
                            "group": group_name
                        })

            self.progress_tracker.update_progress({"phase": "implementation_loop", "status": "completed"})

            # --- PHASE 8: Finalization - Commit changes ---
            if task_overall_success and all_changes_applied_successfully:
                self.scratchpad.log("Coordinator", "Implementation loop completed. Proceeding to finalize task.")
                print("\n✅ Implementation complete. Finalizing task...")
                self._finalize_task(all_changes_applied_successfully)
            elif all_changes_applied_successfully:
                self.scratchpad.log("Coordinator", "Implementation loop completed with partial success. Some groups failed.", level=LogLevel.WARNING)
                print("\n⚠️ Task completed with partial success. Some feature groups failed implementation. Finalizing applied changes...")
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
                inputs={"request_text": request_text}
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
                if hasattr(self, 'database_tool') and self.database_tool:
                    try:
                        db_configs = self.config.config.get("databases", {})
                        if db_configs:
                            self.scratchpad.log("Coordinator", "Validating database integrity...")
                            for db_name in db_configs:
                                test_result = self.database_tool.test_connection(db_name)
                                if not test_result.get("success", False):
                                    error_msg = test_result.get("error", "Unknown database error")
                                    self.progress_tracker.update_progress({"phase": "validation_run", "status": "failed", "step": "database", "error": error_msg})
                                    validation_result["failed_step"] = "database"
                                    validation_result["output"] = error_msg
                                    validation_result["metadata"]["db_name"] = db_name
                                    return validation_result
                                self.database_tool.get_schema_info(db_name)
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
                lint_cmd = "flake8 ." # Example, could be configurable
                lint_result = self.bash_tool.run_command(lint_cmd, timeout=120)
                lint_code = lint_result.get('exit_code', 1)
                lint_out = lint_result.get('output', '')
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
                type_cmd = "mypy ." # Example, could be configurable
                type_result = self.bash_tool.run_command(type_cmd, timeout=120)
                type_code = type_result.get('exit_code', 1)
                type_out = type_result.get('output', '')
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
                    result = self.bash_tool.run_command("pip install -r requirements.txt", timeout=300)
                    self.scratchpad.log("Coordinator", f"Dependency installation result: exit_code={result.get('exit_code', 1)}")
                
                # Execute SQL scripts if any and database_tool is available
                if sql_scripts and hasattr(self, 'database_tool') and self.database_tool:
                    self.scratchpad.log("Coordinator", "Executing database scripts...")
                    db_configs = self.config.config.get("databases", {})
                    
                    if db_configs:
                        for script_path in sql_scripts:
                            # Determine target database from script path or content
                            target_db = self._determine_target_database(script_path, db_configs)
                            if target_db:
                                self.scratchpad.log("Coordinator", f"Executing SQL script {script_path} on database {target_db}")
                                result = self.database_tool.execute_script(script_path, db_name=target_db)
                                
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
            
            # Save database schema metadata if database tool is available
            if hasattr(self, 'database_tool') and self.database_tool:
                try:
                    db_configs = self.config.config.get("databases", {})
                    if db_configs:
                        self.scratchpad.log("Coordinator", "Saving database schema metadata...")
                        schema_metadata = {}
                        
                        for db_name in db_configs:
                            # Get schema info for each database
                            schema_result = self.database_tool.get_schema_info(db_name)
                            if schema_result.get("success", False):
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
                if hasattr(self, 'database_tool') and self.database_tool:
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