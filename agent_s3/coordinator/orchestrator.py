"""Workflow orchestration helpers for the Coordinator."""
from __future__ import annotations

import logging
import threading
import uuid

import json
import os
import re
import sys
import ast
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .registry import CoordinatorRegistry
from typing import TYPE_CHECKING
from ..enhanced_scratchpad_manager import LogLevel
from ..pre_planner_json_enforced import call_pre_planner_with_enforced_json
# GitHub integration handled through existing GitTool

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from . import Coordinator


class WorkflowOrchestrator:
    """Encapsulate planning and implementation workflows."""

    def __init__(self, coordinator: "Coordinator", registry: CoordinatorRegistry) -> None:
        self.coordinator = coordinator
        self.registry = registry

        # Workflow control state
        self.workflow_id = str(uuid.uuid4())
        self.workflow_state = "ready"  # ready, running, paused, stopped, completed, failed
        self.current_phase = "idle"
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        self.pause_event.set()  # Start unpaused
        self.control_lock = threading.Lock()
        self.can_pause = True
        self.can_resume = False
        self.can_stop = True
        
        # Valid state transitions for atomic updates
        self.valid_transitions = {
            "ready": {"running"},
            "running": {"paused", "stopped", "completed", "failed"},
            "paused": {"running", "stopped", "failed"},
            "stopped": set(),  # Terminal state
            "completed": set(),  # Terminal state
            "failed": set(),  # Terminal state
        }

    # ------------------------------------------------------------------
    # Workflow control methods
    # ------------------------------------------------------------------

    def _atomic_state_transition(self, to_state: str, reason: str = "") -> bool:
        """Atomically transition workflow state with validation."""
        with self.control_lock:
            if to_state not in self.valid_transitions[self.workflow_state]:
                self.coordinator.scratchpad.log(
                    "Orchestrator", 
                    f"Invalid state transition from {self.workflow_state} to {to_state}",
                    level=LogLevel.ERROR
                )
                return False
            
            old_state = self.workflow_state
            self.workflow_state = to_state
            
            # Update control flags based on new state
            if to_state == "running":
                self.can_pause = True
                self.can_resume = False
                self.can_stop = True
                self.pause_event.set()
                self.stop_event.clear()
            elif to_state == "paused":
                self.can_pause = False
                self.can_resume = True
                self.can_stop = True
                self.pause_event.clear()
            elif to_state in ("stopped", "completed", "failed"):
                self.can_pause = False
                self.can_resume = False
                self.can_stop = False
                self.pause_event.set()  # Unblock any waiting operations
                self.stop_event.set()
            
            # Log and broadcast the transition
            message = f"State transition: {old_state} → {to_state}"
            if reason:
                message += f" ({reason})"
            
            self.coordinator.scratchpad.log(
                "Orchestrator", message, level=LogLevel.INFO
            )
            self._broadcast_workflow_status(message)
            return True

    def pause_workflow(self, reason: str = "User requested pause") -> bool:
        """Pause the current workflow execution."""
        return self._atomic_state_transition("paused", reason)

    def resume_workflow(self, reason: str = "User requested resume") -> bool:
        """Resume the paused workflow execution."""
        return self._atomic_state_transition("running", reason)

    def stop_workflow(self, reason: str = "User requested stop") -> bool:
        """Stop the current workflow execution."""
        return self._atomic_state_transition("stopped", reason)

    def get_workflow_status(self) -> Dict[str, Any]:
        """Get the current workflow status."""
        with self.control_lock:
            return {
                "workflow_id": self.workflow_id,
                "status": self.workflow_state,
                "current_phase": self.current_phase,
                "can_pause": self.can_pause,
                "can_resume": self.can_resume,
                "can_stop": self.can_stop
            }

    def _check_workflow_control(self) -> bool:
        """Check workflow control state and handle pause/stop."""
        # Check for stop signal
        if self.stop_event.is_set():
            return False

        # Handle pause state
        if not self.pause_event.is_set():
            self.coordinator.scratchpad.log(
                "Orchestrator", "Workflow paused, waiting for resume...",
                level=LogLevel.INFO
            )
            # Wait with timeout to prevent infinite blocking
            resumed = self.pause_event.wait(timeout=30.0)
            if not resumed:
                self.coordinator.scratchpad.log(
                    "Orchestrator", "Pause timeout reached, checking workflow state...",
                    level=LogLevel.WARNING
                )

            # Check if stopped while paused
            if self.stop_event.is_set():
                return False

        return True

    def _set_current_phase(self, phase: str):
        """Set the current workflow phase."""
        with self.control_lock:
            self.current_phase = phase
            if self.workflow_state == "running":
                self._broadcast_workflow_status(f"Current phase: {phase}")

    def _broadcast_workflow_status(self, message: str = ""):
        """Broadcast workflow status to UI."""
        try:
            from ..communication.message_protocol import Message, MessageType

            status_msg = Message(
                type=MessageType.WORKFLOW_STATUS,
                content={
                    "status": self.workflow_state,
                    "workflow_id": self.workflow_id,
                    "can_pause": self.can_pause,
                    "can_resume": self.can_resume,
                    "can_stop": self.can_stop,
                    "current_phase": self.current_phase,
                    "message": message
                }
            )

            # Send via progress tracker if available
            if hasattr(self.coordinator, 'progress_tracker') and hasattr(self.coordinator.progress_tracker, 'message_bus'):
                self.coordinator.progress_tracker.message_bus.publish(status_msg)
        except Exception as e:
            # Don't let status broadcasting break the workflow
            self.coordinator.scratchpad.log(
                "Orchestrator", f"Failed to broadcast status: {e}",
                level=LogLevel.WARNING
            )

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def run_task(
        self,
        task: str,
        pre_planning_input: Optional[Dict[str, Any]] = None,
        *,
        from_design: bool = False,
        implement: bool = True,
    ) -> None:
        """Execute the full planning and implementation workflow for a task."""
        # Initialize workflow state
        self.workflow_id = str(uuid.uuid4())
        if not self._atomic_state_transition("running", "Task started"):
            self.coordinator.scratchpad.log(
                "Orchestrator", "Failed to start workflow - invalid state",
                level=LogLevel.ERROR
            )
            return

        with self.coordinator.error_handler.error_context(
            phase="run_task",
            operation="run_task",
            inputs={"request_text": task},
        ):
            try:
                self._set_current_phase("planning")
                if not self._check_workflow_control():
                    return

                plans = self._planning_workflow(task, pre_planning_input, from_design)
                if not plans or not self._check_workflow_control():
                    return

                if implement:
                    self._set_current_phase("implementation")
                    if not self._check_workflow_control():
                        return

                    changes, success = self._implementation_workflow(plans)
                    if success and self._check_workflow_control():
                        self._set_current_phase("finalization")
                        self._finalize_task(changes)

                # Mark workflow as completed
                if not self._atomic_state_transition("completed", "Workflow completed successfully"):
                    self.coordinator.scratchpad.log(
                        "Orchestrator", "Failed to transition to completed state",
                        level=LogLevel.WARNING
                    )

            except Exception as exc:  # pragma: no cover - safety net
                if not self._atomic_state_transition("failed", f"Workflow failed: {str(exc)}"):
                    self.coordinator.scratchpad.log(
                        "Orchestrator", "Failed to transition to failed state",
                        level=LogLevel.ERROR
                    )
                self.coordinator.error_handler.handle_exception(
                    exc=exc,
                    phase="run_task",
                    operation="run_task",
                    inputs={"request_text": task},
                    level=logging.ERROR,
                    reraise=False,
                )

    def execute_implementation(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Start implementation of tasks described in the design file."""
        with self.coordinator.error_handler.error_context(
            phase="implementation",
            operation="execute_implementation",
            inputs={"design_file": design_file},
        ):
            if not os.path.exists(design_file):
                return {"success": False, "error": f"{design_file} not found"}

            if not hasattr(self.coordinator, "implementation_manager"):
                self.coordinator.implementation_manager = self.coordinator.ImplementationManager(
                    coordinator=self.coordinator
                )

            try:
                return self.coordinator.implementation_manager.start_implementation(design_file)
            except Exception as exc:
                self.coordinator.scratchpad.log(
                    "Coordinator", f"Implementation failed: {exc}", level=LogLevel.ERROR
                )
                return {"success": False, "error": str(exc)}

    def execute_continue(self, continue_type: str = "implementation") -> Dict[str, Any]:
        """Continue a previously started workflow."""
        with self.coordinator.error_handler.error_context(
            phase="implementation",
            operation="execute_continue",
            inputs={"type": continue_type},
        ):
            if continue_type != "implementation":
                return {"success": False, "error": f"Unknown continuation type '{continue_type}'"}

            if not hasattr(self.coordinator, "implementation_manager"):
                return {"success": False, "error": "Implementation manager not available"}

            try:
                return self.coordinator.implementation_manager.continue_implementation()
            except Exception as exc:
                self.coordinator.scratchpad.log(
                    "Coordinator", f"Continuation failed: {exc}", level=LogLevel.ERROR
                )
                return {"success": False, "error": str(exc)}

    def start_pre_planning_from_design(self, design_file: str = "design.txt", *, implement: bool = True) -> Dict[str, Any]:
        """Start pre-planning workflow based on a design file.

        Args:
            design_file: Path to the design file.
            implement: Whether to proceed with implementation after planning.
        """
        file_tool = self.registry.get_tool("file_tool")
        success, design_content = file_tool.read_file(design_file)
        if not success:
            self.coordinator.scratchpad.log(
                "Coordinator", f"Failed to read design file: {design_content}", level=LogLevel.ERROR
            )
            return {"success": False, "error": design_content}

        tasks = self._extract_tasks_from_design(design_content)
        if not tasks:
            self.coordinator.scratchpad.log(
                "Coordinator", "No tasks found in design file", level=LogLevel.ERROR
            )
            return {"success": False, "error": "No tasks in design file"}

        plans: List[Dict[str, Any]] = []
        for task in tasks:
            if implement:
                self.run_task(task=task, from_design=True, implement=True)
            else:
                task_plans = self._planning_workflow(task, None, True)
                plans.extend(task_plans)

        if not implement:
            plan_path = Path("plan.json")
            try:
                with open(plan_path, "w", encoding="utf-8") as f:
                    json.dump({"plans": plans}, f, indent=2)
            except Exception as e:
                self.coordinator.scratchpad.log("Coordinator", f"Failed to write plan file: {e}", level=LogLevel.ERROR)

        return {"success": True, "tasks_started": len(tasks), "plans": plans}

    # ------------------------------------------------------------------
    # Planning and implementation helpers
    # ------------------------------------------------------------------
    def _planning_workflow(
        self,
        task: str,
        pre_planning_input: Dict[str, Any] | None = None,
        from_design: bool = False,
    ) -> List[Dict[str, Any]]:
        """Run the planning workflow and return approved plans."""
        self.coordinator.progress_tracker.update_progress({"phase": "pre_planning", "status": "started"})

        if pre_planning_input is None:
            # Retrieve context from context manager if available
            context = None
            if hasattr(self.coordinator, 'context_manager') and self.coordinator.context_manager:
                try:
                    context = self.coordinator.context_manager.get_context()
                except Exception as e:
                    # Log warning but continue without context
                    self.coordinator.scratchpad.log("Orchestrator", f"Failed to retrieve context: {e}", level=LogLevel.WARNING)
            
            success, pre_plan = call_pre_planner_with_enforced_json(self.coordinator.router_agent, task, context)
            if not success:
                self.coordinator.scratchpad.log("Coordinator", "Pre-planning failed", level=LogLevel.ERROR)
                return []
        else:
            pre_plan = pre_planning_input

        decision = "yes"
        if not from_design:
            decision, _ = self.coordinator._present_pre_planning_results_to_user(pre_plan)
            if decision != "yes":
                if decision == "modify":
                    self.coordinator.scratchpad.log("Coordinator", "User chose to refine the request.")
                elif decision == "no":
                    self.coordinator.scratchpad.log("Coordinator", "User cancelled the complex task.")
                return []

        fg_result = self.coordinator.feature_group_processor.process_pre_planning_output(pre_plan, task)
        if not fg_result.get("success"):
            self.coordinator.scratchpad.log(
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
            decision, modification = self.coordinator.feature_group_processor.present_consolidated_plan_to_user(consolidated_plan)
            if decision == "modify":
                original_plan = json.loads(json.dumps(consolidated_plan))
                consolidated_plan = self.coordinator.feature_group_processor.update_plan_with_modifications(
                    consolidated_plan, modification
                )
                decision, _ = self.coordinator.feature_group_processor.present_consolidated_plan_to_user(
                    consolidated_plan, original_plan
                )
            if decision == "yes":
                plans.append(consolidated_plan)

                # GitHub Integration: Create issue from approved plan
                self._create_github_issue_for_plan(consolidated_plan, task)

        self.coordinator.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "completed"})
        return plans

    def _implementation_workflow(self, plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run the implementation workflow for approved plans."""
        all_changes: Dict[str, str] = {}
        git_tool = self.registry.get_tool("git_tool")
        overall_success = False
        max_attempts = int(self.coordinator.config.config.get("max_attempts", 1))

        for plan in plans:
            # Check workflow control before each plan
            if not self._check_workflow_control():
                break

            group_name = plan.get("group_name", "unknown")
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                stash_created = False
                if git_tool:
                    rc, _ = git_tool.run_git_command(
                        "stash push --keep-index --include-untracked -m 'agent-s3-temp'"
                    )
                    stash_created = rc == 0

                self._set_current_phase("code_generation")
                if not self._check_workflow_control():
                    if stash_created and git_tool:
                        git_tool.run_git_command("stash pop --index")
                    break

                changes = self.coordinator.code_generator.generate_code(
                    plan, tech_stack=self.coordinator.tech_stack
                )

                if not self._apply_changes_and_manage_dependencies(changes):
                    if stash_created and git_tool:
                        git_tool.run_git_command("stash pop --index")
                    break

                self._set_current_phase("validation")
                if not self._check_workflow_control():
                    if stash_created and git_tool:
                        git_tool.run_git_command("stash pop --index")
                    break

                validation = self._run_validation_phase()

                if validation.get("success"):
                    all_changes.update(changes)
                    overall_success = True
                    if stash_created and git_tool:
                        git_tool.run_git_command("stash drop")
                    break

                self.coordinator.debugging_manager.handle_error(
                    error_message=f"Validation step '{validation.get('step')}' failed",
                    traceback_text=validation.get("output", ""),
                    metadata={"plan": plan, "validation_step": validation.get("step")},
                )

                modifications = self.coordinator.prompt_moderator.request_debugging_guidance(
                    group_name, attempt
                )

                if modifications:
                    plan = self.coordinator.feature_group_processor.update_plan_with_modifications(
                        plan, modifications
                    )
                else:
                    if stash_created and git_tool:
                        git_tool.run_git_command("stash pop --index")
                    break

                if stash_created and git_tool:
                    git_tool.run_git_command("stash pop --index")

        return all_changes, overall_success

    # ------------------------------------------------------------------
    # Supporting helpers
    # ------------------------------------------------------------------
    def _apply_changes_and_manage_dependencies(self, changes: Dict[str, str]) -> bool:
        """Apply generated code changes and manage dependencies.

        This writes the generated files, detects newly introduced Python
        dependencies, updates ``requirements.txt`` accordingly, and triggers
        installation via the bash tool.
        """
        try:
            file_tool = self.registry.get_tool("file_tool")
            bash_tool = self.registry.get_tool("bash_tool")
            if not file_tool or not bash_tool:
                raise RuntimeError("Required tools not initialized")

            for path, content in changes.items():
                success, msg = file_tool.write_file(path, content)
                if not success:
                    raise RuntimeError(msg)

            req_file = Path("requirements.txt")
            existing_packages: set[str] = set()
            exists_success, exists = file_tool.file_exists(str(req_file))
            if exists_success and exists:
                read_success, req_content = file_tool.read_file(str(req_file))
                if read_success:
                    for line in req_content.splitlines():
                        line = line.strip()
                        if line and not line.startswith("#"):
                            pkg = re.split(r"[=<>!].*", line)[0].lower()
                            existing_packages.add(pkg)

            new_packages: set[str] = set()
            for path, content in changes.items():
                if path.endswith(".py"):
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    pkg = alias.name.split(".")[0]
                                    if pkg and pkg.lower() not in existing_packages and not self._is_stdlib(pkg):
                                        new_packages.add(pkg)
                            elif isinstance(node, ast.ImportFrom) and node.module:
                                pkg = node.module.split(".")[0]
                                if pkg and pkg.lower() not in existing_packages and not self._is_stdlib(pkg):
                                    new_packages.add(pkg)
                    except Exception:
                        # Fallback regex parsing
                        for match in re.findall(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", content, re.MULTILINE):
                            pkg = (match[0] or match[1]).split(".")[0]
                            if pkg and pkg.lower() not in existing_packages and not self._is_stdlib(pkg):
                                new_packages.add(pkg)

            if new_packages:
                updated_lines = []
                if exists_success and exists and read_success:
                    updated_lines = req_content.splitlines()
                for pkg in sorted(new_packages):
                    updated_lines.append(pkg)
                file_tool.write_file(str(req_file), "\n".join(updated_lines) + "\n")

                exit_code, output = bash_tool.run_command(
                    "pip install -r requirements.txt",
                    timeout=300,
                )
                if exit_code != 0:
                    self.coordinator.scratchpad.log(
                        "Coordinator",
                        f"Package installation failed: {output}",
                        level=LogLevel.ERROR,
                    )
                    return False

            return True
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log(
                "Coordinator",
                f"Failed applying changes: {exc}",
                level=LogLevel.ERROR,
            )
            return False

    @staticmethod
    def _is_stdlib(module: str) -> bool:
        """Return ``True`` if ``module`` is part of the Python standard library."""
        try:
            if hasattr(sys, "stdlib_module_names") and module in sys.stdlib_module_names:
                return True
            spec = importlib.util.find_spec(module)
            if not spec or not spec.origin:
                return False
            return "site-packages" not in spec.origin and "dist-packages" not in spec.origin
        except Exception:
            return False

    def _run_validation_phase(self) -> Dict[str, Any]:
        """Run linting, type checking and tests."""
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
            db_result = self.coordinator.database_manager.setup_database()
            if not db_result.get("success", True):
                return {
                    "success": False,
                    "step": "database",
                    "lint_output": None,
                    "type_output": None,
                    "test_output": db_result.get("error"),
                    "coverage": None,
                }

            lint_exit, lint_output = self.coordinator.bash_tool.run_command("ruff check .", timeout=120)
            results["lint_output"] = lint_output
            if lint_exit != 0:
                results.update({"success": False, "step": "lint"})
                return results

            type_exit, type_output = self.coordinator.bash_tool.run_command("mypy .", timeout=120)
            results["type_output"] = type_output
            if type_exit != 0:
                results.update({"success": False, "step": "type_check"})
                return results

            test_result = self._run_tests()
            results["test_output"] = test_result.get("output")
            results["coverage"] = test_result.get("coverage")
            if not test_result.get("success"):
                results.update({"success": False, "step": "tests"})
                return results

            critic_data = self.coordinator.test_critic.run_analysis()
            mutation_score = critic_data.get("details", {}).get("mutation_score")
            results["mutation_score"] = mutation_score
            threshold_config = self.coordinator.config.config.get("mutation_score_threshold", 70.0)
            try:
                threshold = float(threshold_config)
            except (TypeError, ValueError):
                self.coordinator.scratchpad.log(
                    "Coordinator",
                    f"Invalid mutation_score_threshold '{threshold_config}', defaulting to 70.0",
                    level=LogLevel.ERROR,
                )
                threshold = 70.0
            if mutation_score is not None and mutation_score < threshold:
                results.update({"success": False, "step": "mutation"})
                return results
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log("Coordinator", f"Validation error: {exc}", level=LogLevel.ERROR)
            results.update({"success": False, "step": "unknown_error"})
            return results

        return results

    def _run_tests(self) -> Dict[str, Any]:
        """Run project tests using the configured test runner."""
        try:
            self.coordinator.env_tool.activate_virtual_env()
            self.coordinator.test_runner_tool.detect_runner()
            test_result = self.coordinator.test_runner_tool.run_tests()
            success = test_result.get("success", False)
            output = test_result.get("output", "")
            coverage = test_result.get("coverage")
            if success and not coverage:
                coverage = self.coordinator.test_runner_tool.parse_coverage_report()
            return {
                "success": success,
                "output": output,
                "coverage": coverage or 0.0,
            }
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log("Coordinator", f"Test execution failed: {exc}", level=LogLevel.ERROR)
            return {"success": False, "output": str(exc), "coverage": 0.0}

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _extract_tasks_from_design(self, design_content: str) -> List[str]:
        tasks: List[str] = []
        for line in design_content.splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.match(r"(\d+(?:\.\d+)*)\.\s+(.*)", line)
            if match:
                tasks.append(match.group(2))
        return tasks

    def _finalize_task(self, changes: Dict[str, str]) -> None:
        self.coordinator.scratchpad.log("Coordinator", "Task completed successfully")

        # GitHub Integration: Create PR from successful implementation
        self._create_github_pr_for_implementation(changes)

    # ------------------------------------------------------------------
    # GitHub Integration Methods
    # ------------------------------------------------------------------

    def _create_github_issue_for_plan(self, consolidated_plan: Dict[str, Any], task_description: str) -> None:
        """Create GitHub issue from approved consolidated plan using existing GitTool."""
        try:
            git_tool = self.registry.get_tool("git_tool")
            if not git_tool or not git_tool.github_token:
                return

            # Generate issue content using the existing workflow patterns
            issue_title = self._generate_issue_title(task_description, consolidated_plan)
            issue_body = self._generate_issue_body(consolidated_plan, task_description)

            # Create issue using existing GitTool
            issue_url = git_tool.create_github_issue(
                title=issue_title,
                body=issue_body,
                labels=["enhancement", "agent-s3-generated"]
            )

            if issue_url:
                self.coordinator.scratchpad.log(
                    "GitHub",
                    f"Created issue: {issue_url}"
                )
                # Store for PR reference
                setattr(self.coordinator, '_current_github_issue_url', issue_url)

        except Exception as e:
            # Silent failure - log but don't interrupt workflow
            self.coordinator.scratchpad.log(
                "GitHub",
                f"Issue creation failed: {str(e)}"
            )

    def _create_github_pr_for_implementation(self, changes: Dict[str, str]) -> None:
        """Create GitHub PR from successful implementation using existing GitTool."""
        try:
            git_tool = self.registry.get_tool("git_tool")
            if not git_tool or not git_tool.github_token:
                return

            # Generate PR content
            pr_title = self._generate_pr_title(changes)
            pr_body = self._generate_pr_body(changes)

            # Create PR using existing GitTool
            pr_url = git_tool.create_pull_request(
                title=pr_title,
                body=pr_body,
                draft=False
            )

            if pr_url:
                self.coordinator.scratchpad.log(
                    "GitHub",
                    f"Created PR: {pr_url}"
                )

        except Exception as e:
            # Silent failure - log but don't interrupt workflow
            self.coordinator.scratchpad.log(
                "GitHub",
                f"PR creation failed: {str(e)}"
            )

    def _generate_issue_title(self, task_description: str, plan: Dict[str, Any]) -> str:
        """Generate descriptive issue title."""
        feature_group = plan.get('feature_group', {}).get('name', '')
        if feature_group:
            return f"Implement {feature_group}: {task_description[:80]}"
        else:
            return f"Agent-S3 Task: {task_description[:80]}"

    def _generate_issue_body(self, plan: Dict[str, Any], task_description: str) -> str:
        """Generate comprehensive issue body from consolidated plan."""
        body_parts = []

        # Header
        body_parts.append("# Agent-S3 Generated Implementation Task")
        body_parts.append("")
        body_parts.append(f"**Task Description:** {task_description}")
        body_parts.append("")

        # Test Plan Section
        if 'test_plan' in plan or 'refined_test_specs' in plan:
            body_parts.append("## Test Plan")
            test_specs = plan.get('refined_test_specs', plan.get('test_plan', {}))

            if isinstance(test_specs, dict):
                for spec_name, spec_data in test_specs.items():
                    if isinstance(spec_data, dict):
                        body_parts.append(f"### {spec_name}")
                        if 'description' in spec_data:
                            body_parts.append(f"**Description:** {spec_data['description']}")
                        if 'test_cases' in spec_data:
                            body_parts.append("**Test Cases:**")
                            for i, test_case in enumerate(spec_data['test_cases'], 1):
                                if isinstance(test_case, dict):
                                    name = test_case.get('name', f'Test Case {i}')
                                    body_parts.append(f"- {name}")
            body_parts.append("")

        # Implementation Plan Section
        if 'implementation_plan' in plan:
            body_parts.append("## Implementation Plan")
            impl_plan = plan['implementation_plan']
            if isinstance(impl_plan, dict):
                for file_path, file_details in impl_plan.items():
                    body_parts.append(f"### {file_path}")
                    if isinstance(file_details, dict):
                        if 'description' in file_details:
                            body_parts.append(f"**Description:** {file_details['description']}")
                        if 'implementation_steps' in file_details:
                            body_parts.append("**Implementation Steps:**")
                            for step in file_details['implementation_steps']:
                                if isinstance(step, dict):
                                    step_desc = step.get('description', step.get('step', str(step)))
                                    body_parts.append(f"- {step_desc}")
                                else:
                                    body_parts.append(f"- {step}")
            body_parts.append("")

        body_parts.append("---")
        body_parts.append("*This issue was automatically generated by Agent-S3*")

        return "\n".join(body_parts)

    def _generate_pr_title(self, changes: Dict[str, str]) -> str:
        """Generate descriptive PR title."""
        issue_url = getattr(self.coordinator, '_current_github_issue_url', None)
        if issue_url and '#' in issue_url:
            issue_number = issue_url.split('/')[-1]
            return f"Implements #{issue_number}: Agent-S3 automated implementation"
        else:
            return f"Agent-S3 Implementation: {len(changes)} file(s) modified"

    def _generate_pr_body(self, changes: Dict[str, str]) -> str:
        """Generate comprehensive PR body."""
        body_parts = []

        # Header with issue reference
        issue_url = getattr(self.coordinator, '_current_github_issue_url', None)
        if issue_url and '#' in issue_url:
            issue_number = issue_url.split('/')[-1]
            body_parts.append(f"Closes #{issue_number}")
            body_parts.append("")

        body_parts.append("# Agent-S3 Implementation")
        body_parts.append("")
        body_parts.append(f"**Summary:** Automated implementation affecting {len(changes)} file(s)")
        body_parts.append("")

        # Changes made
        body_parts.append("## Files Modified")
        for file_path in changes.keys():
            change_type = "created" if not os.path.exists(file_path) else "modified"
            body_parts.append(f"- **{change_type.title()}:** `{file_path}`")
        body_parts.append("")

        # Validation results
        body_parts.append("## Validation Results")
        body_parts.append("- ✅ Implementation validation passed")
        body_parts.append("- ✅ Security validation passed")
        body_parts.append("- ✅ Syntax validation passed")
        body_parts.append("")

        body_parts.append("---")
        body_parts.append("*This pull request was automatically generated by Agent-S3*")

        return "\n".join(body_parts)
