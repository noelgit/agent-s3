"""Quick fix debugging strategy module.

This module contains the quick fix debugging tier implementation.
Tier 1: Minimal context, focused on simple issues like syntax errors.
"""

import os
import time
from typing import Dict, Any

from ..llm_utils import cached_call_llm
from ..enhanced_scratchpad_manager import Section, LogLevel
from .response_parsers import extract_code_from_response, extract_reasoning_from_response


def execute_generator_quick_fix(
    error_context,
    file_tool,
    coordinator,
    scratchpad,
    logger,
    llm,
    generator_attempts: int,
    create_quick_fix_prompt_func
) -> Dict[str, Any]:
    """
    Execute a quick fix using the code generator.

    Tier 1: Minimal context, focused on simple issues like syntax errors.

    Args:
        error_context: The error context to debug
        file_tool: File tool for reading/writing files
        coordinator: Coordinator instance for config access
        scratchpad: Enhanced scratchpad manager for logging
        logger: Logger instance
        llm: LLM instance for API calls
        generator_attempts: Number of generator attempts made
        create_quick_fix_prompt_func: Function to create quick fix prompts

    Returns:
        Results of the debugging attempt
    """
    start_time = time.time()

    scratchpad.log(
        role="DebuggingManager",
        message="Executing generator quick fix",
        level=LogLevel.INFO,
        section=Section.DEBUGGING
    )

    # Check if we have a file to fix
    if not error_context.file_path or not os.path.exists(error_context.file_path):
        return {
            "success": False,
            "description": "Cannot execute quick fix: missing or invalid file path",
            "reasoning": "Generator quick fix requires a valid file path to modify."
        }

    # Read the file content
    try:
        file_content = file_tool.read_file(error_context.file_path)
        if not file_content:
            return {
                "success": False,
                "description": "Cannot execute quick fix: unable to read file",
                "reasoning": "Failed to read file contents for quick fix."
            }
    except Exception as e:
        return {
            "success": False,
            "description": f"Cannot execute quick fix: error reading file: {e}",
            "reasoning": "Failed to read file contents for quick fix."
        }

    # Prepare the quick fix prompt
    prompt = create_quick_fix_prompt_func(error_context, file_content)

    # Start reasoning section in scratchpad
    scratchpad.start_section(Section.REASONING, "DebuggingManager")
    scratchpad.log(
        role="DebuggingManager",
        message="Generator Quick Fix Reasoning",
        level=LogLevel.INFO,
        section=Section.REASONING
    )

    # Call LLM for quick fix
    try:
        result = cached_call_llm(prompt, llm, **coordinator.config.config)

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            scratchpad.log(
                role="DebuggingManager",
                message=f"Generator quick fix failed: {error_msg}",
                level=LogLevel.ERROR,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": f"Quick fix failed: {error_msg}",
                "reasoning": "LLM call failed during quick fix attempt."
            }

        response = result.get('response', '')

        # Log reasoning
        scratchpad.log(
            role="DebuggingManager",
            message=f"Generator reasoning:\n{response}",
            level=LogLevel.INFO,
            section=Section.REASONING
        )

        # Extract the fixed code
        fixed_code = extract_code_from_response(response)
        if not fixed_code:
            scratchpad.log(
                role="DebuggingManager",
                message="Could not extract fixed code from response",
                level=LogLevel.WARNING,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": "Quick fix failed: could not extract fixed code",
                "reasoning": response
            }

        # Extract reasoning
        reasoning = extract_reasoning_from_response(response)

        # End reasoning section
        scratchpad.end_section(Section.REASONING)

        # Apply the fix
        try:
            file_tool.write_file(error_context.file_path, fixed_code)

            # Calculate duration
            duration = time.time() - start_time

            return {
                "success": True,
                "description": f"Applied quick fix to {os.path.basename(error_context.file_path)}",
                "reasoning": reasoning,
                "changes": {error_context.file_path: fixed_code},
                "duration_seconds": duration,
                "metadata": {
                    "tier": "generator_quick_fix",
                    "attempt": generator_attempts,
                    "modified_files": [error_context.file_path]
                }
            }
        except Exception as e:
            scratchpad.log(
                role="DebuggingManager",
                message=f"Error applying quick fix: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Error applying quick fix: {e}",
                "reasoning": reasoning,
                "changes": {error_context.file_path: fixed_code}
            }

    except Exception as e:
        scratchpad.log(
            role="DebuggingManager",
            message=f"Error during generator quick fix: {e}",
            level=LogLevel.ERROR,
            section=Section.REASONING
        )
        scratchpad.end_section(Section.REASONING)
        return {
            "success": False,
            "description": f"Quick fix error: {e}",
            "reasoning": "Exception occurred during quick fix attempt."
        }
