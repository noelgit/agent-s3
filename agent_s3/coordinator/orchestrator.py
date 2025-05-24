"""Workflow orchestration helpers for the Coordinator."""
from __future__ import annotations

import logging

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .registry import CoordinatorRegistry
from typing import TYPE_CHECKING
from ..pre_planner_json_enforced import (
    call_pre_planner_with_enforced_json,
    pre_planning_workflow,
)

if TYPE_CHECKING:  # pragma: no cover - used for type hints only
    from . import Coordinator


class WorkflowOrchestrator:
    """Encapsulate planning and implementation workflows."""

    def __init__(self, coordinator: "Coordinator", registry: CoordinatorRegistry) -> None:
        self.coordinator = coordinator
        self.registry = registry

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def run_task(
        self,
        task: str,
        pre_planning_input: Optional[Dict[str, Any]] = None,
        *,
        from_design: bool = False,
    ) -> None:
        """Execute the full planning and implementation workflow for a task."""
        with self.coordinator.error_handler.error_context(
            phase="run_task",
            operation="run_task",
            inputs={"request_text": task},
        ):
            try:
                plans = self._planning_workflow(task, pre_planning_input, from_design)
                if not plans:
                    return
                changes, success = self._implementation_workflow(plans)
                if success:
                    self._finalize_task(changes)
            except Exception as exc:  # pragma: no cover - safety net
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
                    "Coordinator", f"Implementation failed: {exc}", level=self.coordinator.LogLevel.ERROR
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
                    "Coordinator", f"Continuation failed: {exc}", level=self.coordinator.LogLevel.ERROR
                )
                return {"success": False, "error": str(exc)}

    def start_pre_planning_from_design(self, design_file: str = "design.txt") -> Dict[str, Any]:
        """Start pre-planning workflow based on a design file."""
        file_tool = self.registry.get_tool("file_tool")
        success, design_content = file_tool.read_file(design_file)
        if not success:
            self.coordinator.scratchpad.log(
                "Coordinator", f"Failed to read design file: {design_content}", level=self.coordinator.LogLevel.ERROR
            )
            return {"success": False, "error": design_content}

        tasks = self._extract_tasks_from_design(design_content)
        if not tasks:
            self.coordinator.scratchpad.log(
                "Coordinator", "No tasks found in design file", level=self.coordinator.LogLevel.ERROR
            )
            return {"success": False, "error": "No tasks in design file"}

        for task in tasks:
            self.run_task(task=task, from_design=True)

        return {"success": True, "tasks_started": len(tasks)}

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
        mode = self.coordinator.config.config.get("pre_planning_mode", "enforced_json")

        if mode == "off":
            self.coordinator.scratchpad.log("Coordinator", "Pre-planning disabled")
            return []

        if pre_planning_input is None:
            if mode == "enforced_json":
                success, pre_plan = call_pre_planner_with_enforced_json(self.coordinator.router_agent, task)
            else:
                success, pre_plan = pre_planning_workflow(
                    self.coordinator.router_agent,
                    task,
                    max_attempts=2,
                )
            if not success:
                self.coordinator.scratchpad.log("Coordinator", "Pre-planning failed", level=self.coordinator.LogLevel.ERROR)
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
                level=self.coordinator.LogLevel.ERROR,
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

        self.coordinator.progress_tracker.update_progress({"phase": "feature_group_processing", "status": "completed"})
        return plans

    def _implementation_workflow(self, plans: List[Dict[str, Any]]) -> Tuple[Dict[str, str], bool]:
        """Run the implementation workflow for approved plans."""
        all_changes: Dict[str, str] = {}
        git_tool = self.registry.get_tool("git_tool")
        overall_success = False
        for plan in plans:
            stash_created = False
            if git_tool:
                rc, _ = git_tool.run_git_command(
                    "stash push --keep-index --include-untracked -m 'agent-s3-temp'"
                )
                stash_created = rc == 0

            changes = self.coordinator.code_generator.generate_code(plan, tech_stack=self.coordinator.tech_stack)

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

            self.coordinator.debugging_manager.handle_error(
                error_message=f"Validation step '{validation.get('step')}' failed",
                traceback_text=validation.get("output", ""),
                metadata={"plan": plan, "validation_step": validation.get("step")},
            )

            if stash_created and git_tool:
                git_tool.run_git_command("stash pop --index")

        return all_changes, overall_success

    # ------------------------------------------------------------------
    # Supporting helpers
    # ------------------------------------------------------------------
    def _apply_changes_and_manage_dependencies(self, changes: Dict[str, str]) -> bool:
        """Apply generated code changes and manage dependencies."""
        try:
            file_tool = self.registry.get_tool("file_tool")
            for path, content in changes.items():
                if not file_tool:
                    raise RuntimeError("File tool not initialized")
                file_tool.write_file(path, content)
            return True
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log("Coordinator", f"Failed applying changes: {exc}", level=self.coordinator.LogLevel.ERROR)
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

            lint_exit, lint_output = self.coordinator.bash_tool.run_command("flake8 .", timeout=120)
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
                    level=self.coordinator.LogLevel.ERROR,
                )
                threshold = 70.0
            if mutation_score is not None and mutation_score < threshold:
                results.update({"success": False, "step": "mutation"})
                return results
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log("Coordinator", f"Validation error: {exc}", level=self.coordinator.LogLevel.ERROR)
            results.update({"success": False, "step": "unknown_error"})
            return results

        return results

    def _run_tests(self) -> Dict[str, Any]:
        """Run project tests using the configured test runner."""
        try:
            self.coordinator.env_tool.activate_virtual_env()
            self.coordinator.test_runner_tool.detect_runner()
            success, output = self.coordinator.test_runner_tool.run_tests()
            coverage = 0.0
            if success and hasattr(self.coordinator.test_runner_tool, "parse_coverage_report"):
                coverage = self.coordinator.test_runner_tool.parse_coverage_report()
            return {"success": success, "output": output, "coverage": coverage}
        except Exception as exc:  # pragma: no cover - safety net
            self.coordinator.scratchpad.log("Coordinator", f"Test execution failed: {exc}", level=self.coordinator.LogLevel.ERROR)
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
