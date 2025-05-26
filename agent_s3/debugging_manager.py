"""
Comprehensive Debugging System with Chain of Thought Integration.

This module implements a three-tier debugging strategy with CoT-based context
management for effective error resolution.
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from agent_s3.enhanced_scratchpad_manager import (
    EnhancedScratchpadManager,
    Section,
    LogLevel,
)
from agent_s3.planning_helper import generate_plan_via_workflow
from agent_s3.user_config import load_user_config
from agent_s3.debugging import (
    ErrorCategory,
    DebugAttempt,
    DebuggingPhase,
    ErrorContext,
    ErrorPatternMatcher,
    create_error_context,
    process_test_failure_data,
    execute_generator_quick_fix,
    execute_full_debugging,
    execute_strategic_restart,
)




class DebuggingManager:
    """
    Manages the comprehensive debugging process with three-tier strategy
    and Chain of Thought integration.
    """

    # Constants for debugging configuration
    MAX_GENERATOR_ATTEMPTS = 2  # Tier 1: Quick fixes
    MAX_DEBUGGER_ATTEMPTS = 3   # Tier 2: Full debugging
    MAX_RESTART_ATTEMPTS = 2    # Tier 3: Strategic restart

    def __init__(self, coordinator, enhanced_scratchpad: EnhancedScratchpadManager):
        """
        Initialize the debugging manager.

        Args:
            coordinator: The coordinator instance
            enhanced_scratchpad: Enhanced scratchpad manager for CoT logging
        """
        self.coordinator = coordinator
        self.scratchpad = enhanced_scratchpad

        # Access to tools via coordinator
        self.llm = coordinator.llm if coordinator else None
        self.file_tool = coordinator.file_tool if coordinator else None
        self.code_generator = coordinator.code_generator if coordinator else None
        self.error_context_manager = coordinator.error_context_manager if coordinator else None

        # Set up the logger
        self.logger = logging.getLogger("debugging_manager")

        # Initialize debugging state
        self.current_error: Optional[ErrorContext] = None
        self.current_phase = DebuggingPhase.ANALYSIS
        self.attempt_count = 0
        self.generator_attempts = 0
        self.debugger_attempts = 0
        self.restart_attempts = 0

        # Track diagnostics for generation issues
        self.generation_issue_log: Dict[str, List[Dict[str, Any]]] = {}

        # Track debugging history
        self.debug_history: List[DebugAttempt] = []

        # Error categorization utility
        self.pattern_matcher = ErrorPatternMatcher()

        # Per-user customization of debugging limits
        user_cfg = load_user_config()
        self.MAX_GENERATOR_ATTEMPTS = int(
            user_cfg.get("max_quick_fix_attempts", self.MAX_GENERATOR_ATTEMPTS)
        )
        self.MAX_DEBUGGER_ATTEMPTS = int(
            user_cfg.get("max_full_debug_attempts", self.MAX_DEBUGGER_ATTEMPTS)
        )
        self.MAX_RESTART_ATTEMPTS = int(
            user_cfg.get("max_restart_attempts", self.MAX_RESTART_ATTEMPTS)
        )


    def handle_error(self,
                    error_message: str,
                    traceback_text: str,
                    file_path: Optional[str] = None,
                    line_number: Optional[int] = None,
                    function_name: Optional[str] = None,
                    code_snippet: Optional[str] = None,
                    variables: Optional[Dict[str, Any]] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle an error based on the three-tier debugging strategy.

        Args:
            error_message: The error message
            traceback_text: The error traceback
            file_path: Optional file path where the error occurred
            line_number: Optional line number where the error occurred
            function_name: Optional function name where the error occurred
            code_snippet: Optional code snippet around the error
            variables: Optional dictionary of variable values at error time
            metadata: Optional additional metadata

        Returns:
            Results of debugging attempt
        """
        # Process test-specific structured information if this is a test failure
        test_failure_info = process_test_failure_data(metadata)

        # Create error context with test-specific information if available
        error_context = create_error_context(
            self.pattern_matcher,
            error_message,
            traceback_text,
            file_path or test_failure_info.get("test_file"),
            line_number or test_failure_info.get("line_number"),
            function_name,
            code_snippet,
            variables or test_failure_info.get("variables", {}),
            {**metadata, **test_failure_info} if test_failure_info else metadata,
            error_context_manager=self.error_context_manager,
        )

        # Check if this might be a test issue rather than an implementation issue
        if test_failure_info and test_failure_info.get("possible_bad_test", False):
            self.scratchpad.start_section(Section.WARNING, "DebuggingManager")
            self.scratchpad.log(
                role="DebuggingManager",
                message="Warning: This test failure might indicate an issue with the test itself rather than the implementation.",
                level=LogLevel.WARNING,
                section=Section.WARNING,
                metadata={"failure_category": test_failure_info.get("failure_category", "UNKNOWN")}
            )
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Test: {test_failure_info.get('test_name', 'Unknown')}, File: {test_failure_info.get('test_file', 'Unknown')}",
                level=LogLevel.WARNING,
                section=Section.WARNING
            )

            # Add specific reasons why the test might be problematic
            if test_failure_info.get("failure_category") == "ATTRIBUTE_ERROR":
                self.scratchpad.log(
                    role="DebuggingManager",
                    message="The test appears to be looking for an attribute that doesn't exist, possibly with an unconventional name.",
                    level=LogLevel.WARNING,
                    section=Section.WARNING
                )
            elif test_failure_info.get("expected") and test_failure_info.get("actual"):
                expected = test_failure_info.get("expected", "")
                actual = test_failure_info.get("actual", "")
                if expected and actual and (
                    actual.strip().replace(" ", "") == expected.strip().replace(" ", "") or
                    actual.strip().lower() == expected.strip().lower()
                ):
                    self.scratchpad.log(
                        role="DebuggingManager",
                        message="The expected and actual values differ only in formatting or capitalization.",
                        level=LogLevel.WARNING,
                        section=Section.WARNING
                    )

            self.scratchpad.end_section(Section.WARNING)

            # Add flag to error context
            error_context.metadata["possible_test_issue"] = True

        # Log error in enhanced scratchpad
        self.scratchpad.start_section(Section.ERROR, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Handling error: {error_context.get_summary()}",
            level=LogLevel.ERROR,
            section=Section.ERROR,
            metadata=error_context.to_dict()
        )

        # Log detailed test failure information if available
        if test_failure_info:
            failure_category = test_failure_info.get("failure_category", "UNKNOWN")
            test_name = test_failure_info.get("test_name", "Unknown")
            test_file = test_failure_info.get("test_file", "Unknown")

            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Test Failure Details: {failure_category} in test {test_name} ({test_file})",
                level=LogLevel.ERROR,
                section=Section.ERROR
            )

            if "expected" in test_failure_info and "actual" in test_failure_info:
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Expected: {test_failure_info['expected']}, Actual: {test_failure_info['actual']}",
                    level=LogLevel.ERROR,
                    section=Section.ERROR
                )

        # Determine if this is a continuation of an existing error
        if self.current_error and self.pattern_matcher.is_similar_error(error_context, self.current_error):
            # Update attempt count for this error
            error_context.attempt_number = self.current_error.attempt_number + 1
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Continuing with error (attempt {error_context.attempt_number})",
                level=LogLevel.INFO,
                section=Section.ERROR
            )
        else:
            # Reset counters for new error
            self.generator_attempts = 0
            self.debugger_attempts = 0
            self.restart_attempts = 0
            self.scratchpad.log(
                role="DebuggingManager",
                message="New error detected, starting tier 1 (generator quick fix)",
                level=LogLevel.INFO,
                section=Section.ERROR
            )

        # Update current error
        self.current_error = error_context
        self.attempt_count += 1

        # For test failures that might be test issues, consider different debugging strategy
        if test_failure_info and test_failure_info.get("possible_bad_test", False):
            # For potential test issues, prefer full debugging over quick fixes
            if self.debugger_attempts < self.MAX_DEBUGGER_ATTEMPTS:
                self.current_phase = DebuggingPhase.FULL_DEBUG
                self.debugger_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Potential test issue detected. Using tier 2 (full debug) - attempt {self.debugger_attempts}/{self.MAX_DEBUGGER_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = execute_full_debugging(
                    error_context,
                    self.file_tool,
                    self.coordinator,
                    self.scratchpad,
                    self.logger,
                    self.llm,
                    self.debugger_attempts,
                    self._create_full_debugging_prompt
                )
            else:
                # For persistent test issues, use strategic restart
                self.current_phase = DebuggingPhase.STRATEGIC_RESTART
                self.restart_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Potential test issue not resolved. Using tier 3 (strategic restart) - attempt {self.restart_attempts}/{self.MAX_RESTART_ATTEMPTS}",
                    level=LogLevel.WARNING,
                    section=Section.ERROR
                )
                result = execute_strategic_restart(
                    error_context,
                    self.coordinator,
                    self.scratchpad,
                    self.logger,
                    self.llm,
                    self.debug_history,
                    self.pattern_matcher,
                    self.code_generator,
                    generate_plan_via_workflow
                )
        else:
            # Standard debugging flow for normal errors
            if self.generator_attempts < self.MAX_GENERATOR_ATTEMPTS:
                # Tier 1: Generator quick fix
                self.current_phase = DebuggingPhase.QUICK_FIX
                self.generator_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 1 (quick fix) - attempt {self.generator_attempts}/{self.MAX_GENERATOR_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = execute_generator_quick_fix(
                    error_context,
                    self.file_tool,
                    self.coordinator,
                    self.scratchpad,
                    self.logger,
                    self.llm,
                    self.generator_attempts,
                    self._create_quick_fix_prompt
                )

            elif self.debugger_attempts < self.MAX_DEBUGGER_ATTEMPTS:
                # Tier 2: Full debugging with CoT
                self.current_phase = DebuggingPhase.FULL_DEBUG
                self.debugger_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 2 (full debug) - attempt {self.debugger_attempts}/{self.MAX_DEBUGGER_ATTEMPTS}",
                    level=LogLevel.INFO,
                    section=Section.ERROR
                )
                result = execute_full_debugging(
                    error_context,
                    self.file_tool,
                    self.coordinator,
                    self.scratchpad,
                    self.logger,
                    self.llm,
                    self.debugger_attempts,
                    self._create_full_debugging_prompt
                )

            else:
                # Tier 3: Strategic restart
                self.current_phase = DebuggingPhase.STRATEGIC_RESTART
                self.restart_attempts += 1
                self.scratchpad.log(
                    role="DebuggingManager",
                    message=f"Using tier 3 (strategic restart) - attempt {self.restart_attempts}/{self.MAX_RESTART_ATTEMPTS}",
                    level=LogLevel.WARNING,
                    section=Section.ERROR
                )
                result = execute_strategic_restart(
                    error_context,
                    self.coordinator,
                    self.scratchpad,
                    self.logger,
                    self.llm,
                    self.debug_history,
                    self.pattern_matcher,
                    self.code_generator,
                    generate_plan_via_workflow
                )

        # Record debug attempt
        debug_attempt = DebugAttempt(
            error_context=error_context,
            phase=self.current_phase,
            fix_description=result.get("description", ""),
            code_changes=result.get("changes", {}),
            success=result.get("success", False),
            reasoning=result.get("reasoning", ""),
            metadata=result.get("metadata", {})
        )
        self.debug_history.append(debug_attempt)

        # If successful, reset counters
        if result.get("success", False):
            self.current_error = None
            self.generator_attempts = 0
            self.debugger_attempts = 0
            self.restart_attempts = 0

        # End error section
        self.scratchpad.end_section(Section.ERROR)

        return result


    def _create_quick_fix_prompt(self, error_context: ErrorContext, file_content: str) -> str:
        """Create a prompt for generator quick fix."""
        error_message = error_context.message
        traceback = error_context.traceback
        file_path = error_context.file_path
        line_number = error_context.line_number or "unknown"

        # Tailor prompt based on error category
        category_specific_instructions = {
            ErrorCategory.SYNTAX: "Focus on fixing syntax errors like missing parentheses, brackets, or indentation issues.",
            ErrorCategory.TYPE: "Check for type mismatches, incorrect method calls, or inappropriate operations on the wrong data type.",
            ErrorCategory.IMPORT: "Verify import statements, module names, and package availability.",
            ErrorCategory.ATTRIBUTE: "Check for incorrect attribute or method names, or attributes used on the wrong type of object.",
            ErrorCategory.NAME: "Look for undefined variables, typos in variable names, or scope issues.",
            ErrorCategory.INDEX: "Check for array/list index errors, off-by-one errors, or accessing empty collections.",
            ErrorCategory.VALUE: "Verify input values, format specifiers, or conversion operations."
        }

        specific_instructions = category_specific_instructions.get(
            error_context.category,
            "Analyze the error message and traceback to identify and fix the issue."
        )

        # Context snippet
        context_snippet = ""
        if error_context.code_snippet:
            context_snippet = f"\nRelevant code snippet:\n```\n{error_context.code_snippet}\n```\n"

        # Test failure specific information
        test_failure_info = ""
        if "possible_test_issue" in error_context.metadata:
            # This is a potential test issue
            test_failure_info += (
                "\nNOTE: This error might be related to an issue in the test itself"
                " rather than the implementation code.\n"
            )
            # Add details about the failing test
            if "test_name" in error_context.metadata:
                test_name = error_context.metadata.get("test_name", "Unknown")
                test_file = error_context.metadata.get("test_file", "Unknown")
                test_failure_info += f"Failing Test: {test_name} in {test_file}\n"

            # Add expected vs actual if available
            if "expected" in error_context.metadata and "actual" in error_context.metadata:
                expected = error_context.metadata.get("expected", "Unknown")
                actual = error_context.metadata.get("actual", "Unknown")
                test_failure_info += f"Expected: {expected}\nActual: {actual}\n"

            # Check for common test issues
            if "failure_category" in error_context.metadata:
                failure_category = error_context.metadata.get("failure_category", "UNKNOWN")
                if failure_category == "ATTRIBUTE_ERROR":
                    test_failure_info += (
                        "This might be a case where the test is expecting an attribute "
                        "that doesn't exist or has a different name.\n"
                    )
                elif failure_category == "VALUE_MISMATCH":
                    test_failure_info += (
                        "This might be a formatting issue or a case where the test "
                        "has overly specific expectations.\n"
                    )
                elif failure_category == "IMPORT_ERROR":
                    test_failure_info += (
                        "This might be a missing dependency or incorrectly specified import in the test.\n"
                    )
        # Variables context if available
        variables_context = ""
        if error_context.variables:
            variables_context = "\nVariable values at error time:\n"
            for var_name, var_value in error_context.variables.items():
                variables_context += f"- {var_name}: {var_value}\n"

        # Create the prompt
        prompt = f"""
        You are an expert code debugger tasked with fixing a {error_context.category.name} error.

        File: {file_path}
        Error at line: {line_number}
        Error message: {error_message}

        Traceback:
        {traceback}
        {context_snippet}
        {variables_context}
        {test_failure_info}

        Instructions:
        {specific_instructions}

        Full file content:
        ```
        {file_content}
        ```

        Your task is to:
        1. Analyze the error and determine the cause
        2. Fix the issue with minimal changes
        3. Provide a brief explanation of what was wrong and how you fixed it

        Return your answer in the following format:

        ## Analysis
        <Your analysis of the error>

        ## Fix
        ```
        <Full corrected file content>
        ```

        ## Explanation
        <Brief explanation of the fix>
        """

        return prompt

    def _create_full_debugging_prompt(self,
                                     error_context: ErrorContext,
                                     file_content: str,
                                     related_files: Dict[str, str],
                                     cot_context: List[Dict[str, Any]]) -> str:
        """Create a prompt for full debugging with CoT context."""
        error_message = error_context.message
        traceback = error_context.traceback
        file_path = error_context.file_path
        line_number = error_context.line_number or "unknown"

        # Format variables if available
        variables_section = ""
        if error_context.variables:
            variables_section = "Variable values at error time:\n"
            for var_name, var_value in error_context.variables.items():
                variables_section += f"- {var_name}: {var_value}\n"

        # Format related files
        related_files_section = ""
        if related_files:
            related_files_section = "Related files:\n"
            for path, content in related_files.items():
                related_files_section += f"\n{path}:\n```\n{content[:1000]}"
                if len(content) > 1000:
                    related_files_section += f"\n... (truncated, {len(content) - 1000} more chars)"
                related_files_section += "\n```\n"

        # Format Chain of Thought context
        cot_section = ""
        if cot_context:
            cot_section = "Previous debugging insights:\n"
            for i, entry in enumerate(cot_context, 1):
                relevance = entry.get("relevance_score", 0.0)
                content = entry.get("content", "")
                cot_section += f"\nInsight {i} (relevance: {relevance:.2f}):\n{content}\n"

        # Add attempt information
        attempt_info = f"This is debugging attempt #{error_context.attempt_number} for this error."

        # Test failure specific information
        test_failure_section = ""
        if "failure_category" in error_context.metadata or "test_name" in error_context.metadata:
            failure_category = error_context.metadata.get("failure_category", "UNKNOWN")
            test_name = error_context.metadata.get("test_name", "Unknown")
            test_file = error_context.metadata.get("test_file", "Unknown")

            test_failure_section += "\n## Test Failure Details\n"
            test_failure_section += f"Failure Category: {failure_category}\n"
            test_failure_section += f"Test: {test_name} in {test_file}\n"

            if "assertion" in error_context.metadata:
                test_failure_section += f"Assertion: {error_context.metadata['assertion']}\n"

            if "expected" in error_context.metadata and "actual" in error_context.metadata:
                test_failure_section += f"Expected: {error_context.metadata['expected']}\n"
                test_failure_section += f"Actual: {error_context.metadata['actual']}\n"

            # Include original test code if available in failure_info
            if "failure_info" in error_context.metadata and isinstance(error_context.metadata["failure_info"], list):
                for failure in error_context.metadata["failure_info"]:
                    if failure.get("test_name") == test_name and "code" in failure:
                        test_failure_section += f"\nTest Code:\n```\n{failure['code']}\n```\n"
                        break

            # Include implementation plan for the file if available
            if "file_implementation_plan" in error_context.metadata:
                file_plan = error_context.metadata["file_implementation_plan"]
                test_failure_section += "\n## Implementation Plan for this File\n"
                test_failure_section += f"```json\n{json.dumps(file_plan, indent=2)}\n```\n"

            # Include architecture review if available for relevant context
            if "architecture_review" in error_context.metadata and isinstance(error_context.metadata["architecture_review"], dict):
                arch_review = error_context.metadata["architecture_review"]
                logical_gaps = arch_review.get("logical_gaps", [])
                optimizations = arch_review.get("optimization_suggestions", [])

                if logical_gaps or optimizations:
                    test_failure_section += "\n## Relevant Architecture Review Points\n"

                    if logical_gaps:
                        test_failure_section += "Logical Gaps Identified:\n"
                        for gap in logical_gaps[:2]:  # Limit to avoid overloading
                            if isinstance(gap, dict):
                                test_failure_section += (
                                    f"- {gap.get('description', 'Not specified')}\n"
                                )
                            else:
                                test_failure_section += f"- {gap}\n"

                    if optimizations:
                        test_failure_section += "Optimization Suggestions:\n"
                        for opt in optimizations[:2]:  # Limit to avoid overloading
                            if isinstance(opt, dict):
                                test_failure_section += (
                                    f"- {opt.get('description', 'Not specified')}\n"
                                )
                            else:
                                test_failure_section += f"- {opt}\n"

            # Special guidance for test issues
            if (
                "possible_test_issue" in error_context.metadata
                and error_context.metadata["possible_test_issue"]
            ):
                test_failure_section += "\n## Potential Test Issue Detected\n"
                test_failure_section += (
                    "This failure may indicate a problem with the test rather than the implementation.\n"
                )
                if failure_category == "ATTRIBUTE_ERROR":
                    test_failure_section += (
                        "- The test might be looking for an attribute that doesn't exist or has a different name\n"
                    )
                    test_failure_section += (
                        "- Consider whether to adapt the implementation to match the test's expectations or fix the test\n"
                    )
                elif failure_category == "VALUE_MISMATCH":
                    test_failure_section += (
                        "- The test may have overly rigid expectations about formatting or specific values\n"
                    )
                    test_failure_section += (
                        "- Check if the actual and expected values are semantically equivalent despite textual differences\n"
                    )
                elif failure_category == "IMPORT_ERROR":
                    test_failure_section += (
                        "- There might be a missing dependency or incorrect import in the test\n"
                    )
                    test_failure_section += (
                        "- Verify that all required packages are available and imports have correct paths\n"
                    )
        # Create the prompt
        prompt = f"""
        You are an expert software debugger with deep knowledge of error patterns and fixes, specializing in test-driven development.

        ## Error Information
        - Category: {error_context.category.name}
        - File: {file_path}
        - Line: {line_number}
        - Error message: {error_message}
        - {attempt_info}

        ## Traceback
        {traceback}

        {variables_section}
        {test_failure_section}

        ## File Content
        ```
        {file_content}
        ```

        {related_files_section}

        {cot_section}

        ## Instructions
        1. Carefully analyze the error, focusing on the exact cause
        2. Use the Chain of Thought insights from previous debugging if relevant
        3. Consider all possible fixes, especially those that previous attempts may have missed
        4. Implement the most robust solution, not just a quick fix
        5. You may modify multiple files if necessary to resolve the issue
        6. Explain your reasoning process step by step
        7. If this is a test failure, remember that the human-approved tests are authoritative and your implementation should adapt to pass them

        ## Special Considerations for Test Failures
        - The human-reviewed and approved tests define the required behavior
        - In cases where the test expectations seem unusual, implement code that passes the tests exactly as written
        - Only suggest test modifications if there's a clear technical impossibility (e.g., requesting behavior the language can't support)
        - If you need to adapt code to unusual test expectations, add comments explaining the reason

        ## Response Format

        ### Step-by-Step Analysis
        <Detailed analysis of the error, considering previous debugging attempts>

        ### Root Cause
        <Precise identification of the root cause>

        ### Solution Strategy
        <Explanation of your approach to fixing the issue>

        ### File Fixes
        For each file that needs changes:

        ```filepath:{file_path}
        <Complete fixed file content>
        ```

        Add additional files as needed with the same format.

        ### Explanation
        <Concise explanation of the changes made and why they fix the issue>
        """

        return prompt


    def _extract_code_from_response(self, response: Optional[str]) -> Optional[str]:
        """Extract code from a response."""
        if response is None:
            return ""
        # Look for code blocks with triple backticks
        pattern = r'```(?:\w*\n|\n)?(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Return the largest code block
            return max(matches, key=len)

        # No code blocks found, try to extract a file content section
        pattern = r'## Fix\s*\n(.*?)(?:\n##|\Z)'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Clean up any remaining markdown
            code = matches[0].strip()
            code = re.sub(r'^```\w*\s*', '', code)
            code = re.sub(r'```\s*$', '', code)
            return code

        return None


    def analyze_error(self,
                 error_message: str,
                 traceback_text: str,
                 file_path: Optional[str] = None,
                 line_number: Optional[int] = None,
                 function_name: Optional[str] = None,
                 code_snippet: Optional[str] = None,
                 variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze an error without attempting to fix it.

        Args:
            error_message: The error message
            traceback_text: The error traceback
            file_path: Optional file path where the error occurred
            line_number: Optional line number where the error occurred
            function_name: Optional function name where the error occurred
            code_snippet: Optional code snippet around the error
            variables: Optional dictionary of variable values at error time

        Returns:
            Analysis results including category, severity, and potential fix approaches
        """
        # Create error context
        error_context = create_error_context(
            self.pattern_matcher,
            error_message,
            traceback_text,
            file_path,
            line_number,
            function_name,
            code_snippet,
            variables,
            error_context_manager=self.error_context_manager,
        )

        # Log analysis in enhanced scratchpad
        self.scratchpad.start_section(Section.ANALYSIS, "DebuggingManager")
        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Analyzing error: {error_context.get_summary()}",
            level=LogLevel.INFO,
            section=Section.ANALYSIS,
            metadata=error_context.to_dict()
        )

        # Determine severity based on error category
        severity = "HIGH" if error_context.category in [
            ErrorCategory.MEMORY, ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK, ErrorCategory.DATABASE
        ] else "MEDIUM" if error_context.category in [
            ErrorCategory.RUNTIME, ErrorCategory.ASSERTION,
            ErrorCategory.TYPE, ErrorCategory.ATTRIBUTE
        ] else "LOW"

        # Determine likely fix approach based on category
        fix_approach = "CODE_FIX" if error_context.category in [
            ErrorCategory.SYNTAX, ErrorCategory.TYPE,
            ErrorCategory.NAME, ErrorCategory.ATTRIBUTE,
            ErrorCategory.INDEX, ErrorCategory.VALUE
        ] else "ENVIRONMENT_FIX" if error_context.category in [
            ErrorCategory.IMPORT, ErrorCategory.PERMISSION,
            ErrorCategory.NETWORK, ErrorCategory.DATABASE
        ] else "UNKNOWN"

        # Prepare recommended tier
        recommended_tier = "QUICK_FIX" if error_context.category in [
            ErrorCategory.SYNTAX, ErrorCategory.NAME
        ] else "FULL_DEBUG" if error_context.category in [
            ErrorCategory.TYPE, ErrorCategory.ATTRIBUTE,
            ErrorCategory.INDEX, ErrorCategory.VALUE,
            ErrorCategory.IMPORT
        ] else "STRATEGIC_RESTART"

        # Check for similar errors in history
        similar_errors = []
        for attempt in self.debug_history:
            if self.pattern_matcher.is_similar_error(error_context, attempt.error_context):
                similar_errors.append({
                    "phase": attempt.phase.name,
                    "fix_description": attempt.fix_description,
                    "success": attempt.success,
                    "timestamp": attempt.timestamp
                })

        # Prepare the analysis result
        analysis = {
            "error": {
                "category": error_context.category.name,
                "message": error_message,
                "file_path": file_path,
                "line_number": line_number,
                "function_name": function_name
            },
            "severity": severity,
            "fix_approach": fix_approach,
            "recommended_tier": recommended_tier,
            "similar_errors_found": len(similar_errors),
            "similar_errors": similar_errors,
            "is_likely_fixable": error_context.category not in [
                ErrorCategory.PERMISSION, ErrorCategory.NETWORK,
                ErrorCategory.UNKNOWN
            ] or len(similar_errors) > 0
        }

        self.scratchpad.log(
            role="DebuggingManager",
            message=f"Error analysis complete:\n{json.dumps(analysis, indent=2)}",
            level=LogLevel.INFO,
            section=Section.ANALYSIS
        )
        self.scratchpad.end_section(Section.ANALYSIS)

        return analysis

    def debug_error(self,
                   error_message: str,
                   file_path: str,
                   line_number: Optional[int] = None,
                   traceback_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Simpler facade for handle_error with minimal required parameters.

        Args:
            error_message: The error message
            file_path: File path where the error occurred
            line_number: Optional line number where the error occurred
            traceback_text: Optional error traceback (defaults to error_message if not provided)

        Returns:
            Results of debugging attempt
        """
        # Use error message as traceback if not provided
        if not traceback_text:
            traceback_text = error_message

        return self.handle_error(
            error_message=error_message,
            traceback_text=traceback_text,
            file_path=file_path,
            line_number=line_number
        )

    def get_current_error(self) -> Optional[ErrorContext]:
        """
        Get the current error being debugged.

        Returns:
            The current error context or None if no active debugging
        """
        return self.current_error

    def get_error_history(self,
                         limit: Optional[int] = None,
                         filter_category: Optional[ErrorCategory] = None,
                         filter_success: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Get the history of debugging attempts with optional filtering.

        Args:
            limit: Optional maximum number of entries to return
            filter_category: Optional filter by error category
            filter_success: Optional filter by success status

        Returns:
            List of debugging attempts as dictionaries
        """
        history = self.debug_history.copy()

        # Apply filters
        if filter_category:
            history = [a for a in history if a.error_context.category == filter_category]

        if filter_success is not None:
            history = [a for a in history if a.success == filter_success]

        # Convert to dictionaries
        history_dicts = [a.to_dict() for a in history]

        # Apply limit if provided
        if limit and limit > 0:
            history_dicts = history_dicts[-limit:]

        return history_dicts

    def can_debug_error(self, error_message: str, file_path: Optional[str] = None) -> bool:
        """
        Check if an error is debuggable.

        Args:
            error_message: The error message
            file_path: Optional file path where the error occurred

        Returns:
            True if the error is likely debuggable, False otherwise
        """
        # Create a minimal error context for analysis
        error_context = create_error_context(
            self.pattern_matcher,
            error_message,
            error_message,  # Use message as traceback for minimal context
            error_context_manager=self.error_context_manager,
        )

        # Check if file exists (if provided)
        file_exists = file_path and os.path.exists(file_path)

        # Check if error category is debuggable
        debuggable_category = error_context.category not in [
            ErrorCategory.UNKNOWN,
            ErrorCategory.PERMISSION
        ]

        # Check if we have relevant context
        has_context = bool(file_path) or error_context.category != ErrorCategory.UNKNOWN

        # Check if we've successfully debugged similar errors before
        previous_success = any(
            a.success for a in self.debug_history
            if self.pattern_matcher.is_similar_error(error_context, a.error_context)
        )

        # Error is debuggable if file exists and either:
        # 1. It's a debuggable category and we have context, or
        # 2. We've successfully debugged a similar error before
        return (file_exists and ((debuggable_category and has_context) or previous_success))

    def reset(self) -> None:
        """Reset the debugging manager state."""
        self.current_error = None
        self.current_phase = DebuggingPhase.ANALYSIS
        self.attempt_count = 0
        self.generator_attempts = 0
        self.debugger_attempts = 0
        self.restart_attempts = 0

    def get_debug_stats(self) -> Dict[str, Any]:
        """Get debugging statistics."""
        stats = {
            "total_attempts": self.attempt_count,
            "errors_by_category": {},
            "success_rate": 0.0,
            "average_attempts_per_error": 0.0,
            "tier_success_rates": {
                "quick_fix": 0.0,
                "full_debug": 0.0,
                "strategic_restart": 0.0
            }
        }

        # Skip if no history
        if not self.debug_history:
            return stats

        # Calculate error counts by category
        for attempt in self.debug_history:
            category = attempt.error_context.category.name
            if category not in stats["errors_by_category"]:
                stats["errors_by_category"][category] = 0
            stats["errors_by_category"][category] += 1

        # Calculate success rate
        successful_attempts = sum(1 for a in self.debug_history if a.success)
        stats["success_rate"] = successful_attempts / len(self.debug_history) if self.debug_history else 0.0

        # Calculate average attempts per error
        unique_errors = set()
        for attempt in self.debug_history:
            # Create a unique key for each distinct error
            error_key = (
                attempt.error_context.category,
                attempt.error_context.file_path,
                attempt.error_context.message
            )
            unique_errors.add(error_key)

        if unique_errors:
            stats["average_attempts_per_error"] = len(self.debug_history) / len(unique_errors)

        # Calculate tier success rates
        for phase_name, phase_count, phase_successes in [
            ("quick_fix", 0, 0),
            ("full_debug", 0, 0),
            ("strategic_restart", 0, 0)
        ]:
            phase_attempts = [a for a in self.debug_history if a.phase.name.lower() == phase_name.lower()]
            if phase_attempts:
                success_count = sum(1 for a in phase_attempts if a.success)
                stats["tier_success_rates"][phase_name] = success_count / len(phase_attempts)

        return stats

    def register_generation_issues(self, file_path: str, debug_info: Dict[str, Any]) -> None:
        """Record generation diagnostics for later summarization."""
        if file_path not in self.generation_issue_log:
            self.generation_issue_log[file_path] = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            **debug_info,
        }
        self.generation_issue_log[file_path].append(entry)

        if self.scratchpad:
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Recorded generation issues for {file_path}",
                level=LogLevel.INFO,
                section=Section.DEBUGGING,
                metadata={
                    "issue_count": debug_info.get("issue_count"),
                    "categories": debug_info.get("categorized_issues", []),
                },
            )

    def log_diagnostic_result(self) -> None:
        """Summarize recorded generation issues and log them."""
        if not self.generation_issue_log:
            return

        summary: Dict[str, Dict[str, int]] = {}
        for path, entries in self.generation_issue_log.items():
            file_summary: Dict[str, int] = {}
            for info in entries:
                for cat in info.get("categorized_issues", []):
                    file_summary[cat] = file_summary.get(cat, 0) + 1
            summary[path] = file_summary

        if self.scratchpad:
            self.scratchpad.start_section(Section.ANALYSIS, "DebuggingManager")
            self.scratchpad.log(
                role="DebuggingManager",
                message=f"Generation diagnostic summary:\n{json.dumps(summary, indent=2)}",
                level=LogLevel.INFO,
                section=Section.ANALYSIS,
            )
            self.scratchpad.end_section(Section.ANALYSIS)

        self.generation_issue_log.clear()
