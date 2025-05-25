"""File History Analyzer component for Agent-S3.

Analyzes file modification history for context prioritization.
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List


class FileHistoryAnalyzer:
    """Analyzes file modification history for context prioritization."""

    def __init__(self, git_tool=None, config=None, scratchpad=None):
        """Initialize the FileHistoryAnalyzer.

        Args:
            git_tool: GitTool instance for accessing git history
            config: Optional configuration object
            scratchpad: Optional EnhancedScratchpadManager for logging
        """
        self.git_tool = git_tool
        self.config = config
        self.scratchpad = scratchpad

    def get_file_modification_info(self) -> Dict[str, Dict[str, Any]]:
        """Get file modification information for context prioritization.

        Returns:
            Dictionary mapping file paths to modification metadata
        """
        file_info = {}
        self._log("Gathering file modification history...")

        try:
            # Check if git_tool is available
            if not self.git_tool:
                self._log(
                    "GitTool not available, unable to analyze file history",
                    level="warning",
                )
                return {}

            # Get repository modification history
            repo_path = str(Path.cwd())
            commit_history = self.git_tool.get_commit_history(repo_path, max_commits=30)

            # Track file modification counts and last modified dates
            file_counts = {}
            file_last_modified = {}

            if not commit_history:
                self._log("No commit history found", level="warning")
                return {}

            # Use timezone-aware datetime to match ISO format parsing
            # Python 3.10+ compatible timezone usage
            try:
                from zoneinfo import ZoneInfo

                current_time = datetime.now(ZoneInfo("UTC"))
            except ImportError:
                # Fallback for older Python versions
                from datetime import timezone

                current_time = datetime.now(timezone.utc)

            # Process commits to extract file modification patterns
            for commit in commit_history:
                commit_date = datetime.fromisoformat(
                    commit.get("date", "").replace("Z", "+00:00")
                )
                days_since = (current_time - commit_date).days

                # Process files changed in this commit
                files_changed = commit.get("files_changed", [])
                for file_path in files_changed:
                    # Update modification count
                    file_counts[file_path] = file_counts.get(file_path, 0) + 1

                    # Update last modified date if this is more recent
                    if (
                        file_path not in file_last_modified
                        or days_since < file_last_modified[file_path]
                    ):
                        file_last_modified[file_path] = days_since

            # Assemble file information dictionary
            for file_path, count in file_counts.items():
                file_info[file_path] = {
                    "modification_frequency": count,
                    "days_since_modified": file_last_modified.get(file_path, 365),
                    "last_modified": current_time
                    - timedelta(days=file_last_modified.get(file_path, 0)),
                }

            self._log(f"Gathered modification info for {len(file_info)} files")
            logging.info(f"Gathered modification info for {len(file_info)} files")
            return file_info
        except Exception as e:
            error_msg = f"Error getting file modification info: {e}"
            self._log(error_msg, level="error")
            logging.error(error_msg)
            return {}

    def get_recently_modified_files(
        self, days: int = 7, max_files: int = 10
    ) -> List[str]:
        """Get a list of recently modified files.

        Args:
            days: Number of days to look back
            max_files: Maximum number of files to return

        Returns:
            List of recently modified file paths
        """
        file_info = self.get_file_modification_info()

        # Filter files modified within the specified days
        recent_files = [
            path
            for path, info in file_info.items()
            if info.get("days_since_modified", 365) <= days
        ]

        # Sort by recency (most recent first)
        recent_files.sort(
            key=lambda path: file_info.get(path, {}).get("days_since_modified", 365)
        )

        # Return limited number of files
        return recent_files[:max_files]

    def get_frequently_modified_files(self, max_files: int = 10) -> List[str]:
        """Get a list of frequently modified files.

        Args:
            max_files: Maximum number of files to return

        Returns:
            List of frequently modified file paths
        """
        file_info = self.get_file_modification_info()

        # Sort by modification frequency (highest first)
        frequent_files = sorted(
            file_info.keys(),
            key=lambda path: file_info.get(path, {}).get("modification_frequency", 0),
            reverse=True,
        )

        # Return limited number of files
        return frequent_files[:max_files]

    def _log(self, message: str, level: str = "info") -> None:
        """Log a message using the scratchpad or default logger.

        Args:
            message: The message to log
            level: The log level (info, warning, error)
        """
        if self.scratchpad and hasattr(self.scratchpad, "log"):
            self.scratchpad.log("FileHistoryAnalyzer", message, level=level)
        else:
            if level.lower() == "error":
                logging.error(message)
            elif level.lower() == "warning":
                logging.warning(message)
            else:
                logging.info(message)
