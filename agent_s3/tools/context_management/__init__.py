"""Context management package for agent-s3.

This package provides tools for managing context across different phases
of the agent workflow, including checkpoint management, context loading,
and cross-phase validation.
"""

# Expose key modules and functions
from agent_s3.tools.context_management.checkpoint_manager import (
    save_checkpoint,
    load_checkpoint,
    list_checkpoints,
    get_checkpoint_diff,
    ensure_checkpoint_consistency,
    get_latest_checkpoint,
    create_checkpoint_version,
    ContextCheckpoint,
    CheckpointManager,
)

__all__ = [
    "save_checkpoint",
    "load_checkpoint",
    "list_checkpoints",
    "get_checkpoint_diff",
    "ensure_checkpoint_consistency",
    "get_latest_checkpoint",
    "create_checkpoint_version",
    "ContextCheckpoint",
    "CheckpointManager",
]
