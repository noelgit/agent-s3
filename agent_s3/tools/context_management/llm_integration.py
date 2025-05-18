"""
LLM Integration for Context Management.

This module provides integration points between the Context Manager 
and the LLM utility functions, enabling seamless context optimization
for LLM API calls.
"""

import logging
import traceback
from typing import Dict, Any, Optional, List, Tuple, Union, Callable

from agent_s3.tools.context_management.context_manager import ContextManager

logger = logging.getLogger(__name__)

class LLMContextIntegration:
    """
    Integration layer between LLM utilities and Context Management.
    
    This class provides hooks and middleware for integrating context management
    with LLM API calls in a way that's non-intrusive to existing code.
    """
    
    def __init__(self, context_manager: ContextManager):
        """
        Initialize with a context manager instance.
        
        Args:
            context_manager: The ContextManager instance to use
        """
        self.context_manager = context_manager
    
    def optimize_prompt(self, prompt_data: Dict[str, Any], model_name: str = "default") -> Dict[str, Any]:
        """
        Optimize prompt data by applying context management.
        
        Args:
            prompt_data: The prompt data to optimize
            model_name: Target LLM model name
            
        Returns:
            Optimized prompt data
        """
        # Extract context from prompt data
        context = self._extract_context_from_prompt(prompt_data)
        
        # Skip if no context was found
        if not context:
            return prompt_data
        
        # Optimize the context
        optimized_context = self.context_manager.optimize_context(context, model_name)
        
        # Update the prompt data with optimized context
        updated_prompt = self._update_prompt_with_context(prompt_data, optimized_context)
        
        return updated_prompt
    
    def _extract_context_from_prompt(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract context elements from prompt data.
        
        Args:
            prompt_data: The prompt data to extract context from
            
        Returns:
            Extracted context dictionary
        """
        context = {}
        
        # Look for common context keys in different prompt formats
        
        # OpenAI-style messages format
        if "messages" in prompt_data and isinstance(prompt_data["messages"], list):
            # Extract context from system and user messages
            for message in prompt_data["messages"]:
                # Extract code context from content
                if message.get("role") == "system" and "content" in message:
                    code_blocks = self._extract_code_blocks(message["content"])
                    if code_blocks:
                        context["code_context"] = code_blocks
                
                # Extract tool calls context
                if "tool_calls" in message:
                    context["tool_context"] = message["tool_calls"]
            
        # Direct prompt format
        elif "prompt" in prompt_data and isinstance(prompt_data["prompt"], str):
            # Extract code blocks from text
            code_blocks = self._extract_code_blocks(prompt_data["prompt"])
            if code_blocks:
                context["code_context"] = code_blocks
        
        # Direct context format
        elif "context" in prompt_data:
            if isinstance(prompt_data["context"], dict):
                context = prompt_data["context"]
            elif isinstance(prompt_data["context"], str):
                # Simple string context, put in misc_context
                context["misc_context"] = {"content": prompt_data["context"]}
        
        return context
    
    def _extract_code_blocks(self, text: str) -> Dict[str, str]:
        """
        Extract code blocks from text.
        
        Args:
            text: Text to extract code blocks from
            
        Returns:
            Dictionary mapping fake file paths to code content
            
        Note:
            This is a legacy method maintained for backward compatibility.
            The preferred approach is to use the direct context parameter.
        """
        import re
        
        code_blocks = {}
        
        # Pattern for Markdown code blocks
        pattern = r"```(?:(?P<lang>\w+)\n)?(?P<code>.*?)```"
        matches = re.finditer(pattern, text, re.DOTALL)
        
        for i, match in enumerate(matches, 1):
            lang = match.group("lang") or "txt"
            code = match.group("code").strip()
            
            # Create a fake file path for the code block
            file_path = f"code_block_{i}.{lang}"
            code_blocks[file_path] = code
        
        return code_blocks
    
    def _update_prompt_with_context(self, prompt_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update prompt data with optimized context.
        
        Args:
            prompt_data: Original prompt data
            context: Optimized context
            
        Returns:
            Updated prompt data with optimized context
        """
        updated = prompt_data.copy()
        
        # Only use the direct context parameter approach - no more legacy injection into prompts
        if "context" in updated:
            updated["context"] = context
        else:
            # Add context as a direct parameter if it doesn't exist
            updated["context"] = context
        
        return updated
    
    def _replace_code_blocks(self, text: str, code_blocks: Dict[str, str]) -> str:
        """
        Replace code blocks in text with optimized versions.
        
        Args:
            text: Original text with code blocks
            code_blocks: Dictionary of optimized code blocks
            
        Returns:
            Text with optimized code blocks
            
        Note:
            This is a legacy method maintained for backward compatibility.
            The preferred approach is to use the direct context parameter.
            This method is no longer used in the main code path.
        """
        import re
        
        # Pattern for Markdown code blocks
        pattern = r"```(?:(?P<lang>\w+)\n)?(?P<code>.*?)```"
        
        # Find all code blocks
        blocks = list(re.finditer(pattern, text, re.DOTALL))
        
        # If number of blocks doesn't match, don't replace
        if len(blocks) != len(code_blocks):
            return text
        
        # Replace each block with its optimized version
        result = text
        offset = 0
        for i, match in enumerate(blocks, 1):
            block_key = f"code_block_{i}.{match.group('lang') or 'txt'}"
            
            if block_key in code_blocks:
                # Get the optimized code
                optimized_code = code_blocks[block_key]
                
                # Create replacement with original language marker
                lang_marker = match.group("lang") or ""
                replacement = f"```{lang_marker}\n{optimized_code}\n```"
                
                # Calculate positions accounting for previous replacements
                start = match.start() + offset
                end = match.end() + offset
                
                # Replace this block
                result = result[:start] + replacement + result[end:]
                
                # Update offset for future replacements
                offset += len(replacement) - (end - start)
        
        return result

def integrate_with_llm_utils():
    """
    Integrate context management with LLM utilities.
    
    This function patches the llm_utils.py module to add context management.
    """
    try:
        # Handle potential import issues gracefully
        try:
            import agent_s3.llm_utils as llm_utils
            from agent_s3.config import get_config, ConfigModel
        except ImportError as e:
            logger.warning(f"Could not import llm_utils: {e}")
            return False
        
        # Create context manager with config
        try:
            config = get_config()
        except Exception as e:
            logger.warning(f"Error loading config, using defaults: {e}")
            config = ConfigModel()

        cm_cfg = getattr(config, "context_management", {})
            
        # Create context manager and integration
        context_manager = ContextManager(cm_cfg if isinstance(cm_cfg, dict) else cm_cfg.dict())
        integration = LLMContextIntegration(context_manager)
        
        # Check if cached_call_llm exists
        if not hasattr(llm_utils, 'cached_call_llm'):
            logger.warning("llm_utils.cached_call_llm not found, integration skipped")
            return False
            
        # Save original function
        original_cached_call_llm = llm_utils.cached_call_llm
        
        # Create patched function
        def patched_cached_call_llm(prompt, llm, return_kv=False, **kwargs):
            """Patched version with context management"""
            try:
                # Get model name if available
                model_name = getattr(llm, "model_name", "default")
                
                # Convert prompt to structured form for optimization
                if isinstance(prompt, str):
                    prompt_data = {"prompt": prompt}
                elif isinstance(prompt, dict):
                    prompt_data = prompt.copy()  # Use copy to avoid modifying original
                else:
                    prompt_data = {"prompt": str(prompt)}
                    
                # Apply additional kwargs
                for key, value in kwargs.items():
                    if key not in prompt_data:  # Only add if not already present
                        prompt_data[key] = value
                
                # Optimize the prompt
                optimized_prompt_data = integration.optimize_prompt(prompt_data, model_name)
                
                # Extract the prompt back
                if isinstance(prompt, str) and "prompt" in optimized_prompt_data:
                    optimized_prompt = optimized_prompt_data["prompt"]
                else:
                    optimized_prompt = optimized_prompt_data
                
                # Remove used kwargs to avoid duplication
                kwargs_to_remove = []
                for key in prompt_data:
                    if key in kwargs and key != "prompt":
                        kwargs_to_remove.append(key)
                
                for key in kwargs_to_remove:
                    kwargs.pop(key)
                
                # Call original function with optimized prompt
                return original_cached_call_llm(optimized_prompt, llm, return_kv, **kwargs)
                
            except Exception as e:
                # Log the error but fall back to original behavior
                logger.error(f"Error in context optimization: {e}")
                logger.debug(traceback.format_exc())
                # Fall back to original function without optimization
                return original_cached_call_llm(prompt, llm, return_kv, **kwargs)
        
        # Apply patch
        llm_utils.cached_call_llm = patched_cached_call_llm
        
        # Start background optimization if enabled (but don't fail if it doesn't work)
        try:
            if config.get("context_management", {}).get("background_enabled", True):
                context_manager._start_background_optimization()
        except Exception as e:
            logger.warning(f"Failed to start background optimization: {e}")
            # Continue anyway
            
        logger.info("Successfully integrated context management with LLM utilities")
        return True
        
    except Exception as e:
        logger.error(f"Failed to integrate context management with LLM utilities: {e}")
        logger.debug(traceback.format_exc())
        return False
