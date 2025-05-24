"""Component relationship validation utilities."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .constants import ErrorMessages, logger


def validate_component_relationships(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Verify relationships between components are appropriate."""
    issues: List[Dict[str, Any]] = []
    components, dependencies = extract_component_dependencies(system_design)

    for cycle in find_circular_dependencies(components, dependencies):
        issues.append(
            {
                "issue_type": "circular_dependency",
                "severity": "high",
                "description": ErrorMessages.CIRCULAR_DEPENDENCY.format(
                    cycle=" -> ".join(cycle)
                ),
                "components": cycle,
            }
        )

    coupling_scores = calculate_coupling_scores(components, dependencies)
    for component, score in coupling_scores.items():
        if score > 0.7:
            coupled_with = [
                other
                for other in components
                if other != component
                and (
                    dependencies.get((component, other))
                    or dependencies.get((other, component))
                )
            ]
            issues.append(
                {
                    "issue_type": "excessive_coupling",
                    "severity": "medium",
                    "description": ErrorMessages.EXCESSIVE_COUPLING.format(
                        component=component, score=score
                    ),
                    "component": component,
                    "coupling_score": score,
                    "coupled_with": coupled_with,
                }
            )

    issues.extend(check_proper_layering(components, dependencies))
    return issues


def extract_component_dependencies(
    system_design: Dict[str, Any],
) -> Tuple[List[str], Dict[Tuple[str, str], int]]:
    """Extract component dependencies from the system design."""
    components: List[str] = []
    dependencies: Dict[Tuple[str, str], int] = {}
    element_to_component: Dict[str, str] = {}

    for element in system_design.get("code_elements", []):
        if not isinstance(element, dict) or "element_id" not in element:
            continue
        element_id = element["element_id"]
        component = None
        if "target_file" in element:
            file_path = element["target_file"]
            parts = file_path.split("/")
            if len(parts) > 1:
                component = parts[-2]
        if not component and "signature" in element:
            signature = element["signature"]
            if "class" in signature.lower():
                match = re.search(r"class\s+(\w+)", signature)
                if match:
                    component = match.group(1)
        if not component:
            component = element_id
        if component not in components:
            components.append(component)
        element_to_component[element_id] = component

    for flow in system_design.get("data_flow", []):
        if not isinstance(flow, dict):
            continue
        from_element = flow.get("from")
        to_element = flow.get("to")
        if from_element in element_to_component and to_element in element_to_component:
            from_component = element_to_component[from_element]
            to_component = element_to_component[to_element]
            if from_component != to_component:
                key = (from_component, to_component)
                dependencies[key] = dependencies.get(key, 0) + 1
    return components, dependencies


def find_circular_dependencies(
    components: List[str], dependencies: Dict[Tuple[str, str], int]
) -> List[List[str]]:
    """Find circular dependencies in the component graph."""
    graph: Dict[str, List[str]] = defaultdict(list)
    for (from_comp, to_comp), _ in dependencies.items():
        graph[from_comp].append(to_comp)
    cycles: List[List[str]] = []

    def dfs(node: str, path: List[str], visited: set[str]) -> None:
        if node in path:
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            dfs(neighbor, path, visited)
        path.pop()

    for component in components:
        dfs(component, [], set())
    return cycles


def calculate_coupling_scores(
    components: List[str], dependencies: Dict[Tuple[str, str], int]
) -> Dict[str, float]:
    """Calculate coupling scores for each component."""
    scores: Dict[str, float] = {}
    if not components:
        return scores
    max_possible = len(components) - 1
    if max_possible == 0:
        return {comp: 0 for comp in components}
    outgoing: Dict[str, int] = defaultdict(int)
    incoming: Dict[str, int] = defaultdict(int)
    for (from_comp, to_comp), _ in dependencies.items():
        outgoing[from_comp] += 1
        incoming[to_comp] += 1
    for component in components:
        total = outgoing[component] + incoming[component]
        scores[component] = total / (2 * max_possible)
    return scores


def check_proper_layering(
    components: List[str], dependencies: Dict[Tuple[str, str], int]
) -> List[Dict[str, Any]]:
    """Check for proper layering in the architecture."""
    issues: List[Dict[str, Any]] = []
    layer_rules = [
        (r"controller|api|rest|endpoint", r"service|business|domain", True),
        (r"service|business|domain", r"repository|dao|data", True),
        (r"repository|dao|data", r"controller|api|rest|endpoint", False),
    ]
    for (from_comp, to_comp), _ in dependencies.items():
        from_lower = from_comp.lower()
        to_lower = to_comp.lower()
        for higher, lower, allowed in layer_rules:
            is_from_high = re.search(higher, from_lower) is not None
            is_to_high = re.search(higher, to_lower) is not None
            is_from_low = re.search(lower, from_lower) is not None
            is_to_low = re.search(lower, to_lower) is not None
            if is_from_high and is_to_low and not allowed:
                issues.append(
                    {
                        "issue_type": "improper_layering",
                        "severity": "medium",
                        "description": ErrorMessages.IMPROPER_LAYERING_HIGHER.format(
                            from_component=from_comp, to_component=to_comp
                        ),
                        "from_component": from_comp,
                        "to_component": to_comp,
                    }
                )
            elif is_from_low and is_to_high and allowed:
                issues.append(
                    {
                        "issue_type": "improper_layering",
                        "severity": "medium",
                        "description": ErrorMessages.IMPROPER_LAYERING_LOWER.format(
                            from_component=from_comp, to_component=to_comp
                        ),
                        "from_component": from_comp,
                        "to_component": to_comp,
                    }
                )
    return issues


# Repair helpers

def repair_component_relationships(
    system_design: Dict[str, Any], issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair component relationship issues in the system design."""
    repaired = json.loads(json.dumps(system_design))
    circular = [i for i in issues if i.get("issue_type") == "circular_dependency"]
    if circular:
        components, dependencies = extract_component_dependencies(repaired)
        for issue in circular:
            cycle = issue.get("components", [])
            if len(cycle) < 2:
                continue
            weakest_link = None
            min_strength = float("inf")
            for i in range(len(cycle)):
                from_comp = cycle[i]
                to_comp = cycle[(i + 1) % len(cycle)]
                strength = dependencies.get((from_comp, to_comp), 0)
                if strength < min_strength:
                    min_strength = strength
                    weakest_link = (from_comp, to_comp)
            if not weakest_link:
                continue
            from_comp, to_comp = weakest_link
            if "data_flow" in repaired and isinstance(repaired["data_flow"], list):
                element_map: Dict[str, str] = {}
                for element in repaired.get("code_elements", []):
                    if not isinstance(element, dict) or "element_id" not in element:
                        continue
                    element_id = element["element_id"]
                    component = None
                    if "target_file" in element:
                        file_path = element["target_file"]
                        if from_comp in file_path:
                            component = from_comp
                        elif to_comp in file_path:
                            component = to_comp
                    if not component and "signature" in element:
                        sig = element["signature"]
                        if from_comp in sig:
                            component = from_comp
                        elif to_comp in sig:
                            component = to_comp
                    if component:
                        element_map[element_id] = component
                repaired["data_flow"] = [
                    flow
                    for flow in repaired["data_flow"]
                    if not (
                        isinstance(flow, dict)
                        and flow.get("from") in element_map
                        and flow.get("to") in element_map
                        and element_map[flow.get("from")] == from_comp
                        and element_map[flow.get("to")] == to_comp
                    )
                ]
    coupling_issues = [i for i in issues if i.get("issue_type") == "excessive_coupling"]
    if coupling_issues:
        for issue in coupling_issues:
            component = issue.get("component")
            if not component:
                continue
            if "overview" in repaired and isinstance(repaired["overview"], str):
                note = (
                    f"\nNote: Component '{component}' has high coupling and should be refactored"
                    " into smaller, more focused components."
                )
                if note not in repaired["overview"]:
                    repaired["overview"] += note
    return repaired
