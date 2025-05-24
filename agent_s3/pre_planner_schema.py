"""Pre-planning JSON schema definitions."""
from typing import Dict

REQUIRED_SCHEMA: Dict[str, type] = {
    "original_request": str,
    "feature_groups": list,
}

FEATURE_GROUP_SCHEMA: Dict[str, type] = {
    "group_name": str,
    "group_description": str,
    "features": list,
}

FEATURE_SCHEMA: Dict[str, type] = {
    "name": str,
    "description": str,
    "files_affected": list,
    "test_requirements": dict,
    "dependencies": dict,
    "risk_assessment": dict,
    "system_design": dict,
}

