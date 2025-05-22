"""
Implementation Manager for Agent-S3

Manages the implementation of tasks defined in a design plan, tracks progress,
and handles the execution of tasks sequentially.
"""

import json
import os
import logging
import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class ImplementationManager:
    """
    Manages the implementation of tasks from a design document.
    Tracks progress and handles implementation execution.
    """
    
    def __init__(self, coordinator=None):
        """
        Initialize the implementation manager.
        
        Args:
            coordinator: The coordinator instance for accessing other components
        """
        self.coordinator = coordinator
        self.router_agent = coordinator.router_agent if coordinator else None
        self.scratchpad = coordinator.scratchpad if coordinator else None
        self.progress_file = "implementation_progress.json"

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad if available."""
        if self.scratchpad and hasattr(self.scratchpad, "log"):
            self.scratchpad.log("ImplementationManager", message, level=level)
        else:
            if level.lower() == "error":
                logger.error(message)
            elif level.lower() == "warning":
                logger.warning(message)
            else:
                logger.info(message)
        
    def start_implementation(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """
        Start implementing tasks from the design document.
        
        Args:
            design_file: Path to the design file
            
        Returns:
            Dict with implementation results
        """
        self._log(f"Starting implementation from {design_file}")
        
        # Load progress tracker or create if it doesn't exist
        progress = self._load_progress_tracker()
        
        if not progress:
            self._log("No existing progress found, initializing")
            progress = self._initialize_progress_tracker(design_file)
            
        # Find the first pending task
        next_task = self._find_next_task(progress)
        
        if not next_task:
            return {"success": False, "error": "No pending tasks found in the design"}
        
        # Start implementation
        return self._implement_next_task(progress, next_task)
    
    def continue_implementation(self) -> Dict[str, Any]:
        """
        Continue implementing tasks from where we left off.
        
        Returns:
            Dict with implementation results
        """
        self._log("Continuing implementation")
        
        # Load progress tracker
        progress = self._load_progress_tracker()
        
        if not progress:
            return {"success": False, "error": "No existing implementation progress found"}
        
        # Find the next pending task
        next_task = self._find_next_task(progress)
        
        if not next_task:
            return {"success": True, "message": "All tasks are completed"}
        
        # Continue implementation
        return self._implement_next_task(progress, next_task)
    
    def _load_progress_tracker(self) -> Optional[Dict[str, Any]]:
        """
        Load the implementation progress tracker from file.
        
        Returns:
            Dict with progress data or None if file doesn't exist
        """
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self._log(f"Error loading progress tracker: {e}", level="error")
            return None
    
    def _save_progress_tracker(self, progress: Dict[str, Any]) -> bool:
        """
        Save the implementation progress tracker to file.
        
        Args:
            progress: The progress data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update last_updated timestamp
            progress["last_updated"] = datetime.datetime.now().isoformat()
            
            # Save to file
            with open(self.progress_file, 'w') as f:
                json.dump(progress, f, indent=2)
            return True
        except Exception as e:
            self._log(f"Error saving progress tracker: {e}", level="error")
            return False
    
    def _initialize_progress_tracker(self, design_file: str) -> Dict[str, Any]:
        """
        Initialize a new progress tracker from the design file.
        
        Args:
            design_file: Path to the design file
            
        Returns:
            Dict with initialized progress data
        """
        # Default structure
        progress = {
            "design_file": design_file,
            "design_objective": "",
            "created_at": datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat(),
            "tasks": []
        }
        
        try:
            # Read the design file
            with open(design_file, 'r') as f:
                design_content = f.read()
            
            # Extract design objective (first line or appropriate header)
            lines = design_content.split('\n')
            if lines and lines[0]:
                progress["design_objective"] = lines[0].strip()
            
            # Extract hierarchical tasks
            tasks = self._extract_tasks_from_design(design_content)
            progress["tasks"] = tasks
            
            # Save the initialized progress
            self._save_progress_tracker(progress)
            
            return progress
        except Exception as e:
            self._log(f"Error initializing progress tracker: {e}", level="error")
            # Return basic structure even if extraction fails
            return progress
    
    def _extract_tasks_from_design(self, design_content: str) -> List[Dict[str, Any]]:
        """
        Extract hierarchical tasks from the design document.
        
        Args:
            design_content: Content of the design file
            
        Returns:
            List of task dictionaries
        """
        tasks = []
        
        # Process each line
        for line in design_content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Try to match numbered task patterns (1., 1.1., etc.)
            import re
            task_match = re.match(r'(\d+(?:\.\d+)*)\.\s+(.+)', line)
            
            if task_match:
                task_id = task_match.group(1)
                description = task_match.group(2)
                
                # Create task entry
                task = {
                    "id": task_id,
                    "description": description,
                    "status": "pending"
                }
                tasks.append(task)
            
        return tasks
    
    def _find_next_task(self, progress: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the next pending task in the progress tracker.
        
        Args:
            progress: The progress data
            
        Returns:
            Next task dict or None if no pending tasks
        """
        for task in progress.get("tasks", []):
            if task.get("status") == "pending":
                return task
        return None
    
    def _implement_next_task(self, progress: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implement the next task and update progress.
        
        Args:
            progress: The progress data
            task: The task to implement
            
        Returns:
            Dict with implementation results
        """
        task_id = task.get("id")
        description = task.get("description")
        
        self._log(f"Implementing task {task_id}: {description}")
        
        # Update task status to in_progress
        task["status"] = "in_progress"
        task["started_at"] = datetime.datetime.now().isoformat()
        self._save_progress_tracker(progress)
        
        try:
            # Execute the implementation request
            result = self._execute_implementation_request(task)
            
            # Update task status based on result
            if result.get("success", False):
                task["status"] = "completed"
                task["completed_at"] = datetime.datetime.now().isoformat()
                self._log(f"Task {task_id} completed successfully")
            else:
                task["status"] = "failed"
                task["error"] = result.get("error", "Unknown error")
                self._log(f"Task {task_id} failed: {task['error']}", level="error")
            
            # Save updated progress
            self._save_progress_tracker(progress)
            
            # If successful, find and implement the next task
            if task["status"] == "completed":
                next_task = self._find_next_task(progress)
                if next_task:
                    self._log("Moving to next task")
                    return self._implement_next_task(progress, next_task)
            
            # Return final result
            return {
                "success": task["status"] == "completed",
                "task_id": task_id,
                "task_status": task["status"],
                "next_pending": self._find_next_task(progress)
            }
            
        except Exception as e:
            # Handle any exceptions during implementation
            task["status"] = "failed"
            task["error"] = str(e)
            self._save_progress_tracker(progress)
            
            self._log(f"Error implementing task {task_id}: {e}", level="error")
            
            return {
                "success": False,
                "error": str(e),
                "task_id": task_id,
                "task_status": "failed"
            }
    
    def _execute_implementation_request(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the implementation request for a task.
        
        Args:
            task: The task to implement
            
        Returns:
            Dict with execution results
        """
        # Prepare the request
        request = f"Implement the following task: {task['description']}"
        
        # Add task context
        context = self._get_task_context(task)
        if context:
            request += f"\n\nContext:\n{context}"
        
        self._log(f"Executing request: {request[:100]}...")
        
        # Use the router agent to execute the request
        if self.router_agent:
            result = self.router_agent.execute_request(request)
            
            # Run tests if implementation was successful
            if result.get("success", False):
                self._run_tests()
                
            return result
        else:
            return {"success": False, "error": "Router agent not available"}
    
    def _get_task_context(self, task: Dict[str, Any]) -> str:
        """
        Get context information for the task.
        
        Args:
            task: The task to get context for
            
        Returns:
            Context string
        """
        # Build context from related tasks and implementation details
        context = []
        
        # Add task hierarchy information
        task_id = task.get("id", "")
        parent_ids = self._get_parent_task_ids(task_id)
        
        if parent_ids:
            parent_tasks = self._get_tasks_by_ids(parent_ids)
            context.append("Parent tasks:")
            for parent in parent_tasks:
                context.append(f"- {parent['id']}: {parent['description']}")
        
        # Add design objective
        progress = self._load_progress_tracker()
        if progress and "design_objective" in progress:
            context.append(f"\nDesign objective: {progress['design_objective']}")
        
        return "\n".join(context)
    
    def _get_parent_task_ids(self, task_id: str) -> List[str]:
        """
        Get the IDs of parent tasks.
        
        Args:
            task_id: ID of the task
            
        Returns:
            List of parent task IDs
        """
        parent_ids = []
        parts = task_id.split('.')
        
        # Build parent IDs by taking progressively fewer parts
        for i in range(1, len(parts)):
            parent_id = '.'.join(parts[:i])
            parent_ids.append(parent_id)
        
        return parent_ids
    
    def _get_tasks_by_ids(self, task_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get tasks by their IDs.
        
        Args:
            task_ids: List of task IDs
            
        Returns:
            List of matching tasks
        """
        progress = self._load_progress_tracker()
        if not progress:
            return []
        
        matching_tasks = []
        for task in progress.get("tasks", []):
            if task.get("id") in task_ids:
                matching_tasks.append(task)
        
        return matching_tasks
    
    def _run_tests(self) -> Dict[str, Any]:
        """
        Run tests after task implementation.
        
        Returns:
            Dict with test results
        """
        self._log("Running tests after implementation")
        
        # Check if a test runner is available
        if hasattr(self.coordinator, 'test_runner_tool') and self.coordinator.test_runner_tool:
            try:
                test_result = self.coordinator.test_runner_tool.run_tests()
                return test_result
            except Exception as e:
                self._log(f"Error running tests: {e}", level="error")
                return {"success": False, "error": str(e)}
        else:
            self._log("No test runner available, skipping tests")
            return {"success": True, "message": "Skipped - no test runner available"}
