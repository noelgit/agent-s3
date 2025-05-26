"""Full debugging strategy module.

This module contains the full debugging tier implementation.
Tier 2: Comprehensive analysis with historical context.
"""

import os
import time
from typing import Dict, Any

from ..llm_utils import cached_call_llm
from ..enhanced_scratchpad_manager import Section, LogLevel
from .response_parsers import extract_reasoning_from_response, extract_multi_file_fixes
from .context_helpers import get_related_files, is_safe_new_file


def execute_full_debugging(
    error_context,
    file_tool,
    coordinator,
    scratchpad,
    logger,
    llm,
    debugger_attempts: int,
    create_full_debugging_prompt_func
) -> Dict[str, Any]:
    """
    Execute full debugging with Chain of Thought context.

    Tier 2: Comprehensive analysis with historical context.

    Args:
        error_context: The error context to debug
        file_tool: File tool for reading/writing files
        coordinator: Coordinator instance for config access
        scratchpad: Enhanced scratchpad manager for logging
        logger: Logger instance
        llm: LLM instance for API calls
        debugger_attempts: Number of debugger attempts made
        create_full_debugging_prompt_func: Function to create full debugging prompts

    Returns:
        Results of the debugging attempt
    """
    start_time = time.time()

    scratchpad.log(
        role="DebuggingManager",
        message="Executing full debugging with CoT",
        level=LogLevel.INFO,
        section=Section.DEBUGGING
    )

    # Check if we have a file to fix
    if not error_context.file_path or not os.path.exists(error_context.file_path):
        return {
            "success": False,
            "description": "Cannot execute debugging: missing or invalid file path",
            "reasoning": "Full debugging requires a valid file path to modify."
        }

    # Read the file content
    try:
        file_content = file_tool.read_file(error_context.file_path)
        if not file_content:
            return {
                "success": False,
                "description": "Cannot execute debugging: unable to read file",
                "reasoning": "Failed to read file contents for debugging."
            }
    except Exception as e:
        return {
            "success": False,
            "description": f"Cannot execute debugging: error reading file: {e}",
            "reasoning": "Failed to read file contents for debugging."
        }

    # Get related files based on imports or references
    related_files = get_related_files(error_context.file_path, file_content, file_tool)

    # Extract Chain of Thought context relevant to this error
    cot_context = scratchpad.extract_cot_for_debugging(
        error_context.message + "\n" + error_context.traceback,
        max_entries=5
    )

    # Prepare the full debugging prompt with CoT context
    prompt = create_full_debugging_prompt_func(
        error_context,
        file_content,
        related_files,
        cot_context
    )

    # Start reasoning section in scratchpad
    scratchpad.start_section(Section.REASONING, "DebuggingManager")
    scratchpad.log(
        role="DebuggingManager",
        message="Full Debugging Reasoning",
        level=LogLevel.INFO,
        section=Section.REASONING
    )

    # Call LLM for debugging
    try:
        result = cached_call_llm(prompt, llm, **coordinator.config.config)

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            scratchpad.log(
                role="DebuggingManager",
                message=f"Full debugging failed: {error_msg}",
                level=LogLevel.ERROR,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": f"Debugging failed: {error_msg}",
                "reasoning": "LLM call failed during debugging attempt."
            }

        response = result.get('response', '')

        # Log reasoning
        scratchpad.log(
            role="DebuggingManager",
            message=f"Debugging reasoning:\n{response}",
            level=LogLevel.INFO,
            section=Section.REASONING
        )

        # Extract fixes for all files
        fixes = extract_multi_file_fixes(response, error_context)
        if not fixes:
            scratchpad.log(
                role="DebuggingManager",
                message="Could not extract file fixes from response",
                level=LogLevel.WARNING,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": "Debugging failed: could not extract fixes",
                "reasoning": response
            }

        # Extract reasoning
        reasoning = extract_reasoning_from_response(response)

        # End reasoning section
        scratchpad.end_section(Section.REASONING)

        # Apply the fixes
        try:
            for file_path, content in fixes.items():
                # Validate file path - must exist or be in expected directories
                if not os.path.exists(file_path) and not is_safe_new_file(file_path, error_context.file_path):
                    scratchpad.log(
                        role="DebuggingManager",
                        message=f"Skipping invalid file path: {file_path}",
                        level=LogLevel.WARNING
                    )
                    continue

                file_tool.write_file(file_path, content)

            # Calculate duration
            duration = time.time() - start_time

            # Return success if we applied at least one fix
            if fixes:
                return {
                    "success": True,
                    "description": f"Applied fixes to {len(fixes)} files",
                    "reasoning": reasoning,
                    "changes": fixes,
                    "duration_seconds": duration,
                    "metadata": {
                        "tier": "full_debugging",
                        "attempt": debugger_attempts,
                        "modified_files": list(fixes.keys())
                    }
                }
            else:
                return {
                    "success": False,
                    "description": "No valid fixes found to apply",
                    "reasoning": reasoning
                }
        except Exception as e:
            scratchpad.log(
                role="DebuggingManager",
                message=f"Error applying debugging fixes: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Error applying debugging fixes: {e}",
                "reasoning": reasoning,
                "changes": fixes
            }

    except Exception as e:
        scratchpad.log(
            role="DebuggingManager",
            message=f"Error during full debugging: {e}",
            level=LogLevel.ERROR,
            section=Section.REASONING
        )
        scratchpad.end_section(Section.REASONING)
        return {
            "success": False,
            "description": f"Debugging error: {e}",
            "reasoning": "Exception occurred during debugging attempt."
        }
