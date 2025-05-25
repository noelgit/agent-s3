"""Strategic restart debugging module.

This module contains the strategic restart tier implementation.
Tier 3: More extensive changes, preserving error context.
"""

import time
from typing import Dict, Any, Tuple
from enum import Enum

from ..llm_utils import cached_call_llm
from ..enhanced_scratchpad_manager import Section, LogLevel
from .response_parsers import extract_json_from_response


class RestartStrategy(Enum):
    """Restart strategy options for strategic debugging."""
    REGENERATE_CODE = "regenerate_code"
    REDESIGN_PLAN = "redesign_plan"
    MODIFY_REQUEST = "modify_request"


def execute_strategic_restart(
    error_context,
    coordinator,
    scratchpad,
    logger,
    llm,
    debug_history,
    pattern_matcher,
    code_generator,
    generate_plan_via_workflow_func
) -> Dict[str, Any]:
    """
    Execute strategic restart when other debugging tiers fail.

    Tier 3: More extensive changes, preserving error context.

    Args:
        error_context: The error context to debug
        coordinator: Coordinator instance
        scratchpad: Enhanced scratchpad manager for logging
        logger: Logger instance
        llm: LLM instance for API calls
        debug_history: List of previous debugging attempts
        pattern_matcher: Error pattern matcher
        code_generator: Code generator instance
        generate_plan_via_workflow_func: Function to generate plans

    Returns:
        Results of the restart attempt
    """
    scratchpad.log(
        role="DebuggingManager",
        message="Executing strategic restart",
        level=LogLevel.WARNING,
        section=Section.DEBUGGING
    )

    # Start decision reasoning section in scratchpad
    scratchpad.start_section(Section.DECISION, "DebuggingManager")

    # Determine restart strategy
    strategy, reasoning = _determine_restart_strategy(error_context, debug_history)

    scratchpad.log(
        role="DebuggingManager",
        message=f"Selected restart strategy: {strategy.name}\nReasoning: {reasoning}",
        level=LogLevel.INFO,
        section=Section.DECISION
    )

    scratchpad.end_section(Section.DECISION)

    # Execute the selected strategy
    if strategy == RestartStrategy.REGENERATE_CODE:
        return _execute_code_regeneration(
            error_context, coordinator, scratchpad, code_generator
        )
    elif strategy == RestartStrategy.REDESIGN_PLAN:
        return _execute_plan_redesign(
            error_context, coordinator, scratchpad, code_generator, generate_plan_via_workflow_func
        )
    else:  # MODIFY_REQUEST
        return _execute_request_modification(
            error_context, coordinator, scratchpad, llm, debug_history, code_generator, generate_plan_via_workflow_func
        )


def _determine_restart_strategy(error_context, debug_history) -> Tuple[RestartStrategy, str]:
    """Determine the most appropriate restart strategy for the error."""
    # Default strategy
    strategy = RestartStrategy.REGENERATE_CODE

    # Gather context for decision
    error_history = [attempt for attempt in debug_history
                    if attempt.error_context.category == error_context.category]

    # If we have previous similar errors after regenerating code, escalate
    regenerate_attempts = [a for a in error_history
                          if a.metadata.get("restart_strategy") == RestartStrategy.REGENERATE_CODE.name]

    if regenerate_attempts:
        strategy = RestartStrategy.REDESIGN_PLAN
        reasoning = "Previous code regeneration attempts failed to resolve similar errors."
    else:
        reasoning = "Initial restart strategy is to regenerate code while keeping the plan."

    # If we have previous similar errors after redesigning plan, escalate further
    redesign_attempts = [a for a in error_history
                        if a.metadata.get("restart_strategy") == RestartStrategy.REDESIGN_PLAN.name]

    if redesign_attempts:
        strategy = RestartStrategy.MODIFY_REQUEST
        reasoning = "Both code regeneration and plan redesign failed to resolve similar errors."

    # Import here to avoid circular imports
    from ..debugging.models import ErrorCategory

    # Consider error category in decision
    if error_context.category in [ErrorCategory.SYNTAX, ErrorCategory.TYPE,
                                 ErrorCategory.NAME, ErrorCategory.ATTRIBUTE]:
        # These are likely implementation issues, favor code regeneration
        if strategy == RestartStrategy.MODIFY_REQUEST:
            strategy = RestartStrategy.REDESIGN_PLAN
            reasoning += (
                " However, the error type suggests an implementation issue"
                " rather than a fundamental request problem."
            )
    elif error_context.category in [
        ErrorCategory.PERMISSION,
        ErrorCategory.NETWORK,
        ErrorCategory.DATABASE, 
        ErrorCategory.MEMORY
    ]:
        # These may be environmental/system issues, consider modifying request
        if strategy == RestartStrategy.REGENERATE_CODE:
            strategy = RestartStrategy.REDESIGN_PLAN
            reasoning += (
                " The error type suggests a potential architectural or environmental issue"
                " that may require plan changes."
            )
    return strategy, reasoning


def _execute_code_regeneration(error_context, coordinator, scratchpad, code_generator) -> Dict[str, Any]:
    """Execute code regeneration strategy."""
    # Track start time for duration calculation
    strategy_start_time = time.time()

    scratchpad.log(
        role="DebuggingManager",
        message="Executing code regeneration strategy",
        level=LogLevel.INFO,
        section=Section.DEBUGGING
    )

    # We need the current plan and task
    if not hasattr(coordinator, 'current_plan') or not coordinator.current_plan:
        return {
            "success": False,
            "description": "Cannot regenerate code: no current plan available",
            "reasoning": "Code regeneration requires access to the current plan."
        }

    try:
        # Use code generator to regenerate implementation
        # First, prepare error context for code generator
        error_summary = f"Error ({error_context.category.name}): {error_context.message}"

        # Add to plan context
        plan_with_error = (
            coordinator.current_plan
            + f"\n\nPrevious implementation error:\n{error_summary}\n"
        )
        if error_context.traceback:
            plan_with_error += f"Traceback:\n{error_context.traceback}\n"

        # Generate new code
        result = code_generator.generate_code(
            coordinator.current_task,
            plan_with_error,
            coordinator.tech_stack,
            max_token_count=None  # Use default token count
        )

        if not result or not result.get("success", False):
            return {
                "success": False,
                "description": "Code regeneration failed",
                "reasoning": "Failed to generate new code implementation."
            }

        # Extract generated files
        generated_files = result.get("files", {})

        # Apply the generated files
        for file_path, content in generated_files.items():
            coordinator.file_tool.write_file(file_path, content)

        # Calculate duration
        duration = time.time() - strategy_start_time

        return {
            "success": True,
            "description": f"Regenerated code for {len(generated_files)} files",
            "reasoning": "Complete code regeneration based on the existing plan.",
            "changes": generated_files,
            "duration_seconds": duration,
            "metadata": {
                "tier": "strategic_restart",
                "restart_strategy": RestartStrategy.REGENERATE_CODE.name,
                "modified_files": list(generated_files.keys())
            }
        }

    except Exception as e:
        scratchpad.log(
            role="DebuggingManager",
            message=f"Error during code regeneration: {e}",
            level=LogLevel.ERROR
        )
        return {
            "success": False,
            "description": f"Code regeneration error: {e}",
            "reasoning": "Exception occurred during code regeneration."
        }


def _execute_plan_redesign(error_context, coordinator, scratchpad, code_generator, generate_plan_via_workflow_func) -> Dict[str, Any]:
    """Execute plan redesign strategy."""
    # Track start time for duration calculation
    strategy_start_time = time.time()

    scratchpad.log(
        role="DebuggingManager",
        message="Executing plan redesign strategy",
        level=LogLevel.WARNING,
        section=Section.DEBUGGING
    )

    # We need the original task
    if not hasattr(coordinator, 'current_task') or not coordinator.current_task:
        return {
            "success": False,
            "description": "Cannot redesign plan: no current task available",
            "reasoning": "Plan redesign requires access to the current task."
        }

    try:
        # Create a new plan with awareness of the error
        error_summary = f"Error ({error_context.category.name}): {error_context.message}"

        # Use the new sequential planning workflow with error context
        plan_result = generate_plan_via_workflow_func(
            coordinator,
            coordinator.current_task,
            context={"error_context": error_summary}
        )

        if not plan_result or not plan_result.get("success", False):
            return {
                "success": False,
                "description": "Plan redesign failed",
                "reasoning": "Failed to generate a new plan."
            }

        # Get the new plan
        new_plan = plan_result.get("plan", "")
        if not new_plan:
            return {
                "success": False,
                "description": "Plan redesign failed - empty plan",
                "reasoning": "Generated plan was empty."
            }

        # Update coordinator's current plan
        coordinator.current_plan = new_plan

        # Generate code based on new plan
        code_result = code_generator.generate_code(
            coordinator.current_task,
            new_plan,
            coordinator.tech_stack,
            max_token_count=None  # Use default token count
        )

        if not code_result or not code_result.get("success", False):
            return {
                "success": False,
                "description": "Code generation after plan redesign failed",
                "reasoning": "Failed to generate code based on new plan."
            }

        # Extract generated files
        generated_files = code_result.get("files", {})

        # Apply the generated files
        for file_path, content in generated_files.items():
            coordinator.file_tool.write_file(file_path, content)

        # Calculate duration
        duration = time.time() - strategy_start_time

        return {
            "success": True,
            "description": f"Redesigned plan and generated {len(generated_files)} files",
            "reasoning": "Complete plan redesign and code regeneration.",
            "changes": generated_files,
            "duration_seconds": duration,
            "metadata": {
                "tier": "strategic_restart",
                "restart_strategy": RestartStrategy.REDESIGN_PLAN.name,
                "modified_files": list(generated_files.keys()),
                "new_plan": new_plan
            }
        }

    except Exception as e:
        scratchpad.log(
            role="DebuggingManager",
            message=f"Error during plan redesign: {e}",
            level=LogLevel.ERROR
        )
        return {
            "success": False,
            "description": f"Plan redesign error: {e}",
            "reasoning": "Exception occurred during plan redesign."
        }


def _execute_request_modification(
    error_context, coordinator, scratchpad, llm, debug_history, code_generator, generate_plan_via_workflow_func
) -> Dict[str, Any]:
    """Execute request modification strategy."""
    # Track start time for duration calculation
    strategy_start_time = time.time()

    scratchpad.log(
        role="DebuggingManager",
        message="Executing request modification strategy",
        level=LogLevel.WARNING,
        section=Section.DEBUGGING
    )

    # We need the original task
    if not hasattr(coordinator, 'current_task') or not coordinator.current_task:
        return {
            "success": False,
            "description": "Cannot modify request: no current task available",
            "reasoning": "Request modification requires access to the current task."
        }

    try:
        # Start reasoning section for request modification
        scratchpad.start_section(Section.REASONING, "DebuggingManager")

        # Prepare prompt for request modification
        error_summary = (
            f"Error Category: {error_context.category.name}\n"
            f"Error Message: {error_context.message}\n"
            f"File: {error_context.file_path}\n"
            f"Line: {error_context.line_number}\n"
        )

        if error_context.code_snippet:
            error_summary += f"\nCode Snippet:\n{error_context.code_snippet}\n"

        if error_context.traceback:
            error_summary += f"\nTraceback:\n{error_context.traceback}\n"

        # Add debug history context
        debug_context = "Debug Attempt History:\n"
        for i, attempt in enumerate(debug_history[-5:], 1):
            debug_context += f"{i}. {attempt.phase.name} - {attempt.fix_description}\n"
            if attempt.success:
                debug_context += "   Result: SUCCESS\n"
            else:
                debug_context += "   Result: FAILED\n"

        # Create the prompt
        prompt = f"""
        You are an expert AI assistant tasked with modifying a task request that has repeatedly failed to implement.

        Original Task Request:
        {coordinator.current_task}

        Error Information:
        {error_summary}

        {debug_context}

        Multiple debugging attempts and strategic restarts have failed to resolve this issue.

        Based on the error patterns and debugging history, create a modified version of the original task
        that avoids the problems encountered. Consider:

        1. Simplifying requirements that might be causing issues
        2. Suggesting alternative approaches or technologies
        3. Breaking down the task into smaller, more manageable pieces
        4. Addressing any environmental or system constraints revealed by the errors
        5. Clarifying any ambiguities in the original request

        Return a JSON object with the following structure:
        {{
            "modified_task": "The revised task request",
            "rationale": "Explanation of the changes made",
            "implementation_steps": ["Step 1", "Step 2", ...]
        }}
        """

        # Call LLM for request modification
        result = cached_call_llm(prompt, llm, **coordinator.config.config)

        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            scratchpad.log(
                role="DebuggingManager",
                message=f"Request modification failed: {error_msg}",
                level=LogLevel.ERROR,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": f"Request modification failed: {error_msg}",
                "reasoning": "LLM call failed during request modification."
            }

        response = result.get('response', '')

        # Log reasoning
        scratchpad.log(
            role="DebuggingManager",
            message=f"Request modification reasoning:\n{response}",
            level=LogLevel.INFO,
            section=Section.REASONING
        )

        # Extract JSON from response
        modification_data = extract_json_from_response(response)
        if not modification_data:
            scratchpad.log(
                role="DebuggingManager",
                message="Could not extract JSON from response",
                level=LogLevel.WARNING,
                section=Section.REASONING
            )
            scratchpad.end_section(Section.REASONING)
            return {
                "success": False,
                "description": "Request modification failed: could not extract JSON",
                "reasoning": response
            }

        scratchpad.end_section(Section.REASONING)

        # Extract the modified task
        modified_task = modification_data.get("modified_task", "")
        rationale = modification_data.get("rationale", "")
        steps = modification_data.get("implementation_steps", [])

        if not modified_task:
            return {
                "success": False,
                "description": "Request modification failed: no modified task",
                "reasoning": rationale
            }

        # Run the modified task through the full pipeline
        scratchpad.log(
            role="DebuggingManager",
            message=f"Starting execution of modified task:\n{modified_task}",
            level=LogLevel.INFO
        )

        # Store original values
        original_task = coordinator.current_task
        original_plan = getattr(coordinator, 'current_plan', None)

        # Update current task
        coordinator.current_task = modified_task

        try:
            # Generate a new plan using the sequential planning workflow
            plan_result = generate_plan_via_workflow_func(
                coordinator,
                modified_task
            )

            if not plan_result or not plan_result.get("success", False):
                # Restore original values
                coordinator.current_task = original_task
                if original_plan:
                    coordinator.current_plan = original_plan

                return {
                    "success": False,
                    "description": "Modified request planning failed",
                    "reasoning": f"Failed to generate a plan for the modified task. Rationale: {rationale}"
                }

            # Get the new plan
            new_plan = plan_result.get("plan", "")
            coordinator.current_plan = new_plan

            # Generate code based on new plan
            code_result = code_generator.generate_code(
                modified_task,
                new_plan,
                coordinator.tech_stack,
                max_token_count=None  # Use default token count
            )

            if not code_result or not code_result.get("success", False):
                # Restore original values
                coordinator.current_task = original_task
                if original_plan:
                    coordinator.current_plan = original_plan

                return {
                    "success": False,
                    "description": "Code generation for modified request failed",
                    "reasoning": f"Failed to generate code for the modified task. Rationale: {rationale}"
                }

            # Extract generated files
            generated_files = code_result.get("files", {})

            # Apply the generated files
            for file_path, content in generated_files.items():
                coordinator.file_tool.write_file(file_path, content)

            # Calculate duration
            duration = time.time() - strategy_start_time

            return {
                "success": True,
                "description": f"Modified task request and generated {len(generated_files)} files",
                "reasoning": rationale,
                "changes": generated_files,
                "duration_seconds": duration,
                "metadata": {
                    "tier": "strategic_restart",
                    "restart_strategy": RestartStrategy.MODIFY_REQUEST.name,
                    "modified_files": list(generated_files.keys()),
                    "modified_task": modified_task,
                    "new_plan": new_plan,
                    "implementation_steps": steps
                }
            }

        except Exception as e:
            # Restore original values
            coordinator.current_task = original_task
            if original_plan:
                coordinator.current_plan = original_plan

            scratchpad.log(
                role="DebuggingManager",
                message=f"Error executing modified task: {e}",
                level=LogLevel.ERROR
            )
            return {
                "success": False,
                "description": f"Modified task execution error: {e}",
                "reasoning": f"Exception occurred during modified task execution. Rationale: {rationale}"
            }

    except Exception as e:
        scratchpad.log(
            role="DebuggingManager",
            message=f"Error during request modification: {e}",
            level=LogLevel.ERROR
        )
        return {
            "success": False,
            "description": f"Request modification error: {e}",
            "reasoning": "Exception occurred during request modification."
        }