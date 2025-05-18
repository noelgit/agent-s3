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
from agent_s3.pre_planning_validator import PrePlanningValidator
from agent_s3.complexity_analyzer import ComplexityAnalyzer
from agent_s3.database_manager import DatabaseManager
from agent_s3.pre_planning_errors import (
    AgentS3BaseError, PrePlanningError, ValidationError,
    SchemaError, RepairError, ComplexityError, handle_pre_planning_errors
)

__all__ = [
    'Coordinator',
    'WorkspaceInitializer',
    'TechStackDetector',
    'FileHistoryAnalyzer',
    'TaskResumer',
    'PrePlanningValidator',
    'ComplexityAnalyzer',
    'AgentS3BaseError',
    'PrePlanningError',
    'ValidationError',
    'SchemaError',
    'RepairError',
    'ComplexityError',
    'handle_pre_planning_errors',
    'CommandProcessor',
    'DatabaseManager',
]
