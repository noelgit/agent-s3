"""Agent-S3: A fully functional, state-of-the-art AI coding agent."""

# This package now includes ast_tools for AST-guided summarization and follows
# the Single Responsibility Principle. Importing heavy modules at package import
# time can lead to unnecessary dependency errors during test collection when
# optional packages are missing. To mitigate this we expose a lazy import layer
# so that components are loaded only when first accessed.
from importlib import import_module
from typing import Any

__version__ = "0.1.1"

_MODULE_MAP = {
    "Coordinator": "agent_s3.coordinator",
    "WorkspaceInitializer": "agent_s3.workspace_initializer",
    "TechStackDetector": "agent_s3.tech_stack_detector",
    "FileHistoryAnalyzer": "agent_s3.file_history_analyzer",
    "TaskResumer": "agent_s3.task_resumer",
    "CommandProcessor": "agent_s3.command_processor",
    "PrePlannerJsonValidator": "agent_s3.pre_planner_json_validator",
    "ComplexityAnalyzer": "agent_s3.complexity_analyzer",
    "DatabaseManager": "agent_s3.database_manager",
    "redact_sensitive_headers": "agent_s3.security_utils",
    "strip_sensitive_headers": "agent_s3.security_utils",
    "redact_auth_headers": "agent_s3.logging_utils",
    "AgentError": "agent_s3.errors",
    "PrePlanningError": "agent_s3.errors",
    "PlanningError": "agent_s3.errors",
    "JSONPlanningError": "agent_s3.errors",
    "CodeGenerator": "agent_s3.code_generator",
    "ContextManager": "agent_s3.context_manager",
    "CodeValidator": "agent_s3.code_validator",
    "DebugUtils": "agent_s3.debug_utils",
}

__all__ = list(_MODULE_MAP.keys())
if "strip_sensitive_headers" not in __all__:
    __all__.append("strip_sensitive_headers")


def __getattr__(name: str) -> Any:
    """Dynamically import objects on first access."""
    module_path = _MODULE_MAP.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_path)
    return getattr(module, name)
