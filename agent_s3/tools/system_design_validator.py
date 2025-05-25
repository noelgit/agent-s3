"""Public API for system design validation and repair."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .system_design import (
    ErrorMessages,
    logger,
    validate_code_elements,
    validate_design_requirements_alignment,
    validate_design_patterns,
    validate_component_relationships,
    calculate_design_metrics,
    repair_structure,
    repair_code_elements,
    repair_requirements_alignment,
    repair_component_relationships,
    repair_architectural_patterns,
)


class SystemDesignValidationError(Exception):
    """Exception raised when validation of system designs fails."""


# Public functions

def validate_system_design(
    system_design: Dict[str, Any], requirements: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """Validate ``system_design`` against ``requirements``."""
    logger.debug("Starting system design validation")
    validation_issues: List[Dict[str, Any]] = []
    needs_repair = False
    validated_design = json.loads(json.dumps(system_design))

    if not isinstance(system_design, dict):
        validation_issues.append(
            {
                "issue_type": "structure",
                "severity": "critical",
                "description": ErrorMessages.SYSTEM_NOT_DICT,
            }
        )
        return validated_design, validation_issues, True

    for section in ["overview", "code_elements", "data_flow"]:
        if section not in system_design:
            validation_issues.append(
                {
                    "issue_type": "missing_section",
                    "severity": "critical",
                    "description": ErrorMessages.MISSING_SECTION.format(section=section),
                    "section": section,
                }
            )
            needs_repair = True

    code_issues = validate_code_elements(system_design)
    validation_issues.extend(code_issues)
    if any(i["severity"] in ["critical", "high"] for i in code_issues):
        needs_repair = True

    req_issues = validate_design_requirements_alignment(system_design, requirements)
    validation_issues.extend(req_issues)
    if any(i["severity"] in ["critical", "high"] for i in req_issues):
        needs_repair = True

    pattern_issues = validate_design_patterns(system_design)
    validation_issues.extend(pattern_issues)
    if any(i["severity"] in ["critical", "high"] for i in pattern_issues):
        needs_repair = True

    relationship_issues = validate_component_relationships(system_design)
    validation_issues.extend(relationship_issues)
    if any(i["severity"] in ["critical", "high"] for i in relationship_issues):
        needs_repair = True

    metrics = calculate_design_metrics(system_design, requirements)
    if metrics["overall_score"] < 0.7:
        validation_issues.append(
            {
                "issue_type": "low_design_quality",
                "severity": "high",
                "description": ErrorMessages.LOW_DESIGN_SCORE.format(
                    score=metrics["overall_score"]
                ),
                "metrics": metrics,
            }
        )
        needs_repair = True

    return validated_design, validation_issues, needs_repair


def repair_system_design(
    system_design: Dict[str, Any],
    validation_issues: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """Attempt to repair ``system_design`` based on ``validation_issues``."""
    repaired_design = json.loads(json.dumps(system_design))
    if not isinstance(repaired_design, dict):
        repaired_design = {}

    issues_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for issue in validation_issues:
        issues_by_type.setdefault(issue.get("issue_type", ""), []).append(issue)

    logger.debug("Repairing system design, issues=%s", list(issues_by_type.keys()))
    if "structure" in issues_by_type or any(k.startswith("missing_section") for k in issues_by_type):
        repaired_design = repair_structure(repaired_design)

    code_issue_types = {
        "missing_element_id",
        "duplicate_element_id",
        "invalid_element_signature",
        "missing_element_description",
    }
    if any(t in issues_by_type for t in code_issue_types):
        repaired_design = repair_code_elements(repaired_design, issues_by_type)

    if "missing_requirement_coverage" in issues_by_type:
        repaired_design = repair_requirements_alignment(
            repaired_design,
            issues_by_type["missing_requirement_coverage"],
            requirements,
        )

    relationship_issue_types = {
        "circular_dependency",
        "excessive_coupling",
        "missing_relationship",
    }
    if any(t in issues_by_type for t in relationship_issue_types):
        relevant = []
        for t in relationship_issue_types:
            relevant.extend(issues_by_type.get(t, []))
        repaired_design = repair_component_relationships(repaired_design, relevant)

    if "inconsistent_pattern" in issues_by_type or "too_many_patterns" in issues_by_type or "inappropriate_patterns" in issues_by_type:
        pattern_issues = []
        for key in ["inconsistent_pattern", "too_many_patterns", "inappropriate_patterns"]:
            pattern_issues.extend(issues_by_type.get(key, []))
        repaired_design = repair_architectural_patterns(repaired_design, pattern_issues)

    return repaired_design
