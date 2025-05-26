"""Code generator for transforming plans into implementation code."""
from __future__ import annotations

import json
import re
import os
import ast
from typing import Any, Dict, List, Optional, Tuple

from .enhanced_scratchpad_manager import LogLevel
from .tools.context_management.context_manager import ContextManager
from .code_validator import CodeValidator
from .debug_utils import DebugUtils


class CodeGenerator:
    """Generates code for implementation plans."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad
        self.debugging_manager = getattr(coordinator, "debugging_manager", None)
        self.llm = getattr(coordinator, "llm", None)
        self.context_manager = ContextManager(coordinator)
        self.validator = CodeValidator(coordinator)
        self.debug_utils = DebugUtils(self.debugging_manager, self.scratchpad)
        self.max_validation_attempts = 3
        self.max_refinement_attempts = 2
        self._generation_attempts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    def generate_code(self, plan: Dict[str, Any], tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Generate code for all files in the implementation plan."""
        self.scratchpad.log("CodeGenerator", "Starting agentic code generation")
        implementation_plan = plan.get("implementation_plan", {})
        tests = plan.get("tests", {})
        group_name = plan.get("group_name", "Unnamed Group")
        plan_id = plan.get("plan_id", "N/A")
        self.scratchpad.log(
            "CodeGenerator", f"Generating code for feature group: {group_name} (Plan ID: {plan_id})"
        )
        files = self._extract_files_from_plan(implementation_plan)
        if not files:
            self.scratchpad.log(
                "CodeGenerator", "No files found in implementation plan", level=LogLevel.ERROR
            )
            return {}
        results: Dict[str, str] = {}
        for file_path, implementation_details in files:
            self.scratchpad.log("CodeGenerator", f"Processing file {file_path}")
            context = self.context_manager.prepare_file_context(file_path, implementation_details)
            generated_code = self.generate_file(file_path, implementation_details, tests, context)
            results[file_path] = generated_code
        self.scratchpad.log("CodeGenerator", f"Completed generation of {len(results)} files")
        return results

    # ------------------------------------------------------------------
    def _extract_files_from_plan(self, implementation_plan: Dict[str, Any]) -> List[Tuple[str, List[Dict[str, Any]]]]:
        files: List[Tuple[str, List[Dict[str, Any]]]] = []
        try:
            for file_path, details in implementation_plan.items():
                if isinstance(file_path, str) and isinstance(details, list):
                    files.append((file_path, details))
                else:
                    self.scratchpad.log(
                        "CodeGenerator",
                        f"Skipping invalid entry in implementation plan: {file_path}",
                        level=LogLevel.WARNING,
                    )
        except Exception as e:  # pragma: no cover - defensive
            self.scratchpad.log("CodeGenerator", f"Error extracting files from plan: {e}", level=LogLevel.ERROR)
        return files

    # ------------------------------------------------------------------
    def generate_file(
        self,
        file_path: str,
        implementation_details: List[Dict[str, Any]],
        tests: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Generate code for a single file with validation and tests."""
        system_prompt = self.context_manager.create_generation_prompt(context)
        functions_str = "\n\n".join(
            [
                f"Function: {d.get('function', 'unnamed')}\n"
                + (f"Signature: {d.get('signature', 'Not provided')}\n" if 'signature' in d else "")
                + f"Description: {d.get('description', 'Not provided')}\n"
                + (f"Imports: {', '.join(d.get('imports', []))}\n" if d.get('imports') else "")
                for d in implementation_details
            ]
        )
        relevant_tests = self._extract_relevant_tests(tests, file_path)
        test_cases_str = ""
        if relevant_tests:
            unit_tests = relevant_tests.get("unit_tests", [])
            integration_tests = relevant_tests.get("integration_tests", [])
            if unit_tests:
                test_cases_str += "\n\nUnit Tests:\n"
                for test in unit_tests:
                    test_cases_str += f"- Test: {test.get('test_name', 'unnamed')}\n"
                    if "tested_functions" in test:
                        test_cases_str += f"  Tests functions: {', '.join(test['tested_functions'])}\n"
                    if "code" in test:
                        test_cases_str += f"  Code:\n```python\n{test['code']}\n```\n"
            if integration_tests:
                test_cases_str += "\n\nIntegration Tests:\n"
                for test in integration_tests:
                    test_cases_str += f"- Test: {test.get('test_name', 'unnamed')}\n"
                    if "components_involved" in test:
                        test_cases_str += f"  Components: {', '.join(test['components_involved'])}\n"
                    if "code" in test:
                        test_cases_str += f"  Code:\n```python\n{test['code']}\n```\n"
        existing_code_str = ""
        if context.get("existing_code"):
            existing_code_str = f"\nExisting code (to modify/extend):\n```python\n{context['existing_code']}\n```"
        related_files_str = ""
        if context.get("related_files"):
            related_files_str = "\nRelated files:\n"
            for related_path, content in context.get("related_files", {}).items():
                truncated = content[:1000] + "..." if len(content) > 1000 else content
                related_files_str += f"\nFile: {related_path}\n```python\n{truncated}\n```\n"
        user_prompt = (
            f"Generate the code for file: {file_path}\n\n{existing_code_str}\n\nImplementation details:\n{functions_str}\n"
            f"{test_cases_str}\n{related_files_str}\nWrite the complete code for {file_path} that implements all the specified functionality."
        )
        generated_code = self._generate_with_validation(file_path, system_prompt, user_prompt)
        return generated_code

    # ------------------------------------------------------------------
    def _generate_with_validation(
        self, file_path: str, system_prompt: str, user_prompt: str, max_validation_attempts: Optional[int] = None
    ) -> str:
        self.scratchpad.log("CodeGenerator", f"Generating initial code for {file_path}")
        if max_validation_attempts is None:
            max_validation_attempts = self.max_validation_attempts
        response = self.coordinator.router_agent.call_llm_by_role(
            role="generator", system_prompt=system_prompt, user_prompt=user_prompt, config={"temperature": 0.2}
        )
        generated_code = self._extract_code_from_response(response, file_path)
        for attempt in range(max_validation_attempts):
            self.scratchpad.log(
                "CodeGenerator", f"Validating generated code (attempt {attempt + 1}/{max_validation_attempts})"
            )
            is_valid, issues = self.validator.validate_generated_code(file_path, generated_code)
            if is_valid:
                self.scratchpad.log("CodeGenerator", f"Generated valid code for {file_path}")
                break
            self.scratchpad.log("CodeGenerator", f"Validation found issues: {issues}")
            if attempt < max_validation_attempts - 1:
                generated_code = self._refine_code(file_path, generated_code, issues)
            else:
                debug_info = self.debug_utils.collect_debug_info(file_path, generated_code, issues)
                debug_result = self.debug_utils.debug_generation_issue(file_path, debug_info, "validation_failure")
                if debug_result.get("success") and "fixed_code" in debug_result:
                    generated_code = debug_result["fixed_code"]
                    is_valid, issues = self.validator.validate_generated_code(file_path, generated_code)
                    if is_valid:
                        self.scratchpad.log(
                            "CodeGenerator", f"Debugging fix resolved all issues for {file_path}"
                        )
                    else:
                        self.scratchpad.log(
                            "CodeGenerator", f"Debugging fix still has issues: {issues}", level=LogLevel.WARNING
                        )
        test_results = self.validator.run_tests(file_path, generated_code)
        if not test_results.get("success", True):
            self.scratchpad.log(
                "CodeGenerator", f"Tests failed for {file_path}: {test_results.get('issues')}", level=LogLevel.WARNING
            )
            refined_code = self.validator.refine_based_on_test_results(file_path, generated_code, test_results)
            try:
                ast.parse(refined_code)
                generated_code = refined_code
                final_results = self.validator.run_tests(file_path, generated_code)
                if final_results.get("success", False):
                    self.scratchpad.log("CodeGenerator", f"All tests now pass for {file_path}")
                else:
                    self.scratchpad.log(
                        "CodeGenerator",
                        f"Some tests still fail after refinement: {final_results.get('issues')}",
                        level=LogLevel.WARNING,
                    )
            except SyntaxError:
                self.scratchpad.log(
                    "CodeGenerator",
                    "Test-based refinement produced invalid code, keeping previous version",
                    level=LogLevel.WARNING,
                )
        else:
            self.scratchpad.log("CodeGenerator", f"All tests pass for {file_path}")
        return generated_code

    # ------------------------------------------------------------------
    @staticmethod
    def _extract_code_from_response(response: str, file_path: str) -> str:
        code_block_pattern = r"```(?:python)?(?:\s*\n)(.*?)(?:\n```)"
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()
        lines = response.split("\n")
        code_lines: List[str] = []
        in_code = False
        for line in lines:
            if not in_code and not line.strip():
                continue
            if not in_code and (
                line.strip().startswith("import ")
                or line.strip().startswith("from ")
                or line.strip().startswith("def ")
                or line.strip().startswith("class ")
                or line.strip().startswith("#")
            ):
                in_code = True
            if in_code:
                code_lines.append(line)
        if code_lines:
            return "\n".join(code_lines)
        return response

    # ------------------------------------------------------------------
    def _refine_code(self, file_path: str, original_code: str, validation_issues: List[str]) -> str:
        self.scratchpad.log("CodeGenerator", f"Refining code for {file_path}")
        system_prompt = (
            "You are an expert software engineer fixing code that has validation issues.\n"
            "Review the code and the reported issues carefully.\n"
            "Return only the fixed code with no explanations or markdown."
        )
        user_prompt = (
            f"The following code for '{file_path}' has validation issues that need to be fixed:\n\n"
            f"```python\n{original_code}\n```\n\nThese are the validation issues that need to be fixed:\n"
            f"{json.dumps(validation_issues, indent=2)}\n\nPlease fix the code and return only the fixed code."
        )
        response = self.coordinator.router_agent.call_llm_by_role(
            role="generator", system_prompt=system_prompt, user_prompt=user_prompt, config={"temperature": 0.1}
        )
        refined_code = self._extract_code_from_response(response, file_path)
        if not refined_code or len(refined_code.strip()) < 10:
            self.scratchpad.log(
                "CodeGenerator", "Refinement returned invalid code, using original", level=LogLevel.WARNING
            )
            return original_code
        return refined_code

    # ------------------------------------------------------------------
    def _extract_relevant_tests(self, tests: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        file_name = os.path.basename(file_path)
        file_base = os.path.splitext(file_name)[0]

        def is_test_relevant(test: Dict[str, Any]) -> bool:
            if test.get("file", "").endswith(file_path):
                return True
            if "tested_functions" in test:
                for func in test["tested_functions"]:
                    if file_base in func:
                        return True
            if "components_involved" in test:
                for component in test["components_involved"]:
                    if file_base == component or file_base == component.replace("_", ""):
                        return True
            return False

        relevant_tests: Dict[str, Any] = {}
        if "unit_tests" in tests:
            relevant_tests["unit_tests"] = [test for test in tests.get("unit_tests", []) if is_test_relevant(test)]
        if "integration_tests" in tests:
            relevant_tests["integration_tests"] = [
                test for test in tests.get("integration_tests", []) if is_test_relevant(test)
            ]
        return relevant_tests
