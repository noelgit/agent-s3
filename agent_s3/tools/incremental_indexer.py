"""
Incremental Indexer for Agent-S3.

This module implements incremental indexing of code repositories,
enabling efficient updates without requiring full reindexing.
"""

import os
import time
import logging
import threading
import json
from typing import Dict, List, Set, Optional, Tuple, Any, Union, Callable

from agent_s3.tools.file_change_tracker import FileChangeTracker
from agent_s3.tools.index_partition_manager import IndexPartitionManager
from agent_s3.tools.dependency_impact_analyzer import DependencyImpactAnalyzer
from agent_s3.tools.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)

class IncrementalIndexer:
    """
    Core incremental indexing logic that updates only what's changed.
    
    This class provides the ability to incrementally index code repositories,
    update only changed files, and maintain a persistent index.
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        file_tool = None,
        static_analyzer = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the incremental indexer.
        
        Args:
            storage_path: Path to store index data
            embedding_client: Client for generating embeddings
            file_tool: Tool for file operations
            static_analyzer: Analyzer for dependency information
            config: Configuration dictionary
        """
        self.storage_path = storage_path
        if not self.storage_path:
            # Default to a hidden directory in the user's home
            home = os.path.expanduser("~")
            self.storage_path = os.path.join(home, ".agent_s3", "index")
        
        # Create components
        self.file_change_tracker = FileChangeTracker(
            os.path.join(self.storage_path, "change_tracking")
        )
        self.partition_manager = IndexPartitionManager(
            os.path.join(self.storage_path, "partitions")
        )
        self.dependency_analyzer = DependencyImpactAnalyzer()
        
        # Store dependencies
        self.embedding_client = embedding_client
        self.file_tool = file_tool
        self.static_analyzer = static_analyzer
        
        # Configuration
        self.config = config or {}
        self.max_workers = self.config.get('max_indexing_workers', 4)
        self.extensions = self.config.get('extensions', [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java"])
        
        # State
        self.is_indexing = False
        self.indexing_thread = None
        self.indexing_lock = threading.RLock()
        
        # Callback for progress reporting
        self.progress_callback = None
        
        logger.info("Initialized incremental indexer")
    
    def index_repository(
        self,
        repo_path: str,
        force_full: bool = False,
        progress_callback: Optional[Callable] = None,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> Dict[str, Any]:
        """
        Index a repository incrementally or perform a full reindex if needed.
        
        Args:
            repo_path: Path to the repository
            force_full: Force a full reindex
            progress_callback: Function to call with progress updates
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
            
        Returns:
            Dictionary with indexing statistics
        """
        with self.indexing_lock:
            if self.is_indexing:
                return {
                    "status": "error",
                    "message": "Indexing already in progress",
                    "files_indexed": 0,
                    "files_skipped": 0
                }
            
            self.is_indexing = True
            self.progress_callback = progress_callback
        
        try:
            start_time = time.time()
            
            # Check if dependency graph needs updating
            dependency_graph_updated = False
            if self.static_analyzer and hasattr(self.static_analyzer, 'analyze_project'):
                try:
                    # Only update dependency graph if this is a full reindex or it doesn't exist
                    if force_full or not hasattr(self.dependency_analyzer, 'forward_deps') or not self.dependency_analyzer.forward_deps:
                        self._report_progress("Analyzing project dependencies...", 0, 1)
                        dependency_graph = self.static_analyzer.analyze_project(repo_path)
                        self.dependency_analyzer.build_from_dependency_graph(dependency_graph)
                        dependency_graph_updated = True
                        self._report_progress("Dependency analysis complete", 1, 1)
                except Exception as e:
                    logger.error(f"Error analyzing dependencies: {e}")
            
            # Find files to index
            if force_full:
                # Full reindex - get all files
                files_to_index = self._get_all_files(repo_path, include_patterns, exclude_patterns)
                files_skipped = 0
                
                # Clear existing index if doing full reindex
                self._report_progress("Clearing existing index for full reindexing...", 0, 1)
                self.partition_manager.clear_all()
            else:
                # Incremental update - get changed files
                self._report_progress("Finding changed files...", 0, 1)
                changed_files = self.file_change_tracker.get_changed_files(repo_path, self.extensions)
                
                # Determine impacted files
                if dependency_graph_updated and changed_files:
                    self._report_progress("Analyzing dependency impact...", 0, 1)
                    impact_results = self.dependency_analyzer.calculate_impact_scope(changed_files)
                    impacted_files = impact_results.get('prioritized_impacts', [])
                    
                    # Combined list of files to update (changed + impacted)
                    files_to_index = list(set(changed_files + impacted_files))
                    files_skipped = 0
                else:
                    files_to_index = changed_files
                    files_skipped = 0
            
            # Count total files for progress reporting
            total_files = len(files_to_index)
            files_indexed = 0
            
            # Update each file
            for i, file_path in enumerate(files_to_index):
                try:
                    self._report_progress(
                        f"Indexing file {i+1}/{total_files}: {os.path.basename(file_path)}",
                        i, total_files
                    )
                    
                    success = self._index_file(file_path)
                    
                    if success:
                        files_indexed += 1
                        
                        # Record that we've tracked this file
                        self.file_change_tracker.track_file(file_path)
                    else:
                        files_skipped += 1
                except Exception as e:
                    logger.error(f"Error indexing file {file_path}: {e}")
                    files_skipped += 1
            
            # Save all changes
            self._report_progress("Saving index...", total_files, total_files)
            self.partition_manager.commit_all()
            
            # Calculate statistics
            end_time = time.time()
            duration = end_time - start_time
            
            stats = {
                "status": "success",
                "files_indexed": files_indexed,
                "files_skipped": files_skipped,
                "total_files": total_files,
                "duration_seconds": duration,
                "repository": repo_path,
                "full_index": force_full,
                "timestamp": end_time
            }
            
            logger.info(f"Indexed {files_indexed} files ({files_skipped} skipped) in {duration:.2f} seconds")
            
            return stats
        except Exception as e:
            logger.error(f"Error indexing repository: {e}")
            return {
                "status": "error",
                "message": str(e),
                "files_indexed": 0,
                "files_skipped": 0
            }
        finally:
            with self.indexing_lock:
                self.is_indexing = False
                self.progress_callback = None
    
    def update_files(
        self,
        file_paths: List[str],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Update specific files in the index.
        
        Args:
            file_paths: Paths to files to update
            progress_callback: Function to call with progress updates
            
        Returns:
            Dictionary with indexing statistics
        """
        with self.indexing_lock:
            if self.is_indexing:
                return {
                    "status": "error",
                    "message": "Indexing already in progress",
                    "files_indexed": 0,
                    "files_skipped": 0
                }
            
            self.is_indexing = True
            self.progress_callback = progress_callback
        
        try:
            start_time = time.time()
            
            # Count total files for progress reporting
            total_files = len(file_paths)
            files_indexed = 0
            files_skipped = 0
            
            # Update each file
            for i, file_path in enumerate(file_paths):
                try:
                    self._report_progress(
                        f"Indexing file {i+1}/{total_files}: {os.path.basename(file_path)}",
                        i, total_files
                    )
                    
                    success = self._index_file(file_path)
                    
                    if success:
                        files_indexed += 1
                        
                        # Record that we've tracked this file
                        self.file_change_tracker.track_file(file_path)
                    else:
                        files_skipped += 1
                except Exception as e:
                    logger.error(f"Error indexing file {file_path}: {e}")
                    files_skipped += 1
            
            # Save all changes
            self._report_progress("Saving index...", total_files, total_files)
            self.partition_manager.commit_all()
            
            # Calculate statistics
            end_time = time.time()
            duration = end_time - start_time
            
            stats = {
                "status": "success",
                "files_indexed": files_indexed,
                "files_skipped": files_skipped,
                "total_files": total_files,
                "duration_seconds": duration,
                "timestamp": end_time
            }
            
            logger.info(f"Indexed {files_indexed} files ({files_skipped} skipped) in {duration:.2f} seconds")
            
            return stats
        except Exception as e:
            logger.error(f"Error updating files: {e}")
            return {
                "status": "error",
                "message": str(e),
                "files_indexed": 0,
                "files_skipped": 0
            }
        finally:
            with self.indexing_lock:
                self.is_indexing = False
                self.progress_callback = None
    
    def remove_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Remove files from the index.
        
        Args:
            file_paths: Paths to files to remove
            
        Returns:
            Dictionary with removal statistics
        """
        with self.indexing_lock:
            if self.is_indexing:
                return {
                    "status": "error",
                    "message": "Indexing already in progress",
                    "files_removed": 0
                }
            
            self.is_indexing = True
        
        try:
            files_removed = 0
            
            for file_path in file_paths:
                try:
                    success = self.partition_manager.remove_file(file_path)
                    
                    if success:
                        files_removed += 1
                except Exception as e:
                    logger.error(f"Error removing file {file_path}: {e}")
            
            # Save all changes
            self.partition_manager.commit_all()
            
            return {
                "status": "success",
                "files_removed": files_removed,
                "total_files": len(file_paths)
            }
        except Exception as e:
            logger.error(f"Error removing files: {e}")
            return {
                "status": "error",
                "message": str(e),
                "files_removed": 0
            }
        finally:
            with self.indexing_lock:
                self.is_indexing = False
    
    def _index_file(self, file_path: str) -> bool:
        """
        Index a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file was indexed successfully, False otherwise
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                # Remove from index if it exists
                self.partition_manager.remove_file(file_path)
                return True
                
            # Read file content
            if self.file_tool and hasattr(self.file_tool, 'read_file'):
                content = self.file_tool.read_file(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
            if not content:
                return False
                
            # Generate embedding
            if not self.embedding_client:
                return False
                
            embedding = self.embedding_client.get_embedding(content)
            
            if not embedding:
                return False
                
            # Extract metadata
            metadata = self._extract_file_metadata(file_path, content)
            
            # Add/update in index
            success = self.partition_manager.add_or_update_file(
                file_path=file_path,
                embedding=embedding,
                metadata=metadata
            )
            
            return success
        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {e}")
            return False
    
    def _extract_file_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Extract metadata for a file.
        
        Args:
            file_path: Path to the file
            content: Content of the file
            
        Returns:
            Dictionary with file metadata
        """
        metadata = {
            "path": file_path,
            "size": len(content),
            "last_indexed": time.time(),
        }
        
        # Detect language based on extension
        ext = os.path.splitext(file_path)[1].lower()
        
        python_exts = ['.py', '.pyi', '.pyx']
        javascript_exts = ['.js', '.jsx', '.mjs']
        typescript_exts = ['.ts', '.tsx']
        web_exts = ['.html', '.htm', '.css', '.scss', '.sass', '.less']
        java_exts = ['.java']
        csharp_exts = ['.cs']
        
        if ext in python_exts:
            metadata["language"] = "python"
        elif ext in javascript_exts:
            metadata["language"] = "javascript"
        elif ext in typescript_exts:
            metadata["language"] = "typescript"
        elif ext in web_exts:
            metadata["language"] = "web"
        elif ext in java_exts:
            metadata["language"] = "java"
        elif ext in csharp_exts:
            metadata["language"] = "csharp"
        else:
            metadata["language"] = "other"
        
        # Extract metadata from static analyzer if available
        if self.static_analyzer and hasattr(self.static_analyzer, 'analyze_file'):
            try:
                analysis = self.static_analyzer.analyze_file(file_path)
                if analysis and isinstance(analysis, dict):
                    # Extract additional metadata from analysis
                    for key in ['imports', 'exports', 'functions', 'classes']:
                        if key in analysis:
                            metadata[key] = analysis[key]
                    
                    # Extract symbols
                    symbols = []
                    for node_type in ['functions', 'classes', 'variables']:
                        if node_type in analysis:
                            for item in analysis[node_type]:
                                if 'name' in item:
                                    symbols.append(item['name'])
                    
                    metadata['symbols'] = symbols
            except Exception as e:
                logger.error(f"Error extracting metadata from static analyzer: {e}")
        
        return metadata
    
    def _get_all_files(
        self, 
        directory: str,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> List[str]:
        """
        Get all files in a directory matching the criteria.
        
        Args:
            directory: Directory to scan
            include_patterns: List of glob patterns to include
            exclude_patterns: List of glob patterns to exclude
            
        Returns:
            List of file paths
        """
        include_patterns = include_patterns or ['*.*']
        exclude_patterns = exclude_patterns or ['node_modules/*', '__pycache__/*', '.git/*']
        
        # Default exclusion directories
        exclude_dirs = {'node_modules', '__pycache__', '.git', 'venv', 'env'}
        
        all_files = []
        
        try:
            # Walk through directory
            for root, dirs, files in os.walk(directory):
                # Exclude directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    # Check extension
                    if not any(file.endswith(ext) for ext in self.extensions):
                        continue
                        
                    file_path = os.path.join(root, file)
                    
                    # Apply include patterns
                    included = False
                    for pattern in include_patterns:
                        if self._match_pattern(file_path, pattern):
                            included = True
                            break
                            
                    if not included:
                        continue
                        
                    # Apply exclude patterns
                    excluded = False
                    for pattern in exclude_patterns:
                        if self._match_pattern(file_path, pattern):
                            excluded = True
                            break
                            
                    if excluded:
                        continue
                        
                    all_files.append(file_path)
                    
            return all_files
        except Exception as e:
            logger.error(f"Error getting files: {e}")
            return []
    
    def _match_pattern(self, file_path: str, pattern: str) -> bool:
        """
        Check if a file path matches a glob pattern.
        
        Args:
            file_path: Path to check
            pattern: Glob pattern
            
        Returns:
            True if file matches pattern, False otherwise
        """
        try:
            from fnmatch import fnmatch
            
            # Simple glob pattern matching
            return fnmatch(file_path, pattern)
        except Exception:
            # Fallback to simple matching
            return pattern in file_path
    
    def _report_progress(self, message: str, current: int, total: int) -> None:
        """
        Report progress to the callback function.
        
        Args:
            message: Progress message
            current: Current progress value
            total: Total progress value
        """
        if self.progress_callback:
            try:
                progress = {
                    "message": message,
                    "current": current,
                    "total": total,
                    "percentage": int((current / max(1, total)) * 100),
                    "timestamp": time.time()
                }
                
                self.progress_callback(progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    def start_background_indexing(
        self,
        repo_path: str,
        force_full: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Start indexing in a background thread.
        
        Args:
            repo_path: Path to the repository
            force_full: Force a full reindex
            progress_callback: Function to call with progress updates
            
        Returns:
            ID of the indexing job
        """
        with self.indexing_lock:
            if self.is_indexing:
                return ""
        
        # Create a thread for indexing
        thread = threading.Thread(
            target=self.index_repository,
            args=(repo_path, force_full, progress_callback)
        )
        thread.daemon = True
        
        # Start thread
        thread.start()
        self.indexing_thread = thread
        
        job_id = f"index_{int(time.time())}"
        logger.info(f"Started background indexing job: {job_id}")
        
        return job_id
    
    def is_indexing_job_running(self) -> bool:
        """
        Check if an indexing job is running.
        
        Returns:
            True if indexing is in progress, False otherwise
        """
        with self.indexing_lock:
            return self.is_indexing
    
    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the index.
        
        Returns:
            Dictionary with index statistics
        """
        try:
            partition_stats = self.partition_manager.get_partition_stats()
            tracking_stats = self.file_change_tracker.get_stats()
            
            stats = {
                "partitions": partition_stats,
                "tracking": tracking_stats,
                "is_indexing": self.is_indexing
            }
            
            return stats
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {
                "error": str(e)
            }
