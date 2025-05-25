"""Validation helpers for generated code."""
from __future__ import annotations

import ast
import json
import os
import re
import tempfile
from typing import Any, Dict, List, Tuple


class CodeValidator:
    """Run validation checks and project tests."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad

    def validate_generated_code(self, file_path: str, generated_code: str) -> Tuple[bool, List[str]]:
        """Validate generated code with syntax, linting and type checks."""
        issues: List[str] = []
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e.msg}")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".py")
        try:
            tmp.write(generated_code.encode())
            tmp.flush()
            if hasattr(self.coordinator, "bash_tool") and self.coordinator.bash_tool:
                rc, output = self.coordinator.bash_tool.run_command(f"flake8 {tmp.name}")
                if rc != 0 and output:
                    issues.extend([f"Linting: {line}" for line in output.splitlines() if line.strip()])

                rc, output = self.coordinator.bash_tool.run_command(f"python -m mypy {tmp.name}")
                if rc != 0 and output:
                    issues.extend([f"Type checking: {line}" for line in output.splitlines() if line.strip()])
        finally:
            tmp.close()
            os.unlink(tmp.name)
        return len(issues) == 0, issues

    def run_tests(self, file_path: str, generated_code: str) -> Dict[str, Any]:
        """Run project tests and return structured results."""
        if hasattr(self.coordinator, "test_runner_tool") and self.coordinator.test_runner_tool:
            try:
                return self.coordinator.test_runner_tool.run_tests()
            except Exception as e:
                return {"success": False, "issues": [str(e)]}
        if hasattr(self.coordinator, "bash_tool") and self.coordinator.bash_tool:
            rc, output = self.coordinator.bash_tool.run_command("python -m pytest -v")
            success = rc == 0
            result = {"success": success, "output": output}
            if not success:
                result["issues"] = output.splitlines()
            return result
        return {"success": True, "message": "No test runner available"}

    def refine_based_on_test_results(self, file_path: str, code: str, test_results: Dict[str, Any]) -> str:
        """Refine generated code based on failing test results."""
        failures = test_results.get("failure_info") or test_results.get("issues", [])
        details = json.dumps(failures, indent=2)
        system_prompt = "You are a developer fixing code to satisfy failing tests."
        user_prompt = (
            f"The following code for '{file_path}' fails tests:\n```python\n{code}\n```\n\n"
            f"Test failures:\n{details}\n\nPlease update the code so that the tests pass. Return only the fixed code."
        )
        response = self.coordinator.router_agent.call_llm_by_role(
            role="generator",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config={"temperature": 0.1},
        )
        refined = self._extract_code_from_response(response, file_path)
        return refined if refined else code

    def _extract_code_from_response(self, response: str, file_path: str) -> str:
        code_block_pattern = r"```(?:python)?(?:\s*\n)(.*?)(?:\n```)"
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()
        return response
