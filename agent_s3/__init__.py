"""Agent-S3: A fully functional, state-of-the-art AI coding agent."""

# This package now includes ast_tools for AST-guided summarization
# and has been refactored to use Single Responsibility Principle.

__version__ = "0.2.0"

# Core components
from agent_s3.coordinator import Coordinator
from agent_s3.workspace_initializer import WorkspaceInitializer
from agent_s3.tech_stack_detector import TechStackDetector
from agent_s3.file_history_analyzer import FileHistoryAnalyzer
from agent_s3.task_resumer import TaskResumer
from agent_s3.command_processor import CommandProcessor

__all__ = [
    'Coordinator',
    'WorkspaceInitializer',
    'TechStackDetector',
    'FileHistoryAnalyzer',
    'TaskResumer',
    'CommandProcessor',
]
