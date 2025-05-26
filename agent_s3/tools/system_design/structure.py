"""Structure validation utilities."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Set

from .constants import ErrorMessages


def validate_code_elements(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate code elements in the system design."""
    issues: List[Dict[str, Any]] = []

    if "code_elements" not in system_design:
        return issues

    code_elements = system_design.get("code_elements", [])
    if not isinstance(code_elements, list):
        issues.append(
            {
                "issue_type": "invalid_code_elements_format",
                "severity": "critical",
                "description": ErrorMessages.INVALID_CODE_ELEMENTS_FORMAT.format(
                    type=type(code_elements)
                ),
            }
        )
        return issues

    element_ids: Set[str] = set()
    for idx, element in enumerate(code_elements):
        if not isinstance(element, dict):
            issues.append(
                {
                    "issue_type": "invalid_element_format",
                    "severity": "critical",
                    "description": ErrorMessages.INVALID_ELEMENT_FORMAT.format(
                        index=idx
                    ),
                    "index": idx,
                }
            )
            continue

        for field in ["element_id", "signature", "description"]:
            if field not in element:
                issues.append(
                    {
                        "issue_type": f"missing_element_{field}",
                        "severity": "high",
                        "description": ErrorMessages.MISSING_ELEMENT_FIELD.format(
                            index=idx, field=field
                        ),
                        "index": idx,
                    }
                )

        element_id = element.get("element_id")
        if element_id:
            if element_id in element_ids:
                issues.append(
                    {
                        "issue_type": "duplicate_element_id",
                        "severity": "critical",
                        "description": ErrorMessages.DUPLICATE_ELEMENT_ID.format(
                            element_id=element_id
                        ),
                        "element_id": element_id,
                    }
                )
            else:
                element_ids.add(element_id)

        signature = element.get("signature", "")
        if signature and not is_valid_signature(signature):
            issues.append(
                {
                    "issue_type": "invalid_element_signature",
                    "severity": "high",
                    "description": ErrorMessages.INVALID_SIGNATURE.format(
                        element_id=element_id, signature=signature
                    ),
                    "element_id": element_id,
                    "signature": signature,
                }
            )
    return issues


def is_valid_signature(signature: str) -> bool:
    """Return True if a signature has a valid format."""
    patterns = [
        r"def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:",
        r"function\s+\w+\s*\([^)]*\)\s*{",
        r"async\s+function\s+\w+\s*\([^)]*\)",
        r"const\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
        r"public\s+(?:static\s+)?(?:\w+\s+)+\w+\s*\([^)]*\)",
        r"class\s+\w+",
        r"interface\s+\w+",
        r"\w+\([^)]*\)\s*{\s*",
        r"@\w+(?:\([^)]*\))?\s*\n\s*def",
    ]
    for pattern in patterns:
        if re.search(pattern, signature):
            return True
    return False


def validate_design_requirements_alignment(
    system_design: Dict[str, Any], requirements: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Check if the system design satisfies all requirements."""
    issues: List[Dict[str, Any]] = []
    requirement_ids = extract_requirement_ids(requirements)
    covered: Set[str] = set()

    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            if "requirements_addressed" in element:
                addressed = element.get("requirements_addressed", [])
                if isinstance(addressed, list):
                    covered.update(addressed)

            description = element.get("description", "")
            if description:
                for req_id in requirement_ids:
                    if req_id in description:
                        covered.add(req_id)

    overview = system_design.get("overview", "")
    if isinstance(overview, str):
        for req_id in requirement_ids:
            if req_id in overview:
                covered.add(req_id)

    missing = requirement_ids - covered
    if missing:
        issues.append(
            {
                "issue_type": "missing_requirement_coverage",
                "severity": "high",
                "description": ErrorMessages.MISSING_REQUIREMENT_COVERAGE.format(
                    requirements=", ".join(missing)
                ),
                "missing_requirements": list(missing),
            }
        )

    if requirement_ids:
        coverage = len(covered) / len(requirement_ids)
        if coverage < 0.9:
            issues.append(
                {
                    "issue_type": "low_requirements_coverage",
                    "severity": "medium",
                    "description": ErrorMessages.LOW_REQUIREMENTS_COVERAGE.format(
                        coverage=coverage
                    ),
                    "coverage": coverage,
                    "covered_count": len(covered),
                    "total_count": len(requirement_ids),
                }
            )
    return issues


def extract_requirement_ids(requirements: Dict[str, Any]) -> Set[str]:
    """Extract requirement IDs from the requirements data."""
    ids: Set[str] = set()
    if "functional_requirements" in requirements:
        for req in requirements["functional_requirements"]:
            if isinstance(req, dict) and "id" in req:
                ids.add(req["id"])
    if "non_functional_requirements" in requirements:
        for req in requirements["non_functional_requirements"]:
            if isinstance(req, dict) and "id" in req:
                ids.add(req["id"])
    return ids


def calculate_design_metrics(
    system_design: Dict[str, Any], requirements: Dict[str, Any]
) -> Dict[str, float]:
    """Calculate quality metrics for the system design."""
    metrics: Dict[str, float] = {}
    requirement_ids = extract_requirement_ids(requirements)
    covered: Set[str] = set()

    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            if "requirements_addressed" in element:
                addressed = element.get("requirements_addressed", [])
                if isinstance(addressed, list):
                    covered.update(addressed)
            description = element.get("description", "")
            if description:
                for req_id in requirement_ids:
                    if req_id in description:
                        covered.add(req_id)

    if requirement_ids:
        metrics["requirements_coverage_score"] = len(covered) / len(requirement_ids)
    else:
        metrics["requirements_coverage_score"] = 1.0

    components, deps = extract_component_dependencies(system_design)

    if components:
        internal = 0
        total = 0
        for element in system_design.get("code_elements", []):
            if not isinstance(element, dict) or "element_id" not in element:
                continue
            element_id = element["element_id"]
            component_name = None
            for comp in components:
                if comp in element_id or (
                    "target_file" in element and comp in element["target_file"]
                ):
                    component_name = comp
                    break
            if not component_name:
                continue
            for flow in system_design.get("data_flow", []):
                if not isinstance(flow, dict):
                    continue
                if flow.get("from") == element_id:
                    total += 1
                    to_element = flow.get("to")
                    to_component = None
                    for other in system_design.get("code_elements", []):
                        if isinstance(other, dict) and other.get("element_id") == to_element:
                            for comp in components:
                                if comp in to_element or (
                                    "target_file" in other and comp in other["target_file"]
                                ):
                                    to_component = comp
                                    break
                            break
                    if to_component == component_name:
                        internal += 1
        cohesion = internal / max(total, 1)
        metrics["design_cohesion_score"] = min(1.0, cohesion * 1.2)
    else:
        metrics["design_cohesion_score"] = 0.0

    coupling_scores = calculate_coupling_scores(components, deps)
    if coupling_scores:
        avg = sum(coupling_scores.values()) / len(coupling_scores)
        ideal_min, ideal_max = 0.2, 0.4
        if avg < ideal_min:
            metrics["design_coupling_score"] = avg / ideal_min
        elif avg > ideal_max:
            excess = avg - ideal_max
            metrics["design_coupling_score"] = max(0, 1 - (excess / 0.6))
        else:
            metrics["design_coupling_score"] = 1.0
    else:
        metrics["design_coupling_score"] = 0.0

    weights = {
        "requirements_coverage_score": 0.5,
        "design_cohesion_score": 0.25,
        "design_coupling_score": 0.25,
    }
    overall = sum(metrics[m] * w for m, w in weights.items())
    metrics["overall_score"] = overall
    return metrics


# Repair helpers

def repair_structure(system_design: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure required sections exist."""
    repaired = system_design.copy() if isinstance(system_design, dict) else {}
    for section in ["overview", "code_elements", "data_flow"]:
        if section not in repaired:
            if section == "overview":
                repaired[section] = "System design overview"
            else:
                repaired[section] = []
    return repaired


def repair_code_elements(
    system_design: Dict[str, Any], issues_by_type: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Repair code elements in the design."""
    repaired = json.loads(json.dumps(system_design))
    if "code_elements" not in repaired or not isinstance(repaired["code_elements"], list):
        repaired["code_elements"] = []
    if repaired["code_elements"]:
        if "missing_element_id" in issues_by_type:
            for issue in issues_by_type["missing_element_id"]:
                idx = issue.get("index")
                if idx is not None and idx < len(repaired["code_elements"]):
                    element = repaired["code_elements"][idx]
                    if isinstance(element, dict) and "element_id" not in element:
                        base_id = "element"
                        if "signature" in element:
                            sig = element["signature"]
                            match = re.search(r"\b(\w+)\s*\(", sig)
                            if match:
                                base_id = match.group(1)
                        existing_ids = {
                            e["element_id"]
                            for e in repaired["code_elements"]
                            if isinstance(e, dict) and "element_id" in e
                        }
                        element_id = base_id
                        counter = 1
                        while element_id in existing_ids:
                            element_id = f"{base_id}_{counter}"
                            counter += 1
                        element["element_id"] = element_id
        if "invalid_element_signature" in issues_by_type:
            for issue in issues_by_type["invalid_element_signature"]:
                element_id = issue.get("element_id")
                if element_id:
                    for element in repaired["code_elements"]:
                        if (
                            isinstance(element, dict)
                            and element.get("element_id") == element_id
                        ):
                            old_sig = element.get("signature", "")
                            if "def" in old_sig and ":" not in old_sig:
                                element["signature"] = old_sig + ":"
                            elif "function" in old_sig and "{" not in old_sig:
                                element["signature"] = old_sig + " {"
                            elif "class" in old_sig and ":" not in old_sig:
                                element["signature"] = old_sig + ":"
    return repaired


def repair_requirements_alignment(
    system_design: Dict[str, Any],
    issues: List[Dict[str, Any]],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    """Add missing requirement references to the design."""
    repaired = json.loads(json.dumps(system_design))
    for issue in issues:
        missing_reqs = issue.get("missing_requirements", [])
        if not missing_reqs:
            continue
        for req_id in missing_reqs:
            added = False
            for element in repaired.get("code_elements", []):
                if not isinstance(element, dict):
                    continue
                if is_element_related_to_requirement(element, req_id, requirements):
                    if "requirements_addressed" not in element:
                        element["requirements_addressed"] = []
                    if req_id not in element["requirements_addressed"]:
                        element["requirements_addressed"].append(req_id)
                    if "description" in element and req_id not in element["description"]:
                        element["description"] += f" Addresses requirement {req_id}."
                    added = True
                    break
            if not added and "overview" in repaired:
                if req_id not in repaired["overview"]:
                    repaired["overview"] += f"\nThe design addresses requirement {req_id}."
    return repaired


def is_element_related_to_requirement(
    element: Dict[str, Any], req_id: str, requirements: Dict[str, Any]
) -> bool:
    """Check if an element might relate to a requirement."""
    req_details = None
    if "functional_requirements" in requirements:
        for req in requirements["functional_requirements"]:
            if isinstance(req, dict) and req.get("id") == req_id:
                req_details = req
                break
    if not req_details and "non_functional_requirements" in requirements:
        for req in requirements["non_functional_requirements"]:
            if isinstance(req, dict) and req.get("id") == req_id:
                req_details = req
                break
    if not req_details:
        return False
    req_desc = req_details.get("description", "").lower()
    req_keywords = set(re.findall(r"\b\w+\b", req_desc))
    element_desc = element.get("description", "").lower()
    element_sig = element.get("signature", "").lower()
    element_text = f"{element_desc} {element_sig}"
    element_keywords = set(re.findall(r"\b\w+\b", element_text))
    overlap = len(req_keywords.intersection(element_keywords))
    return overlap >= 3 or (len(req_keywords) > 0 and overlap / len(req_keywords) > 0.2)

