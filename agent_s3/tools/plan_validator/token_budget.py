from __future__ import annotations

from typing import Any, Dict, List

from .config import TOKEN_BUDGET_LIMITS


def validate_token_budget(data: Dict[str, Any]) -> List[str]:
    """Validate that token budget estimates are within limits."""
    errors: List[str] = []
    total_tokens = 0
    for i, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
        group_tokens = 0
        for j, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
            est_tokens = feature.get("est_tokens", 0)
            complexity = feature.get("complexity_enum", 0)
            if complexity in TOKEN_BUDGET_LIMITS and est_tokens > TOKEN_BUDGET_LIMITS[complexity]:
                errors.append(
                    f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} "
                    f"exceeds token budget: {est_tokens} tokens for complexity level {complexity}"
                )
            group_tokens += est_tokens
        total_tokens += group_tokens
    global_budget = data.get("token_budget", 100000)
    if total_tokens > global_budget:
        errors.append(f"Total token estimate ({total_tokens}) exceeds global budget ({global_budget})")
    return errors


def validate_complexity_sanity(data: Dict[str, Any]) -> List[str]:
    """Check that complexity levels correlate with token estimates."""
    errors: List[str] = []
    for i, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
        for j, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
            est_tokens = feature.get("est_tokens", 0)
            complexity = feature.get("complexity_enum", 0)
            if complexity not in TOKEN_BUDGET_LIMITS:
                errors.append(
                    f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} "
                    f"has invalid complexity level: {complexity}"
                )
                continue
            if complexity == 0 and est_tokens > TOKEN_BUDGET_LIMITS[0]:
                errors.append(
                    f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} "
                    f"marked as trivial but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[0]})"
                )
            elif complexity == 1 and est_tokens > TOKEN_BUDGET_LIMITS[1]:
                errors.append(
                    f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} "
                    f"marked as simple but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[1]})"
                )
            elif complexity == 2 and est_tokens > TOKEN_BUDGET_LIMITS[2]:
                errors.append(
                    f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} "
                    f"marked as moderate but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[2]})"
                )
    return errors
