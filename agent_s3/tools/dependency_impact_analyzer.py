"""
Dependency Impact Analyzer for Agent-S3.

This module provides functionality to determine which files in a codebase
are affected by changes to a particular file based on dependency relationships.
"""

import os
import logging
from collections import defaultdict, deque
from typing import Dict, List, Set, Any

logger = logging.getLogger(__name__)

class DependencyImpactAnalyzer:
    """
    Analyzer for determining the transitive impact of file changes.

    This class builds a reverse dependency graph and provides methods
    to efficiently determine which files are affected by changes to a given file.
    """

    def __init__(self):
        """Initialize the dependency impact analyzer."""
        # Forward dependencies: file -> files it depends on
        self.forward_deps: Dict[str, Set[str]] = defaultdict(set)

        # Reverse dependencies: file -> files that depend on it
        self.reverse_deps: Dict[str, Set[str]] = defaultdict(set)

        # File metadata
        self.file_metadata: Dict[str, Dict[str, Any]] = {}

        # Cached impact analysis results
        self._impact_cache: Dict[str, Dict[str, Any]] = {}

    def build_from_dependency_graph(self, graph: Dict[str, Any]) -> None:
        """
        Build dependency mappings from a dependency graph.

        Args:
            graph: Dependency graph with 'nodes' and 'edges'
        """
        # Reset existing data
        self.forward_deps = defaultdict(set)
        self.reverse_deps = defaultdict(set)
        self.file_metadata = {}

        if not graph or 'nodes' not in graph or 'edges' not in graph:
            logger.warning("Invalid dependency graph provided")
            return

        try:
            # Extract file paths from nodes
            nodes = graph.get('nodes', {})
            for node_id, node in nodes.items():
                if node.get('type') == 'file':
                    file_path = node.get('path') or node_id
                    self.file_metadata[file_path] = {
                        'id': node_id,
                        'language': node.get('language'),
                        'lines': node.get('lines'),
                        'type': node.get('type')
                    }

            # Process edges to build dependency maps
            edges = graph.get('edges', [])
            for edge in edges:
                edge_type = edge.get('type')

                # Skip edge types we don't care about
                if not edge_type or edge_type not in {'import', 'use', 'include', 'call', 'inherit', 'implement'}:
                    continue

                source_id = edge.get('source')
                target_id = edge.get('target')

                if not source_id or not target_id:
                    continue

                # Get file paths
                source_node = nodes.get(source_id, {})
                target_node = nodes.get(target_id, {})

                # Get file containing the source node
                source_file = None
                if source_node.get('type') == 'file':
                    source_file = source_node.get('path') or source_id
                elif 'parent' in source_node:
                    parent_id = source_node['parent']
                    parent_node = nodes.get(parent_id, {})
                    if parent_node.get('type') == 'file':
                        source_file = parent_node.get('path') or parent_id

                # Get file containing the target node
                target_file = None
                if target_node.get('type') == 'file':
                    target_file = target_node.get('path') or target_id
                elif 'parent' in target_node:
                    parent_id = target_node['parent']
                    parent_node = nodes.get(parent_id, {})
                    if parent_node.get('type') == 'file':
                        target_file = parent_node.get('path') or parent_id

                # Add to dependency maps if we have valid file paths
                if source_file and target_file and source_file != target_file:
                    # Forward dependency: source depends on target
                    self.forward_deps[source_file].add(target_file)

                    # Reverse dependency: target is depended on by source
                    self.reverse_deps[target_file].add(source_file)

            logger.info("%s", Built dependency impact analyzer with {len(self.file_metadata)} files)
        except Exception as e:
            logger.error("%s", Error building dependency impact analyzer: {e})

    def get_dependent_files(self, file_path: str, max_depth: int = 3) -> List[str]:
        """
        Get files that depend on the specified file directly or indirectly.

        Args:
            file_path: Path to the file
            max_depth: Maximum depth to traverse in the dependency graph

        Returns:
            List of file paths that depend on the specified file
        """
        # Check cache first
        cache_key = f"{file_path}:{max_depth}"
        if cache_key in self._impact_cache:
            return self._impact_cache[cache_key]['dependent_files']

        # Normalize path
        file_path = os.path.abspath(file_path)

        # Find all dependent files through breadth-first search
        dependent_files = set()
        visited = set([file_path])
        queue = deque([(file_path, 0)])  # (file_path, depth)

        while queue:
            current_file, depth = queue.popleft()

            # Stop if we've reached max depth
            if depth >= max_depth:
                continue

            # Get direct dependents
            dependents = self.reverse_deps.get(current_file, set())

            for dependent in dependents:
                if dependent not in visited:
                    visited.add(dependent)
                    dependent_files.add(dependent)
                    queue.append((dependent, depth + 1))

        # Convert to sorted list
        result = sorted(list(dependent_files))

        # Cache the result
        self._impact_cache[cache_key] = {
            'dependent_files': result,
            'count': len(result),
            'file_path': file_path,
            'max_depth': max_depth
        }

        return result

    def calculate_impact_scope(self, changed_files: List[str], max_depth: int = 3) -> Dict[str,
         Any]:        """
        Calculate the full impact scope of changes to multiple files.

        Args:
            changed_files: List of files that have changed
            max_depth: Maximum depth to traverse in the dependency graph

        Returns:
            Dictionary with impact analysis results
        """
        # Normalize paths
        changed_files = [os.path.abspath(f) for f in changed_files]

        # Build comprehensive impact set
        all_impacted = set()
        direct_impacts = {}

        for file_path in changed_files:
            dependents = self.get_dependent_files(file_path, max_depth)
            direct_impacts[file_path] = dependents
            all_impacted.update(dependents)

        # Remove the changed files themselves from the impacted set
        all_impacted -= set(changed_files)

        # Calculate priority scores based on dependency distance
        priority_scores = {}

        for impacted in all_impacted:
            # Higher priority if impacted by multiple changes
            impact_count = 0
            min_distance = max_depth + 1

            # Find minimum distance from any changed file
            for file_path in changed_files:
                if impacted in direct_impacts.get(file_path, []):
                    impact_count += 1

                    # Find distance (expensive but worthwhile for prioritization)
                    distance = self._find_distance(file_path, impacted)
                    if distance < min_distance:
                        min_distance = distance

            # Calculate priority score (higher is more important)
            # Formula: impact_count / (distance^2)
            if min_distance > 0:
                priority_scores[impacted] = impact_count / (min_distance * min_distance)
            else:
                priority_scores[impacted] = impact_count

        # Sort impacted files by priority
        prioritized_impacts = sorted(
            list(all_impacted),
            key=lambda x: priority_scores.get(x, 0),
            reverse=True
        )

        return {
            'changed_files': changed_files,
            'directly_impacted_files': list(all_impacted),
            'prioritized_impacts': prioritized_impacts,
            'impact_count': len(all_impacted),
            'priority_scores': priority_scores
        }

    def _find_distance(self, source: str, target: str) -> int:
        """
        Find shortest path distance between source and target files.

        Args:
            source: Source file path
            target: Target file path

        Returns:
            Shortest path distance or max_int if no path exists
        """
        # Simple BFS to find shortest path
        visited = set([source])
        queue = deque([(source, 0)])  # (file_path, distance)

        while queue:
            current, distance = queue.popleft()

            if current == target:
                return distance

            # Use reverse dependencies since we're looking for things that depend on us
            next_files = self.reverse_deps.get(current, set())

            for next_file in next_files:
                if next_file not in visited:
                    visited.add(next_file)
                    queue.append((next_file, distance + 1))

        # No path found
        return float('inf')

    def clear_cache(self) -> None:
        """Clear the impact analysis cache."""
        self._impact_cache = {}
