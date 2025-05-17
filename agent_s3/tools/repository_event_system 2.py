"""
Repository Event System for Agent-S3.

This module provides functionality to monitor repository changes in real-time
and trigger incremental updates for the code analysis and indexing systems.
"""

import os
import time
import logging
import threading
from typing import Dict, List, Set, Optional, Tuple, Any, Union, Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import watchdog for file system monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    logger.warning("Watchdog not available. Real-time file monitoring won't work.")
    WATCHDOG_AVAILABLE = False
    # Define stub classes for type checking
    class Observer:
        def __init__(self, *args, **kwargs): pass
        def schedule(self, *args, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def join(self): pass
    
    class FileSystemEventHandler:
        def dispatch(self, event): pass
    
    class FileSystemEvent:
        def __init__(self, src_path=""): 
            self.src_path = src_path
            self.is_directory = False
            self.event_type = "unknown"

# Event types
CREATE_EVENT = "create"
MODIFY_EVENT = "modify"
DELETE_EVENT = "delete"
MOVE_EVENT = "move"

class RepositoryEventHandler(FileSystemEventHandler):
    """
    Custom handler for repository file events.
    
    Implements debouncing and filtering for more efficient event processing.
    """
    
    def __init__(
        self, 
        callback: Callable[[str, str], None],
        file_patterns: List[str] = None,
        debounce_seconds: float = 1.0,
        ignore_dirs: List[str] = None
    ):
        """
        Initialize the repository event handler.
        
        Args:
            callback: Function to call with (event_type, file_path) when a relevant change occurs
            file_patterns: List of file patterns to monitor (e.g., "*.py", "*.js")
            debounce_seconds: Time in seconds to wait before firing events (to avoid duplicates)
            ignore_dirs: List of directory patterns to ignore (e.g., "node_modules", "__pycache__")
        """
        self.callback = callback
        self.file_patterns = file_patterns or ["*.*"]
        self.debounce_seconds = debounce_seconds
        self.ignore_dirs = ignore_dirs or ["node_modules", "__pycache__", ".git", "venv", "env", "build", "dist"]
        
        # Event tracking for debouncing
        self._pending_events: Dict[str, Dict[str, Any]] = {}
        self._last_event_time = 0
        self._process_timer = None
        self._event_lock = threading.Lock()
    
    def dispatch(self, event: FileSystemEvent) -> None:
        """
        Process a file system event.
        
        Args:
            event: The file system event to process
        """
        if not hasattr(event, 'src_path'):
            return
            
        # Skip directories
        if getattr(event, 'is_directory', False):
            return
        
        # Check if in ignored directories
        file_path = event.src_path
        for ignore_dir in self.ignore_dirs:
            if ignore_dir in file_path.split(os.path.sep):
                return
        
        # Check file pattern matching
        file_matches = False
        for pattern in self.file_patterns:
            if pattern == "*.*" or file_path.endswith(pattern.replace("*", "")):
                file_matches = True
                break
        
        if not file_matches:
            return
        
        # Determine event type
        event_type = None
        if hasattr(event, 'event_type'):
            event_type = event.event_type
        else:
            # Try to infer type from class name
            class_name = event.__class__.__name__.lower()
            if 'create' in class_name:
                event_type = CREATE_EVENT
            elif 'modify' in class_name:
                event_type = MODIFY_EVENT
            elif 'delete' in class_name:
                event_type = DELETE_EVENT
            elif 'move' in class_name:
                event_type = MOVE_EVENT
        
        if not event_type:
            event_type = MODIFY_EVENT  # Default to modify
        
        # Add to pending events with lock
        with self._event_lock:
            self._pending_events[file_path] = {
                'event_type': event_type,
                'timestamp': time.time(),
                'path': file_path
            }
            
            # Schedule processing if not already scheduled
            if not self._process_timer:
                self._process_timer = threading.Timer(
                    self.debounce_seconds, 
                    self._process_pending_events
                )
                self._process_timer.daemon = True
                self._process_timer.start()
    
    def _process_pending_events(self) -> None:
        """Process pending events after debounce period."""
        with self._event_lock:
            # Reset timer
            self._process_timer = None
            
            # Process events
            current_time = time.time()
            events_to_process = {}
            
            # Only process events that have settled (haven't been updated recently)
            for file_path, event_data in self._pending_events.items():
                if current_time - event_data['timestamp'] >= self.debounce_seconds:
                    events_to_process[file_path] = event_data
            
            # Remove processed events
            for file_path in events_to_process:
                del self._pending_events[file_path]
            
            # Schedule another processing round if we have remaining events
            if self._pending_events and not self._process_timer:
                self._process_timer = threading.Timer(
                    self.debounce_seconds,
                    self._process_pending_events
                )
                self._process_timer.daemon = True
                self._process_timer.start()
        
        # Call callback for each processed event (outside the lock)
        for file_path, event_data in events_to_process.items():
            try:
                self.callback(event_data['event_type'], file_path)
            except Exception as e:
                logger.error(f"Error in repository event callback: {e}")


class RepositoryEventSystem:
    """
    System for monitoring repository changes and triggering updates.
    
    Uses file system watchers to detect changes and dispatches events
    to registered handlers.
    """
    
    def __init__(self):
        """Initialize the repository event system."""
        self.observers: List[Observer] = []
        self.handlers: Dict[str, RepositoryEventHandler] = {}
        self.watched_paths: Dict[str, List[str]] = {}
    
    def watch_repository(
        self, 
        repo_path: str, 
        callback: Callable[[str, str], None],
        file_patterns: List[str] = None,
        recursive: bool = True,
        ignore_dirs: List[str] = None,
        watch_id: str = None
    ) -> str:
        """
        Start watching a repository for changes.
        
        Args:
            repo_path: Path to the repository to watch
            callback: Function to call when file changes are detected
            file_patterns: List of file patterns to watch (e.g. ["*.py", "*.js"])
            recursive: Whether to watch subdirectories
            ignore_dirs: List of directories to ignore
            watch_id: Optional ID for the watch (generated if not provided)
            
        Returns:
            ID of the watch (can be used to stop watching)
        """
        if not WATCHDOG_AVAILABLE:
            logger.error("Watchdog not available. Cannot watch repository.")
            return ""
            
        # Normalize path
        repo_path = os.path.abspath(repo_path)
        
        # Generate ID if not provided
        if not watch_id:
            watch_id = f"watch_{len(self.handlers)}_{int(time.time())}"
        
        try:
            # Create handler
            handler = RepositoryEventHandler(
                callback=callback,
                file_patterns=file_patterns or ["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"],
                debounce_seconds=1.0,
                ignore_dirs=ignore_dirs
            )
            
            # Create observer
            observer = Observer()
            observer.schedule(
                handler, 
                repo_path,
                recursive=recursive
            )
            
            # Start watching
            observer.start()
            
            # Store references
            self.observers.append(observer)
            self.handlers[watch_id] = handler
            self.watched_paths[watch_id] = repo_path
            
            logger.info(f"Started watching repository: {repo_path} (ID: {watch_id})")
            return watch_id
        except Exception as e:
            logger.error(f"Error setting up repository watcher: {e}")
            return ""
    
    def stop_watching(self, watch_id: str) -> bool:
        """
        Stop watching a repository.
        
        Args:
            watch_id: ID of the watch to stop
            
        Returns:
            True if successfully stopped, False otherwise
        """
        if not watch_id or watch_id not in self.handlers:
            return False
        
        try:
            # Find the observer for this handler
            handler = self.handlers[watch_id]
            
            for i, observer in enumerate(self.observers):
                # We can't directly match observers to handlers, so we stop them all
                # and recreate the ones we want to keep
                observer.stop()
                observer.join()
            
            # Remove the stopped watch
            del self.handlers[watch_id]
            if watch_id in self.watched_paths:
                del self.watched_paths[watch_id]
            
            # Recreate observers for remaining handlers
            new_observers = []
            for w_id, handler in self.handlers.items():
                if w_id in self.watched_paths:
                    observer = Observer()
                    observer.schedule(
                        handler,
                        self.watched_paths[w_id],
                        recursive=True
                    )
                    observer.start()
                    new_observers.append(observer)
            
            self.observers = new_observers
            return True
        except Exception as e:
            logger.error(f"Error stopping repository watcher: {e}")
            return False
    
    def stop_all(self) -> None:
        """Stop all repository watchers."""
        for observer in self.observers:
            try:
                observer.stop()
                observer.join()
            except Exception as e:
                logger.error(f"Error stopping observer: {e}")
        
        # Clear references
        self.observers = []
        self.handlers = {}
        self.watched_paths = {}
        
        logger.info("Stopped all repository watchers")
