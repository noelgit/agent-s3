"""
This module has been deprecated. The ScratchpadManager class has been replaced by
EnhancedScratchpadManager from agent_s3.enhanced_scratchpad_manager module.

Please update imports to use EnhancedScratchpadManager directly:
from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager, LogLevel, Section

This file exists as a compatibility shim for older code that may still depend on it.
"""

import sys

def __getattr__(name):
    if name == "ScratchpadManager":
        import warnings
        from agent_s3.enhanced_scratchpad_manager import EnhancedScratchpadManager
        
        warnings.warn(
            "ScratchpadManager has been replaced by EnhancedScratchpadManager. "
            "Please update your imports to use EnhancedScratchpadManager directly.",
            DeprecationWarning,
            stacklevel=2
        )
        
        return EnhancedScratchpadManager
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")