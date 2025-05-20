"""Utility functions for managing LLM API calls with error recovery.

This module provides robust error handling for LLM API calls, including retries,
backoff, and fallback strategies with advanced semantic caching.
"""

import time
from typing import Any, Dict, Optional, Callable, Type, List, Union, Tuple
import requests
import json
import os
import threading
import numpy as np
import logging

# Import GPTCache
try:
    from gptcache import cache
except ImportError:
    cache = None

# Type hint for ScratchpadManager to avoid circular imports
ScratchpadManagerType = Any

# Common retryable errors for LLM API calls
LLM_API_RETRYABLE_ERRORS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,  # For 5xx errors or 429 Too Many Requests
)

# Fallback prompt template when a call fails
FALLBACK_PROMPT_TEMPLATE = "Previous attempt failed. Please re-evaluate the request carefully, " \
                          "focusing on the core task and required output format. Be concise. " \
                          "Original request summary: {prompt_summary}"

# Initialize GPTCache if available
if cache:
    cache.init()

from agent_s3.cache.helpers import read_cache, write_cache
from agent_s3.progress_tracker import progress_tracker


def call_llm_via_supabase(prompt: str, github_token: str, config: Dict[str, Any], timeout: Optional[float] = None) -> str:
    """Call a remote LLM via Supabase edge function.

    Args:
        prompt: Prompt text to send to the remote LLM service.
        github_token: Authenticated GitHub token for authorization.
        config: Configuration dictionary containing Supabase URL and key.
        timeout: Optional request timeout override.

    Returns:
        The text response from the remote service.
    """
    supabase_url = config.get("supabase_url") or os.getenv("SUPABASE_URL")
    api_key = config.get("supabase_service_role_key") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not api_key:
        raise ValueError("Supabase configuration missing")

    headers = {
        "Content-Type": "application/json",
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "X-GitHub-Token": github_token,
    }
    payload = {"prompt": prompt}
    response = requests.post(
        supabase_url,
        json=payload,
        headers=headers,
        timeout=timeout or config.get("llm_default_timeout", 60.0),
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        if "response" in data:
            return data["response"]
        if "choices" in data and data["choices"]:
            # OpenAI style response
            choice = data["choices"][0]
            if isinstance(choice, dict):
                return choice.get("text") or choice.get("message", {}).get("content", "")
    return response.text

def cached_call_llm(prompt, llm, return_kv=False, **kwargs):
    """Use semantic cache for LLM calls for better performance and cost optimization.
    
    Args:
        prompt: The prompt text or structured prompt data to send to the LLM
        llm: The LLM client instance to use for generation
        return_kv: Whether to return the KV tensor along with the response
        **kwargs: Additional arguments to pass to the LLM call
        
    Returns:
        The LLM response, either from cache or freshly generated
        If return_kv is True, returns a tuple (response, kv_tensor)
    """
    method_name = kwargs.pop('method_name', 'generate')
    config = kwargs.pop('config', {})
    scratchpad_manager = kwargs.pop('scratchpad_manager', None)
    prompt_summary = kwargs.pop('prompt_summary', prompt[:100] + "..." if len(prompt) > 100 else prompt)

    use_remote_llm = getattr(config, 'use_remote_llm', False)
    github_token = getattr(config, 'github_token', None)

    if use_remote_llm:
        try:
            from agent_s3.auth import load_token
            if not github_token:
                token_data = load_token()
                if token_data:
                    github_token = token_data.get('token') or token_data.get('access_token')
        except Exception:
            github_token = github_token

        if not github_token:
            raise ValueError('GitHub token required for remote LLM')

        class _RemoteLLM:
            def __init__(self, cfg, token):
                self.cfg = cfg
                self.token = token

            def generate(self, params):
                return call_llm_via_supabase(
                    params.get('prompt', ''),
                    self.token,
                    self.cfg,
                    timeout=params.get('timeout', self.cfg.get('llm_default_timeout', 60.0)),
                )

            def attach_kv(self, _kv):
                return None

            def get_kv_tensor(self):
                return None

        llm_to_use = _RemoteLLM(config, github_token)
    else:
        llm_to_use = llm

    hit = read_cache(prompt, llm_to_use)
    if hit:
        progress_tracker.increment("semantic_hits")
        return hit
    
    # Convert prompt to the expected format
    prompt_data = {
        'prompt': prompt,
        **kwargs
    }
    
    result = call_llm_with_retry(
        llm_client_instance=llm_to_use,
        method_name=method_name,
        prompt_data=prompt_data,
        config=config,
        scratchpad_manager=scratchpad_manager,
        prompt_summary=prompt_summary
    )

    if not result.get('success') and use_remote_llm:
        if scratchpad_manager:
            scratchpad_manager.log(
                "LLM Utils",
                "Remote LLM failed, falling back to local"
            )
        else:
            logging.warning("Remote LLM failed, falling back to local")

        llm_to_use = llm
        result = call_llm_with_retry(
            llm_client_instance=llm_to_use,
            method_name=method_name,
            prompt_data=prompt_data,
            config=config,
            scratchpad_manager=scratchpad_manager,
            prompt_summary=prompt_summary
        )
    
    if result['success']:
        response = result['response']
        
        # Validate that we received a valid response
        if response is None:
            error_msg = "Received empty response from LLM API"
            if return_kv:
                return f"Error: {error_msg}", None
            return f"Error: {error_msg}"
        
        # Extract the KV tensor if available
        kv_tensor = getattr(llm_to_use, 'get_kv_tensor', lambda: None)()

        if kv_tensor is not None:
            write_cache(prompt, response, kv_tensor)
        elif cache:
            try:
                cache.set(prompt, response)
            except Exception as e:
                logging.warning(f"Cache write failed: {e}")
        
        if return_kv:
            return response, kv_tensor
        return response
    else:
        # Return a default response for error cases
        if return_kv:
            return f"Error: {result['error']}", None
        return f"Error: {result['error']}"

def call_llm_with_retry(
    llm_client_instance: Any,
    method_name: str,
    prompt_data: Dict[str, Any],
    config: Dict[str, Any],
    scratchpad_manager: ScratchpadManagerType,
    prompt_summary: str
) -> Dict[str, Any]:
    """Call an LLM API with retry logic, fallback strategy and caching.
    
    This function attempts to call the specified method on the LLM client,
    with configurable retry logic for transient errors and a fallback strategy
    if all retries fail. Results are cached using GPTCache if available.
    
    Args:
        llm_client_instance: The instantiated LLM client object
        method_name: Name of the method to call on the client
        prompt_data: The data to send to the LLM, including prompts
        config: Configuration dictionary with retry settings
        scratchpad_manager: Instance of ScratchpadManager for logging
        prompt_summary: A brief summary of the prompt (for fallback and logging)
        
    Returns:
        A dictionary with the structure:
        - On success: {'success': True, 'response': response_data}
        - On failure: {'success': False, 'error': error_message, 'details': error_details}
    """
    # Allow scratchpad_manager to be optional
    if scratchpad_manager is None:
        class _NoOpScratchpad:
            def log(self, category: str, message: str, **_kwargs: Any) -> None:
                logging.info(f"[{category}] {message}")

        scratchpad_manager = _NoOpScratchpad()

    # Wrap the LLM client method with GPTCache if available
    try:
        method_to_call = getattr(llm_client_instance, method_name)
    except AttributeError:
        error_msg = f"Method '{method_name}' not found on LLM client"
        scratchpad_manager.log("LLM Utils", f"Error: {error_msg}")
        return {
            'success': False,
            'error': error_msg,
            'details': f"Available methods: {dir(llm_client_instance)}"
        }
    
    # Apply GPTCache decorator if available
    if cache:
        try:
            method_to_call = cache(method_to_call)
        except Exception as e:
            scratchpad_manager.log("LLM Cache", f"GPTCache wrap error: {e}")

    # Get timeout and retry settings from config
    timeout = prompt_data.get('timeout', config.get('llm_default_timeout', 60.0))
    max_retries = config.get('llm_max_retries', 3)
    initial_backoff = config.get('llm_initial_backoff', 1.0)
    backoff_factor = config.get('llm_backoff_factor', 2.0)
    
    # Main retry loop
    last_error = None
    last_error_details = None
    
    for attempt in range(max_retries):
        scratchpad_manager.log("LLM Utils", f"Attempt {attempt + 1}/{max_retries} - Calling LLM API via {method_name}")
        
        try:
            # Clone prompt_data and call LLM via GPTCache-wrapped method
            current_prompt_data = prompt_data.copy()
            current_prompt_data['timeout'] = timeout
            response = method_to_call(current_prompt_data)

            if response is None:
                raise ValueError("LLM API returned None response")
            
            # Log success
            scratchpad_manager.log("LLM Utils", f"LLM API call succeeded on attempt {attempt + 1}")
            
            # Check if this is a cached response
            if isinstance(response, dict) and 'cached' in response:
                # Return with the cached flag preserved
                return {'success': True, 'response': response['response'], 'cached': True}
            # Return success with the response
            return {'success': True, 'response': response}
            
        except LLM_API_RETRYABLE_ERRORS as e:
            # Capture the error for potential later use
            last_error = str(e)
            last_error_details = type(e).__name__
            
            # Check if this is the last attempt
            if attempt < max_retries - 1:
                # Calculate backoff time
                backoff_time = initial_backoff * (backoff_factor ** attempt)
                
                # Log the retry
                scratchpad_manager.log(
                    "LLM Utils",
                    f"Retryable error: {type(e).__name__}: {str(e)}. Retrying in {backoff_time:.2f}s"
                )
                
                # Wait before retrying
                time.sleep(backoff_time)
            else:
                # Log the final retry failure
                scratchpad_manager.log(
                    "LLM Utils",
                    f"Failed after {max_retries} attempts with error: {type(e).__name__}: {str(e)}"
                )
                break
                
        except Exception as e:
            # Non-retryable error
            last_error = str(e)
            last_error_details = type(e).__name__
            
            scratchpad_manager.log(
                "LLM Utils",
                f"Non-retryable error: {type(e).__name__}: {str(e)}"
            )
            break
    
    # All retries failed, check if we should try the fallback strategy
    fallback_strategy = config.get('llm_fallback_strategy', 'none')
    
    if fallback_strategy == 'retry_simplified':
        scratchpad_manager.log("LLM Utils", "Attempting fallback with simplified prompt")
        
        try:
            # Create fallback prompt using the template
            fallback_prompt = FALLBACK_PROMPT_TEMPLATE.format(prompt_summary=prompt_summary)
            
            # Clone prompt_data to avoid modifying the original
            fallback_prompt_data = prompt_data.copy()
            
            # Inject fallback prompt - the exact key depends on the client's expected structure
            # Attempt to find the right key (messages, prompt, etc.)
            if 'messages' in fallback_prompt_data:
                # OpenAI-style API with messages array
                if isinstance(fallback_prompt_data['messages'], list) and len(fallback_prompt_data['messages']) > 0:
                    # Find the user message (typically the last one) and prepend our fallback text
                    for i, msg in enumerate(fallback_prompt_data['messages']):
                        if msg.get('role', '') == 'user':
                            fallback_prompt_data['messages'][i]['content'] = fallback_prompt + "\n\n" + msg['content']
                            break
            elif 'prompt' in fallback_prompt_data:
                # Simple prompt-based API
                fallback_prompt_data['prompt'] = fallback_prompt + "\n\n" + fallback_prompt_data['prompt']
            else:
                # If we can't find a standard key, just add our own
                fallback_prompt_data['fallback_prefix'] = fallback_prompt
            
            # Call the API with the fallback prompt
            response = method_to_call(fallback_prompt_data)
            
            # Basic response validation
            if response is None:
                raise ValueError("Fallback LLM API call returned None response")
            
            # Log success
            scratchpad_manager.log("LLM Utils", "Fallback LLM API call succeeded")
            
            # Return success with the response
            return {
                'success': True,
                'response': response,
                'used_fallback': True
            }
            
        except Exception as e:
            # Fallback also failed
            scratchpad_manager.log(
                "LLM Utils",
                f"Fallback strategy failed with error: {type(e).__name__}: {str(e)}"
            )
            last_error = str(e)
            last_error_details = type(e).__name__
    
    # If we reach here, both the main attempts and fallback (if enabled) have failed
    scratchpad_manager.log("LLM Utils", "All recovery attempts failed")
    
    return {
        'success': False,
        'error': (f"LLM API call failed after {max_retries} attempts" +
                 (f" and fallback" if fallback_strategy != 'none' else "")),
        'details': f"Last error: {last_error_details}: {last_error}"
    }


def get_embedding(
    text: str,
    model: str = "text-embedding-ada-002",
    config: Optional[Dict[str, Any]] = None,
    dimensions: int = 1536,
    retry_count: int = 3
) -> Optional[List[float]]:
    """Generate an embedding vector for the provided text.
    
    This function provides a fallback mechanism for embedding generation
    when the primary embedding service (RouterAgent) is unavailable.
    
    Args:
        text: The text to generate an embedding for
        model: The embedding model to use (default: text-embedding-ada-002)
        config: Optional configuration containing API keys
        dimensions: Target embedding dimensions (default: 1536)
        retry_count: Number of retries on failure
        
    Returns:
        A list of floats representing the embedding vector, or None on failure
    """
    if not text or not text.strip():
        return None
        
    # Load configuration if not provided
    if config is None:
        from agent_s3 import config as app_config
        config = app_config.get_config()
    
    # Try to use OpenRouter API for embeddings
    api_key = getattr(config, 'openrouter_key', None)
    if not api_key:
        # Try OpenAI API key if OpenRouter is not available
        api_key = getattr(config, 'openai_key', None)
        
    if not api_key:
        # No API keys available, return None
        return None
        
    # Prepare API endpoint based on the model
    if model.startswith("openai/"):
        endpoint = "https://api.openrouter.ai/api/v1/embeddings"
        model_name = model  # Keep the full model name for OpenRouter
    else:
        # Assume direct OpenAI API access
        endpoint = "https://api.openai.com/v1/embeddings"
        model_name = model.replace("openai/", "")  # Remove prefix if present
        
    # Prepare HTTP headers
    headers = {
        "Content-Type": "application/json",
    }
    
    # Set the appropriate authorization header
    if endpoint.startswith("https://api.openrouter.ai"):
        headers["Authorization"] = f"Bearer {api_key}"
        headers["HTTP-Referer"] = config.get("openrouter_referer", "http://localhost")
        headers["X-Title"] = config.get("openrouter_title", "Agent-S3")
    else:
        headers["Authorization"] = f"Bearer {api_key}"
    
    # Prepare the request payload
    payload = {
        "model": model_name,
        "input": text[:8192],  # Limit input to 8K characters
    }
    
    # Retry logic
    for attempt in range(retry_count):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract embedding based on API response format
            if "data" in data and len(data["data"]) > 0:
                # OpenAI/OpenRouter format
                embedding = data["data"][0].get("embedding")
                if embedding:
                    # Ensure we return the requested dimensions
                    if len(embedding) != dimensions:
                        # Pad or truncate to match requested dimensions
                        if len(embedding) > dimensions:
                            return embedding[:dimensions]
                        else:
                            padded = embedding + [0.0] * (dimensions - len(embedding))
                            return padded
                    return embedding
            
            # If we couldn't extract the embedding, log and retry
            print(f"Failed to extract embedding from response: {data}")
            
        except Exception as e:
            print(f"Embedding generation attempt {attempt+1} failed: {e}")
            if attempt == retry_count - 1:
                # Final attempt failed
                return None
                
            # Wait before retrying (simple exponential backoff)
            time.sleep(2 ** attempt)
    
    # If all attempts failed or we couldn't extract the embedding
    return None
