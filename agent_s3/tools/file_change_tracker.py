"""
File Change Tracker for Agent-S3.

This module provides efficient tracking of file changes to enable incremental indexing
and updates. It uses a combination of file modification times and content hashing to
detect changes since the last indexing operation.
"""

import os
import time
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class FileChangeTracker:
    """
    Tracks file changes using modification times and content hashing.

    This class maintains a persistent store of file metadata to detect changes
    between indexing operations, enabling efficient incremental updates.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the file change tracker.

        Args:
            storage_path: Path to store the file tracking data. If None, defaults to a
                          location within the user's home directory.
        """
        self.storage_path = storage_path
        if not self.storage_path:
            # Default to a hidden directory in the user's home
            home = os.path.expanduser("~")
            self.storage_path = os.path.join(home, ".agent_s3", "tracking")

        # Ensure storage directory exists
        os.makedirs(self.storage_path, exist_ok=True)

        # File state tracking
        self._file_state: Dict[str, Dict[str, Any]] = {}
        self._file_hashes: Dict[str, str] = {}

        # Load existing state if available
        self._load_state()

    def _load_state(self) -> None:
        """Load file state information from disk."""
        state_path = os.path.join(self.storage_path, "file_state.json")
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    data = json.load(f)
                    self._file_state = data.get('file_state', {})
                    self._file_hashes = data.get('file_hashes', {})
                logger.info("%s", Loaded tracking information for {len(self._file_state)} files)
            except Exception as e:
                logger.error("%s", Error loading file state information: {e})
                # Reset state if corrupted
                self._file_state = {}
                self._file_hashes = {}

    def _save_state(self) -> None:
        """Save file state information to disk."""
        state_path = os.path.join(self.storage_path, "file_state.json")
        try:
            # Create a combined state object
            data = {
                'file_state': self._file_state,
                'file_hashes': self._file_hashes,
                'timestamp': time.time()
            }

            # Write to a temporary file first, then rename for atomic update
            temp_path = state_path + ".tmp"
            with open(temp_path, 'w') as f:
                json.dump(data, f)

            # Atomic replacement
            os.replace(temp_path, state_path)
            logger.debug("%s", Saved tracking information for {len(self._file_state)} files)
        except Exception as e:
            logger.error("%s", Error saving file state information: {e})

    def compute_file_hash(self, file_path: str, content: Optional[str] = None) -> str:
        """
        Compute a hash for a file's content.

        Args:
            file_path: Path to the file
            content: Optional pre-loaded content (to avoid re-reading)

        Returns:
            Hash string for the file
        """
        try:
            if content is None:
                with open(file_path, 'rb') as f:
                    content = f.read()
            elif isinstance(content, str):
                content = content.encode('utf-8')

            # Use a fast hash function (murmurhash would be ideal, but hashlib is standard)
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            logger.error("%s", Error computing hash for {file_path}: {e})
            # Return a timestamp-based hash as fallback
            return f"err-{int(time.time())}"

    def track_file(self, file_path: str, content: Optional[str] = None) -> bool:
        """
        Add or update a file in the tracking system.

        Args:
            file_path: Path to the file to track
            content: Optional pre-loaded content (to avoid re-reading)

        Returns:
            True if the file was successfully tracked, False otherwise
        """
        try:
            # Standardize path
            file_path = os.path.abspath(file_path)

            # Check if file exists
            if not os.path.isfile(file_path):
                return False

            # Get file metadata
            stat = os.stat(file_path)
            mtime = stat.st_mtime
            size = stat.st_size

            # Compute hash
            file_hash = self.compute_file_hash(file_path, content)

            # Update tracking information
            self._file_state[file_path] = {
                'mtime': mtime,
                'size': size,
                'last_indexed': time.time(),
                'hash': file_hash
            }

            # Store hash separately for quick access
            self._file_hashes[file_path] = file_hash

            return True
        except Exception as e:
            logger.error("%s", Error tracking file {file_path}: {e})
            return False

    def is_file_changed(self, file_path: str, content: Optional[str] = None) -> bool:
        """
        Check if a file has changed since it was last indexed.

        Args:
            file_path: Path to the file to check
            content: Optional pre-loaded content (to avoid re-reading)

        Returns:
            True if the file has changed or wasn't previously tracked, False otherwise
        """
        try:
            # Standardize path
            file_path = os.path.abspath(file_path)

            # Check if file exists
            if not os.path.isfile(file_path):
                # File doesn't exist, but we were tracking it before
                if file_path in self._file_state:
                    return True
                return False

            # Not tracked yet
            if file_path not in self._file_state:
                return True

            # Quick check - modification time
            prev_state = self._file_state[file_path]
            curr_mtime = os.stat(file_path).st_mtime

            # If modification time has changed, do a full check
            if curr_mtime > prev_state['mtime']:
                # Hash comparison for absolute confirmation
                curr_hash = self.compute_file_hash(file_path, content)
                return curr_hash != prev_state['hash']

            # File hasn't changed
            return False
        except Exception as e:
            logger.error("%s", Error checking if file changed {file_path}: {e})
            # Assume changed if error occurs
            return True

    def get_changed_files(self, directory: str, extensions: List[str] = None) -> List[str]:
        """
        Find all files that have changed in a directory since they were last tracked.

        Args:
            directory: Directory to scan for changed files
            extensions: Optional list of file extensions to check (e.g. ['.py', '.js'])

        Returns:
            List of paths to files that have changed
        """
        changed_files = []

        try:
            # Walk through directory
            for root, _, files in os.walk(directory):
                for filename in files:
                    # Filter by extension if specified
                    if extensions and not any(filename.endswith(ext) for ext in extensions):
                        continue

                    file_path = os.path.join(root, filename)

                    # Check if file has changed
                    if self.is_file_changed(file_path):
                        changed_files.append(file_path)
        except Exception as e:
            logger.error("%s", Error getting changed files in {directory}: {e})

        return changed_files

    def track_directory(self, directory: str, extensions: List[str] = None) -> int:
        """
        Track all files in a directory.

        Args:
            directory: Directory to scan and track files in
            extensions: Optional list of file extensions to track (e.g. ['.py', '.js'])

        Returns:
            Number of files successfully tracked
        """
        count = 0

        try:
            # Walk through directory
            for root, _, files in os.walk(directory):
                for filename in files:
                    # Filter by extension if specified
                    if extensions and not any(filename.endswith(ext) for ext in extensions):
                        continue

                    file_path = os.path.join(root, filename)

                    # Track the file
                    if self.track_file(file_path):
                        count += 1

            # Save state after tracking a directory
            self._save_state()
        except Exception as e:
            logger.error("%s", Error tracking directory {directory}: {e})

        return count

    def clear_tracking_data(self) -> None:
        """Clear all tracking data."""
        self._file_state = {}
        self._file_hashes = {}
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tracked files.

        Returns:
            Dictionary with tracking statistics
        """
        if not self._file_state:
            return {
                'tracked_files': 0,
                'total_size': 0,
                'oldest_tracked': None,
                'newest_tracked': None
            }

        # Calculate stats
        total_size = sum(info.get('size', 0) for info in self._file_state.values())
        timestamps = [info.get('last_indexed', 0) for info in self._file_state.values()]

        return {
            'tracked_files': len(self._file_state),
            'total_size': total_size,
            'oldest_tracked': min(timestamps) if timestamps else None,
            'newest_tracked': max(timestamps) if timestamps else None
        }
