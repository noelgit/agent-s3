"""Helper functions for repairing implementation plans."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Set

from .utils import find_best_match


# ---------------------------- Repair Functions ----------------------------


def repair_structure(plan: Dict[str, Any], system_design: Dict[str, Any]) -> Dict[str, Any]:
    """Repair basic structure issues in the implementation plan."""
    if not isinstance(plan, dict):
        plan = {}
    if not plan:
        code_elements = system_design.get("code_elements", [])
        files_by_type: Dict[str, List[Dict[str, Any]]] = {}
        for element in code_elements:
            if isinstance(element, dict) and "element_id" in element:
                element_type = element.get("element_type", "unknown")
                files_by_type.setdefault(element_type, []).append(element)
        for element_type, elements in files_by_type.items():
            if element_type == "class":
                file_path = "models.py"
            elif element_type == "function":
                file_path = "functions.py"
            elif "service" in element_type or "controller" in element_type:
                file_path = "services.py"
            else:
                file_path = f"{element_type.replace(' ', '_')}.py"
            plan[file_path] = []
            for element in elements:
                element_id = element.get("element_id", "")
                name = element.get("name", "Unknown")
                signature = element.get("signature", f"def {name.lower()}():")
                plan[file_path].append(
                    {
                        "function": signature,
                        "description": f"Implementation of {name}",
                        "element_id": element_id,
                        "steps": [
                            {
                                "step_description": "Implement core functionality",
                                "pseudo_code": "# TODO: Implement core functionality",
                                "relevant_data_structures": [],
                                "api_calls_made": [],
                                "error_handling_notes": "Handle potential errors",
                            }
                        ],
                        "edge_cases": ["Error handling needed"],
                        "architecture_issues_addressed": [],
                    }
                )
    return plan


def repair_file_paths(plan: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Repair invalid file paths in the implementation plan."""
    repaired_plan: Dict[str, Any] = {}
    for file_path, functions in plan.items():
        is_valid = True
        for issue in issues:
            if issue.get("file_path") == file_path:
                is_valid = False
                break
        if is_valid:
            repaired_plan[file_path] = functions
        else:
            if isinstance(file_path, (int, float, bool)):
                new_file_path = f"file_{file_path}.py"
                repaired_plan[new_file_path] = functions
            elif not isinstance(file_path, str):
                new_file_path = "unnamed_file.py"
                repaired_plan[new_file_path] = functions
            else:
                if not file_path.endswith(
                    (".py", ".js", ".ts", ".java", ".rb", ".go", ".c", ".cpp", ".h", ".hpp")
                ):
                    new_file_path = f"{file_path}.py"
                    repaired_plan[new_file_path] = functions
                else:
                    repaired_plan[file_path] = functions
    return repaired_plan


def repair_functions_format(plan: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Repair invalid functions format in the implementation plan."""
    repaired_plan: Dict[str, Any] = {}
    for file_path, functions in plan.items():
        needs_repair = any(issue.get("file_path") == file_path for issue in issues)
        if not needs_repair or isinstance(functions, list):
            repaired_plan[file_path] = functions
        else:
            if isinstance(functions, dict):
                repaired_plan[file_path] = [functions]
            elif isinstance(functions, str):
                repaired_plan[file_path] = [
                    {
                        "function": functions,
                        "description": "Auto-generated function description",
                        "element_id": f"auto_generated_{file_path.replace('.', '_').replace('/', '_')}",
                        "steps": [
                            {
                                "step_description": "Implement function logic",
                                "pseudo_code": functions,
                                "relevant_data_structures": [],
                                "api_calls_made": [],
                                "error_handling_notes": "",
                            }
                        ],
                        "edge_cases": [],
                        "architecture_issues_addressed": [],
                    }
                ]
            else:
                repaired_plan[file_path] = []
    return repaired_plan


def repair_missing_elements(
    plan: Dict[str, Any], issues: List[Dict[str, Any]], system_design: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair missing element implementations in the implementation plan."""
    repaired_plan = json.loads(json.dumps(plan))
    elements_by_type: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        element_id = issue.get("element_id")
        if not element_id:
            continue
        element = next(
            (e for e in system_design.get("code_elements", []) if isinstance(e, dict) and e.get("element_id") == element_id),
            None,
        )
        if not element:
            continue
        element_type = element.get("element_type", "unknown")
        elements_by_type.setdefault(element_type, []).append(element)
    for element_type, elements in elements_by_type.items():
        file_path = None
        for fp, functions in repaired_plan.items():
            if not isinstance(functions, list):
                continue
            for function in functions:
                if not isinstance(function, dict):
                    continue
                function_element_id = function.get("element_id")
                if not function_element_id:
                    continue
                function_element = next(
                    (e for e in system_design.get("code_elements", []) if isinstance(e, dict) and e.get("element_id") == function_element_id),
                    None,
                )
                if not function_element:
                    continue
                if function_element.get("element_type") == element_type:
                    file_path = fp
                    break
            if file_path:
                break
        if not file_path:
            if element_type == "class":
                file_path = "models.py"
            elif element_type == "function":
                file_path = "functions.py"
            elif "service" in element_type or "controller" in element_type:
                file_path = "services.py"
            else:
                file_path = f"{element_type.replace(' ', '_')}.py"
            base_path = file_path
            counter = 1
            while file_path in repaired_plan:
                file_path = f"{base_path[:-3]}_{counter}.py"
                counter += 1
            repaired_plan[file_path] = []
        for element in elements:
            element_id = element.get("element_id")
            name = element.get("name", "Unknown")
            signature = element.get("signature", f"def {name.lower()}():")
            repaired_plan[file_path].append(
                {
                    "function": signature,
                    "description": f"Implementation of {name}",
                    "element_id": element_id,
                    "steps": [
                        {
                            "step_description": "Implement core functionality",
                            "pseudo_code": "# TODO: Implement core functionality",
                            "relevant_data_structures": [],
                            "api_calls_made": [],
                            "error_handling_notes": "Handle potential errors",
                        }
                    ],
                    "edge_cases": ["Error handling needed"],
                    "architecture_issues_addressed": [],
                }
            )
    return repaired_plan


def repair_element_id_references(
    plan: Dict[str, Any], issues: List[Dict[str, Any]], system_design: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair invalid element ID references in the implementation plan."""
    repaired_plan = json.loads(json.dumps(plan))
    valid_element_ids: Set[str] = {
        element["element_id"]
        for element in system_design.get("code_elements", [])
        if isinstance(element, dict) and "element_id" in element
    }
    for issue in issues:
        file_path = issue.get("file_path")
        function_index = issue.get("function_index")
        invalid_id = issue.get("invalid_id")
        if not file_path or function_index is None or not invalid_id:
            continue
        if file_path in repaired_plan and isinstance(repaired_plan[file_path], list):
            functions = repaired_plan[file_path]
            if 0 <= function_index < len(functions):
                function = functions[function_index]
                best_match = find_best_match(invalid_id, valid_element_ids)
                if best_match:
                    function["element_id"] = best_match
                elif valid_element_ids:
                    function["element_id"] = next(iter(valid_element_ids))
    return repaired_plan


def repair_incomplete_implementations(
    plan: Dict[str, Any],
    issues: List[Dict[str, Any]],
    system_design: Dict[str, Any],
    test_implementations: Dict[str, Any],
) -> Dict[str, Any]:
    """Repair incomplete function implementations in the implementation plan."""
    repaired_plan = json.loads(json.dumps(plan))
    for issue in issues:
        file_path = issue.get("file_path")
        function_index = issue.get("function_index")
        if file_path not in repaired_plan or not isinstance(repaired_plan[file_path], list):
            continue
        functions = repaired_plan[file_path]
        if not (0 <= function_index < len(functions)):
            continue
        function = functions[function_index]
        if "steps" not in function or not isinstance(function["steps"], list):
            function["steps"] = [
                {
                    "step_description": "Implement logic",
                    "pseudo_code": "# TODO: implement",
                    "relevant_data_structures": [],
                    "api_calls_made": [],
                    "error_handling_notes": "",
                }
            ]
        if "edge_cases" not in function or not isinstance(function["edge_cases"], list):
            function["edge_cases"] = []
        if "architecture_issues_addressed" not in function or not isinstance(function["architecture_issues_addressed"], list):
            function["architecture_issues_addressed"] = []
    return repaired_plan


def repair_architecture_issue_coverage(
    plan: Dict[str, Any], issues: List[Dict[str, Any]], architecture_review: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair architecture issue coverage in the implementation plan."""
    repaired_plan = json.loads(json.dumps(plan))
    element_map: Dict[str, List[tuple[str, int]]] = {}
    for file_path, functions in repaired_plan.items():
        if not isinstance(functions, list):
            continue
        for idx, function in enumerate(functions):
            if isinstance(function, dict) and "element_id" in function:
                element_id = function["element_id"]
                element_map.setdefault(element_id, []).append((file_path, idx))
    for issue in issues:
        issue_type = issue.get("issue_type")
        arch_issue_id = issue.get("arch_issue_id")
        if issue_type == "unaddressed_critical_issue" and arch_issue_id:
            arch_issue = None
            for section in ("logical_gaps", "security_concerns", "optimization_opportunities"):
                for ai in architecture_review.get(section, []):
                    if isinstance(ai, dict) and ai.get("id") == arch_issue_id:
                        arch_issue = ai
                        break
                if arch_issue:
                    break
            if not arch_issue:
                continue
            raw_target_elements = arch_issue.get("target_element_ids", [])
            if isinstance(raw_target_elements, list):
                target_elements = [te for te in raw_target_elements if te]
            elif raw_target_elements:
                target_elements = [raw_target_elements]
            else:
                target_elements = []
            if not target_elements:
                description = arch_issue.get("description", "")
                for element_id in element_map.keys():
                    if element_id.lower() in description.lower():
                        target_elements.append(element_id)
            assigned = False
            for element_id in target_elements:
                if element_id in element_map:
                    for file_path, function_idx in element_map[element_id]:
                        function = repaired_plan[file_path][function_idx]
                        function.setdefault("architecture_issues_addressed", [])
                        if arch_issue_id not in function["architecture_issues_addressed"]:
                            function["architecture_issues_addressed"].append(arch_issue_id)
                            assigned = True
                            break
                    if assigned:
                        break
            if not assigned and repaired_plan:
                first_file = next(iter(repaired_plan.keys()))
                functions = repaired_plan[first_file]
                if isinstance(functions, list) and functions:
                    first_function = functions[0]
                    if isinstance(first_function, dict):
                        first_function.setdefault("architecture_issues_addressed", [])
                        if arch_issue_id not in first_function["architecture_issues_addressed"]:
                            first_function["architecture_issues_addressed"].append(arch_issue_id)
    return repaired_plan


__all__ = [
    "repair_structure",
    "repair_file_paths",
    "repair_functions_format",
    "repair_missing_elements",
    "repair_element_id_references",
    "repair_incomplete_implementations",
    "repair_architecture_issue_coverage",
]
