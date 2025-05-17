# Central schema definitions for agent-s3 JSON outputs.

"""Shared schema definitions for JSON outputs used in pre-planning and planning."""

from typing import Dict, Any

# Pre-planning output schema definitions
PREPLANNING_REQUIRED_SCHEMA: Dict[str, Any] = {
    "original_request": str,
    "feature_groups": list,
}

PREPLANNING_FEATURE_GROUP_SCHEMA: Dict[str, Any] = {
    "group_name": str,
    "group_description": str,
    "features": list,
}

PREPLANNING_FEATURE_SCHEMA: Dict[str, Any] = {
    "name": str,
    "description": str,
    "files_affected": list,
    "test_requirements": dict,
    "dependencies": dict,
    "risk_assessment": dict,
    "system_design": dict,
}

# Planner output basic schema
PLANNING_REQUIRED_TOP_LEVEL_KEYS = {
    "architecture_review",
    "tests",
    "implementation_plan",
    "discussion",
}
