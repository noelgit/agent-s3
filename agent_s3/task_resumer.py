"""Task Resumer component for Agent-S3.

Handles the resumption of interrupted tasks.
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Tuple

class TaskResumer:
    """Handles detection and resumption of interrupted tasks."""

    def __init__(self, coordinator, task_state_manager, scratchpad=None, progress_tracker=None):
        """Initialize the TaskResumer.
        
        Args:
            coordinator: Coordinator instance for accessing other components
            task_state_manager: TaskStateManager for accessing and saving task states
            scratchpad: Optional EnhancedScratchpadManager for logging
            progress_tracker: Optional ProgressTracker for updating task progress
        """
        self.coordinator = coordinator
        self.task_state_manager = task_state_manager
        self.scratchpad = scratchpad
        self.progress_tracker = progress_tracker
        self.current_task_id = None
    
    def check_for_interrupted_tasks(self) -> None:
        """Check for interrupted tasks and offer to resume them."""
        # Initialize resumption prompt
        if self.progress_tracker:
            self.progress_tracker.update_progress({
                "phase": "resumption",
                "status": "pending",
                "message": "Detecting interrupted tasks",
                "timestamp": datetime.now().isoformat()
            })
            
        # Get metadata for active tasks
        active_meta = self.task_state_manager.get_active_tasks()
        if not active_meta:
            self._log("No active tasks found to resume.")
            return
            
        # Sort by last updated time
        tasks_meta = sorted(active_meta, key=lambda m: m.get('last_updated', ''), reverse=True)
        self._log(f"Found {len(tasks_meta)} tasks available for resumption.")
        
        # Display resumable tasks
        print("\nDetected potentially interrupted tasks:")
        max_show = min(3, len(tasks_meta))
        for i, meta in enumerate(tasks_meta[:max_show], start=1):
            desc = f"Phase: {meta['phase']}, Request: {meta.get('request_text','')[:60]}"
            print(f"{i}. {desc} (Last updated: {meta.get('last_updated')})")
        print("\n0. Start fresh (don't resume any task)")
        
        # Prompt selection
        while True:
            choice = input(f"\nChoose a task to resume (0-{max_show}): ").strip()
            if not choice or choice == '0':
                self._log("User chose to start fresh.")
                return
                
            try:
                idx = int(choice)
            except ValueError:
                print("Enter a valid number.")
                continue
                
            if 1 <= idx <= max_show:
                selected = tasks_meta[idx-1]
                task_id = selected['task_id']
                phase = selected['phase']
                self._log(f"Resuming task {task_id} from phase {phase}")
                
                # Load full TaskState
                state = self.task_state_manager.load_task_snapshot(task_id, phase)
                if not state:
                    state = self.task_state_manager.recover_from_corrupted_snapshot(task_id, phase)
                    
                if not state:
                    print(f"Cannot load state for task {task_id}, phase {phase}. Starting fresh.")
                    return
                    
                # Update progress
                self.current_task_id = task_id
                if self.progress_tracker:
                    self.progress_tracker.update_progress({
                        "phase": "resumption",
                        "status": "resumed",
                        "message": f"Resumed task {task_id} at phase {phase}",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                # Resume
                self.resume_task(state)
                return
            else:
                print(f"Please choose between 0 and {max_show}.")
    
    def auto_resume_interrupted_task(self) -> Tuple[bool, str]:
        """Proactively detect and resume the most recent interrupted task.
        
        Returns:
            Tuple of (success, message)
        """
        # Get active tasks (sorted by last_updated desc)
        active_tasks = self.task_state_manager.get_active_tasks()
        if not active_tasks:
            return False, "No interrupted tasks found."
            
        latest_task = active_tasks[0]
        task_id = latest_task['task_id']
        phase = latest_task['phase']
        
        # Validate state before resuming
        state = self.task_state_manager.load_task_snapshot(task_id, phase)
        if not state:
            # Try recovery
            state = self.task_state_manager.recover_from_corrupted_snapshot(task_id, phase)
            if not state:
                self._log(f"Failed to load or recover state for task {task_id}, phase {phase}.")
                return False, f"Failed to load or recover state for task {task_id}, phase {phase}."
        
        # Prompt user for confirmation
        print(f"\nDetected an interrupted task: {phase} phase, request: {latest_task.get('request_text','')[:60]}")
        user_choice = input("Would you like to resume this task? (yes/no): ").strip().lower()
        if user_choice not in ["yes", "y"]:
            self._log(f"User declined to resume interrupted task {task_id}.")
            return False, "User declined to resume interrupted task."
            
        self.current_task_id = task_id
        self._log(f"Auto-resuming interrupted task {task_id} from phase {phase}.")
        
        if self.progress_tracker:
            self.progress_tracker.update_progress({
                "phase": "resumption",
                "status": "auto_resumed",
                "message": f"Resumed task {task_id} at phase {phase}",
                "timestamp": datetime.now().isoformat()
            })
            
        self.resume_task(state)
        return True, f"Resumed interrupted task {task_id} at phase {phase}."
    
    def resume_task(self, task_state) -> None:
        """Resume execution from a previously interrupted task.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        phase = task_state.phase
        self._log(f"Resuming task {task_state.task_id} from phase '{phase}'")
        
        try:
            if phase == "planning":
                self._resume_planning_phase(task_state)
            elif phase == "prompt_approval":
                self._resume_prompt_approval_phase(task_state)
            elif phase == "code_generation":
                self._resume_code_generation_phase(task_state)
            elif phase == "execution":
                self._resume_execution_phase(task_state)
            elif phase == "pr_creation":
                self._resume_pr_creation_phase(task_state)
            else:
                # Unknown phase
                print(f"Unknown phase '{phase}'. Cannot resume. Please start a new task.")
                self._log(f"Cannot resume unknown phase '{phase}'")
        
        except Exception as e:
            error_msg = f"Error resuming task: {e}"
            self._log(error_msg, level="error")
            print(f"Error: {error_msg}")
            print("Please start a new task.")
            traceback.print_exc()
    
    def _resume_planning_phase(self, task_state) -> None:
        """Resume from planning phase.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        # Extract state data
        request_text = getattr(task_state, 'request_text', '')
        plan = getattr(task_state, 'plan', {})
        discussion = getattr(task_state, 'discussion', '')
        code_context = getattr(task_state, 'code_context', {})
        
        print(f"\nResuming planning for: {request_text}")
        
        # If we already have a plan, we can jump to prompt approval
        if plan:
            print("Found existing plan, resuming from prompt approval phase.")
            self._update_development_status("resumed", "Resumed task from planning phase",
                                          phase="planning", request=request_text)
            
            # Pass the existing plan to prompt approval
            self.coordinator.prompt_moderator.moderate_prompt(request_text, plan, discussion)
        else:
            # Otherwise restart planning with the original request
            print("No existing plan found, restarting planning phase.")
            self.coordinator.planner.plan_development(request_text, code_context)
    
    def _resume_prompt_approval_phase(self, task_state) -> None:
        """Resume from prompt approval phase.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        # Extract state data
        plan = getattr(task_state, 'plan', {})
        discussion = getattr(task_state, 'discussion', '')
        is_approved = getattr(task_state, 'is_approved', False)
        user_modifications = getattr(task_state, 'user_modifications', '')
        
        request_text = "Original request not available"
        if plan and isinstance(plan, dict):
            request_text = plan.get('request_text', request_text)
        
        print(f"\nResuming prompt approval for: {request_text}")
        
        # If the prompt was already approved, move to code generation
        if is_approved:
            print("Prompt was already approved, resuming from code generation phase.")
            self._update_development_status("resumed", "Resumed task from prompt approval phase", 
                                          phase="prompt_approval", request=request_text)
            
            # Start code generation with the approved plan
            self.coordinator.code_generator.generate_code(plan, user_modifications)
        else:
            # Otherwise restart prompt approval
            print("Prompt was not approved, restarting prompt approval phase.")
            self.coordinator.prompt_moderator.moderate_prompt(request_text, plan, discussion)
    
    def _resume_code_generation_phase(self, task_state) -> None:
        """Resume from code generation phase.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        # Extract state data
        plan = getattr(task_state, 'plan', {})
        generated_changes = getattr(task_state, 'generated_changes', [])
        current_iteration = getattr(task_state, 'current_iteration', 0)
        _ = getattr(task_state, 'code_context', {})
        
        request_text = "Original request not available"
        if plan and isinstance(plan, dict):
            request_text = plan.get('request_text', request_text)
        
        print(f"\nResuming code generation for: {request_text}")
        print(f"Found {len(generated_changes)} generated changes, iteration {current_iteration}")
        
        # Prepare the code generator with the saved state
        self.coordinator.code_generator.plan = plan
        self.coordinator.code_generator.iteration = current_iteration
        
        if generated_changes:
            # If we already have generated changes, resume from execution
            print("Found existing generated changes, resuming from execution phase.")
            self._update_development_status("resumed", "Resumed task from code generation phase", 
                                          phase="code_generation", request=request_text)
            
            # Start execution with the generated changes
            if hasattr(self.coordinator, '_execute_changes'):
                self.coordinator._execute_changes(generated_changes, current_iteration, request_text)
            else:
                print("Unable to execute changes: _execute_changes method not found")
        else:
            # Otherwise restart code generation
            print("No generated changes found, restarting code generation phase.")
            self.coordinator.code_generator.generate_code(plan, "")
    
    def _resume_execution_phase(self, task_state) -> None:
        """Resume from execution phase with granular sub-state support.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        # Extract state data
        changes = getattr(task_state, 'changes', [])
        iteration = getattr(task_state, 'iteration', 0)
        _ = getattr(task_state, 'test_results', {})
        is_applied = getattr(task_state, 'is_applied', False)
        errors = getattr(task_state, 'errors', [])
        
        # Get sub-state for granular resumption
        sub_state = getattr(task_state, 'sub_state', 'PREPARING')
        raw_test_output = getattr(task_state, 'raw_test_output', None)
        pending_changes = getattr(task_state, 'pending_changes', [])
        applied_changes = getattr(task_state, 'applied_changes', [])
        
        print(f"\nResuming execution with {len(changes)} changes, iteration {iteration}, sub-state {sub_state}")
        
        # If execution was already completed, ask if user wants to create a PR
        if is_applied and not errors:
            user_choice = input("\nExecution was completed successfully. Create a PR? (yes/no): ").strip().lower()
            if user_choice in ["yes", "y"]:
                print("Resuming with PR creation phase.")
                self._update_development_status("resumed", "Resumed task from execution phase (completed)", 
                                              phase="execution")
                
                # Start PR creation
                if hasattr(self.coordinator, '_create_pr'):
                    self.coordinator._create_pr(changes, "No description available")
                else:
                    print("Unable to create PR: _create_pr method not found")
            else:
                print("Task completed, not creating PR as requested.")
                self._update_development_status("completed", "Task completed without PR", 
                                              phase="execution")
        else:
            # Resume execution based on specific sub-state
            print(f"Resuming execution phase from sub-state: {sub_state}")
            self._update_development_status("resumed", f"Resumed task from execution phase (sub-state: {sub_state})", 
                                          phase="execution")
            
            if sub_state == "APPLYING_CHANGES":
                # Resume from applying changes
                print("Resuming from applying code changes...")
                # Use pending_changes if available, otherwise use all changes
                changes_to_apply = pending_changes if pending_changes else changes
                # Track changes that were already applied
                already_applied = applied_changes if applied_changes else []
                
                if hasattr(self.coordinator, '_execute_changes_atomically'):
                    self.coordinator._execute_changes_atomically(changes_to_apply, iteration, already_applied=already_applied)
                else:
                    print("Unable to execute changes atomically: _execute_changes_atomically method not found")
            elif sub_state == "RUNNING_TESTS":
                # Resume from running tests
                print("Resuming from running tests...")
                if hasattr(self.coordinator, '_run_tests_after_changes'):
                    self.coordinator._run_tests_after_changes(changes, iteration)
                else:
                    print("Unable to run tests: _run_tests_after_changes method not found")
            elif sub_state == "ANALYZING_RESULTS":
                # Resume from analyzing test results
                print("Resuming from analyzing test results...")
                if hasattr(self.coordinator, '_analyze_test_results') and raw_test_output:
                    self.coordinator._analyze_test_results(raw_test_output, changes, iteration)
                else:
                    # If no raw test output is available or method not found, re-run tests
                    print("No test output available or method not found, re-running tests...")
                    if hasattr(self.coordinator, '_run_tests_after_changes'):
                        self.coordinator._run_tests_after_changes(changes, iteration)
                    else:
                        print("Unable to run tests: _run_tests_after_changes method not found")
            else:
                # Default: restart execution from the beginning
                print("Restarting execution phase...")
                if hasattr(self.coordinator, '_execute_changes'):
                    self.coordinator._execute_changes(changes, iteration, "Resumed execution")
                else:
                    print("Unable to execute changes: _execute_changes method not found")
    
    def _resume_pr_creation_phase(self, task_state) -> None:
        """Resume from PR creation phase with granular sub-state support.
        
        Args:
            task_state: The task state object loaded from TaskStateManager
        """
        # Extract state data
        branch_name = getattr(task_state, 'branch_name', '')
        pr_title = getattr(task_state, 'pr_title', '')
        pr_body = getattr(task_state, 'pr_body', '')
        is_created = getattr(task_state, 'is_created', False)
        
        # Get sub-state for granular resumption
        sub_state = getattr(task_state, 'sub_state', 'PREPARING')
        base_branch = getattr(task_state, 'base_branch', 'main')
        draft = getattr(task_state, 'draft', False)
        
        print(f"\nResuming PR creation for branch: {branch_name}, sub-state: {sub_state}")
        
        # If PR was already created, just notify the user
        if is_created:
            pr_url = getattr(task_state, 'pr_url', 'Unknown URL')
            print(f"PR was already created: {pr_url}")
            self._update_development_status("completed", "Task completed with PR", 
                                          phase="pr_creation")
        else:
            # Resume PR creation based on specific sub-state
            self._update_development_status("resumed", f"Resumed PR creation (sub-state: {sub_state})", 
                                          phase="pr_creation")
            
            if sub_state == "CREATING_BRANCH":
                # Resume from creating branch
                print("Resuming from creating branch...")
                if hasattr(self.coordinator, '_create_pr_branch'):
                    self.coordinator._create_pr_branch(branch_name, base_branch)
                    self.coordinator._stage_pr_changes()
                    self.coordinator._commit_pr_changes(pr_title)
                    self.coordinator._push_pr_branch(branch_name)
                    self.coordinator._submit_pr(branch_name, pr_title, pr_body, base_branch, draft)
                else:
                    print("Unable to create PR branch: required methods not found")
            elif sub_state == "COMMITTING":
                # Resume from committing changes
                print("Resuming from committing changes...")
                if hasattr(self.coordinator, '_commit_pr_changes'):
                    self.coordinator._commit_pr_changes(pr_title)
                    self.coordinator._push_pr_branch(branch_name)
                    self.coordinator._submit_pr(branch_name, pr_title, pr_body, base_branch, draft)
                else:
                    print("Unable to commit PR changes: required methods not found")
            elif sub_state == "PUSHING":
                # Resume from pushing changes
                print("Resuming from pushing branch...")
                if hasattr(self.coordinator, '_push_pr_branch'):
                    self.coordinator._push_pr_branch(branch_name)
                    self.coordinator._submit_pr(branch_name, pr_title, pr_body, base_branch, draft)
                else:
                    print("Unable to push PR branch: required methods not found")
            elif sub_state == "CREATING_API_REQUEST":
                # Resume from creating PR API request
                print("Resuming from creating PR API request...")
                if hasattr(self.coordinator, '_submit_pr'):
                    self.coordinator._submit_pr(branch_name, pr_title, pr_body, base_branch, draft)
                else:
                    print("Unable to submit PR: _submit_pr method not found")
            else:
                # Default: restart PR creation from the beginning
                print("Restarting PR creation...")
                if hasattr(self.coordinator, '_create_pr'):
                    self.coordinator._create_pr([], pr_body, branch_name, pr_title, base_branch, draft)
                else:
                    print("Unable to create PR: _create_pr method not found")
    
    def _update_development_status(self, status: str, message: str, phase: Optional[str] = None, request: Optional[str] = None) -> None:
        """Update development status in progress tracker.
        
        Args:
            status: Status string (e.g., "resumed", "completed", "failed")
            message: Status message
            phase: Optional phase name
            request: Optional request text
        """
        if not self.progress_tracker:
            return
            
        update = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if phase:
            update["phase"] = phase
            
        if request:
            update["request"] = request
            
        self.progress_tracker.update_progress(update)
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad or default logger.
        
        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad and hasattr(self.scratchpad, 'log'):
            self.scratchpad.log("TaskResumer", message, level=level)
        else:
            if level.lower() == "error":
                logging.error(message)
            elif level.lower() == "warning":
                logging.warning(message)
            else:
                logging.info(message)
