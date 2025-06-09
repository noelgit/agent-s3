"""
Unified Context Management System

This module provides a unified interface for both legacy and new context management systems,
eliminating confusion and providing seamless integration across the codebase.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# The legacy context_manager was consolidated into tools.context_management
from .context_manager import ContextManager as LegacyContextManager
from .context_manager import ContextManager as NewContextManager
from .coordinator_integration import CoordinatorContextIntegration


logger = logging.getLogger(__name__)


class ContextSource(Enum):
    """Enumeration of available context sources."""
    LEGACY = "legacy"
    NEW = "new"
    UNIFIED = "unified"
    AUTO = "auto"


@dataclass
class ContextResult:
    """Structured result from context retrieval operations."""
    content: str
    source: ContextSource
    metadata: Dict[str, Any]
    confidence: float
    token_count: Optional[int] = None
    retrieval_time: Optional[float] = None


class UnifiedContextManager:
    """
    Unified interface for context management that coordinates between legacy and new systems.
    
    This class provides:
    - Seamless switching between context management systems
    - Deduplication of overlapping context
    - Performance monitoring and optimization
    - Fallback mechanisms for robust error handling
    """
    
    def __init__(self, 
                 prefer_new_system: bool = True,
                 enable_deduplication: bool = True,
                 max_token_limit: Optional[int] = None):
        """
        Initialize the unified context manager.
        
        Args:
            prefer_new_system: Whether to prefer the new context management system
            enable_deduplication: Whether to deduplicate overlapping context
            max_token_limit: Maximum token limit for context retrieval
        """
        self.prefer_new_system = prefer_new_system
        self.enable_deduplication = enable_deduplication
        self.max_token_limit = max_token_limit
        
        # Initialize both context managers
        try:
            self.legacy_manager = LegacyContextManager()
            self.legacy_available = True
            logger.info("Legacy context manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize legacy context manager: {e}")
            self.legacy_manager = None
            self.legacy_available = False
            
        try:
            self.new_manager = NewContextManager()
            self.new_available = True
            logger.info("New context manager initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize new context manager: {e}")
            self.new_manager = None
            self.new_available = False
            
        # Initialize coordinator integration
        try:
            self.coordinator_integration = CoordinatorContextIntegration()
            self.coordinator_available = True
            logger.info("Coordinator context integration initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize coordinator integration: {e}")
            self.coordinator_integration = None
            self.coordinator_available = False
            
        # Context cache for deduplication
        self._context_cache: Dict[str, ContextResult] = {}
        self._metrics = {
            'legacy_calls': 0,
            'new_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'deduplication_saves': 0
        }
    
    def get_context(self, 
                   query: str, 
                   source: ContextSource = ContextSource.AUTO,
                   **kwargs) -> ContextResult:
        """
        Retrieve context using the unified interface.
        
        Args:
            query: The context query or identifier
            source: Which context source to use
            **kwargs: Additional arguments passed to the underlying managers
            
        Returns:
            ContextResult with unified structure
            
        Raises:
            RuntimeError: If no context managers are available
        """
        import time
        start_time = time.time()
        
        # Check cache first if deduplication is enabled
        cache_key = f"{source.value}:{query}:{hash(str(sorted(kwargs.items())))}"
        if self.enable_deduplication and cache_key in self._context_cache:
            self._metrics['cache_hits'] += 1
            result = self._context_cache[cache_key]
            logger.debug(f"Context cache hit for query: {query[:50]}...")
            return result
            
        self._metrics['cache_misses'] += 1
        
        # Determine which context manager to use
        if source == ContextSource.AUTO:
            source = self._determine_best_source(query, **kwargs)
        
        # Retrieve context from the appropriate source
        try:
            if source == ContextSource.NEW and self.new_available:
                result = self._get_context_from_new(query, **kwargs)
                self._metrics['new_calls'] += 1
            elif source == ContextSource.LEGACY and self.legacy_available:
                result = self._get_context_from_legacy(query, **kwargs)
                self._metrics['legacy_calls'] += 1
            elif source == ContextSource.UNIFIED:
                result = self._get_unified_context(query, **kwargs)
            else:
                # Fallback logic
                result = self._get_fallback_context(query, **kwargs)
                
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            result = self._get_fallback_context(query, **kwargs)
        
        # Add timing information
        result.retrieval_time = time.time() - start_time
        
        # Cache the result if deduplication is enabled
        if self.enable_deduplication:
            self._context_cache[cache_key] = result
            
        return result
    
    def _determine_best_source(self, query: str, **kwargs) -> ContextSource:
        """
        Determine the best context source based on query characteristics and system availability.
        """
        # Prefer new system if available and configured
        if self.prefer_new_system and self.new_available:
            return ContextSource.NEW
        elif self.legacy_available:
            return ContextSource.LEGACY
        elif self.new_available:
            return ContextSource.NEW
        else:
            raise RuntimeError("No context managers available")
    
    def _get_context_from_new(self, query: str, **kwargs) -> ContextResult:
        """Retrieve context from the new context management system."""
        try:
            # Call the new context manager's get_context method
            if hasattr(self.new_manager, 'get_context'):
                context_data = self.new_manager.get_context(query, **kwargs)
            else:
                # Fallback to available methods
                context_data = self._call_new_manager_fallback(query, **kwargs)
                
            return ContextResult(
                content=str(context_data),
                source=ContextSource.NEW,
                metadata={'query': query, 'kwargs': kwargs},
                confidence=0.9,  # High confidence for new system
                token_count=self._estimate_token_count(str(context_data))
            )
        except Exception as e:
            logger.error(f"Error in new context manager: {e}")
            raise
    
    def _get_context_from_legacy(self, query: str, **kwargs) -> ContextResult:
        """Retrieve context from the legacy context management system."""
        try:
            # Call the legacy context manager
            if hasattr(self.legacy_manager, 'get_context'):
                context_data = self.legacy_manager.get_context(query, **kwargs)
            else:
                # Fallback to available methods
                context_data = self._call_legacy_manager_fallback(query, **kwargs)
                
            return ContextResult(
                content=str(context_data),
                source=ContextSource.LEGACY,
                metadata={'query': query, 'kwargs': kwargs},
                confidence=0.8,  # Good confidence for legacy system
                token_count=self._estimate_token_count(str(context_data))
            )
        except Exception as e:
            logger.error(f"Error in legacy context manager: {e}")
            raise
    
    def _get_unified_context(self, query: str, **kwargs) -> ContextResult:
        """
        Retrieve context from both systems and intelligently combine them.
        """
        results = []
        
        # Try to get context from both systems
        if self.new_available:
            try:
                new_result = self._get_context_from_new(query, **kwargs)
                results.append(new_result)
            except Exception as e:
                logger.warning(f"New context manager failed: {e}")
                
        if self.legacy_available:
            try:
                legacy_result = self._get_context_from_legacy(query, **kwargs)
                results.append(legacy_result)
            except Exception as e:
                logger.warning(f"Legacy context manager failed: {e}")
        
        if not results:
            raise RuntimeError("All context managers failed")
        
        # Combine and deduplicate results
        combined_content = self._combine_context_results(results)
        
        return ContextResult(
            content=combined_content,
            source=ContextSource.UNIFIED,
            metadata={
                'query': query, 
                'kwargs': kwargs,
                'sources_used': [r.source.value for r in results],
                'deduplication_applied': self.enable_deduplication
            },
            confidence=max(r.confidence for r in results),
            token_count=self._estimate_token_count(combined_content)
        )
    
    def _get_fallback_context(self, query: str, **kwargs) -> ContextResult:
        """
        Provide fallback context when all other methods fail.
        """
        logger.warning(f"Using fallback context for query: {query}")
        
        # Try each available system in order of preference
        fallback_attempts = []
        
        if self.new_available:
            fallback_attempts.append(('new', self._get_context_from_new))
        if self.legacy_available:
            fallback_attempts.append(('legacy', self._get_context_from_legacy))
            
        for system_name, get_func in fallback_attempts:
            try:
                return get_func(query, **kwargs)
            except Exception as e:
                logger.warning(f"Fallback attempt with {system_name} failed: {e}")
        
        # Final fallback - return empty context with warning
        return ContextResult(
            content="",
            source=ContextSource.AUTO,
            metadata={'query': query, 'error': 'All context retrieval methods failed'},
            confidence=0.0
        )
    
    def _call_new_manager_fallback(self, query: str, **kwargs) -> Any:
        """Fallback method calls for new context manager."""
        # Try different method names that might exist
        for method_name in ['retrieve_context', 'get_relevant_context', 'search_context']:
            if hasattr(self.new_manager, method_name):
                method = getattr(self.new_manager, method_name)
                return method(query, **kwargs)
        
        # If no methods work, return the manager itself or empty string
        return str(self.new_manager) if self.new_manager else ""
    
    def _call_legacy_manager_fallback(self, query: str, **kwargs) -> Any:
        """Fallback method calls for legacy context manager."""
        # Try different method names that might exist
        for method_name in ['retrieve_context', 'get_relevant_context', 'search_context']:
            if hasattr(self.legacy_manager, method_name):
                method = getattr(self.legacy_manager, method_name)
                return method(query, **kwargs)
        
        # If no methods work, return the manager itself or empty string
        return str(self.legacy_manager) if self.legacy_manager else ""
    
    def _combine_context_results(self, results: List[ContextResult]) -> str:
        """
        Intelligently combine context results from multiple sources.
        """
        if not results:
            return ""
        
        if len(results) == 1:
            return results[0].content
        
        # If deduplication is enabled, remove overlapping content
        if self.enable_deduplication:
            deduplicated_content = self._deduplicate_content([r.content for r in results])
            self._metrics['deduplication_saves'] += len(results) - len(deduplicated_content.split('\n'))
            return deduplicated_content
        else:
            # Simple concatenation with source labels
            combined = []
            for result in results:
                combined.append(f"=== Context from {result.source.value} ===")
                combined.append(result.content)
                combined.append("")
            
            return "\n".join(combined)
    
    def _deduplicate_content(self, content_list: List[str]) -> str:
        """
        Remove duplicate lines and sections from multiple content sources.
        """
        all_lines = []
        seen_lines = set()
        
        for content in content_list:
            lines = content.split('\n')
            for line in lines:
                line_stripped = line.strip()
                if line_stripped and line_stripped not in seen_lines:
                    seen_lines.add(line_stripped)
                    all_lines.append(line)
        
        return '\n'.join(all_lines)
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate the token count of the given text.
        """
        # Simple estimation: ~4 characters per token on average
        return len(text) // 4
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the unified context manager.
        """
        return {
            **self._metrics,
            'cache_size': len(self._context_cache),
            'systems_available': {
                'legacy': self.legacy_available,
                'new': self.new_available,
                'coordinator': self.coordinator_available
            },
            'cache_hit_rate': (
                self._metrics['cache_hits'] / 
                (self._metrics['cache_hits'] + self._metrics['cache_misses'])
                if (self._metrics['cache_hits'] + self._metrics['cache_misses']) > 0 
                else 0
            )
        }
    
    def clear_cache(self):
        """Clear the context cache."""
        self._context_cache.clear()
        logger.info("Context cache cleared")
    
    def health_check(self) -> Dict[str, bool]:
        """
        Check the health of all context management systems.
        """
        health = {}
        
        # Test legacy system
        if self.legacy_available:
            try:
                self._get_context_from_legacy("test", max_results=1)
                health['legacy'] = True
            except Exception:
                health['legacy'] = False
        else:
            health['legacy'] = False
            
        # Test new system
        if self.new_available:
            try:
                self._get_context_from_new("test", max_results=1)
                health['new'] = True
            except Exception:
                health['new'] = False
        else:
            health['new'] = False
            
        # Test coordinator integration
        if self.coordinator_available:
            try:
                # Simple health check for coordinator
                health['coordinator'] = hasattr(self.coordinator_integration, 'get_context')
            except Exception:
                health['coordinator'] = False
        else:
            health['coordinator'] = False
            
        return health


# Global instance for easy access
_unified_context_manager = None


def get_unified_context_manager() -> UnifiedContextManager:
    """
    Get the global unified context manager instance.
    """
    global _unified_context_manager
    if _unified_context_manager is None:
        _unified_context_manager = UnifiedContextManager()
    return _unified_context_manager


def reset_unified_context_manager():
    """
    Reset the global unified context manager instance.
    """
    global _unified_context_manager
    _unified_context_manager = None
