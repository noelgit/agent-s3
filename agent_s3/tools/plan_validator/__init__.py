from __future__ import annotations

import datetime
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

from .validator import PlanValidator
from .ast_utils import CodeAnalyzer, PlanValidationError, validate_code_syntax
from .config import RESERVED_ENV_VARS, TOKEN_BUDGET_LIMITS
from .structural_checks import (
    validate_duplicate_symbols,
    validate_identifier_hygiene,
    validate_path_validity,
    validate_reserved_prefixes,
    validate_schema,
    validate_stub_test_coherence,
)
from .token_budget import validate_complexity_sanity, validate_token_budget

logger = logging.getLogger(__name__)

__all__ = [
    "PlanValidationError",
    "CodeAnalyzer",
    "PlanValidator",
    "validate_pre_plan",
    "validate_schema",
    "validate_code_syntax",
    "validate_identifier_hygiene",
    "validate_path_validity",
    "validate_token_budget",
    "validate_duplicate_symbols",
    "validate_reserved_prefixes",
    "validate_stub_test_coherence",
    "validate_complexity_sanity",
    "write_junit_report",
    "create_github_annotations",
]


def validate_pre_plan(
    data: Dict[str, Any],
    repo_root: str | None = None,
    context_registry: Any | None = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Validate Pre-Planner JSON output with fast, deterministic checks."""
    if repo_root is None:
        repo_root = os.getcwd()

    validation_results = {
        "critical": [],
        "warnings": [],
        "suggestions": [],
        "sections": {"architecture": False, "implementation": False, "tests": False},
    }

    dangerous_patterns = [
        "rm -rf",
        "deltree",
        "format",
        "DROP TABLE",
        "DROP DATABASE",
        "DELETE FROM",
        "TRUNCATE TABLE",
        "sudo",
        "chmod 777",
        "eval(",
        "exec(",
        "system(",
        "shell_exec",
        "os.system",
    ]

    for group_idx, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
        for feature_idx, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
            description = feature.get("description", "")
            for pattern in dangerous_patterns:
                if pattern.lower() in description.lower():
                    validation_results["critical"].append(
                        {
                            "message": f"Feature '{feature.get('name', f'at index {feature_idx}')}' contains potentially dangerous operation '{pattern}' in description",
                            "category": "security",
                            "suggestion": f"Remove or replace the dangerous operation '{pattern}'",
                        }
                    )
            if "system_design" in feature and isinstance(feature["system_design"], dict):
                validation_results["sections"]["architecture"] = True
                for el_idx, element in enumerate(feature["system_design"].get("code_elements", [])):
                    if not isinstance(element, dict):
                        continue
                    for field in ["signature", "description"]:
                        content = element.get(field, "")
                        for pattern in dangerous_patterns:
                            if pattern.lower() in content.lower():
                                validation_results["critical"].append(
                                    {
                                        "message": f"Code element '{element.get('name', f'at index {el_idx}')}' contains potentially dangerous operation '{pattern}' in {field}",
                                        "category": "security",
                                        "suggestion": f"Remove or replace the dangerous operation '{pattern}'",
                                    }
                                )
            if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                validation_results["sections"]["tests"] = True
                test_req = feature["test_requirements"]
                total_tests = 0
                for tests in test_req.values():
                    if isinstance(tests, list):
                        total_tests += len(tests)
                if total_tests == 0:
                    validation_results["critical"].append(
                        {
                            "message": (
                                f"Feature '{feature.get('name', f'at index {feature_idx}')}' "
                                "must include at least one test case in 'test_requirements'"
                            ),
                            "category": "tests",
                            "suggestion": "Add unit, integration, property-based, or acceptance tests",
                        }
                    )
            if "implementation_steps" in feature and isinstance(feature["implementation_steps"], list):
                valid_steps_found = False
                for step_idx, step in enumerate(feature["implementation_steps"]):
                    if not isinstance(step, dict):
                        continue
                    valid_steps_found = True
                    for field in ["description", "code"]:
                        content = step.get(field, "")
                        for pattern in dangerous_patterns:
                            if pattern.lower() in content.lower():
                                validation_results["critical"].append(
                                    {
                                        "message": f"Implementation step {step_idx} contains potentially dangerous operation '{pattern}' in {field}",
                                        "category": "security",
                                        "suggestion": f"Remove or replace the dangerous operation '{pattern}'",
                                    }
                                )
                if valid_steps_found:
                    validation_results["sections"]["implementation"] = True

    for error in validate_schema(data):
        if "missing required field" in error.lower() or "must be a" in error.lower():
            validation_results["critical"].append({"message": error, "category": "schema", "suggestion": None})
        else:
            validation_results["warnings"].append({"message": error, "category": "schema", "suggestion": None})

    for error in validate_code_syntax(data):
        validation_results["critical"].append({"message": error["message"], "category": "syntax", "suggestion": error.get("suggestion")})

    for error in validate_identifier_hygiene(data):
        if "reserved" in error.lower() or "duplicate" in error.lower():
            validation_results["critical"].append({"message": error, "category": "identifiers", "suggestion": None})
        else:
            validation_results["warnings"].append({"message": error, "category": "identifiers", "suggestion": None})

    for error in validate_path_validity(data, repo_root):
        validation_results["warnings"].append({"message": error, "category": "paths", "suggestion": None})

    for error in validate_token_budget(data):
        if "exceeds global budget" in error.lower():
            validation_results["critical"].append(
                {
                    "message": error,
                    "category": "tokens",
                    "suggestion": "Consider breaking down the task into smaller subtasks",
                }
            )
        else:
            validation_results["warnings"].append({"message": error, "category": "tokens", "suggestion": None})

    for error in validate_duplicate_symbols(data):
        validation_results["critical"].append({"message": error, "category": "duplicates", "suggestion": None})

    for error in validate_reserved_prefixes(data):
        validation_results["warnings"].append({"message": error, "category": "env_vars", "suggestion": None})

    for error in validate_stub_test_coherence(data):
        validation_results["warnings"].append({"message": error, "category": "tests", "suggestion": None})

    for error in validate_complexity_sanity(data):
        validation_results["warnings"].append({"message": error, "category": "complexity", "suggestion": None})

    missing_sections = []
    for section, present in validation_results["sections"].items():
        if not present:
            missing_sections.append(section)
            validation_results["critical"].append(
                {
                    "message": f"Missing required section: {section.capitalize()}",
                    "category": "completeness",
                    "suggestion": f"Add the {section.capitalize()} section to ensure a complete plan",
                }
            )

    validation_results["summary"] = {
        "critical_count": len(validation_results["critical"]),
        "warning_count": len(validation_results["warnings"]),
        "suggestion_count": len(validation_results["suggestions"]),
        "missing_sections": missing_sections,
    }

    is_valid = len(validation_results["critical"]) == 0

    if context_registry and not is_valid:
        try:
            context_registry.add("validation_errors", validation_results)
        except Exception:
            pass

    if not is_valid:
        error_report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_status": "failed",
            "critical_errors": validation_results["critical"],
            "warnings": validation_results["warnings"],
            "suggestions": validation_results["suggestions"],
            "sections_status": {
                section: "missing" if section in missing_sections else "present" for section in validation_results["sections"]
            },
        }
        try:
            report_path = "validation_error_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(error_report, f, indent=2)
            logger.info("Validation error report saved to %s", report_path)
        except Exception as exc:
            logger.error("Failed to save validation error report: %s", exc)

    return is_valid, validation_results


def write_junit_report(errors: List[str], output_path: str = "plan_validation.xml") -> bool:
    """Write validation errors as JUnit XML for CI integration."""
    try:
        testsuites = ET.Element("testsuites")
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", "Plan Validation")
        testsuite.set("tests", str(len(errors) if errors else 1))
        testsuite.set("errors", str(len(errors)))
        testsuite.set("failures", "0")
        testsuite.set("timestamp", datetime.datetime.now().isoformat())
        if errors:
            for error in errors:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", error[:40] + "..." if len(error) > 40 else error)
                testcase.set("classname", "plan_validator")
                error_elem = ET.SubElement(testcase, "error")
                error_elem.set("message", error)
                error_elem.text = error
        else:
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("name", "Plan validation passed")
            testcase.set("classname", "plan_validator")
        tree = ET.ElementTree(testsuites)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception as exc:  # pragma: no cover - file/IO issues
        logger.error("Error writing JUnit report: %s", exc)
        return False


def create_github_annotations(errors: List[str]) -> List[Dict[str, Any]]:
    """Format validation errors as GitHub annotations."""
    annotations = []
    for error in errors:
        annotation = {
            "message": error,
            "annotation_level": "failure",
            "title": "Plan Validation Error",
        }
        file_match = re.search(r"in\s+file\s+['\"]?([^'\"\s]+)['\"]?", error)
        if file_match:
            annotation["path"] = file_match.group(1)
        route_match = re.search(r"Route\s+['\"]([^'\"]+)['\"]", error)
        if route_match:
            annotation["path"] = "api_routes.md"
        if any(x in error.lower() for x in ["warning", "suggest", "recommend", "consider"]):
            annotation["annotation_level"] = "warning"
        annotations.append(annotation)
    return annotations
