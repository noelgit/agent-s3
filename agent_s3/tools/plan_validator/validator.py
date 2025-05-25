from __future__ import annotations

from typing import Any, Dict, List, Tuple


class PlanValidator:
    """Lightweight validator used in unit tests."""

    def validate_plan_structure(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if "plan" not in plan:
            errors.append("missing required section 'plan'")
            return False, errors
        required = {"architecture_review", "implementation_plan", "testing_strategy"}
        missing = [sec for sec in required if sec not in plan["plan"]]
        if missing:
            errors.append(f"missing required section(s): {', '.join(missing)}")
        return not errors, errors

    def validate_implementation_steps(self, steps: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        for step in steps:
            if not all(k in step for k in ("id", "description", "file_path")):
                errors.append("missing required field in implementation step")
        return not errors, errors

    def validate_architecture_review(self, arch: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if "components" not in arch or not arch.get("components"):
            errors.append("architecture review missing components")
        return not errors, errors

    def validate_testing_strategy(self, testing: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        total = sum(len(v) for v in testing.values() if isinstance(v, list))
        if total == 0:
            errors.append("no tests specified")
        return not errors, errors

    def validate_full_plan(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        is_valid = True
        all_errors: List[str] = []
        sections = plan.get("plan", {})
        checks = [
            self.validate_plan_structure(plan),
            self.validate_implementation_steps(sections.get("implementation_plan", {}).get("steps", [])),
            self.validate_architecture_review(sections.get("architecture_review", {})),
            self.validate_testing_strategy(sections.get("testing_strategy", {})),
        ]
        for valid, errs in checks:
            if not valid:
                is_valid = False
                all_errors.extend(errs)
        return is_valid, all_errors
