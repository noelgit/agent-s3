"""
Enhanced LLM Integration for Context Management.

This module provides integration points between the Context Manager
and the LLM utility functions, enabling seamless context optimization
for LLM API calls with unified context management support.
"""

import logging
import traceback
import time
from typing import Dict, Any, Optional, Union

from agent_s3.tools.context_management.context_manager import ContextManager
from .context_monitoring import get_context_monitor, monitor_context_operation

# Define ContextSource and ContextResult locally since unified_context_manager was removed
class ContextSource:
    # Define constants that were previously in unified_context_manager
    AUTO = "auto"
    LEGACY = "legacy"
    COORDINATOR = "coordinator"
    
    def __init__(self, source_type: str, priority: int = 1):
        self.source_type = source_type
        self.priority = priority

class ContextResult:
    def __init__(self, content: Any, source: ContextSource, tokens: int = 0):
        self.content = content
        self.source = source
        self.tokens = tokens

logger = logging.getLogger(__name__)


class EnhancedLLMContextIntegration:
    """
    Enhanced integration layer between LLM utilities and Context Management.

    This class provides hooks and middleware for integrating context management
    with LLM API calls with support for unified context management, monitoring,
    and intelligent optimization.
    """

    def __init__(self, 
                 context_manager: Optional[ContextManager] = None,
                 use_unified_manager: bool = True,
                 enable_monitoring: bool = True):
        """
        Initialize with context management configuration.

        Args:
            context_manager: Optional specific ContextManager instance
            use_unified_manager: Whether to use the unified context manager
            enable_monitoring: Whether to enable context monitoring
        """
        self.context_manager = context_manager
        self.use_unified_manager = use_unified_manager
        self.enable_monitoring = enable_monitoring
        
        # Get consolidated context manager if enabled (unified_context_manager removed)
        if self.use_unified_manager:
            # Use the provided context manager as the unified manager
            self.unified_manager = context_manager
        else:
            self.unified_manager = None
            
        # Get monitor if enabled
        if self.enable_monitoring:
            self.monitor = get_context_monitor()
        else:
            self.monitor = None
            
        logger.info(f"Enhanced LLM Context Integration initialized "
                   f"(unified: {use_unified_manager}, monitoring: {enable_monitoring})")

    @monitor_context_operation("prompt_optimization", "llm_integration")
    def optimize_prompt(
        self, 
        prompt_data: Dict[str, Any], 
        context: Union[Dict[str, Any], str, None] = None,
        context_source: ContextSource = ContextSource.AUTO,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize prompt data using enhanced context management.

        Args:
            prompt_data: The prompt data to optimize
            context: Context data (dict, string, or None)
            context_source: Which context source to prefer
            **kwargs: Additional context parameters

        Returns:
            The prompt data updated with optimized context
        """
        start_time = time.time()
        
        try:
            # Handle different context input types
            if isinstance(context, str):
                # If context is a string query, retrieve context
                context_result = self._get_context(context, context_source, **kwargs)
                optimized_context = context_result.content
                metadata = context_result.metadata
            elif isinstance(context, dict):
                # If context is a dict, optimize it directly
                optimized_context = self._optimize_context_dict(context)
                metadata = {'source': 'provided_dict'}
            elif context is None:
                # Try to extract context from prompt_data
                context_query = self._extract_context_query(prompt_data)
                if context_query:
                    context_result = self._get_context(context_query, context_source, **kwargs)
                    optimized_context = context_result.content
                    metadata = context_result.metadata
                else:
                    # No context available
                    optimized_context = ""
                    metadata = {'source': 'none'}
            else:
                logger.warning(f"Unsupported context type: {type(context)}")
                optimized_context = str(context)
                metadata = {'source': 'fallback'}

            # Update prompt_data with optimized context
            enhanced_prompt_data = self._integrate_context_into_prompt(
                prompt_data, optimized_context, metadata
            )
            
            duration = time.time() - start_time
            logger.debug(f"Prompt optimization completed in {duration:.2f}s")
            
            return enhanced_prompt_data
            
        except Exception as e:
            logger.error(f"Error optimizing prompt: {e}")
            if self.monitor:
                self.monitor.record_event(
                    event_type="prompt_optimization_error",
                    source="llm_integration",
                    query=str(prompt_data).get('content', 'unknown')[:100],
                    success=False,
                    error_message=str(e)
                )
            return prompt_data  # Return original on error

    def _get_context(self, query: str, source: ContextSource, **kwargs) -> ContextResult:
        """Get context using the appropriate context manager."""
        if self.use_unified_manager and self.unified_manager:
            return self.unified_manager.get_context(query, source, **kwargs)
        elif self.context_manager:
            # Use legacy context manager
            context_data = self.context_manager.get_context(query, **kwargs)
            return ContextResult(
                content=str(context_data),
                source=ContextSource.LEGACY,
                metadata={'query': query, 'kwargs': kwargs},
                confidence=0.8
            )
        else:
            # No context manager available
            logger.warning("No context manager available for context retrieval")
            return ContextResult(
                content="",
                source=ContextSource.AUTO,
                metadata={'error': 'No context manager available'},
                confidence=0.0
            )

    def _optimize_context_dict(self, context_dict: Dict[str, Any]) -> str:
        """Optimize a context dictionary into a formatted string."""
        if self.context_manager and hasattr(self.context_manager, 'optimize_context'):
            try:
                return self.context_manager.optimize_context(context_dict)
            except Exception as e:
                logger.warning(f"Context optimization failed: {e}")
        
        # Fallback to simple formatting
        return self._format_context_dict(context_dict)

    def _format_context_dict(self, context_dict: Dict[str, Any]) -> str:
        """Format a context dictionary into a readable string."""
        if not context_dict:
            return ""
        
        formatted_parts = []
        for key, value in context_dict.items():
            if isinstance(value, (str, int, float, bool)):
                formatted_parts.append(f"{key}: {value}")
            elif isinstance(value, (list, tuple)):
                formatted_parts.append(f"{key}: {', '.join(map(str, value))}")
            elif isinstance(value, dict):
                nested = ', '.join(f"{k}: {v}" for k, v in value.items())
                formatted_parts.append(f"{key}: {{{nested}}}")
            else:
                formatted_parts.append(f"{key}: {str(value)}")
        
        return "\n".join(formatted_parts)

    def _extract_context_query(self, prompt_data: Dict[str, Any]) -> Optional[str]:
        """Extract a context query from prompt data."""
        # Try different keys that might contain useful context queries
        for key in ['content', 'prompt', 'task', 'query', 'message']:
            if key in prompt_data:
                content = prompt_data[key]
                if isinstance(content, str) and len(content) > 10:
                    return content[:200]  # Truncate for context query
        
        return None

    def _integrate_context_into_prompt(self, 
                                     prompt_data: Dict[str, Any], 
                                     context: str, 
                                     metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Integrate optimized context into prompt data."""
        enhanced_data = prompt_data.copy()
        
        if not context.strip():
            return enhanced_data
        
        # Add context to the prompt in different ways based on structure
        if 'messages' in enhanced_data:
            # Chat-style prompt structure
            self._integrate_context_into_messages(enhanced_data, context, metadata)
        elif 'prompt' in enhanced_data:
            # Simple prompt structure
            self._integrate_context_into_simple_prompt(enhanced_data, context, metadata)
        elif 'content' in enhanced_data:
            # Content-based structure
            self._integrate_context_into_content(enhanced_data, context, metadata)
        else:
            # Fallback: add as new field
            enhanced_data['context'] = context
            enhanced_data['context_metadata'] = metadata
        
        return enhanced_data

    def _integrate_context_into_messages(self, 
                                       prompt_data: Dict[str, Any], 
                                       context: str, 
                                       metadata: Dict[str, Any]):
        """Integrate context into chat messages format."""
        messages = prompt_data.get('messages', [])
        
        # Add context as a system message if no system message exists
        has_system = any(msg.get('role') == 'system' for msg in messages)
        
        if not has_system and context.strip():
            context_message = {
                'role': 'system',
                'content': f"Relevant Context:\n{context}"
            }
            messages.insert(0, context_message)
        elif has_system:
            # Append to existing system message
            for msg in messages:
                if msg.get('role') == 'system':
                    msg['content'] += f"\n\nAdditional Context:\n{context}"
                    break
        
        prompt_data['messages'] = messages

    def _integrate_context_into_simple_prompt(self, 
                                            prompt_data: Dict[str, Any], 
                                            context: str, 
                                            metadata: Dict[str, Any]):
        """Integrate context into simple prompt format."""
        original_prompt = prompt_data.get('prompt', '')
        
        if context.strip():
            enhanced_prompt = f"Context:\n{context}\n\nTask:\n{original_prompt}"
            prompt_data['prompt'] = enhanced_prompt

    def _integrate_context_into_content(self, 
                                      prompt_data: Dict[str, Any], 
                                      context: str, 
                                      metadata: Dict[str, Any]):
        """Integrate context into content-based format."""
        original_content = prompt_data.get('content', '')
        
        if context.strip():
            enhanced_content = f"Relevant Context:\n{context}\n\n{original_content}"
            prompt_data['content'] = enhanced_content

    @monitor_context_operation("llm_call_preparation", "llm_integration")  
    def prepare_llm_call(self, 
                        call_params: Dict[str, Any],
                        context_query: Optional[str] = None,
                        context_source: ContextSource = ContextSource.AUTO) -> Dict[str, Any]:
        """
        Prepare an LLM call with optimized context.
        
        Args:
            call_params: Original LLM call parameters
            context_query: Optional query for context retrieval
            context_source: Which context source to use
            
        Returns:
            Enhanced call parameters with optimized context
        """
        try:
            # If context query is provided, get context and optimize prompt
            if context_query:
                enhanced_params = self.optimize_prompt(
                    call_params, 
                    context_query, 
                    context_source
                )
            else:
                enhanced_params = call_params.copy()
            
            # Add metadata about context optimization
            if 'metadata' not in enhanced_params:
                enhanced_params['metadata'] = {}
            
            enhanced_params['metadata']['context_optimized'] = bool(context_query)
            enhanced_params['metadata']['context_source'] = context_source.value
            enhanced_params['metadata']['optimization_timestamp'] = time.time()
            
            return enhanced_params
            
        except Exception as e:
            logger.error(f"Error preparing LLM call: {e}")
            return call_params

    def get_integration_status(self) -> Dict[str, Any]:
        """Get status information about the LLM integration."""
        status = {
            'context_manager_available': self.context_manager is not None,
            'unified_manager_enabled': self.use_unified_manager,
            'unified_manager_available': self.unified_manager is not None,
            'monitoring_enabled': self.enable_monitoring,
            'monitor_available': self.monitor is not None
        }
        
        # Add unified manager health if available
        if self.unified_manager:
            try:
                status['unified_manager_health'] = self.unified_manager.health_check()
                status['unified_manager_metrics'] = self.unified_manager.get_metrics()
            except Exception as e:
                status['unified_manager_error'] = str(e)
        
        # Add monitor metrics if available
        if self.monitor:
            try:
                status['monitor_metrics'] = self.monitor.get_current_metrics()
            except Exception as e:
                status['monitor_error'] = str(e)
        
        return status


class LLMContextIntegration(EnhancedLLMContextIntegration):
    """
    Legacy LLM Context Integration class for backward compatibility.
    
    This maintains the original interface while providing enhanced functionality.
    """
    
    def __init__(self, context_manager: ContextManager):
        """
        Initialize with a context manager instance (legacy interface).

        Args:
            context_manager: The ContextManager instance to use
        """
        super().__init__(
            context_manager=context_manager,
            use_unified_manager=False,  # Use legacy mode for compatibility
            enable_monitoring=True
        )

    def optimize_prompt(
        self, prompt_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize prompt data using the provided context.

        Args:
            prompt_data: The prompt data to optimize.
            context: Structured context to include in the prompt.

        Returns:
            The prompt data updated with optimized context.
        """
        # Skip if no context was provided
        if not context:
            return prompt_data

        # Optimize the context
        optimized_context = self.context_manager.optimize_context(context)

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
                # Extract tool calls context
                if "tool_calls" in message:
                    context["tool_context"] = message["tool_calls"]

        # Direct prompt format
        elif "prompt" in prompt_data and isinstance(prompt_data["prompt"], str):
            # Plain text prompt has no structured context
            pass

        # Direct context format
        elif "context" in prompt_data:
            if isinstance(prompt_data["context"], dict):
                context = prompt_data["context"]
            elif isinstance(prompt_data["context"], str):
                # Simple string context, put in misc_context
                context["misc_context"] = {"content": prompt_data["context"]}

        return context


    def _update_prompt_with_context(
        self, prompt_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update prompt data with optimized context.

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
            logger.warning("Could not import llm_utils: %s", e)
            return False

        # Create context manager with config
        try:
            config = get_config()
        except Exception as e:
            logger.warning("Error loading config, using defaults: %s", e)
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

                # Optimize the prompt using provided context if available
                context = prompt_data.get("context", {})
                optimized_prompt_data = integration.optimize_prompt(
                    prompt_data, context
                )

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
                logger.error("Error in context optimization: %s", e)
                logger.debug(traceback.format_exc())
                # Fall back to original function without optimization
                return original_cached_call_llm(prompt, llm, return_kv, **kwargs)

        # Apply patch
        llm_utils.cached_call_llm = patched_cached_call_llm

        # Start background optimization (always enabled, but don't fail if it doesn't work)
        try:
            context_manager._start_background_optimization()
        except Exception as e:
            logger.warning("Failed to start background optimization: %s", e)
            # Continue anyway

        logger.info("Successfully integrated context management with LLM utilities")
        return True

    except Exception as e:
        logger.error("Failed to integrate context management with LLM utilities: %s", e)
        logger.debug(traceback.format_exc())
        return False
