"""Stub VSCode bridge for backwards compatibility."""

class VSCodeBridge:
    """Minimal stub VSCode bridge for backwards compatibility."""
    
    def __init__(self):
        self.connection_active = False
        self.config = type('Config', (), {
            'prefer_ui': False,
            'fallback_to_terminal': True,
            'response_timeout': 30
        })()
    
    def send_terminal_output(self, message):
        """Stub method - does nothing to avoid duplicate output."""
        pass
    
    def send_interactive_approval(self, *args, **kwargs):
        """Stub method - returns None to trigger terminal fallback."""
        return None
    
    def send_interactive_diff(self, *args, **kwargs):
        """Stub method - returns None to trigger terminal fallback."""
        return None
    
    def send_log_output(self, message, level="info"):
        """Stub method - does nothing to avoid duplicate output."""
        pass
    
    def send_progress_indicator(self, *args, **kwargs):
        """Stub method - does nothing."""
        pass
    
    def send_progress_update(self, message, percent):
        """Stub method - does nothing to avoid duplicate output."""
        pass