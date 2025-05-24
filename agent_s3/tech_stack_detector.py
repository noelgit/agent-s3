"""Tech Stack Detector component for Agent-S3.

Responsible for detecting the technologies, frameworks, and libraries in the workspace.
"""

import logging
from pathlib import Path
from typing import Any, Dict

class TechStackDetector:
    """Detects and analyzes the tech stack used in a project workspace."""

    def __init__(self, config=None, file_tool=None, scratchpad=None, workspace_path=None):
        """Initialize the TechStackDetector.

        Args:
            config: Configuration object
            file_tool: Optional FileTool instance for file operations
            scratchpad: Optional EnhancedScratchpadManager for logging
            workspace_path: Optional workspace path override (defaults to cwd)
        """
        self.config = config
        self.file_tool = file_tool
        self.scratchpad = scratchpad
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.tech_stack_manager = None
        self._detected_stack = None

    def detect_tech_stack(self) -> Dict[str, Any]:
        """Detect the primary technologies used in the workspace.

        Returns:
            Dictionary with structured tech stack information
        """
        logging.info("Detecting tech stack with enhanced version information...")
        self._log("Detecting tech stack...")

        try:
            # Import here to avoid circular imports
            from agent_s3.tools.tech_stack_manager import TechStackManager

            # Create or reuse tech stack manager
            if not self.tech_stack_manager:
                self.tech_stack_manager = TechStackManager(
                    config=self.config,
                    file_tool=self.file_tool,
                    workspace_path=str(self.workspace_path)
                )

            # Detect tech stack
            self._detected_stack = self.tech_stack_manager.detect_tech_stack()

            # Get structured tech stack data with versioning and best practices
            structured_data = self.get_structured_tech_stack()

            # Log detected tech stack summary
            formatted_stack = self.get_formatted_tech_stack()
            self._log(f"Detected tech stack:\n{formatted_stack}")
            logging.info(f"Tech stack detection complete with {len(structured_data['languages'])} languages, "
                        f"{len(structured_data['frameworks'])} frameworks, "
                        f"{len(structured_data['libraries'])} libraries")

            return structured_data
        except ImportError as e:
            error_msg = f"TechStackManager not available: {e}"
            self._log(error_msg, level="error")
            logging.error(error_msg)
            return self._get_empty_tech_stack()
        except Exception as e:
            error_msg = f"Error detecting tech stack: {e}"
            self._log(error_msg, level="error")
            logging.error(error_msg)
            return self._get_empty_tech_stack()

    def get_structured_tech_stack(self) -> Dict[str, Any]:
        """Get structured tech stack data with versioning and best practices.

        Returns:
            Dictionary with structured tech stack information
        """
        if self.tech_stack_manager and hasattr(self.tech_stack_manager, 'get_structured_tech_stack'):
            return self.tech_stack_manager.get_structured_tech_stack()

        # Fallback if tech stack manager doesn't have the method
        return self._get_empty_tech_stack() if not self._detected_stack else self._detected_stack

    def get_formatted_tech_stack(self) -> str:
        """Get a formatted string representation of the tech stack.

        Returns:
            Formatted tech stack string for display
        """
        if self.tech_stack_manager and hasattr(self.tech_stack_manager, 'get_formatted_tech_stack'):
            return self.tech_stack_manager.get_formatted_tech_stack()

        # Fallback - create a simple formatted string
        stack = self.get_structured_tech_stack()
        formatted = ["# Tech Stack Summary"]

        # Languages
        if stack.get('languages'):
            formatted.append("\n## Languages")
            for lang in stack.get('languages', []):
                name = lang.get('name', 'Unknown') if isinstance(lang, dict) else lang
                version = lang.get('version', 'Unknown') if isinstance(lang, dict) else 'Unknown'
                formatted.append(f"- {name} {version}")

        # Frameworks
        if stack.get('frameworks'):
            formatted.append("\n## Frameworks")
            for framework in stack.get('frameworks', []):
                name = framework.get('name', 'Unknown') if isinstance(framework, dict) else framework
                version = framework.get('version', 'Unknown') if isinstance(framework, dict) else 'Unknown'
                formatted.append(f"- {name} {version}")

        # Libraries
        if stack.get('libraries'):
            formatted.append("\n## Libraries")
            for lib in stack.get('libraries', []):
                name = lib.get('name', 'Unknown') if isinstance(lib, dict) else lib
                version = lib.get('version', 'Unknown') if isinstance(lib, dict) else 'Unknown'
                formatted.append(f"- {name} {version}")

        return "\n".join(formatted)

    def _get_empty_tech_stack(self) -> Dict[str, Any]:
        """Return an empty tech stack dictionary.

        Returns:
            Empty tech stack dictionary with default structure
        """
        return {
            "languages": [],
            "frameworks": [],
            "libraries": [],
            "tools": [],
            "versions": {},
            "meta": {}
        }

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad or default logger.

        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad and hasattr(self.scratchpad, 'log'):
            self.scratchpad.log("TechStackDetector", message, level=level)
        else:
            if level.lower() == "error":
                logging.error(message)
            elif level.lower() == "warning":
                logging.warning(message)
            else:
                logging.info(message)
