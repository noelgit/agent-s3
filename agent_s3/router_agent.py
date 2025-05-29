"""Router Agent for selecting appropriate LLMs."""

import os
import json
import logging
import time
import re  # Add import for regex pattern matching
from .pattern_constants import ERROR_PATTERN, EXCEPTION_PATTERN
from time import sleep
import requests
import traceback  # Added import
from typing import Dict, Any, Optional, Tuple, List

import jsonschema

logger = logging.getLogger(__name__)

# Maximum number of characters from LLM responses to include in log messages
MAX_LOG_LEN = 500

# Initialize models_by_role at module level to avoid undefined global variable
_models_by_role = {}

# Command patterns for special routing
COMMAND_PATTERNS = {
    "continue": r"@agent\s+Continue:?\s*(?:\"|\')?(.*?)(?:\"|\')?$",
    "debug": r"@agent\s+Debug:?\s*(?:\"|\')?(.*?)(?:\"|\')?$",
    "test": r"@agent\s+Test:?\s*(?:\"|\')?(.*?)(?:\"|\')?$",
    "plan": r"@agent\s+Plan:?\s*(?:\"|\')?(.*?)(?:\"|\')?$",
    "execute": r"@agent\s+Execute:?\s*(?:\"|\')?(.*?)(?:\"|\')?$",
}

# Path to the JSON Schema describing a valid LLM entry
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "llm_entry_schema.json")
with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    LLM_ENTRY_SCHEMA = json.load(schema_file)

class MetricsTracker:
    """Collects metrics for LLM calls."""
    def __init__(self):
        self._records = []
    def record(self, role: str, model: str, duration: float, success: bool, tokens: int):
        self._records.append({
            'role': role,
            'model': model,
            'duration': duration,
            'success': success,
            'tokens': tokens
        })
    def get_metrics(self):
        """Return recorded metrics."""
        return list(self._records)

def _validate_entry(entry: Dict[str, Any], index: int) -> None:
    """Validate a single llm.json entry against the schema."""
    try:
        jsonschema.validate(instance=entry, schema=LLM_ENTRY_SCHEMA)
    except jsonschema.exceptions.ValidationError as e:
        path = "->" + "->".join([str(p) for p in e.path]) if e.path else "root" # Ensure path is a string
        raise ValueError(
            f"llm.json entry {index} validation error at {path}: {e.message}"
        )

def _load_llm_config(config_obj: Optional[Any] = None): # Add config_obj parameter
    """Load the LLM configuration from llm.json."""
    try:
        # Determine the base path for llm.json
        # Prioritize config_obj.settings.workspace_path if available
        base_path = os.getcwd() # Default to current working directory
        if config_obj and hasattr(config_obj, 'settings') and hasattr(config_obj.settings, 'workspace_path'):
            # Ensure workspace_path is an absolute path or resolve it
            ws_path = config_obj.settings.workspace_path
            if not os.path.isabs(ws_path):
                # This assumes ws_path is relative to where the script was initially run,
                # or it's just "." which means the project root.
                # For robustness, one might need to establish a clear project root earlier.
                # For now, let's assume it's either absolute or relative to a known root.
                # If ws_path is ".", os.path.join will handle it correctly.
                pass # ws_path is used as is if relative, joined with getcwd if needed by os.path.join
            base_path = ws_path # Use workspace_path from config

        # If base_path is still relative (e.g. "."), make it absolute from CWD
        # This is a fallback if workspace_path was not absolute or not set effectively
        if not os.path.isabs(base_path):
             base_path = os.path.abspath(os.path.join(os.getcwd(), base_path))


        # Check if we are in a subdirectory like 'vscode' and adjust base_path
        # This is a heuristic. A more robust solution would be to find a project root marker.
        # For now, if 'vscode' is in the path and llm.json is not found there, try one level up.
        potential_llm_path = os.path.join(base_path, 'llm.json')
        if 'vscode' in base_path.split(os.sep) and not os.path.exists(potential_llm_path):
            logger.info(f"llm.json not found in {base_path}, trying parent directory as it might be a 'vscode' subdirectory context.")
            parent_dir = os.path.dirname(base_path)
            if os.path.exists(os.path.join(parent_dir, 'llm.json')):
                base_path = parent_dir
                logger.info(f"Found llm.json in parent directory: {base_path}")


        config_path = os.path.join(base_path, 'llm.json')
        logger.info(f"Attempting to load LLM config from: {config_path}")

        if not os.path.exists(config_path):
            logger.error("LLM configuration file not found: %s", config_path)
            # Try to find llm.json in the script's directory or its parent as a last resort
            script_dir = os.path.dirname(os.path.abspath(__file__))
            fallback_paths = [
                os.path.join(script_dir, '..', 'llm.json'), # one level up from agent_s3 (project root)
                os.path.join(script_dir, 'llm.json') # alongside router_agent.py (less likely)
            ]
            found_fallback = False
            for fb_path in fallback_paths:
                fb_path_abs = os.path.abspath(fb_path)
                logger.info(f"Checking fallback LLM config path: {fb_path_abs}")
                if os.path.exists(fb_path_abs):
                    config_path = fb_path_abs
                    logger.info(f"Found LLM config at fallback location: {config_path}")
                    found_fallback = True
                    break
            if not found_fallback:
                raise FileNotFoundError(f"LLM configuration file not found at primary path {config_path} or fallbacks.")

        with open(config_path, 'r') as f:
            llm_config = json.load(f)

        if not isinstance(llm_config, list):
            raise ValueError("llm.json must contain a list of model entries")

        # Validate entries with schema
        for idx, model_info in enumerate(llm_config):
            _validate_entry(model_info, idx)
        models_by_role = {}
        for model_info in llm_config:
            roles = model_info.get("role")
            if isinstance(roles, str):
                roles = [roles]  # Ensure roles is always a list
            if isinstance(roles, list):
                for role in roles:
                    if role in models_by_role:
                        logger.warning(
                            "Duplicate role definition found for %s. Using the last definition found in llm.json.",
                            role,
                        )
                    models_by_role[role] = model_info
            else:
                logger.warning(
                    "Skipping model entry due to invalid or missing 'role': %s",
                    model_info.get("model"),
                )

        logger.info(
            "Loaded LLM configuration for roles: %s",
            list(models_by_role.keys()),
        )
        return models_by_role
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding llm.json: {e}")
    except Exception as e:
        logger.error(f"Failed to load LLM configuration: {e}", exc_info=True)
        raise

class RouterAgent:
    """Routes LLM requests to the appropriate model based on the task."""

    def __init__(self, config=None):
        """Initialize the router agent.

        Args:
            config: Optional configuration object or dictionary.
        """
        global _models_by_role  # Properly reference the global variable
        if not _models_by_role:
            _models_by_role = _load_llm_config(config) # Pass config object
        # Store configuration
        self.config = config
        # Metrics collector
        self.metrics = MetricsTracker()
        # Circuit breaker state
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}

    def choose_llm(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Choose the appropriate LLM based on the query and metadata."""
        if metadata is None:
            metadata = {}

        # Check for special command patterns
        command_type, command_content = self.process_command_pattern(query)
        if command_type:
            # Map command types to specific roles
            command_role_map = {
                "debug": "error_analyzer",
                "test": "test_planner",
                "plan": "planner",
                "execute": "generator",
                "continue": "generator"  # Default to generator for continuations
            }

            # Override role based on command if a mapping exists
            if command_type in command_role_map:
                original_role = metadata.get("role")
                role = command_role_map[command_type]
                logger.info(
                    "Command pattern '%s' detected. Routing to role '%s' instead of '%s'",
                    command_type,
                    role,
                    original_role,
                )
                # Update metadata with the new role
                metadata["role"] = role
                metadata["command_type"] = command_type
                metadata["command_content"] = command_content
            else:
                logger.warning(
                    "Command pattern '%s' detected but no role mapping found.",
                    command_type,
                )

        role = metadata.get("role")
        if not role:
            logger.warning("No 'role' provided in metadata. Cannot determine appropriate LLM.")
            return None

        if not _models_by_role:
            logger.error("LLM configuration is missing. Cannot choose LLM.")
            return None

        model_info = _models_by_role.get(role)

        if not model_info:
            logger.warning(
                "No model configured for role: '%s'. Available roles: %s",
                role,
                list(_models_by_role.keys()),
            )
            return None

        model_name = model_info.get("model")
        context_window = model_info.get("context_window")

        if not model_name:
            logger.error(
                "Configuration for role '%s' is missing the 'model' name.", role
            )
            return None

        try:
            estimated_tokens = len(query.split())  # Simplified token estimation
            logger.info(
                "Estimated tokens for query: %s (using model context: %s)",
                estimated_tokens,
                model_name,
            )

            if context_window and estimated_tokens > context_window:
                logger.warning(
                    f"Estimated token count ({estimated_tokens}) exceeds the context window "
                    f"({context_window}) for model '{model_name}' (role: '{role}'). "
                    f"Input may be truncated by the LLM."
                )
        except Exception as e:
            logger.exception(
                "Failed to estimate token count: %s. Skipping context window check.",
                e,
            )

        logger.info("Routing to model '%s' for role '%s'.", model_name, role)
        return model_name

    def run(self, prompt: Dict[str, Any], **config: Any) -> Optional[str]:
        """Convenience wrapper to call an LLM using a structured prompt."""
        role = prompt.get("role", "pre_planner")
        system_prompt = prompt.get("system", "")
        user_prompt = prompt.get("user", "")

        context = prompt.get("context")
        if context:
            try:
                context_str = json.dumps(context, indent=2)
            except (TypeError, ValueError):
                context_str = str(context)
            user_prompt += "\n\nContext:\n" + context_str

        scratchpad = config.pop("scratchpad", None)
        if scratchpad is None:
            class _NoOpScratchpad:
                def log(self, *_a, **_k):
                    return None

            scratchpad = _NoOpScratchpad()

        return self.call_llm_by_role(
            role=role,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            scratchpad=scratchpad,
        )

    def call_llm_by_role(
        self,
        role: str,
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any],  # Pass config for API keys and retry settings
        scratchpad: Any,  # Pass scratchpad for logging
        fallback_role: Optional[str] = None,
        tech_stack: Optional[Dict[str, Any]] = None,  # Added tech_stack parameter
        code_context: Optional[Dict[str, str]] = None,  # Added code_context parameter
        metadata: Optional[Dict[str, Any]] = None,  # New metadata parameter for command info
        **kwargs: Any  # Additional parameters for the API call
    ) -> Optional[str]:
        """Calls the appropriate LLM based on role, handling retries and fallbacks.

        Args:
            role: The role identifier used to select the appropriate model
            system_prompt: System prompt to set the LLM behavior
            user_prompt: The primary user query/prompt
            config: Configuration containing API keys and settings
            scratchpad: Logger for tracking call progress and outcomes
            fallback_role: Optional role to use if primary role fails
            tech_stack: Optional tech stack information (languages, frameworks, etc.)
            code_context: Optional code snippets relevant to the request
            metadata: Optional metadata including command type and content
            **kwargs: Additional parameters for the API call

        Returns:
            The LLM response text or None if the call fails
        """
        # Initialize metadata if not provided
        if metadata is None:
            metadata = {}

        model_info = _models_by_role.get(role)
        if not model_info:
            scratchpad.log("RouterAgent", f"Error: No model configured for role: '{role}'", level="error")
            return None

        model_name = model_info.get("model")
        if not model_name:
            scratchpad.log("RouterAgent", f"Error: Configuration for role '{role}' is missing the 'model' name.", level="error")
            return None

        # Enhance system prompt based on command metadata if present
        if "command_type" in metadata and "command_content" in metadata:
            command_type = metadata["command_type"]
            command_content = metadata["command_content"]

            # Log the command processing
            scratchpad.log("RouterAgent",
                         f"Processing @agent {command_type.capitalize()} command: '{command_content}'")

            # Command-specific system prompt enhancements
            command_instructions = {
                "debug": "\nYou are in DEBUG mode. Focus on identifying and fixing errors in the code. "
                        "Analyze error messages carefully and provide detailed diagnostics.",

                "test": "\nYou are in TEST mode. Focus on creating or improving test coverage. "
                       "Write comprehensive tests that validate functionality and edge cases.",

                "plan": "\nYou are in PLAN mode. Create a clear, structured plan for implementation. "
                       "Break down complex tasks into manageable steps with consideration for dependencies.",

                "execute": "\nYou are in EXECUTE mode. Implement the requested feature or changes according "
                          "to best practices. Focus on producing working, well-structured code.",

                "continue": "\nYou are in CONTINUE mode. Pick up from your previous work and continue "
                           "implementation or analysis. Maintain consistency with the established approach."
            }

            # Enhance system prompt with command-specific instructions
            if command_type in command_instructions:
                system_prompt += command_instructions[command_type]
                scratchpad.log("RouterAgent", f"Enhanced system prompt with {command_type} mode instructions")

            # For continue command, append a special instruction about previous work
            if command_type == "continue":
                system_prompt += (
                    "\nReview previous outputs and context carefully to ensure continuity."
                )
        max_retries = config.get('max_retries', 3)
        initial_backoff = config.get('initial_backoff', 1.0)
        backoff_multiplier = config.get('backoff_multiplier', 2.0)
        failure_threshold = config.get('failure_threshold', 5)
        cooldown = config.get('cooldown_period', 300)
        timeout = config.get('llm_timeout', 60)

        backoff = initial_backoff
        primary_failed = False
        response_content = None

        # Initialize circuit breaker state for the model if not present
        if model_name not in self._failure_counts:
            self._failure_counts[model_name] = 0
            self._last_failure_time[model_name] = 0

        for attempt in range(max_retries):
            # Check circuit breaker
            if (
                self._failure_counts[model_name] >= failure_threshold
                and time.time() < self._last_failure_time[model_name] + cooldown
            ):
                scratchpad.log(
                    "RouterAgent",
                    f"Circuit breaker tripped for {model_name} (Role: {role}). Attempting fallback if available.",
                    level="warning",
                )
                primary_failed = True
                break

            try:
                response_content = self._execute_llm_call(
                    model_info,
                    system_prompt,
                    user_prompt,
                    config,  # For API key
                    scratchpad,
                    timeout=timeout,
                    role=role,
                    tech_stack=tech_stack,  # Pass tech_stack
                    code_context=code_context,  # Pass code_context
                    metadata=metadata,  # Pass command metadata
                    **kwargs
                )
                self._failure_counts[model_name] = 0  # Reset failure count on success
                primary_failed = False
                scratchpad.log(
                    "RouterAgent",
                    f"Successfully called {model_name} (Role: {role}) on attempt {attempt + 1}",
                )
                break  # Success
            except Exception as e:
                self._failure_counts[model_name] += 1
                self._last_failure_time[model_name] = time.time()
                scratchpad.log(
                    "RouterAgent",
                    (
                        f"Attempt {attempt + 1}/{max_retries} failed for {model_name} "
                        f"(Role: {role}): {e}"
                    ),
                    level="warning",
                )
                if attempt + 1 == max_retries:
                    primary_failed = True
                    scratchpad.log(
                        "RouterAgent",
                        (
                            f"{model_name} (Role: {role}) failed after {max_retries} attempts."
                        ),
                        level="error",
                    )
                else:
                    sleep(backoff)
                    backoff *= backoff_multiplier

        # Fallback logic
        if primary_failed and fallback_role:
            scratchpad.log("RouterAgent", f"Primary model for role '{role}' failed. Falling back to role '{fallback_role}'.", level="warning")
            fallback_model_info = _models_by_role.get(fallback_role)
            if not fallback_model_info:
                scratchpad.log("RouterAgent", f"Error: No model configured for fallback role: '{fallback_role}'", level="error")
                return None
            fallback_model_name = fallback_model_info.get("model")
            if not fallback_model_name:
                scratchpad.log("RouterAgent", f"Error: Configuration for fallback role '{fallback_role}' is missing the 'model' name.", level="error")
                return None

            try:
                # Use a single attempt for fallback for simplicity, could add retries too
                response_content = self._execute_llm_call(
                    fallback_model_info,
                    system_prompt,
                    user_prompt,
                    config,
                    scratchpad,
                    timeout=timeout,
                    role=fallback_role,
                    tech_stack=tech_stack,  # Pass tech_stack
                    code_context=code_context,  # Pass code_context
                    metadata=metadata,  # Pass command metadata
                    **kwargs
                )
                scratchpad.log("RouterAgent", f"Successfully called fallback {fallback_model_name} (Role: {fallback_role})")
            except Exception as e:
                scratchpad.log("RouterAgent", f"Fallback model {fallback_model_name} (Role: {fallback_role}) also failed: {e}", level="error")
                return None  # Both primary and fallback failed
        elif primary_failed:
            scratchpad.log("RouterAgent", f"Primary model for role '{role}' failed and no fallback specified.", level="error")
            return None  # Primary failed, no fallback

        return response_content

    def _execute_llm_call(
        self,
        model_info: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
        config: Dict[str, Any],
        scratchpad: Any,
        timeout: int,
        role: str,
        tech_stack: Optional[Dict[str, Any]] = None,  # Tech stack parameter
        code_context: Optional[Dict[str, str]] = None,  # Code context parameter
        historical_context: Optional[Dict[str, Any]] = None,  # Historical context parameter
        file_metadata: Optional[Dict[str, Any]] = None,  # File metadata parameter
        related_features: Optional[List[str]] = None,  # Related features parameter
        metadata: Optional[Dict[str, Any]] = None,  # Metadata parameter including command info
        **kwargs: Any
    ) -> Optional[str]:
        """Executes a single LLM API call.

        Now supports enhanced context with tech stack, code snippets, command metadata,
        historical context, file metadata, and related features.
        """
        start = time.time()
        model_name = model_info["model"]
        api_details = model_info.get("api", {})
        endpoint_str = api_details.get("endpoint")
        auth_header_template = api_details.get("auth_header")

        # Get the context window size for token management
        context_window = model_info.get("context_window", 8000)  # Default to 8K if not specified

        # Initialize metadata if not provided
        if metadata is None:
            metadata = {}

        # Apply role-specific system prompt enhancements
        allocation = self._get_role_specific_context_allocation(role, context_window)
        if "system_prompt_suffix" in allocation:
            # Enhance system prompt with test-side workaround prohibition
            system_prompt += allocation["system_prompt_suffix"]
            scratchpad.log("RouterAgent", "Added test-side workaround prohibition to system prompt")

        # Enhanced prompt with tech stack, code context and command info if provided
        enhanced_user_prompt = user_prompt

        # Add command-specific context to the user prompt if this is a command
        if "command_type" in metadata and "command_content" in metadata:
            command_type = metadata["command_type"]
            command_content = metadata["command_content"]

            # Handle specific command types
            if command_type == "continue":
                # For continue commands, replace the user prompt entirely with command content if it exists
                if command_content:
                    enhanced_user_prompt = f"CONTINUE TASK: {command_content}"
                else:
                    enhanced_user_prompt = "Continue from where you left off with the previous task."

            elif command_content:  # For other commands with content
                # Prefix the user prompt with the command info
                command_prefixes = {
                    "debug": "DEBUG TASK: ",
                    "test": "TEST TASK: ",
                    "plan": "PLANNING TASK: ",
                    "execute": "EXECUTION TASK: "
                }
                prefix = command_prefixes.get(command_type, f"{command_type.upper()} TASK: ")

                if command_content not in user_prompt:  # Only add if not already present
                    enhanced_user_prompt = f"{prefix}{command_content}\n\n{user_prompt}"

        # Include tech stack information if available
        if tech_stack:
            tech_stack_sections = []
            for category, items in tech_stack.items():
                if items:  # Only include non-empty categories
                    # Handle both list and set inputs
                    items_list = list(items) if not isinstance(items, list) else items
                    if items_list:
                        tech_stack_sections.append(f"{category.title()}: {', '.join(items_list)}")

            if tech_stack_sections:
                tech_stack_str = "\n".join(tech_stack_sections)
                enhanced_user_prompt = f"Detected Tech Stack:\n{tech_stack_str}\n\n{enhanced_user_prompt}"
                scratchpad.log("RouterAgent", f"Added tech stack context for {role}: {tech_stack_str}")

        # Get role-specific allocation settings
        allocation = self._get_role_specific_context_allocation(role, context_window)

        # Include historical context if available and if role allocation requests it
        if historical_context and allocation.get("include_historical_context", False):
            historical_sections = []

            # Process recent changes
            if "previous_changes" in historical_context and historical_context["previous_changes"]:
                changes = historical_context["previous_changes"][:5]  # Limit to 5
                changes_text = "Recent Changes:\n" + \
                     "\n".join([f"- {change}" for change in changes])
                historical_sections.append(changes_text)

            # Process file change frequency
            if "file_change_frequency" in historical_context and historical_context["file_change_frequency"]:
                freq_items = list(historical_context["file_change_frequency"].items())
                top_files = sorted(freq_items, key=lambda x: x[1], reverse=True)[:5]  # Top 5
                freq_text = "Frequently Modified Files:\n" + \
                     "\n".join([f"- {file}: {freq} changes" for file, freq in top_files])
                historical_sections.append(freq_text)

            if historical_sections:
                historical_text = "Historical Context:\n" + "\n\n".join(historical_sections)
                enhanced_user_prompt = f"{historical_text}\n\n{enhanced_user_prompt}"
                scratchpad.log("RouterAgent", f"Added historical context for {role} based on role allocation")

        # Include file metadata if available and if role allocation requests it
        if file_metadata and allocation.get("include_file_metadata", False):
            metadata_text = "File Metadata:\n" + json.dumps(file_metadata, indent=2)
            enhanced_user_prompt = f"{metadata_text}\n\n{enhanced_user_prompt}"
            scratchpad.log("RouterAgent", f"Added file metadata for {role} based on role allocation")

        # Include related features if available and if role allocation requests it
        if related_features and allocation.get("include_related_features", False):
            features_text = "Related Past Features:\n" + \
                 "\n".join([f"- {feature}" for feature in related_features[:3]])
            enhanced_user_prompt = f"{features_text}\n\n{enhanced_user_prompt}"
            scratchpad.log("RouterAgent", f"Added related features for {role} based on role allocation")

        # Include relevant code context if available
        if code_context:
            # Simple token estimation (can be refined)
            def estimate_tokens(text):
                return len(text.split()) * 1.3  # Rough estimation: words * 1.3

            # We already retrieved the allocation above, but reuse it to calculate max_context_tokens
            # allocation = self._get_role_specific_context_allocation(role, context_window)
            max_context_tokens = min(allocation["max_abs_tokens"],
                                    int(context_window * allocation["max_context_pct"]))

            code_context_str = ""
            current_tokens = 0

            # <<< START NEW BLOCK: Load guidelines for guideline_expert >>>
            if role.lower() == "guideline_expert":
                guidelines_path = os.path.join(os.getcwd(), ".github", "copilot-instructions.md") # Use os.getcwd() for robustness
                if os.path.exists(guidelines_path):
                    try:
                        with open(guidelines_path, "r", encoding="utf-8") as f:
                            guidelines_content = f.read()
                        guidelines_header = f"--- {os.path.relpath(guidelines_path)} ---\n" # Use relative path for header
                        guidelines_block = f"{guidelines_header}{guidelines_content}\n\n"
                        guidelines_tokens = estimate_tokens(guidelines_block)

                        # Allocate a significant portion of the budget specifically for guidelines
                        guideline_budget = max_context_tokens * 0.75
                        if guidelines_tokens <= guideline_budget:
                            code_context_str += guidelines_block
                            current_tokens += guidelines_tokens
                            scratchpad.log("RouterAgent", f"Loaded guidelines ({guidelines_tokens:.0f} tokens) for guideline_expert.")
                        else:
                            # Truncate guidelines if too long (simple truncation)
                            max_guideline_chars = int(len(guidelines_content) * (guideline_budget / guidelines_tokens))
                            truncated_content = guidelines_content[:max_guideline_chars] + \
                                 "\n... (guidelines truncated)"
                            truncated_block = f"{guidelines_header}{truncated_content}\n\n"
                            truncated_tokens = estimate_tokens(truncated_block)
                            code_context_str += truncated_block
                            current_tokens += truncated_tokens
                            scratchpad.log("RouterAgent", f"Loaded truncated guidelines ({truncated_tokens:.0f} tokens) for guideline_expert.")

                    except Exception as e:
                        scratchpad.log("RouterAgent", f"Error loading guidelines file {guidelines_path}: {e}", level="ERROR")
                else:
                    scratchpad.log("RouterAgent", f"Guidelines file not found at {guidelines_path} for guideline_expert.", level="WARNING")
            # <<< END NEW BLOCK >>>

            # Log the new allocation settings
            scratchpad.log("RouterAgent",
                f"Using role-specific context allocation for {role}: "
                f"{allocation['max_context_pct']*100:.0f}% of context window, "
                f"max {max_context_tokens} tokens (was 15%/1500 tokens)")

            # Preserve original ordering - respect relevance ranking from code analysis tool
            # The code_context is assumed to already be ordered by relevance
            files_to_process = list(code_context.items()) # Convert to list to iterate

            # If role needs to preserve structure, include brief metadata about all files first
            if allocation.get("preserve_structure", False) and len(files_to_process) > 5:
                structure_summary = "Project Structure Overview:\n"
                for path, content in files_to_process:
                    line_count = content.count('\n') + 1
                    structure_summary += f"- {path}: {line_count} lines\n"

                structure_tokens = estimate_tokens(structure_summary)
                # Use up to 15% of our context budget for structure overview
                if structure_tokens <= max_context_tokens * 0.15:
                    code_context_str += structure_summary + "\n\n"
                    current_tokens += structure_tokens

            for path, content in files_to_process:
                context_header = f"--- {path} ---\n"

                # If we should prioritize comments for this role, extract and highlight them
                if allocation.get("prioritize_comments", False) and "# " in content:
                    # Extract comments (simplistic approach - could be improved)
                    comments = "\n".join([line for line in content.split("\n")
                                         if line.strip().startswith("# ") or
                                         line.strip().startswith('"""') or
                                         line.strip().startswith("'''") or
                                         "# " in line])

                    if len(comments) > 100:  # Only if we have meaningful comments
                        comment_block = f"{context_header}DOCUMENTATION COMMENTS:\n{comments}\n\n"
                        comment_tokens = estimate_tokens(comment_block)

                        # If we can fit comments, add them with higher priority
                        if current_tokens + comment_tokens <= max_context_tokens * 0.4:
                            code_context_str += comment_block
                            current_tokens += comment_tokens

                            # Reduce remaining content by removing processed comments
                            content = "\n".join([line for line in content.split("\n")
                                              if not (line.strip().startswith("# ") or
                                                    "# " in line or
                                                    line.strip().startswith('"""') or
                                                    line.strip().startswith("'''"))])

                # Process the full content or remaining content after comment extraction
                context_block = f"{context_header}{content}\n\n"
                block_tokens = estimate_tokens(context_block)

                if current_tokens + block_tokens <= max_context_tokens:
                    code_context_str += context_block
                    current_tokens += block_tokens
                else:
                    # Try adding just the header if content is too long
                    header_tokens = estimate_tokens(context_header)
                    truncation_msg = "... (content truncated)\n\n"
                    truncation_tokens = estimate_tokens(truncation_msg)

                    if current_tokens + header_tokens + truncation_tokens <= max_context_tokens:
                        code_context_str += context_header + truncation_msg
                        current_tokens += header_tokens + truncation_tokens

                    # For error_analyzer role, try to include error-relevant parts even if we need to truncate
                    if role.lower() == "error_analyzer" and ERROR_PATTERN.search(content):
                        error_lines = [
                            i
                            for i, line in enumerate(content.split("\n"))
                            if ERROR_PATTERN.search(line) or EXCEPTION_PATTERN.search(line)
                        ]

                        if error_lines:
                            line_context = allocation.get("error_context_lines", 10)
                            error_context = []
                            for error_line in error_lines[:3]:  # Focus on first 3 errors max
                                lines = content.split("\n")
                                start = max(0, error_line - line_context)
                                end = min(len(lines), error_line + line_context)
                                error_snippet = "\n".join(lines[start:end])
                                error_context.append(f"ERROR CONTEXT (lines {start}-{end}):\n{error_snippet}")

                            error_content = "\n\n".join(error_context)
                            error_tokens = estimate_tokens(error_content)

                            # If we can fit error context within remaining budget
                            remaining_tokens = max_context_tokens - current_tokens
                            if error_tokens <= remaining_tokens:
                                code_context_str += f"{context_header}[ERROR CONTEXTS ONLY]\n{error_content}\n\n"
                                current_tokens += error_tokens + header_tokens
                    # No more space for additional files
                    code_context_str += "\n... (more files truncated due to token limits)"
                    break  # Stop adding more files once limit is hit

            if code_context_str:
                enhanced_user_prompt = f"Relevant Code Context:\n{code_context_str}\n\n{enhanced_user_prompt}"
                scratchpad.log("RouterAgent",
                    f"Added code context for {role} (estimated {current_tokens:.0f} tokens, "
                    f"{len(code_context)} files, limit {max_context_tokens:.0f})")

        # Add reminder about test-side workarounds to the user prompt
        reminder = "\n\n⚠️ IMPORTANT: You must NEVER modify tests to make failing code pass. Always fix the implementation code itself, not the tests. Modifying tests to accommodate broken code is strictly prohibited. ⚠️"
        enhanced_user_prompt += reminder
        scratchpad.log("RouterAgent", "Added test integrity reminder to user prompt")

        if not endpoint_str or not auth_header_template:
            raise ValueError(f"API endpoint or auth_header missing for model {model_name}")

        # Determine HTTP method and endpoint URL
        method = "POST"
        if endpoint_str.startswith("POST "):
            endpoint = endpoint_str.split(" ", 1)[1]
        elif endpoint_str.startswith("GET "):
            method = "GET"
            endpoint = endpoint_str.split(" ", 1)[1]
        else:
            endpoint = endpoint_str  # Assume POST if not specified

        # Resolve API key from config
        api_key_name = None
        if "$OPENROUTER_KEY" in auth_header_template:
            api_key_name = "openrouter_key"
        elif "$OPENAI_KEY" in auth_header_template:
            api_key_name = "openai_key"  # Example, adjust as needed
        # Add more key types here

        if not api_key_name or not config.get(api_key_name):
            raise ValueError(f"API key ({api_key_name or 'specified in auth_header'}) not found in configuration for model {model_name}")

        api_key = config[api_key_name]
        auth_header_value = auth_header_template.replace(f"${api_key_name.upper()}", api_key)
        auth_header_name = auth_header_value.split(":", 1)[0].strip()
        auth_token = auth_header_value.split(":", 1)[1].strip()

        headers = {
            auth_header_name: auth_token,
            "Content-Type": "application/json",
            # Add OpenRouter specific headers if needed (already present in validation call)
            "HTTP-Referer": config.get("openrouter_referer", "http://localhost"),  # Make configurable
            "X-Title": config.get("openrouter_title", "Agent-S3")  # Make configurable
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_user_prompt}  # Use enhanced prompt
        ]

        # Combine default parameters from llm.json with call-specific kwargs
        payload = {
            "model": model_name,
            "messages": messages,
            **model_info.get("parameters", {}),  # Defaults from llm.json
            **kwargs  # Override with call-specific params
        }

        # Estimate total tokens for logging and potential warnings
        def estimate_tokens(text):
            return len(text.split()) * 1.3  # Rough estimation: words * 1.3

        total_tokens = estimate_tokens(system_prompt) + estimate_tokens(enhanced_user_prompt)
        if total_tokens > context_window * 0.9:  # Within 90% of limit
            scratchpad.log("RouterAgent",
                f"WARNING: Estimated input tokens ({total_tokens:.0f}) approaching context window ({context_window}) "
                f"for {model_name}. Content may be truncated.", level="warning")

        scratchpad.log("RouterAgent", f"Calling {method} {endpoint} for model {model_name} "
                      f"(Role: {role}, est. tokens: {total_tokens:.0f})")

        try:
            response = requests.request(
                method,
                endpoint,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

            response_data = response.json()
            scratchpad.log("RouterAgent", f"Raw response from {model_name}: {json.dumps(response_data, indent=2)}")

            # Extract content - common pattern for OpenAI/OpenRouter compatible APIs
            if response_data.get("choices") and isinstance(response_data["choices"], list) and len(response_data["choices"]) > 0:
                message = response_data["choices"][0].get("message")
                if message and isinstance(message, dict):
                    content = message.get("content")
                    if content:
                        # Record success metrics
                        duration = time.time() - start
                        tokens = len(system_prompt.split()) + len(enhanced_user_prompt.split()) + len(str(content).split())
                        self.metrics.record(role, model_name, duration, True, tokens)
                        return str(content).strip()

            # Handle potential variations in response structure if needed
            # ... add more parsing logic for different API formats ...

            raise ValueError(f"Could not extract content from {model_name} response structure: {response_data}")

        except requests.exceptions.Timeout:
            duration = time.time() - start
            self.metrics.record(role, model_name, duration, False, 0)
            scratchpad.log("RouterAgent", f"API call to {model_name} timed out after {timeout} seconds.", level="error")
            raise TimeoutError(f"API call to {model_name} timed out.")
        except requests.exceptions.RequestException as e:
            duration = time.time() - start
            self.metrics.record(role, model_name, duration, False, 0)
            response_text = e.response.text if e.response else "No response body"
            error_msg = (
                f"API call to {model_name} failed: {e}. Response: "
                f"{response_text[:MAX_LOG_LEN]}"
            )
            scratchpad.log("RouterAgent", error_msg, level="error")
            raise ConnectionError(error_msg)
        except (json.JSONDecodeError, KeyError, IndexError, AttributeError, ValueError) as e:
            duration = time.time() - start
            self.metrics.record(role, model_name, duration, False, 0)
            error_msg = (
                f"Failed to process response from {model_name}: {e}. Response data: "
                f"{response.text[:MAX_LOG_LEN]}"
            )
            scratchpad.log("RouterAgent", error_msg, level="error")
            raise ValueError(error_msg)
        except Exception as e:
            # Record failure metrics
            duration = time.time() - start
            self.metrics.record(role, model_name, duration, False, 0)
            error_msg = f"Unexpected error during API call to {model_name}: {e}"
            scratchpad.log("RouterAgent", f"{error_msg}\n{traceback.format_exc()}", level="error")
            raise

    def reload_config(self):
        """Reload llm.json config and reset router state."""
        global _models_by_role
        _models_by_role = _load_llm_config()
        self._failure_counts.clear()
        self._last_failure_time.clear()

    def get_metrics(self):
        """Return aggregated LLM call metrics."""
        return self.metrics.get_metrics()

    def process_command_pattern(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Process special command patterns to determine if this is a command query.

        Args:
            query: The user query string

        Returns:
            Tuple of (command_type, command_content) if a command is detected,
            otherwise (None, None)
        """
        for cmd_type, pattern in COMMAND_PATTERNS.items():
            match = re.search(pattern, query, re.IGNORECASE | re.DOTALL)
            if match:
                # Extract the command content (what comes after the command)
                cmd_content = match.group(1).strip() if match.group(1) else ""
                return cmd_type, cmd_content

        # No command pattern matched
        return None, None

    def _get_role_specific_context_allocation(
        self,
        role: str,
        context_window: int
    ) -> Dict[str, Any]:
        """Get role-specific context allocation settings."""
        # Define allocations for different roles
        allocations = {
            # Pre-planner for task analysis and feature decomposition
            "pre_planner": {
                "max_context_pct": 0.60,  # 60% of context window
                "max_abs_tokens": min(100000, int(context_window * 0.6)),
                "prioritize_comments": True,
                "preserve_structure": True,
                "preserve_relevance_order": True,
                "include_historical_context": True,  # Include file history, changes, etc.
                "include_file_metadata": True,       # Include file and directory structures
                "include_related_features": True,    # Include related past tasks/features
                "system_prompt_suffix": "\n\nEXTREMELY CRITICAL: Your task is to analyze and decompose requests into well-structured features. You MUST output valid JSON that strictly follows the provided schema. Focus on identifying the underlying user intent, breaking down features, and assessing risks. Respond with JSON ONLY - no extra text or explanations."
            },

            # Update planner for better context allocation
            "planner": {
                "max_context_pct": 0.60,  # 60% of context window
                "max_abs_tokens": min(100000, int(context_window * 0.6)),
                "prioritize_comments": True,
                "preserve_structure": True,
                "preserve_relevance_order": True,  # Added to maintain search relevance order
                # Add no-workaround directive
                "system_prompt_suffix": "\n\nEXTREMELY CRITICAL: Test-side workarounds are ABSOLUTELY PROHIBITED and must NOT be done under ANY circumstances. All test cases must be properly implemented - NEVER include temporary hacks, mocks, or commented code to make tests pass artificially. Tests must NEVER be modified to accommodate broken code. Implementations MUST have proper functionality that tests verify, not tests that are weakened to accommodate broken implementations. Test integrity is the highest priority and must be maintained AT ALL COSTS. Any solution that requires modifying tests to make them pass is STRICTLY FORBIDDEN."
            },
            # Update generator for smarter file selection
            "generator": {
                "max_context_pct": 0.40,
                "max_abs_tokens": min(50000, int(context_window * 0.4)),
                "prioritize_comments": False,
                "preserve_structure": False,
                "preserve_relevance_order": True,  # Added to maintain search relevance order
                "min_files": 3,  # Ensure at least 3 most relevant files are included
                "max_files": 12,  # Increased from 8 to allow more context when needed
                # Add no-workaround directive
                "system_prompt_suffix": "\n\nEXTREMELY CRITICAL: Test-side workarounds are ABSOLUTELY PROHIBITED and must NOT be done under ANY circumstances. Your code MUST work properly on its own, without ANY modifications to tests. NEVER include temporary hacks, mocks that bypass actual functionality, or modified assertions that weaken test validity. Always implement the proper functionality that satisfies the original test requirements. All fixes MUST be in the implementation code, NEVER in the tests. Modifying tests to make them pass is STRICTLY FORBIDDEN and constitutes a critical failure. Test integrity is the highest priority and must be maintained AT ALL COSTS."
            },
            # Enhanced debugger context
            "error_analyzer": {
                "max_context_pct": 0.50,
                "max_abs_tokens": min(60000, int(context_window * 0.5)),
                "prioritize_comments": False,
                "preserve_structure": False,
                "preserve_relevance_order": True,
                "error_context_lines": 50,
                "include_error_history": True,  # Added to track error patterns
                # Add no-workaround directive
                "system_prompt_suffix": "\n\nEXTREMELY CRITICAL: Test-side workarounds are ABSOLUTELY PROHIBITED and must NOT be done under ANY circumstances. When debugging, you MUST fix the actual implementation code to properly satisfy test requirements - NEVER modify the tests to accommodate broken implementations. NEVER suggest commenting out assertions, weakening test conditions, adding sleeps/delays, or any other testing hacks. Tests exist to verify correct behavior and must NEVER be compromised. All fixes MUST be in the implementation code, NEVER in the tests. Modifying tests to make them pass is STRICTLY FORBIDDEN and constitutes a critical failure. Test integrity is the highest priority and must be maintained AT ALL COSTS."
            }
        }

        # Default allocation
        default_allocation = {
            "max_context_pct": 0.30,
            "max_abs_tokens": min(20000, int(context_window * 0.3)),
            "prioritize_comments": True,
            "preserve_structure": False,
            "preserve_relevance_order": True,  # Default to preserving relevance order
            # Add no-workaround directive to all roles
            "system_prompt_suffix": "\n\nEXTREMELY CRITICAL: Test-side workarounds are ABSOLUTELY PROHIBITED and must NOT be done under ANY circumstances. You MUST fix the actual implementation code to properly satisfy test requirements - NEVER modify the tests to accommodate broken implementations. Tests exist to verify correct behavior and their integrity must be maintained AT ALL COSTS."
        }

        # Return role-specific allocation if available, otherwise use default
        return allocations.get(role.lower(), default_allocation)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    router = RouterAgent()

    plan_meta = {"role": "planner"}
    plan_query = "Create a plan to refactor the user authentication module."
    chosen_plan_model = router.choose_llm(plan_query, plan_meta)
    logger.info("Chosen model for planner: %s", chosen_plan_model)

    gen_meta = {"role": "generator"}
    gen_query = "Implement the following function: def calculate_sum(a, b): ..."
    chosen_gen_model = router.choose_llm(gen_query, gen_meta)
    logger.info("Chosen model for generator: %s", chosen_gen_model)

    scaffold_meta = {"role": "scaffolder"}
    scaffold_query = "Create a basic Flask app structure."
    chosen_scaffold_model = router.choose_llm(scaffold_query, scaffold_meta)
    logger.info("Chosen model for scaffolder: %s", chosen_scaffold_model)

    missing_role_meta = {}
    missing_role_query = "What is Python?"
    chosen_missing_model = router.choose_llm(missing_role_query, missing_role_meta)
    logger.info("Chosen model for missing role: %s", chosen_missing_model)

    invalid_role_meta = {"role": "debugger"}
    invalid_role_query = "Debug this code."
    chosen_invalid_model = router.choose_llm(invalid_role_query, invalid_role_meta)
    logger.info("Chosen model for invalid role: %s", chosen_invalid_model)

    large_query = " ".join(["word"] * 40000)
    chosen_large_plan_model = router.choose_llm(large_query, plan_meta)
    logger.info("Chosen model for large query (planner): %s", chosen_large_plan_model)
