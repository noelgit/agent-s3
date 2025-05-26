"""Utilities for preparing generation context."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from .enhanced_scratchpad_manager import LogLevel
from .config import CONTEXT_WINDOW_GENERATOR


class ContextManager:
    """Manage context gathering and caching for code generation."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad
        self._context_cache: Dict[str, Dict[str, Any]] = {}
        self._context_cache_max_size = 10
        self._context_dependency_map: Dict[str, Dict[str, Any]] = {}

    def allocate_token_budget(self, total_tokens: int, attempt_num: int = 1) -> Dict[str, int]:
        """Allocate token budget for context elements."""
        task_tokens = int(total_tokens * 0.1)
        plan_tokens = int(total_tokens * 0.3)
        code_tokens = int(total_tokens * 0.5)
        tech_tokens = total_tokens - (task_tokens + plan_tokens + code_tokens)

        if attempt_num >= 2:
            code_tokens += int(total_tokens * 0.1)
            plan_tokens = max(plan_tokens - int(total_tokens * 0.05), 0)
        if attempt_num >= 3:
            code_tokens += int(total_tokens * 0.1)
            plan_tokens = max(plan_tokens - int(total_tokens * 0.05), 0)

        allocation = {
            "task": task_tokens,
            "plan": plan_tokens,
            "code_context": code_tokens,
            "tech_stack": tech_tokens,
        }
        diff = total_tokens - sum(allocation.values())
        allocation["code_context"] += diff
        return allocation

    def gather_minimal_context(
        self,
        task: str,
        plan: Any,
        tech_stack: Dict[str, Any],
        token_budgets: Dict[str, int],
    ) -> Dict[str, Any]:
        """Return minimal context for generation, handling JSON plans."""
        is_json = isinstance(plan, dict)
        context = {
            "task": task,
            "tech_stack": tech_stack,
            "code_context": {},
            "is_json_plan": is_json,
            "previous_attempts": [],
        }
        if is_json:
            context["test_plan"] = plan.get("test_plan")
            context["plan"] = json.dumps(plan.get("functional_plan", plan), indent=2)
        else:
            context["plan"] = str(plan)
        return context

    def gather_full_context(
        self,
        task: str,
        plan: Any,
        tech_stack: Dict[str, Any],
        token_budgets: Dict[str, int],
        failed_attempts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Gather full context for generation with optional summarization."""
        context = self.gather_minimal_context(task, plan, tech_stack, token_budgets)
        context["previous_attempts"] = failed_attempts or []

        if self.coordinator and hasattr(self.coordinator, "memory_manager"):
            mm = self.coordinator.memory_manager
            plan_str = context["plan"]
            budget = token_budgets.get("plan", len(str(plan_str)))
            if isinstance(plan_str, str) and mm.estimate_token_count(plan_str) > budget:
                context["plan"] = mm.summarize(plan_str, budget)
        return context

    def create_generation_prompt(self, context: Dict[str, Any]) -> str:
        """Create a generation prompt from gathered context."""
        task = context.get("task", "")
        plan = context.get("plan", "")
        prompt_sections = [f"# Task\n{task}"]
        if context.get("is_json_plan"):
            prompt_sections.append("# Structured Plan (JSON Format)")
            prompt_sections.append(str(plan))
            if context.get("test_plan") is not None:
                prompt_sections.append("# Test Plan")
                prompt_sections.append(json.dumps(context["test_plan"], indent=2))
            prompt_sections.append("# Instructions for JSON Plan Implementation")
            prompt_sections.append(
                "Follow these steps to implement the feature based on the JSON structured plan"
            )
        else:
            prompt_sections.append("# Plan")
            prompt_sections.append(str(plan))
        return "\n".join(prompt_sections)

    def prepare_file_context(
        self, file_path: str, implementation_details: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare context for a file by reading related existing files."""
        self._validate_path(file_path)
        self.scratchpad.log("ContextManager", f"Preparing context for {file_path}")

        cache_key = self._get_context_cache_key(file_path, implementation_details)
        cached_context = self._context_cache.get(cache_key)
        if cached_context and self._is_context_cache_valid(file_path, cached_context):
            self.scratchpad.log("ContextManager", f"Using cached context for {file_path}")
            return cached_context

        context: Dict[str, Any] = {}
        try:
            if hasattr(self.coordinator, "file_tool") and self.coordinator.file_tool:
                if os.path.exists(file_path):
                    existing_code = self.coordinator.file_tool.read_file(file_path)
                    context["existing_code"] = existing_code
                    self.scratchpad.log("ContextManager", f"Added existing code for {file_path} to context")
                else:
                    context["existing_code"] = ""
        except Exception as e:
            self.scratchpad.log(
                "ContextManager", f"Error reading existing file {file_path}: {e}", level=LogLevel.WARNING
            )
            context["existing_code"] = ""

        imports = set()
        for detail in implementation_details:
            if "imports" in detail:
                if isinstance(detail["imports"], list):
                    imports.update(detail["imports"])
                elif isinstance(detail["imports"], str):
                    imports.add(detail["imports"])
            if "signature" in detail:
                signature = detail.get("signature", "")
                import_matches = re.findall(r"from\s+(\S+)\s+import\s+|import\s+(\S+)", signature)
                for from_import, direct_import in import_matches:
                    if from_import:
                        imports.add(from_import)
                    if direct_import:
                        imports.add(direct_import)
        context["imports"] = list(imports)

        related_files: Dict[str, str] = {}
        dependency_paths = self._extract_imports_and_dependencies(file_path, context["imports"])

        file_dir = os.path.dirname(file_path)
        if hasattr(self.coordinator, "file_tool") and self.coordinator.file_tool:
            try:
                if os.path.exists(file_dir):
                    dir_files = [
                        os.path.join(file_dir, f)
                        for f in os.listdir(file_dir)
                        if os.path.isfile(os.path.join(file_dir, f)) and f.endswith(".py")
                    ]
                    for dep_path in dir_files[:3]:
                        if dep_path != file_path and dep_path not in dependency_paths:
                            dependency_paths.append(dep_path)
            except Exception as e:
                self.scratchpad.log(
                    "ContextManager", f"Error listing directory {file_dir}: {e}", level=LogLevel.WARNING
                )

        for dep_path in dependency_paths:
            try:
                if hasattr(self.coordinator, "file_tool") and self.coordinator.file_tool:
                    if os.path.exists(dep_path):
                        related_content = self.coordinator.file_tool.read_file(dep_path)
                        if related_content:
                            if len(related_content) > 2000:
                                related_content = related_content[:2000] + "... [truncated]"
                            related_files[dep_path] = related_content
            except Exception as e:
                self.scratchpad.log(
                    "ContextManager", f"Error reading related file {dep_path}: {e}", level=LogLevel.WARNING
                )

        context["related_files"] = related_files
        self.scratchpad.log("ContextManager", f"Added {len(related_files)} related files to context")

        functions_to_implement = [d["function"] for d in implementation_details if "function" in d]
        context["functions_to_implement"] = functions_to_implement

        file_complexity = self._estimate_file_complexity(implementation_details, file_path)
        max_tokens = self._get_model_token_capacity()
        token_budget = min(int(max_tokens * 0.75), 6000 + (file_complexity * 1000))
        prioritized_context = self._prioritize_context(context, token_budget)

        self.scratchpad.log(
            "ContextManager",
            f"Context preparation complete for {file_path} (complexity: {file_complexity:.1f}, budget: {token_budget} tokens)",
        )
        self._cache_context(file_path, prioritized_context, dependency_paths)
        return prioritized_context

    # internal helpers
    def _get_context_cache_key(self, file_path: str, details: Any) -> str:
        try:
            serialized = json.dumps(details, sort_keys=True, default=str)
        except Exception:
            serialized = str(details)
        return f"{file_path}:{hash(serialized)}"

    def _is_context_cache_valid(self, file_path: str, cached_context: Dict[str, Any]) -> bool:
        cache_key = self._get_context_cache_key(file_path, cached_context.get("functions_to_implement", []))
        dep_info = self._context_dependency_map.get(cache_key)
        if not dep_info:
            return False
        for path, mtime in dep_info.get("timestamps", {}).items():
            try:
                if os.path.exists(path) and os.path.getmtime(path) > mtime:
                    return False
            except Exception:
                return False
        return True

    def _cache_context(self, file_path: str, context: Dict[str, Any], dependencies: List[str]) -> None:
        cache_key = self._get_context_cache_key(file_path, context.get("functions_to_implement", []))
        if len(self._context_cache) >= self._context_cache_max_size:
            oldest_key = next(iter(self._context_cache))
            self._context_cache.pop(oldest_key, None)
            self._context_dependency_map.pop(oldest_key, None)
        self._context_cache[cache_key] = context
        timestamps: Dict[str, float] = {}
        for p in [file_path] + list(dependencies):
            if os.path.exists(p):
                try:
                    timestamps[p] = os.path.getmtime(p)
                except Exception:
                    pass
        self._context_dependency_map[cache_key] = {"paths": dependencies, "timestamps": timestamps}

    def _extract_imports_and_dependencies(self, file_path: str, imports: List[str]) -> List[str]:
        dep_paths: List[str] = []
        base_dir = os.path.dirname(file_path)
        for imp in imports:
            module_path = os.path.join(base_dir, imp.replace(".", os.sep) + ".py")
            if os.path.exists(module_path):
                dep_paths.append(module_path)
            else:
                alt_path = imp.replace(".", os.sep) + ".py"
                if os.path.exists(alt_path):
                    dep_paths.append(alt_path)
        return dep_paths

    def _prioritize_context(self, context: Dict[str, Any], token_budget: int) -> Dict[str, Any]:
        def approx_tokens(s: str) -> int:
            return len(s) // 4

        prioritized = {
            "existing_code": context.get("existing_code", ""),
            "related_files": dict(context.get("related_files", {})),
            "imports": context.get("imports", []),
            "functions_to_implement": context.get("functions_to_implement", []),
        }

        def total_tokens(ctx: Dict[str, Any]) -> int:
            tokens = approx_tokens(ctx.get("existing_code", ""))
            for content in ctx.get("related_files", {}).values():
                tokens += approx_tokens(content)
            return tokens

        while total_tokens(prioritized) > token_budget and prioritized["related_files"]:
            largest = max(prioritized["related_files"].items(), key=lambda x: len(x[1]))[0]
            prioritized["related_files"].pop(largest)

        if total_tokens(prioritized) > token_budget and prioritized.get("existing_code"):
            excess = total_tokens(prioritized) - token_budget
            cut_chars = excess * 4
            prioritized["existing_code"] = prioritized["existing_code"][:-cut_chars]
        return prioritized

    def _estimate_file_complexity(
        self, implementation_details: List[Dict[str, Any]], file_path: Optional[str] = None
    ) -> float:
        complexity = 1.0
        if not implementation_details:
            return complexity
        funcs = sum(1 for d in implementation_details if "function" in d)
        classes = sum(1 for d in implementation_details if "class" in d)
        imports = sum(len(d.get("imports", [])) for d in implementation_details)
        complexity += 0.2 * funcs + 0.3 * classes + 0.05 * imports
        for d in implementation_details:
            sig = d.get("signature", "")
            complexity += 0.02 * sig.count(",")
            if re.search(r"thread|async|process", sig, re.IGNORECASE):
                complexity += 0.3
        if file_path and ("tests" in file_path or os.path.basename(file_path).startswith("test_")):
            complexity += 0.3
        if file_path and hasattr(self.coordinator, "file_tool") and self.coordinator.file_tool:
            try:
                if os.path.exists(file_path):
                    existing = self.coordinator.file_tool.read_file(file_path)
                    defs = len(re.findall(r"^\s*def\s", existing, re.MULTILINE)) + len(
                        re.findall(r"^\s*class\s", existing, re.MULTILINE)
                    )
                    complexity += 0.1 * min(defs, 10)
            except Exception:
                pass
        return complexity

    def _get_model_token_capacity(self) -> int:
        return CONTEXT_WINDOW_GENERATOR

    @staticmethod
    def _validate_path(path: str) -> None:
        """Validate that the provided path stays within the workspace.

        Symlinks are resolved to their real locations to prevent bypassing the
        workspace boundary checks through link traversal.
        """

        normalized = os.path.normpath(path)
        workspace_root = os.path.realpath(os.getcwd())

        # Resolve the absolute path including any symlinks
        candidate = (
            normalized
            if os.path.isabs(normalized)
            else os.path.join(workspace_root, normalized)
        )
        resolved = os.path.realpath(candidate)

        # Ensure the resolved path is within the workspace directory
        if os.path.commonpath([workspace_root, resolved]) != workspace_root:
            raise ValueError("Invalid absolute path outside workspace")

        # Reject paths that explicitly navigate upward
        if ".." in normalized.split(os.sep):
            raise ValueError("Path traversal detected")
