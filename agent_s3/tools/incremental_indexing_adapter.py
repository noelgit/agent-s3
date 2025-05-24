"""
Integration module for connecting incremental indexing system with the CodeAnalysisTool.

This module provides the glue code to connect the incremental indexing system with
the existing CodeAnalysisTool, enabling efficient updates to the code search index.
"""

import os
import logging
import threading
from typing import Dict, List, Optional, Any, Callable

from agent_s3.tools.repository_event_system import RepositoryEventSystem
from agent_s3.tools.incremental_indexer import IncrementalIndexer

logger = logging.getLogger(__name__)

class IncrementalIndexingAdapter:
    """
    Adapter class to integrate the incremental indexing system with CodeAnalysisTool.

    This class provides a compatibility layer that allows the CodeAnalysisTool to use
    the incremental indexing system without significant changes to its API.
    """

    def __init__(self, code_analysis_tool, static_analyzer=None, config=None):
        """
        Initialize the incremental indexing adapter.

        Args:
            code_analysis_tool: Instance of CodeAnalysisTool
            static_analyzer: Optional instance of StaticAnalyzer
            config: Configuration dictionary
        """
        self.code_analysis_tool = code_analysis_tool
        self.static_analyzer = static_analyzer
        self.config = config or {}

        # Create indexer with dependencies from CodeAnalysisTool
        self.indexer = IncrementalIndexer(
            storage_path=self._get_storage_path(),
            embedding_client=getattr(code_analysis_tool, 'embedding_client', None),
            file_tool=getattr(code_analysis_tool, 'file_tool', None),
            static_analyzer=self.static_analyzer,
            config=self.config
        )

        # Create repository event system
        self.repo_event_system = RepositoryEventSystem()

        # File tracking for watch events
        self.file_change_tracker = self.indexer.file_change_tracker

        # Watch ID for cleanup
        self._watch_id = None

        # Cache overrides
        self._original_search_code = None
        self._original_embedding_cache = {}

        logger.info("Initialized incremental indexing adapter")

    def _get_storage_path(self) -> str:
        """
        Get storage path for index data.

        Returns:
            Path to store indexing data
        """
        # Try to use the same storage path as CodeAnalysisTool if available
        try:
            if hasattr(self.code_analysis_tool, '_cache_dir'):
                cache_dir = getattr(self.code_analysis_tool, '_cache_dir')
                if cache_dir:
                    return os.path.join(cache_dir, "incremental_index")
        except Exception as e:
            logger.error("%s", Error accessing cache directory: {e})

        # Default to a hidden directory in the user's home
        home = os.path.expanduser("~")
        return os.path.join(home, ".agent_s3", "incremental_index")

    def initialize(self) -> bool:
        """
        Initialize the adapter and connect to CodeAnalysisTool.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Store original search_code method for chaining
            if hasattr(self.code_analysis_tool, 'search_code'):
                self._original_search_code = self.code_analysis_tool.search_code

            # Store original embedding cache
            if hasattr(self.code_analysis_tool, '_embedding_cache'):
                self._original_embedding_cache = getattr(self.code_analysis_tool, '_embedding_cache')

            # Inject our search method
            if hasattr(self.code_analysis_tool, 'search_code'):
                setattr(self.code_analysis_tool, 'search_code', self.search_code_wrapper)

            # Add our index update method
            if not hasattr(self.code_analysis_tool, 'update_index_incrementally'):
                setattr(self.code_analysis_tool, 'update_index_incrementally', self.update_index)

            # Add index stats method
            if not hasattr(self.code_analysis_tool, 'get_index_stats'):
                setattr(self.code_analysis_tool, 'get_index_stats', self.get_index_stats)

            logger.info("Successfully initialized incremental indexing adapter")
            return True
        except Exception as e:
            logger.error("%s", Error initializing incremental indexing adapter: {e})
            return False

    def enable_watch_mode(self, repo_path: str) -> str:
        """
        Enable watch mode for a repository to automatically update the index.

        Args:
            repo_path: Path to the repository to watch

        Returns:
            Watch ID or empty string if failed
        """
        try:
            # Stop any existing watch
            if self._watch_id:
                self.repo_event_system.stop_watching(self._watch_id)
                self._watch_id = None

            # Define callback for repository events
            def repo_event_callback(event_type: str, file_path: str):
                try:
                    # Only process changes to code files
                    ext = os.path.splitext(file_path)[1].lower()
                    extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.java', '.go', '.php']

                    if ext not in extensions:
                        return

                    logger.debug("%s", Repository event: {event_type} - {file_path})

                    # Only update on create or modify events
                    if event_type in ['create', 'modify']:
                        # Use a background thread to avoid blocking
                        thread = threading.Thread(
                            target=self.update_index,
                            args=([file_path],),
                            kwargs={'analyze_dependencies': True}
                        )
                        thread.daemon = True
                        thread.start()
                except Exception as e:
                    logger.error("%s", Error in repository event callback: {e})

            # Start watching
            extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.java', '.go', '.php']
            watch_id = self.repo_event_system.watch_repository(
                repo_path=repo_path,
                callback=repo_event_callback,
                file_patterns=[f"*{ext}" for ext in extensions],
                recursive=True
            )

            if watch_id:
                self._watch_id = watch_id
                logger.info("%s", Started watching repository: {repo_path})
                return watch_id
            else:
                logger.error("%s", Failed to start watching repository: {repo_path})
                return ""
        except Exception as e:
            logger.error("%s", Error enabling watch mode: {e})
            return ""

    def disable_watch_mode(self) -> bool:
        """
        Disable watch mode for repositories.

        Returns:
            True if successful, False otherwise
        """
        if not self._watch_id:
            return True

        try:
            result = self.repo_event_system.stop_watching(self._watch_id)
            if result:
                self._watch_id = None
                logger.info("Stopped watching repository")
            return result
        except Exception as e:
            logger.error("%s", Error disabling watch mode: {e})
            return False

    def update_index(
        self,
        file_paths: Optional[List[str]] = None,
        analyze_dependencies: bool = False,
        force_full: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Update the code search index incrementally.

        Args:
            file_paths: Optional list of file paths to update specifically
            analyze_dependencies: Whether to analyze dependencies of changed files
            force_full: Force a full reindex
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with indexing statistics
        """
        try:
            # Determine workspace root
            workspace_root = None
            if hasattr(self.code_analysis_tool, 'file_tool') and hasattr(self.code_analysis_tool.file_tool, 'workspace_root'):
                workspace_root = self.code_analysis_tool.file_tool.workspace_root

            # If specific files are provided
            if file_paths and not force_full:
                logger.info("%s", Updating index for {len(file_paths)} specific files)

                # If dependency analysis is enabled and static analyzer is available
                if analyze_dependencies and self.static_analyzer:
                    # Get dependency graph if not already built
                    if not hasattr(self.indexer.dependency_analyzer, 'forward_deps') or not self.indexer.dependency_analyzer.forward_deps:
                        if hasattr(self.static_analyzer, 'analyze_project') and workspace_root:
                            dependency_graph = self.static_analyzer.analyze_project(workspace_root)
                            self.indexer.dependency_analyzer.build_from_dependency_graph(dependency_graph)

                    # Calculate impact scope
                    impact_results = self.indexer.dependency_analyzer.calculate_impact_scope(file_paths)
                    impacted_files = impact_results.get('prioritized_impacts', [])

                    # Combined list of files to update (changed + impacted)
                    combined_files = list(set(file_paths + impacted_files))

                    logger.info("%s", Updating {len(file_paths)} changed files and {len(impacted_files)} impacted files)

                    # Update files
                    return self.indexer.update_files(combined_files, progress_callback)
                else:
                    # Update only specified files
                    return self.indexer.update_files(file_paths, progress_callback)
            else:
                # Full index update
                logger.info("%s", Performing {'full' if force_full else 'incremental'} index update)

                if workspace_root:
                    return self.indexer.index_repository(
                        workspace_root,
                        force_full=force_full,
                        progress_callback=progress_callback
                    )
                else:
                    logger.error("Workspace root not available")
                    return {
                        "status": "error",
                        "message": "Workspace root not available",
                        "files_indexed": 0
                    }
        except Exception as e:
            logger.error("%s", Error updating index: {e})
            return {
                "status": "error",
                "message": str(e),
                "files_indexed": 0
            }

    def search_code_wrapper(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """
        Wrapper for CodeAnalysisTool.search_code that uses the incremental index.

        Args:
            query: Search query
            *args: Passed through to original search_code
            **kwargs: Passed through to original search_code

        Returns:
            List of search results
        """
        try:
            # Check if we have a query embedding
            query_embedding = None

            # Try to get query embedding from CodeAnalysisTool
            if hasattr(self.code_analysis_tool, 'embedding_client'):
                embedding_client = self.code_analysis_tool.embedding_client
                if embedding_client and hasattr(embedding_client, 'get_embedding'):
                    query_embedding = embedding_client.get_embedding(query)

            # If we have a query embedding, search using incremental index
            if query_embedding and self.indexer.partition_manager:
                logger.debug("%s", Searching incremental index for: {query})

                # Search across all partitions
                results = self.indexer.partition_manager.search_all_partitions(
                    query_embedding=query_embedding,
                    top_k=kwargs.get('top_k', 10) or 10
                )

                # Format results to match CodeAnalysisTool output
                formatted_results = []

                for result in results:
                    file_path = result['file_path']
                    score = result['score']
                    metadata = result.get('metadata', {})

                    # If file_tool is available, read file content
                    content = metadata.get('content', '')
                    if not content and hasattr(self.code_analysis_tool, 'file_tool'):
                        file_tool = self.code_analysis_tool.file_tool
                        if file_tool and hasattr(file_tool, 'read_file'):
                            content = file_tool.read_file(file_path)

                    formatted_results.append({
                        'file': file_path,
                        'score': score,
                        'content': content,
                        'metadata': metadata
                    })

                # If we didn't get enough results, fall back to original search
                if len(formatted_results) < kwargs.get('top_k', 10) and self._original_search_code:
                    logger.debug("Falling back to original search_code")

                    original_results = self._original_search_code(query, *args, **kwargs)

                    # Combine results, avoiding duplicates
                    existing_files = {r['file'] for r in formatted_results}
                    for result in original_results:
                        if result['file'] not in existing_files:
                            formatted_results.append(result)
                            existing_files.add(result['file'])

                    # Sort by score
                    formatted_results.sort(key=lambda x: x['score'], reverse=True)

                    # Trim to top-k
                    top_k = kwargs.get('top_k', 10) or 10
                    formatted_results = formatted_results[:top_k]

                return formatted_results
            elif self._original_search_code:
                # Fall back to original search_code
                return self._original_search_code(query, *args, **kwargs)
            else:
                logger.error("Original search_code method not available")
                return []
        except Exception as e:
            logger.error("%s", Error in search_code_wrapper: {e})

            # Fall back to original search_code
            if self._original_search_code:
                return self._original_search_code(query, *args, **kwargs)
            return []

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the incremental index.

        Returns:
            Dictionary with index statistics
        """
        try:
            stats = self.indexer.get_index_stats() if self.indexer else {}

            # Add watch mode status
            stats['watch_mode'] = {
                'enabled': self._watch_id is not None,
                'watch_id': self._watch_id
            }

            return stats
        except Exception as e:
            logger.error("%s", Error getting index stats: {e})
            return {
                "error": str(e)
            }

    def teardown(self) -> bool:
        """
        Tear down the adapter and restore original CodeAnalysisTool state.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Restore original search_code method
            if self._original_search_code and hasattr(self.code_analysis_tool, 'search_code'):
                setattr(self.code_analysis_tool, 'search_code', self._original_search_code)

            # Disable watch mode
            self.disable_watch_mode()

            logger.info("Successfully torn down incremental indexing adapter")
            return True
        except Exception as e:
            logger.error("%s", Error tearing down incremental indexing adapter: {e})
            return False


def install_incremental_indexing(code_analysis_tool, static_analyzer=None, config=None)
     -> IncrementalIndexingAdapter:    """
    Install incremental indexing into an existing CodeAnalysisTool instance.

    Args:
        code_analysis_tool: Instance of CodeAnalysisTool
        static_analyzer: Optional instance of StaticAnalyzer
        config: Configuration dictionary

    Returns:
        Configured IncrementalIndexingAdapter instance
    """
    adapter = IncrementalIndexingAdapter(code_analysis_tool, static_analyzer, config)
    adapter.initialize()
    return adapter
