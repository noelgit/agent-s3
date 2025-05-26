"""Utilities to build hierarchical code context for debugging."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict


class ContextHierarchyManager:
    """Manage context retrieval and summarization for errors."""

    def __init__(self, file_tool=None, code_analysis_tool=None, memory_manager=None, context_manager=None, scratchpad=None) -> None:
        self.file_tool = file_tool
        self.code_analysis_tool = code_analysis_tool
        self.memory_manager = memory_manager
        self.context_manager = context_manager
        self.scratchpad = scratchpad

    def gather_context_using_context_manager(self, context: Dict[str, Any], error_info: Dict[str, Any], max_token_count: int) -> Dict[str, Any]:
        file_paths = error_info.get("file_paths", [])
        if not file_paths:
            return context

        primary_file = file_paths[0] if file_paths else None
        try:
            if primary_file and hasattr(self.context_manager, '_refine_current_context'):
                self.context_manager._refine_current_context(file_paths, max_tokens=max_token_count)
                context_files = self.context_manager.get_current_context_snapshot().get("files", {})
                context["relevant_code"] = context_files
            elif hasattr(self.context_manager, 'get_context'):
                cm_context = self.context_manager.get_context()
                if cm_context and "files" in cm_context:
                    relevant_files = {path: cm_context["files"][path] for path in file_paths if path in cm_context["files"]}
                    if not relevant_files and hasattr(self.context_manager, 'read_file'):
                        for file_path in file_paths:
                            try:
                                content = self.context_manager.read_file(file_path)
                                if content:
                                    relevant_files[file_path] = content
                            except Exception as exc:  # pragma: no cover - log only
                                self._log(f"Error reading file {file_path} via context manager: {exc}", level="error")
                    context["relevant_code"] = relevant_files
            else:
                token_budgets = self.allocate_token_budgets(max_token_count, error_info, len(file_paths))
                context["relevant_code"] = self.add_code_context(error_info, token_budgets)
        except Exception as exc:  # pragma: no cover - log only
            self._log(f"Error using context manager: {exc}", level="error")
            token_budgets = self.allocate_token_budgets(max_token_count, error_info, len(file_paths))
            context["relevant_code"] = self.add_code_context(error_info, token_budgets)
        return context

    def _log(self, message: str, level: str = "info") -> None:
        if self.scratchpad and hasattr(self.scratchpad, 'log'):
            self.scratchpad.log("ErrorContextManager", message, level=level)
        else:
            logger = logging.getLogger(__name__)
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)

    def get_context_using_context_manager(self, file_path: str, line_number: int, error_message: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        try:
            if hasattr(self.context_manager, 'read_file'):
                content = self.context_manager.read_file(file_path)
            elif hasattr(self.context_manager, 'get_file_content'):
                content = self.context_manager.get_file_content(file_path)
            else:
                content = self.file_tool.read_file(file_path) if self.file_tool else ""
            if content:
                lines = content.split('\n')
                start_line = max(0, line_number - 5)
                end_line = min(len(lines), line_number + 5)
                snippet = []
                for i in range(start_line, end_line):
                    prefix = "-> " if i == line_number - 1 else "   "
                    snippet.append(f"{i+1}: {prefix}{lines[i]}")
                context["code_snippet"] = "\n".join(snippet)
            if hasattr(self.context_manager, 'get_context'):
                cm_context = self.context_manager.get_context()
                if cm_context and "variables" in cm_context:
                    context["variables"] = cm_context["variables"]
            if hasattr(self.context_manager, 'get_file_dependencies'):
                deps = self.context_manager.get_file_dependencies(file_path)
                if deps:
                    context["dependencies"] = deps
            if hasattr(self.context_manager, 'get_dependent_files'):
                dependents = self.context_manager.get_dependent_files(file_path)
                if dependents:
                    context["dependents"] = dependents
        except Exception as exc:  # pragma: no cover - log only
            self._log(f"Error getting context using context manager: {exc}", level="error")
        return context

    def get_context_using_direct_access(self, file_path: str, line_number: int, error_message: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {}
        try:
            if self.file_tool:
                content = self.file_tool.read_file(file_path)
                if content:
                    lines = content.split('\n')
                    start_line = max(0, line_number - 5)
                    end_line = min(len(lines), line_number + 5)
                    snippet = []
                    for i in range(start_line, end_line):
                        prefix = "-> " if i == line_number - 1 else "   "
                        snippet.append(f"{i+1}: {prefix}{lines[i]}")
                    context["code_snippet"] = "\n".join(snippet)
            if self.code_analysis_tool and hasattr(self.code_analysis_tool, 'get_file_imports'):
                try:
                    imports = self.code_analysis_tool.get_file_imports(file_path)
                    if imports:
                        context["imports"] = imports
                except Exception as exc:  # pragma: no cover - log only
                    self._log(f"Error getting imports: {exc}", level="warning")
        except Exception as exc:  # pragma: no cover - log only
            self._log(f"Error getting context using direct access: {exc}", level="error")
        return context

    def allocate_token_budgets(self, max_token_count: int, error_info: Dict[str, Any], file_count: int) -> Dict[str, int]:
        budgets = {
            "error_message": int(max_token_count * 0.05),
            "stack_trace": int(max_token_count * 0.10),
            "error_location": int(max_token_count * 0.25),
            "related_files": int(max_token_count * 0.50),
            "similar_pattern": int(max_token_count * 0.10),
        }
        if error_info.get("file_paths") and error_info.get("line_numbers"):
            budgets["error_location"] = int(max_token_count * 0.3)
        else:
            budgets["error_location"] = 0
            budgets["related_files"] = int(max_token_count * 0.75)

        if file_count > 0:
            budgets["per_file"] = budgets["related_files"] // file_count
        else:
            budgets["per_file"] = 0
        return budgets

    def add_code_context(self, error_info: Dict[str, Any], token_budgets: Dict[str, int]) -> Dict[str, str]:
        if not self.file_tool or not error_info.get("file_paths"):
            return {}

        code_context: Dict[str, str] = {}
        primary_file = None
        primary_line = None
        if error_info.get("file_paths") and error_info.get("line_numbers"):
            primary_file = error_info["file_paths"][0]
            primary_line = error_info["line_numbers"][0]

        file_paths = error_info["file_paths"]
        have_mm = bool(self.memory_manager)

        for file_path in file_paths:
            try:
                if not os.path.isfile(file_path):
                    continue
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if not content:
                    continue
                is_primary = file_path == primary_file
                if is_primary and primary_line is not None:
                    lines = content.split('\n')
                    if primary_line >= len(lines):
                        primary_line = len(lines) - 1
                    context_start = max(0, primary_line - 10)
                    context_end = min(len(lines), primary_line + 10)
                    error_context = []
                    for i in range(context_start, context_end):
                        marker = "-> " if i == primary_line else "   "
                        error_context.append(f"{i+1}: {marker}{lines[i]}")
                    error_location_content = "\n".join(error_context)
                    if have_mm and len(lines) > 50:
                        upper_content = "\n".join(lines[:context_start])
                        upper_tokens = token_budgets["per_file"] // 4
                        if upper_content and upper_tokens > 100:
                            upper_summary = self.memory_manager.hierarchical_summarize(upper_content, target_tokens=upper_tokens)
                            upper_content = f"[BEFORE ERROR]:\n{upper_summary}"
                        else:
                            upper_content = ""
                        lower_content = "\n".join(lines[context_end:])
                        lower_tokens = token_budgets["per_file"] // 4
                        if lower_content and lower_tokens > 100:
                            lower_summary = self.memory_manager.hierarchical_summarize(lower_content, target_tokens=lower_tokens)
                            lower_content = f"[AFTER ERROR]:\n{lower_summary}"
                        else:
                            lower_content = ""
                        combined = []
                        if upper_content:
                            combined.append(upper_content)
                        combined.append("[ERROR LOCATION]:\n" + error_location_content)
                        if lower_content:
                            combined.append(lower_content)
                        code_context[file_path] = "\n\n".join(combined)
                    else:
                        code_context[file_path] = error_location_content
                else:
                    tokens_for_file = max(token_budgets["per_file"], 500)
                    if have_mm and self.memory_manager.estimate_token_count(content) > tokens_for_file:
                        summary = self.memory_manager.hierarchical_summarize(content, target_tokens=tokens_for_file)
                        code_context[file_path] = f"[SUMMARY]:\n{summary}"
                    else:
                        code_context[file_path] = content
            except Exception as exc:  # pragma: no cover - log only
                if self.scratchpad:
                    self.scratchpad.log("ErrorContextManager", f"Error processing file {file_path}: {exc}")
                continue
        return code_context
