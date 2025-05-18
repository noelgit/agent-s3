"""Simple pre-emptive planning error detection utilities."""

from __future__ import annotations

from typing import Dict, List

from agent_s3.tools.plan_validator import validate_pre_plan


def detect_preemptive_errors(plan_data: Dict) -> List[str]:
    """Detect critical issues in planning data before implementation."""
    errors: List[str] = []

    valid, results = validate_pre_plan(plan_data)
    if not valid:
        for item in results.get("critical", []):
            msg = item.get("message") if isinstance(item, dict) else str(item)
            errors.append(msg)

    # Check for duplicate feature names
    seen = set()
    for group in plan_data.get("feature_groups", []):
        for feature in group.get("features", []):
            name = feature.get("name")
            if not name:
                continue
            if name in seen:
                errors.append(f"Duplicate feature name: {name}")
            else:
                seen.add(name)
    return errors
