"""Code generator for transforming plans into implementation code.

Implements agentic code generation with processing, context management,
validation, refinement, and debugging integration.
"""

import json
import re
import os
import ast
import tempfile
import subprocess
import time
import traceback
import datetime
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
import threading

from .enhanced_scratchpad_manager import LogLevel
from .tools.test_critic.core import TestType, TestVerdict


class CodeGenerator:
    """Generates code based on plans and tests with agentic capabilities."""

    def __init__(self, coordinator):
        """Initialize with a reference to the coordinator."""
        self.coordinator = coordinator
        self.scratchpad = coordinator.scratchpad
        self.debugging_manager = getattr(coordinator, 'debugging_manager', None)

        # Track generation attempts
        self.current_attempt = 0
        self.max_validation_attempts = 3
        self.max_refinement_attempts = 2
        
        # Add context cache
        self._context_cache = {}
        self._context_cache_max_size = 10  # Limit cache size
        self._context_dependency_map = {}  # Track dependencies between files
        self._generation_attempts = {}  # Track generation attempts per file

    def generate_code(self, plan: Dict[str, Any], tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Generates code for all files in the implementation plan.

        Args:
            plan: The consolidated plan dictionary for a feature group.
                  Expected keys: 'implementation_plan', 'tests', 'group_name'.
            tech_stack: Optional dictionary describing the project's tech stack.

        Returns:
            A dictionary mapping file paths to generated code content.
            Will return an empty dictionary if no files could be generated.
        """
        self.scratchpad.log("CodeGenerator", "Starting agentic code generation")

        implementation_plan = plan.get("implementation_plan", {})
        tests = plan.get("tests", {})
        group_name = plan.get("group_name", "Unnamed Group")
        plan_id = plan.get("plan_id", "N/A")

        self.scratchpad.log("CodeGenerator", f"Generating code for feature group: {group_name} (Plan ID: {plan_id})")

        # Extract files from plan
        files = self._extract_files_from_plan(implementation_plan)
        if not files:
            self.scratchpad.log("CodeGenerator", "No files found in implementation plan", level=LogLevel.ERROR)
            return {}  # Return empty dictionary to indicate failure

        self.scratchpad.log("CodeGenerator", f"Found {len(files)} files to generate")

        results = {}

        # Generate files one by one
        for file_path, implementation_details in files:
            self.scratchpad.log("CodeGenerator", f"Processing file {file_path}")

            # Prepare context for this specific file
            context = self._prepare_file_context(file_path, implementation_details)

            # Generate the file
            generated_code = self.generate_file(file_path, implementation_details, tests, context)

            results[file_path] = generated_code

        self.scratchpad.log("CodeGenerator", f"Completed generation of {len(results)} files")
        return results

    def _extract_files_from_plan(self, implementation_plan: Dict[str, Any]) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """Extracts file paths and their implementation details from the implementation plan.

        Args:
            implementation_plan: The implementation plan containing file details

        Returns:
            List of tuples containing (file_path, implementation_details)
        """
        files = []

        try:
            for file_path, details in implementation_plan.items():
                # Ensure the file path is a string and details is a list
                if isinstance(file_path, str) and isinstance(details, list):
                    files.append((file_path, details))
                else:
                    self.scratchpad.log("CodeGenerator", f"Skipping invalid entry in implementation plan: {file_path}", level=LogLevel.WARNING)
        except Exception as e:
            self.scratchpad.log("CodeGenerator", f"Error extracting files from plan: {e}", level=LogLevel.ERROR)

        return files

    def _prepare_file_context(self, file_path: str, implementation_details: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepares context for a file by reading relevant existing files and extracting related information.

        Args:
            file_path: The path of the file being generated
            implementation_details: Details about the functions/classes to implement

        Returns:
            Dictionary containing context information for the file
        """
        self.scratchpad.log("CodeGenerator", f"Preparing context for {file_path}")

        # Check if context is already cached
        cache_key = self._get_context_cache_key(file_path, implementation_details)
        cached_context = self._context_cache.get(cache_key)
        if cached_context and self._is_context_cache_valid(file_path, cached_context):
            self.scratchpad.log("CodeGenerator", f"Using cached context for {file_path}")
            return cached_context

        context = {}

        # Read the existing file if it exists
        try:
            if hasattr(self.coordinator, 'file_tool') and self.coordinator.file_tool:
                if os.path.exists(file_path):
                    existing_code = self.coordinator.file_tool.read_file(file_path)
                    context['existing_code'] = existing_code
                    self.scratchpad.log("CodeGenerator", f"Added existing code for {file_path} to context")
                else:
                    context['existing_code'] = ""
        except Exception as e:
            self.scratchpad.log("CodeGenerator", f"Error reading existing file {file_path}: {e}", level=LogLevel.WARNING)
            context['existing_code'] = ""

        # Extract imports from implementation details
        imports = set()
        for detail in implementation_details:
            if 'imports' in detail:
                if isinstance(detail['imports'], list):
                    imports.update(detail['imports'])
                elif isinstance(detail['imports'], str):
                    imports.add(detail['imports'])

            # Extract imports from function signatures if available
            if 'signature' in detail:
                signature = detail.get('signature', '')
                import_matches = re.findall(r'from\s+(\S+)\s+import\s+|import\s+(\S+)', signature)
                for from_import, direct_import in import_matches:
                    if from_import:
                        imports.add(from_import)
                    if direct_import:
                        imports.add(direct_import)

        context['imports'] = list(imports)

        # Identify and read related files based on imports and directory structure
        related_files = {}

        # First, find dependencies based on imports
        dependency_paths = self._extract_imports_and_dependencies(file_path, context['imports'])

        # Then, find other files in the same directory
        file_dir = os.path.dirname(file_path)
        if hasattr(self.coordinator, 'file_tool') and self.coordinator.file_tool:
            try:
                if os.path.exists(file_dir):
                    dir_files = [os.path.join(file_dir, f) for f in os.listdir(file_dir)
                                if os.path.isfile(os.path.join(file_dir, f)) and f.endswith('.py')]

                    # Add up to 3 most relevant files from the same directory
                    for dep_path in dir_files[:3]:
                        if dep_path != file_path and dep_path not in dependency_paths:
                            dependency_paths.append(dep_path)
            except Exception as e:
                self.scratchpad.log("CodeGenerator", f"Error listing directory {file_dir}: {e}", level=LogLevel.WARNING)

        # Read content for all dependency paths
        for dep_path in dependency_paths:
            try:
                if hasattr(self.coordinator, 'file_tool') and self.coordinator.file_tool:
                    if os.path.exists(dep_path):
                        related_content = self.coordinator.file_tool.read_file(dep_path)
                        if related_content:
                            # Limit content size for context efficiency
                            if len(related_content) > 2000:
                                related_content = related_content[:2000] + "... [truncated]"
                            related_files[dep_path] = related_content
            except Exception as e:
                self.scratchpad.log("CodeGenerator", f"Error reading related file {dep_path}: {e}", level=LogLevel.WARNING)

        context['related_files'] = related_files
        self.scratchpad.log("CodeGenerator", f"Added {len(related_files)} related files to context")

        # Add class and function requirements from implementation details
        functions_to_implement = []
        for detail in implementation_details:
            if 'function' in detail:
                functions_to_implement.append(detail['function'])

        context['functions_to_implement'] = functions_to_implement

        # Calculate dynamic token budget based on model and file complexity
        file_complexity = self._estimate_file_complexity(implementation_details)
        max_tokens = self._get_model_token_capacity()
        token_budget = min(int(max_tokens * 0.75), 6000 + (file_complexity * 1000))
        
        # Prioritize context to fit within token budget
        prioritized_context = self._prioritize_context(context, token_budget)
        
        self.scratchpad.log("CodeGenerator", f"Context preparation complete for {file_path} (complexity: {file_complexity:.1f}, budget: {token_budget} tokens)")

        # Cache the context
        self._cache_context(file_path, prioritized_context, dependency_paths)

        return prioritized_context

    def generate_file(self, file_path: str, implementation_details: List[Dict[str, Any]], tests: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Generates code for a single file with validation and test execution.
        
        Args:
            file_path: Path to the file being generated
            implementation_details: List of details about functions/classes to implement
            tests: Dictionary of tests relevant to this implementation
            context: Additional context information
            
        Returns:
            Generated code as a string
        """
        self.scratchpad.log("CodeGenerator", f"Generating code for {file_path}")
        
        # Extract relevant tests
        relevant_tests = self._extract_relevant_tests(tests, file_path)
        
        # Create system prompt
        system_prompt = f"""You are an expert software engineer generating code for '{file_path}'.
        Generate high-quality, idiomatic Python code based on the implementation details and tests provided.
        Your task is to generate ONLY the code for this specific file, not multiple files.
        
        Follow these requirements:
        1. Include all necessary imports at the top of the file
        2. Implement all specified functions/classes according to details
        3. Add comprehensive docstrings for all public functions and classes
        4. Include proper type hints for all function parameters and return values
        5. Follow PEP 8 style guidelines
        6. Ensure the code will pass the specified tests
        7. Respond only with the code, no explanations
        """
        
        # Create user prompt with implementation details and test requirements
        functions_str = "\n\n".join([
            f"Function: {detail.get('function', 'unnamed')}\n" +
            (f"Signature: {detail.get('signature', 'Not provided')}\n" if 'signature' in detail else "") +
            f"Description: {detail.get('description', 'Not provided')}\n" +
            (f"Imports: {', '.join(detail.get('imports', []))}\n" if detail.get('imports') else "")
            for detail in implementation_details
        ])
        
        test_cases_str = ""
        if relevant_tests:
            unit_tests = relevant_tests.get("unit_tests", [])
            integration_tests = relevant_tests.get("integration_tests", [])
            
            if unit_tests:
                test_cases_str += "\n\nUnit Tests:\n"
                for test in unit_tests:
                    test_cases_str += f"- Test: {test.get('test_name', 'unnamed')}\n"
                    if 'tested_functions' in test:
                        test_cases_str += f"  Tests functions: {', '.join(test['tested_functions'])}\n"
                    if 'code' in test:
                        test_cases_str += f"  Code:\n```python\n{test['code']}\n```\n"
            
            if integration_tests:
                test_cases_str += "\n\nIntegration Tests:\n"
                for test in integration_tests:
                    test_cases_str += f"- Test: {test.get('test_name', 'unnamed')}\n"
                    if 'components_involved' in test:
                        test_cases_str += f"  Components: {', '.join(test['components_involved'])}\n"
                    if 'code' in test:
                        test_cases_str += f"  Code:\n```python\n{test['code']}\n```\n"
        
        # Include existing code if available
        existing_code_str = ""
        if context.get("existing_code"):
            existing_code_str = f"\nExisting code (to modify/extend):\n```python\n{context['existing_code']}\n```"
        
        # Include related files for context
        related_files_str = ""
        if context.get("related_files"):
            related_files_str = "\nRelated files:\n"
            for related_path, content in context.get("related_files", {}).items():
                # Truncate content to keep prompt size manageable
                truncated = content[:1000] + "..." if len(content) > 1000 else content
                related_files_str += f"\nFile: {related_path}\n```python\n{truncated}\n```\n"
        
        user_prompt = f"""Generate the code for file: {file_path}
        
        {existing_code_str}
        
        Implementation details:
        {functions_str}
        
        {test_cases_str}
        
        {related_files_str}
        
        Write the complete code for {file_path} that implements all the specified functionality.
        Ensure your code is properly formatted, well-documented, and will pass all tests.
        """
        
        # Generate code with validation
        generated_code = self._generate_with_validation(file_path, system_prompt, user_prompt)
        
        return generated_code

    def _generate_with_validation(self, file_path: str, system_prompt: str, user_prompt: str, 
                                  max_validation_attempts: int = None) -> str:
        """Generates code with validation and refinement until it passes or reaches max attempts.
        
        Implements a multi-stage process:
        1. Initial code generation
        2. Syntax and linting validation
        3. Test execution and validation
        4. Refinement based on issues (if any)
        
        Args:
            file_path: Path to the file being generated
            system_prompt: System prompt for the LLM
            user_prompt: User prompt containing implementation details
            max_validation_attempts: Maximum number of validation attempts (defaults to class attribute)
        
        Returns:
            Generated and validated code as a string
        """
        self.scratchpad.log("CodeGenerator", f"Generating initial code for {file_path}")
        
        if max_validation_attempts is None:
            max_validation_attempts = self.max_validation_attempts
            
        # Initial generation
        response = self.coordinator.router_agent.call_llm_by_role(
            role='generator',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config={'temperature': 0.2}  # Lower temperature for precision
        )
        
        # Extract code from response
        generated_code = self._extract_code_from_response(response, file_path)
        
        # Validate and refine cycle
        for attempt in range(max_validation_attempts):
            self.scratchpad.log("CodeGenerator", f"Validating generated code (attempt {attempt+1}/{max_validation_attempts})")
            
            # Check for syntax and lint issues
            is_valid, issues = self._validate_generated_code(file_path, generated_code)
            
            if is_valid:
                self.scratchpad.log("CodeGenerator", f"Generated valid code for {file_path}")
                break
            
            self.scratchpad.log("CodeGenerator", f"Validation found issues: {issues}")
            
            if attempt < max_validation_attempts - 1:  # Still have attempts left
                # Refine based on validation issues
                generated_code = self._refine_code(file_path, generated_code, issues)
            else:  # Last attempt, try debugging if available
                if self.debugging_manager:
                    # Collect debug information
                    debug_info = self._collect_debug_info(file_path, generated_code, issues)
                    
                    # Try to debug the generation issue
                    debug_result = self._debug_generation_issue(file_path, debug_info, 'validation_failure')
                    
                    if debug_result.get("success", False) and "fixed_code" in debug_result:
                        self.scratchpad.log("CodeGenerator", f"Applied debugging fix for {file_path}")
                        generated_code = debug_result["fixed_code"]
                        
                        # Verify the fix
                        is_valid, issues = self._validate_generated_code(file_path, generated_code)
                        if is_valid:
                            self.scratchpad.log("CodeGenerator", f"Debugging fix resolved all issues for {file_path}")
                        else:
                            self.scratchpad.log("CodeGenerator", f"Debugging fix still has issues: {issues}", 
                                               level=LogLevel.WARNING)
        
        # Final step: Run tests against our best code (even if it has minor issues)
        test_results = self._run_tests(file_path, generated_code)
        
        if not test_results["success"]:
            self.scratchpad.log("CodeGenerator", f"Tests failed for {file_path}: {test_results['issues']}", 
                               level=LogLevel.WARNING)
            
            # Try to refine based on test failures
            refined_code = self._refine_based_on_test_results(file_path, generated_code, test_results)
            
            # Verify that the refined code is at least syntactically valid
            try:
                ast.parse(refined_code)
                self.scratchpad.log("CodeGenerator", f"Applied test-based refinements for {file_path}")
                generated_code = refined_code
                
                # Run tests one more time
                final_test_results = self._run_tests(file_path, generated_code)
                
                if final_test_results["success"]:
                    self.scratchpad.log("CodeGenerator", f"All tests now pass for {file_path}")
                else:
                    self.scratchpad.log("CodeGenerator", 
                                       f"Some tests still fail after refinement: {final_test_results['issues']}", 
                                       level=LogLevel.WARNING)
            except SyntaxError:
                self.scratchpad.log("CodeGenerator", 
                                   "Test-based refinement produced invalid code, keeping previous version", 
                                   level=LogLevel.WARNING)
        else:
            self.scratchpad.log("CodeGenerator", f"All tests pass for {file_path}")
        
        return generated_code

    def _extract_relevant_tests(self, tests: Dict[str, Any], file_path: str) -> Dict[str, Any]:
        """Extract tests relevant to a specific file.
        
        Args:
            tests: Dictionary of all tests
            file_path: Path to the file being implemented
            
        Returns:
            Dictionary with relevant test definitions
        """
        # Extract base file name without extension for matching
        file_name = os.path.basename(file_path)
        file_base = os.path.splitext(file_name)[0]
        
        # Helper function to check if a test is relevant to this file
        def is_test_relevant(test):
            # Check for direct file path match
            if test.get("file", "").endswith(file_path):
                return True
                
            # Check for module name match (e.g., "test_module.py" matches "module.py")
            if "tested_functions" in test:
                for func in test["tested_functions"]:
                    if file_base in func:
                        return True
                        
            # Check for component involvement in integration tests
            if "components_involved" in test:
                for component in test["components_involved"]:
                    if file_base == component or file_base == component.replace("_", ""):
                        return True
                        
            return False
        
        relevant_tests = {}
        
        # Filter unit tests
        if "unit_tests" in tests:
            relevant_tests["unit_tests"] = [
                test for test in tests.get("unit_tests", [])
                if is_test_relevant(test)
            ]
        
        # Filter integration tests
        if "integration_tests" in tests:
            relevant_tests["integration_tests"] = [
                test for test in tests.get("integration_tests", [])
                if is_test_relevant(test)
            ]
        
        return relevant_tests

    def _extract_code_from_response(self, response: str, file_path: str) -> str:
        """Extract code from an LLM response.
        
        Args:
            response: The LLM response string
            file_path: Path to the file being generated (for context)
            
        Returns:
            Extracted code as a string
        """
        # First try to extract code from markdown code blocks
        code_block_pattern = r'```(?:python)?(?:\s*\n)(.*?)(?:\n```)'
        matches = re.findall(code_block_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
            
        # Fallback: Try to extract the first substantial code-like segment
        lines = response.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            # Skip explanatory text at the beginning
            if not in_code and not line.strip():
                continue
                
            # Start collecting when we see something that looks like code
            if not in_code and (line.strip().startswith('import ') or
                              line.strip().startswith('from ') or
                              line.strip().startswith('def ') or
                              line.strip().startswith('class ') or
                              line.strip().startswith('#')):
                in_code = True
                
            if in_code:
                code_lines.append(line)
                
        if code_lines:
            return '\n'.join(code_lines)
            
        # If nothing else works, return the whole response but log a warning
        self.scratchpad.log("CodeGenerator", f"Could not extract code from LLM response for {file_path}", level=LogLevel.WARNING)
        return response

    def _refine_code(self, file_path: str, original_code: str, validation_issues: List[str]) -> str:
        """Refines code based on validation issues.
        
        Args:
            file_path: Path to the file being refined
            original_code: Current version of the code
            validation_issues: List of validation issues to address
            
        Returns:
            Refined code as a string
        """
        self.scratchpad.log("CodeGenerator", f"Refining code for {file_path}")
        
        system_prompt = """You are an expert software engineer fixing code that has validation issues.
        Review the code and the reported issues carefully.
        Your task is to fix all the issues while preserving the core functionality and structure.
        Return only the fixed code with no explanations or markdown.
        """
        
        user_prompt = f"""The following code for '{file_path}' has validation issues that need to be fixed:
        
```python
{original_code}
```

These are the validation issues that need to be fixed:
{json.dumps(validation_issues, indent=2)}

Please fix the code to address all these issues. Return only the fixed code.
"""
        
        response = self.coordinator.router_agent.call_llm_by_role(
            role='generator',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config={'temperature': 0.1}  # Lower temperature for refinement
        )
        
        # Extract code
        refined_code = self._extract_code_from_response(response, file_path)
        if not refined_code or len(refined_code.strip()) < 10:  # Fallback if extraction fails
            self.scratchpad.log("CodeGenerator", "Refinement returned invalid code, using original", level=LogLevel.WARNING)
            return original_code
            
        return refined_code

    def _collect_debug_info(self, file_path: str, generated_code: str, issues: List[str]) -> Dict[str, Any]:
        """Collects debug information for problematic code generation.
        
        Args:
            file_path: Path to the file with issues
            generated_code: The problematic code
            issues: List of validation issues
            
        Returns:
            Dictionary with debug information
        """
        debug_info = {
            "file_path": file_path,
            "generated_code": generated_code,
            "issues": issues,
            "issue_count": len(issues),
            "timestamp": datetime.datetime.now().isoformat(),
            "issue_categories": {}
        }
        
        # Categorize issues
        syntax_issues = []
        lint_issues = []
        type_issues = []
        test_issues = []
        other_issues = []
        
        for issue in issues:
            if "Syntax error" in issue:
                syntax_issues.append(issue)
            elif "Linting" in issue:
                lint_issues.append(issue) 
            elif "Type checking" in issue:
                type_issues.append(issue)
            elif "Test failure" in issue or "Test '" in issue:
                test_issues.append(issue)
            else:
                other_issues.append(issue)
        
        if syntax_issues:
            debug_info["issue_categories"]["syntax"] = syntax_issues
        if lint_issues:
            debug_info["issue_categories"]["lint"] = lint_issues
        if type_issues:
            debug_info["issue_categories"]["type"] = type_issues
        if test_issues:
            debug_info["issue_categories"]["test"] = test_issues
        if other_issues:
            debug_info["issue_categories"]["other"] = other_issues
            
        # Add summary for quick reference
        debug_info["summary"] = (
            f"{len(syntax_issues)} syntax, {len(lint_issues)} lint, "
            f"{len(type_issues)} type, {len(test_issues)} test issues"
        )
        
        # Critical issues are syntax errors and test failures
        debug_info["critical_issues"] = syntax_issues + test_issues
        
        return debug_info