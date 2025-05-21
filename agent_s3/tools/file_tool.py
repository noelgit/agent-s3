"""Provides functions for reading/writing files securely."""

import os
import re
import mimetypes
from pathlib import Path
from typing import Optional, List, Tuple, Set, Dict, Any


class FileTool:
    """Tool for secure file operations with protection against path traversal attacks."""
    
    def __init__(self, allowed_dirs: Optional[List[str]] = None, 
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB default limit
                 allowed_extensions: Optional[List[str]] = None):
        """Initialize the file tool with security settings.
        
        Args:
            allowed_dirs: List of directories that can be accessed. If None, allows the current directory.
            max_file_size: Maximum file size in bytes (default: 10MB).
            allowed_extensions: List of allowed file extensions (e.g., ['.txt', '.py']). If None, all extensions allowed.
        """
        self.allowed_dirs = allowed_dirs or [os.getcwd()]
        # Normalize paths to absolute real paths to avoid symlink escapes
        self.allowed_dirs = [os.path.realpath(dir_path) for dir_path in self.allowed_dirs]
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions
        
        # Set up logging
        try:
            import logging
            self.logger = logging.getLogger("file_tool")
        except ImportError:
            self.logger = None
    
    def _is_path_allowed(self, file_path: str) -> Tuple[bool, str]:
        """Check if a path is safe and allowed.
        
        This method checks:
        1. Path traversal attacks (e.g., using '../' to access parent directories)
        2. If the path is within allowed directories
        3. If the file extension is allowed
        
        Args:
            file_path: Path to check
        
        Returns:
            A tuple of (is_allowed, error_message)
        """
        try:
            # Check for path traversal attacks
            # Use realpath to resolve any symlinks before comparison
            norm_path = os.path.normpath(os.path.realpath(file_path))
            
            # Check if path is within allowed directories
            allowed = False
            for dir_path in self.allowed_dirs:
                if norm_path.startswith(dir_path):
                    allowed = True
                    break
            
            if not allowed:
                if self.logger:
                    self.logger.warning(f"Attempted access to restricted path: {norm_path}")
                return False, f"Access to path outside allowed directories: {file_path}"
            
            # Check file extension if restricted
            if self.allowed_extensions is not None:
                file_ext = os.path.splitext(file_path)[1].lower()
                if file_ext not in self.allowed_extensions:
                    if self.logger:
                        self.logger.warning(f"Attempted access to file with disallowed extension: {file_ext}")
                    return False, f"File extension not allowed: {file_ext}"
            
            return True, ""
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error in path validation: {e}")
            return False, f"Error validating path: {e}"
    
    def _check_file_size(self, file_path: str) -> Tuple[bool, str]:
        """Check if a file size is within limits.
        
        Args:
            file_path: Path to the file to check
        
        Returns:
            A tuple of (is_within_limit, error_message)
        """
        try:
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                msg = f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
                if self.logger:
                    self.logger.warning(f"File size limit exceeded: {file_path}, {file_size} bytes")
                return False, msg
            return True, ""
        except Exception as e:
            return False, f"Error checking file size: {e}"
    
    def _detect_mime_type(self, file_path: str) -> str:
        """Detect the MIME type of a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            The MIME type as a string, or 'application/octet-stream' if unknown
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'
    
    def read_file(self, file_path: str, max_size: Optional[int] = None) -> Tuple[bool, str]:
        """Read the content of a file securely.
        
        Args:
            file_path: Path to the file to read
            max_size: Optional override for maximum file size
            
        Returns:
            A tuple containing (success, content or error message)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(file_path)
        if not is_allowed:
            return False, error
        
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
            
        # Check file size
        size_ok, error = self._check_file_size(file_path)
        if not size_ok:
            return False, error
        
        # Read the file
        try:
            with open(file_path, "r") as f:
                content = f.read()
            return True, content
        except UnicodeDecodeError:
            # Try binary mode for non-text files
            try:
                with open(file_path, "rb") as f:
                    binary_content = f.read()
                return False, f"Cannot display binary file ({self._detect_mime_type(file_path)}). File size: {len(binary_content)} bytes"
            except Exception as e:
                return False, f"Error reading file: {e}"
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error reading file {file_path}: {e}")
            return False, f"Error reading file: {e}"
    
    def write_file(self, file_path: str, content: str, overwrite: bool = True) -> Tuple[bool, str]:
        """Write content to a file securely.
        
        Args:
            file_path: Path to the file to write
            content: Content to write to the file
            overwrite: Whether to overwrite existing files
            
        Returns:
            A tuple containing (success, message)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(file_path)
        if not is_allowed:
            return False, error
            
        # Check if file exists and handle overwrite setting
        if os.path.exists(file_path) and not overwrite:
            if self.logger:
                self.logger.warning(f"Attempted to overwrite file without permission: {file_path}")
            return False, f"File already exists and overwrite is not allowed: {file_path}"
        
        # Check content size
        content_size = len(content.encode('utf-8'))
        if content_size > self.max_file_size:
            if self.logger:
                self.logger.warning(f"Content size exceeds maximum limit: {content_size} > {self.max_file_size}")
            return False, f"Content size ({content_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
        
        try:
            # Ensure the directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                # Validate the directory is within allowed paths
                dir_allowed, dir_error = self._is_path_allowed(directory)
                if not dir_allowed:
                    return False, dir_error
                os.makedirs(directory, exist_ok=True)
            
            # Write the file
            with open(file_path, "w") as f:
                f.write(content)
            
            if self.logger:
                self.logger.info(f"Successfully wrote to {file_path}")
            return True, f"Successfully wrote to {file_path}"
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error writing to file {file_path}: {e}")
            return False, f"Error writing file: {e}"
    
    def append_to_file(self, file_path: str, content: str) -> Tuple[bool, str]:
        """Append content to a file securely.
        
        Args:
            file_path: Path to the file to append to
            content: Content to append to the file
            
        Returns:
            A tuple containing (success, message)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(file_path)
        if not is_allowed:
            return False, error
        
        # Check content size
        if os.path.exists(file_path):
            try:
                current_size = os.path.getsize(file_path)
            except OSError:
                current_size = 0
                
            content_size = len(content.encode('utf-8'))
            if current_size + content_size > self.max_file_size:
                return False, f"Resulting file size would exceed maximum allowed size"
        
        try:
            # Ensure the directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                dir_allowed, dir_error = self._is_path_allowed(directory)
                if not dir_allowed:
                    return False, dir_error
                os.makedirs(directory, exist_ok=True)
            
            # Append to the file
            with open(file_path, "a") as f:
                f.write(content)
            
            return True, f"Successfully appended to {file_path}"
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error appending to file {file_path}: {e}")
            return False, f"Error appending to file: {e}"
    
    def list_files(self, directory: str, pattern: Optional[str] = None) -> Tuple[bool, List[str]]:
        """List files in a directory securely, optionally filtering by pattern.
        
        Args:
            directory: Directory to list files from
            pattern: Optional glob pattern to filter files
            
        Returns:
            Tuple of (success, list of file paths)
        """
        # Validate directory path
        is_allowed, error = self._is_path_allowed(directory)
        if not is_allowed:
            return False, [f"Error: {error}"]
        
        try:
            if not os.path.exists(directory):
                return False, [f"Directory not found: {directory}"]
                
            if not os.path.isdir(directory):
                return False, [f"Not a directory: {directory}"]
                
            if pattern:
                files = list(str(p) for p in Path(directory).glob(pattern) if os.path.isfile(p))
            else:
                files = [os.path.join(directory, f) for f in os.listdir(directory) 
                         if os.path.isfile(os.path.join(directory, f))]
            
            # Filter files by allowed extensions
            if self.allowed_extensions is not None:
                files = [f for f in files if os.path.splitext(f)[1].lower() in self.allowed_extensions]
                
            return True, files
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error listing files in {directory}: {e}")
            return False, [f"Error listing files: {e}"]
    
    def file_exists(self, file_path: str) -> Tuple[bool, bool]:
        """Check if a file exists securely.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            Tuple of (success, exists)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(file_path)
        if not is_allowed:
            return False, False
        
        return True, os.path.isfile(file_path)
    
    def directory_exists(self, directory: str) -> Tuple[bool, bool]:
        """Check if a directory exists securely.
        
        Args:
            directory: Path to the directory to check
            
        Returns:
            Tuple of (success, exists)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(directory)
        if not is_allowed:
            return False, False
        
        return True, os.path.isdir(directory)
    
    def delete_file(self, file_path: str) -> Tuple[bool, str]:
        """Delete a file securely.
        
        Args:
            file_path: Path to the file to delete
            
        Returns:
            Tuple of (success, message)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(file_path)
        if not is_allowed:
            return False, error
        
        try:
            if not os.path.exists(file_path):
                return False, f"File not found: {file_path}"
                
            if not os.path.isfile(file_path):
                return False, f"Not a file: {file_path}"
                
            os.remove(file_path)
            if self.logger:
                self.logger.info(f"Successfully deleted {file_path}")
            return True, f"Successfully deleted {file_path}"
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error deleting file {file_path}: {e}")
            return False, f"Error deleting file: {e}"
    
    def create_directory(self, directory: str) -> Tuple[bool, str]:
        """Create a directory securely.
        
        Args:
            directory: Path to the directory to create
            
        Returns:
            Tuple of (success, message)
        """
        # Validate path
        is_allowed, error = self._is_path_allowed(directory)
        if not is_allowed:
            return False, error
        
        try:
            os.makedirs(directory, exist_ok=True)
            return True, f"Successfully created directory {directory}"
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error creating directory {directory}: {e}")
            return False, f"Error creating directory: {e}"
