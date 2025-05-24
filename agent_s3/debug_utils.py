"""Integration helpers for the debugging manager."""
from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List

from .enhanced_scratchpad_manager import LogLevel


class DebugUtils:
    """Assist with collection and analysis of debug information."""

    def __init__(self, debugging_manager: Any, scratchpad: Any) -> None:
        self.debugging_manager = debugging_manager
        self.scratchpad = scratchpad

    def collect_debug_info(self, file_path: str, generated_code: str, issues: List[str]) -> Dict[str, Any]:
        """Collect debug information for problematic code generation."""
        debug_info = {
            "file_path": file_path,
            "generated_code": generated_code,
            "issues": issues,
            "issue_count": len(issues),
            "timestamp": datetime.datetime.now().isoformat(),
            "issue_categories": {},
        }
        syntax_issues: List[str] = []
        lint_issues: List[str] = []
        type_issues: List[str] = []
        test_issues: List[str] = []
        import_issues: List[str] = []
        undefined_issues: List[str] = []
        other_issues: List[str] = []
        for issue in issues:
            if "Syntax error" in issue or "invalid syntax" in issue:
                syntax_issues.append(issue)
            elif "No module named" in issue:
                import_issues.append(issue)
            elif "not defined" in issue or "undefined" in issue:
                undefined_issues.append(issue)
            elif "Linting" in issue:
                lint_issues.append(issue)
            elif "Type checking" in issue or "Incompatible" in issue:
                type_issues.append(issue)
            elif "Test failure" in issue or "Test '" in issue:
                test_issues.append(issue)
            else:
                other_issues.append(issue)
        if syntax_issues:
            debug_info["issue_categories"]["syntax"] = syntax_issues
        if import_issues:
            debug_info["issue_categories"]["import"] = import_issues
        if undefined_issues:
            debug_info["issue_categories"]["undefined"] = undefined_issues
        if lint_issues:
            debug_info["issue_categories"]["lint"] = lint_issues
        if type_issues:
            debug_info["issue_categories"]["type"] = type_issues
        if test_issues:
            debug_info["issue_categories"]["test"] = test_issues
        if other_issues:
            debug_info["issue_categories"]["other"] = other_issues
        debug_info["summary"] = (
            f"{len(syntax_issues)} syntax, {len(lint_issues)} lint, "
            f"{len(type_issues)} type, {len(test_issues)} test issues"
        )
        debug_info["critical_issues"] = syntax_issues + import_issues + undefined_issues + test_issues
        return debug_info

    def debug_generation_issue(self, file_path: str, info: Any, issues: Any) -> Dict[str, Any]:
        """Provide diagnostics for generation issues and integrate with debugging manager."""
        if isinstance(info, dict) and isinstance(issues, str):
            debug_info = info
        else:
            generated_code = info
            issues_list = issues if isinstance(issues, list) else [issues]
            debug_info = self.collect_debug_info(file_path, generated_code, issues_list)
        debug_info["categorized_issues"] = list(debug_info.get("issue_categories", {}).keys())
        suggested: List[Dict[str, str]] = []
        for issue in debug_info.get("issues", []):
            suggestion = "Review the issue"
            if "No module named" in issue:
                mod = re.search(r"No module named '([^']+)'", issue)
                if mod:
                    suggestion = f"Install or add module '{mod.group(1)}'"
            elif "not defined" in issue or "undefined" in issue:
                name_match = re.search(r"'([^']+)'", issue)
                if name_match:
                    suggestion = f"Define '{name_match.group(1)}' before use"
            elif "Syntax error" in issue or "invalid syntax" in issue:
                suggestion = "Fix the syntax near the referenced line"
            elif "Incompatible" in issue or "type" in issue.lower():
                suggestion = "Check type annotations and return values"
            suggested.append({"issue": issue, "suggestion": suggestion})
        debug_info["suggested_fixes"] = suggested
        fixed_code = None
        if self.debugging_manager:
            if hasattr(self.debugging_manager, "register_generation_issues"):
                self.debugging_manager.register_generation_issues(file_path, debug_info)
            if hasattr(self.debugging_manager, "analyze_issue"):
                try:
                    analysis_result = self.debugging_manager.analyze_issue(file_path, debug_info)
                    if isinstance(analysis_result, dict):
                        if analysis_result.get("analysis"):
                            debug_info["analysis"] = analysis_result["analysis"]
                        if analysis_result.get("suggested_fixes"):
                            debug_info.setdefault("suggested_fixes", []).extend(analysis_result.get("suggested_fixes"))
                        fixed_code = analysis_result.get("fixed_code")
                except Exception as e:  # pragma: no cover - best effort
                    self.scratchpad.log("DebugUtils", f"Debugging manager analyze_issue failed: {e}", level=LogLevel.WARNING)
            if hasattr(self.debugging_manager, "log_diagnostic_result"):
                self.debugging_manager.log_diagnostic_result()
        if fixed_code:
            return {"success": True, "fixed_code": fixed_code}
        return debug_info
