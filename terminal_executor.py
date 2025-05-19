import os
import re
from typing import List, Tuple, Optional, Dict

class TerminalExecutor:
    def __init__(self, allowed_dirs: List[str], denylist: List[str], logger: Optional[object] = None):
        self.allowed_dirs = allowed_dirs
        self.denylist = denylist
        self.logger = logger

    def _is_path_allowed(self, path: str) -> bool:
        """Check if a path is within allowed directories, following symlinks securely."""
        abs_path = os.path.realpath(path)
        for allowed_dir in self.allowed_dirs:
            allowed_real = os.path.realpath(allowed_dir)
            try:
                rel = os.path.relpath(abs_path, allowed_real)
                # If relpath starts with '..', abs_path is outside allowed_real
                if rel.startswith('..') or rel.startswith(os.pardir):
                    continue
                # Prevent escape via symlinks
                if os.path.islink(path):
                    link_target = os.path.realpath(os.readlink(path))
                    rel_link = os.path.relpath(link_target, allowed_real)
                    if rel_link.startswith('..') or rel_link.startswith(os.pardir):
                        return False
                return True
            except Exception:
                continue
        return False

    def _validate_command(self, command: str) -> Tuple[bool, str]:
        """
        Validate a command against security rules.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check against denylist
        for forbidden in self.denylist:
            if forbidden in command:
                if self.logger:
                    self.logger.warning(f"Command contains forbidden token: {forbidden}")
                return False, f"Error: Command contains forbidden token '{forbidden}'"

        # Capture absolute and relative paths (./ or ../)
        path_pattern = re.compile(r'(?:^|\s|"|\'|\()((?:\.{1,2}/|/)[^\s"\'\)\|;&<>]+)')
        paths = path_pattern.findall(command)

        for path in paths:
            path = os.path.realpath(path.strip())
            if not self._is_path_allowed(path):
                if self.logger:
                    self.logger.warning(f"Command attempts to access restricted path: {path}")
                return False, f"Error: Command attempts to access restricted path '{path}'"

        return True, ""
