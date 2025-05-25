"""LLM integration utilities for planning module.

This module contains functions for calling LLMs with retry logic and parsing responses.
"""

import json
import logging
import re
import time
import random
from typing import Dict, Any
from ..tools.context_management.token_budget import TokenEstimator
from .json_validation import validate_json_schema, repair_json_structure

logger = logging.getLogger(__name__)


class JSONPlannerError(Exception):
    """Exception raised when JSON planning operations fail."""
    pass


def call_llm_with_retry(
    router_agent,
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Any],
    retries: int = 2,
    initial_backoff: float = 1.0,
) -> str:
    """
    Helper function to call LLM with retry logic.
    
    Args:
        router_agent: Router agent instance for LLM calls
        system_prompt: System prompt for the LLM
        user_prompt: User prompt for the LLM
        config: Configuration for the LLM call
        retries: Number of retry attempts
        initial_backoff: Initial backoff time in seconds
        
    Returns:
        LLM response text
        
    Raises:
        JSONPlannerError: If LLM call fails after retries
    """
    estimator = TokenEstimator()
    prompt_tokens = estimator.estimate_tokens_for_text(system_prompt) + estimator.estimate_tokens_for_text(user_prompt)
    safe_max = max(config.get("max_tokens", 0) - prompt_tokens, 0)
    config = {**config, "max_tokens": safe_max}

    try:
        response = router_agent.call_llm_by_role(
            role='planner',
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config
        )
        if not response:
            raise ValueError("LLM returned an empty response.")
        return response
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise JSONPlannerError(f"LLM call failed after retries: {e}")


def parse_and_validate_json(
    response_text: str,
    enforce_schema: bool = True,
    repair_mode: bool = False,
    validation_config: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Parse and validate JSON response from LLM.
    
    Args:
        response_text: Raw response text from LLM
        enforce_schema: Whether to enforce schema validation
        repair_mode: Whether to attempt repair if validation fails
        validation_config: Additional validation configuration
        
    Returns:
        Parsed and validated JSON data
        
    Raises:
        JSONPlannerError: If parsing or validation fails
    """
    if validation_config is None:
        validation_config = {}
    
    # Extract JSON from response
    try:
        parsed_json = _extract_json_from_response_text(response_text)
        if not parsed_json:
            raise ValueError("No valid JSON found in response")
            
        logger.info("Successfully extracted JSON from response")
        
    except Exception as e:
        logger.error("Failed to extract JSON from response: %s", e)
        raise JSONPlannerError(f"Failed to parse JSON: {e}")

    # Validate schema if requested
    if enforce_schema:
        try:
            is_valid, error_message, valid_indices = validate_json_schema(parsed_json)
            
            if not is_valid:
                logger.warning("Schema validation failed: %s", error_message)
                
                if repair_mode:
                    logger.info("Attempting to repair JSON structure")
                    parsed_json = repair_json_structure(parsed_json)
                    
                    # Re-validate after repair
                    is_valid, error_message, valid_indices = validate_json_schema(parsed_json)
                    if not is_valid:
                        raise ValueError(f"JSON repair failed: {error_message}")
                    else:
                        logger.info("Successfully repaired JSON structure")
                else:
                    raise ValueError(f"Schema validation failed: {error_message}")
            else:
                logger.info("Schema validation passed")
                
        except Exception as e:
            logger.error("Schema validation error: %s", e)
            raise JSONPlannerError(f"Schema validation failed: {e}")

    return parsed_json


def retry_with_backoff(
    func,
    max_retries: int = 3,
    initial_backoff: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_backoff: float = 30.0
):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        backoff_multiplier: Multiplier for backoff time
        max_backoff: Maximum backoff time
        
    Returns:
        Function result
        
    Raises:
        Exception: Last exception if all retries fail
    """
    last_exception = None
    backoff = initial_backoff
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries:
                # Add some jitter to prevent thundering herd
                jitter = random.uniform(0.1, 0.3) * backoff
                sleep_time = min(backoff + jitter, max_backoff)
                
                logger.warning(
                    "Attempt %d failed, retrying in %.2f seconds: %s",
                    attempt + 1, sleep_time, str(e)
                )
                
                time.sleep(sleep_time)
                backoff *= backoff_multiplier
            else:
                logger.error("All retry attempts failed")
                
    # Re-raise the last exception
    raise last_exception


def _extract_json_from_response_text(text: str) -> Dict[str, Any]:
    """
    Extract JSON from response text.
    
    Args:
        text: Response text that may contain JSON
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If no valid JSON is found
    """
    # Try to find JSON block with triple backticks
    json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    match = re.search(json_pattern, text, re.DOTALL)
    
    if match:
        json_text = match.group(1).strip()
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass
    
    # Try to find JSON object directly
    json_pattern = r'\{[^{}]*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # Try to parse the entire text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        raise ValueError("No valid JSON found in response")


def get_openrouter_params() -> Dict[str, Any]:
    """
    Get OpenRouter-specific parameters for LLM calls.
    
    Returns:
        Dictionary of OpenRouter parameters
    """
    return {
        "provider": {
            "order": [
                "Together",
                "DeepInfra", 
                "Lepton",
                "Fireworks"
            ],
            "allow_fallbacks": True
        },
        "models": [
            "meta-llama/llama-3.1-405b-instruct",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-70b-instruct"
        ]
    }