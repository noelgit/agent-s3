"""Router Agent for selecting appropriate LLMs."""

import os
import json
import logging
import time
from time import sleep
import requests
import traceback  # Added import
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Initialize models_by_role at module level to avoid undefined global variable
_models_by_role = {}

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

def _validate_entry(entry: Dict[str, Any]):
    """Ensure llm.json entry has required keys/types, else raise."""
    required = {
        'model': str,
        'role': (str, list),
        'context_window': int,
        'parameters': dict,
        'api': dict
    }
    for key, typ in required.items():
        if key not in entry or not isinstance(entry[key], typ):
            raise ValueError(f"llm.json entry missing or invalid '{key}': {entry}")
    api = entry['api']
    for sub in ['endpoint', 'auth_header']:
        if sub not in api or not isinstance(api[sub], str):
            raise ValueError(f"llm.json 'api.{sub}' missing or invalid for model '{entry.get('model')}'")

def _load_llm_config():
    """Load the LLM configuration from llm.json."""
    try:
        config_path = os.path.join(os.getcwd(), 'llm.json')
        if not os.path.exists(config_path):
            logger.error(f"LLM configuration file not found: {config_path}")
            raise FileNotFoundError(f"LLM configuration file not found: {config_path}")
        with open(config_path, 'r') as f:
            llm_config = json.load(f)

        # Validate entries
        for model_info in llm_config:
            _validate_entry(model_info)
        models_by_role = {}
        for model_info in llm_config:
            roles = model_info.get("role")
            if isinstance(roles, str):
                roles = [roles]  # Ensure roles is always a list
            if isinstance(roles, list):
                for role in roles:
                    if role in models_by_role:
                        logger.warning(f"Duplicate role definition found for '{role}'. Using the last definition found in llm.json.")
                    models_by_role[role] = model_info
            else:
                logger.warning(f"Skipping model entry due to invalid or missing 'role': {model_info.get('model')}")

        logger.info(f"Loaded LLM configuration for roles: {list(models_by_role.keys())}")
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

    def __init__(self):
        """Initialize the router agent."""
        global _models_by_role  # Properly reference the global variable
        if not _models_by_role:
            _models_by_role = _load_llm_config()
        # Metrics collector
        self.metrics = MetricsTracker()
        # Circuit breaker state
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}

    def choose_llm(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Choose the appropriate LLM based on the query and metadata."""
        if metadata is None:
            metadata = {}

        role = metadata.get("role")
        if not role:
            logger.warning("No 'role' provided in metadata. Cannot determine appropriate LLM.")
            return None

        if not _models_by_role:
            logger.error("LLM configuration is missing. Cannot choose LLM.")
            return None

        model_info = _models_by_role.get(role)

        if not model_info:
            logger.warning(f"No model configured for role: '{role}'. Available roles: {list(_models_by_role.keys())}")
            return None

        model_name = model_info.get("model")
        context_window = model_info.get("context_window")

        if not model_name:
            logger.error(f"Configuration for role '{role}' is missing the 'model' name.")
            return None

        try:
            estimated_tokens = len(query.split())  # Simplified token estimation
            logger.info(f"Estimated tokens for query: {estimated_tokens} (using model context: {model_name})")

            if context_window and estimated_tokens > context_window:
                logger.warning(
                    f"Estimated token count ({estimated_tokens}) exceeds the context window "
                    f"({context_window}) for model '{model_name}' (role: '{role}'). "
                    f"Input may be truncated by the LLM."
                )
        except Exception as e:
            logger.exception(f"Failed to estimate token count: {e}. Skipping context window check.")

        logger.info(f"Routing to model '{model_name}' for role '{role}'.")
        return model_name

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
            **kwargs: Additional parameters for the API call
        
        Returns:
            The LLM response text or None if the call fails
        """
        model_info = _models_by_role.get(role)
        if not model_info:
            scratchpad.log("RouterAgent", f"Error: No model configured for role: '{role}'", level="error")
            return None

        model_name = model_info.get("model")
        if not model_name:
            scratchpad.log("RouterAgent", f"Error: Configuration for role '{role}' is missing the 'model' name.", level="error")
            return None

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
            if (self._failure_counts[model_name] >= failure_threshold and
                    time.time() < self._last_failure_time[model_name] + cooldown):
                scratchpad.log("RouterAgent", f"Circuit breaker tripped for {model_name} (Role: {role}). Attempting fallback if available.", level="warning")
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
                    **kwargs
                )
                self._failure_counts[model_name] = 0  # Reset failure count on success
                primary_failed = False
                scratchpad.log("RouterAgent", f"Successfully called {model_name} (Role: {role}) on attempt {attempt + 1}")
                break  # Success
            except Exception as e:
                self._failure_counts[model_name] += 1
                self._last_failure_time[model_name] = time.time()
                scratchpad.log("RouterAgent", f"Attempt {attempt + 1}/{max_retries} failed for {model_name} (Role: {role}): {e}", level="warning")
                if attempt + 1 == max_retries:
                    primary_failed = True
                    scratchpad.log("RouterAgent", f"{model_name} (Role: {role}) failed after {max_retries} attempts.", level="error")
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
        tech_stack: Optional[Dict[str, Any]] = None,  # Added tech_stack parameter
        code_context: Optional[Dict[str, str]] = None,  # Added code_context parameter
        **kwargs: Any
    ) -> Optional[str]:
        """Executes a single LLM API call.
        
        Now supports enhanced context with tech stack and code snippets.
        """
        start = time.time()
        model_name = model_info["model"]
        api_details = model_info.get("api", {})
        endpoint_str = api_details.get("endpoint")
        auth_header_template = api_details.get("auth_header")
        
        # Get the context window size for token management
        context_window = model_info.get("context_window", 8000)  # Default to 8K if not specified
        
        # Enhanced prompt with tech stack and code context if provided
        enhanced_user_prompt = user_prompt
        
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
        
        # Include relevant code context if available
        if code_context:
            # Simple token estimation (can be refined)
            def estimate_tokens(text):
                return len(text.split()) * 1.3  # Rough estimation: words * 1.3
            
            code_context_str = ""
            current_tokens = 0
            max_context_tokens = min(1500, context_window * 0.15)  # Use at most 15% of context window for code
            
            # Sort files by likely relevance (can be refined with more sophisticated relevance scoring)
            sorted_files = sorted(code_context.items(), key=lambda x: len(x[1]), reverse=False)
            
            for path, content in sorted_files:
                context_header = f"--- {path} ---\n"
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
                    
                    code_context_str += "\n... (more files truncated due to token limits)"
                    break  # Stop adding more files once limit is hit
            
            if code_context_str:
                enhanced_user_prompt = f"Relevant Code Context:\n{code_context_str}\n\n{enhanced_user_prompt}"
                scratchpad.log("RouterAgent", 
                    f"Added code context for {role} (estimated {current_tokens:.0f} tokens, " 
                    f"{len(code_context)} files, limit {max_context_tokens:.0f})")
        
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
            error_msg = f"API call to {model_name} failed: {e}. Response: {response_text[:500]}"
            scratchpad.log("RouterAgent", error_msg, level="error")
            raise ConnectionError(error_msg)
        except (json.JSONDecodeError, KeyError, IndexError, AttributeError, ValueError) as e:
            duration = time.time() - start
            self.metrics.record(role, model_name, duration, False, 0)
            error_msg = f"Failed to process response from {model_name}: {e}. Response data: {response.text[:500]}"
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

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    router = RouterAgent()

    plan_meta = {"role": "planner"}
    plan_query = "Create a plan to refactor the user authentication module."
    chosen_plan_model = router.choose_llm(plan_query, plan_meta)
    print(f"Chosen model for planner: {chosen_plan_model}")

    gen_meta = {"role": "generator"}
    gen_query = "Implement the following function: def calculate_sum(a, b): ..."
    chosen_gen_model = router.choose_llm(gen_query, gen_meta)
    print(f"Chosen model for generator: {chosen_gen_model}")

    scaffold_meta = {"role": "scaffolder"}
    scaffold_query = "Create a basic Flask app structure."
    chosen_scaffold_model = router.choose_llm(scaffold_query, scaffold_meta)
    print(f"Chosen model for scaffolder: {chosen_scaffold_model}")

    missing_role_meta = {}
    missing_role_query = "What is Python?"
    chosen_missing_model = router.choose_llm(missing_role_query, missing_role_meta)
    print(f"Chosen model for missing role: {chosen_missing_model}")

    invalid_role_meta = {"role": "debugger"}
    invalid_role_query = "Debug this code."
    chosen_invalid_model = router.choose_llm(invalid_role_query, invalid_role_meta)
    print(f"Chosen model for invalid role: {chosen_invalid_model}")

    large_query = " ".join(["word"] * 40000)
    chosen_large_plan_model = router.choose_llm(large_query, plan_meta)
    print(f"Chosen model for large query (planner): {chosen_large_plan_model}")
