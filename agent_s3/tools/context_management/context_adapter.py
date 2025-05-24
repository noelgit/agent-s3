"""
Generic context adapter for Agent-S3.

This module provides a generic context adapter that optimizes context
management regardless of underlying framework.
"""

import os
import re
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ContextAdapter:
    """
    Generic context adapter for framework-agnostic context management.

    Rather than providing framework-specific implementations, this adapter
    intelligently adapts context based on general code patterns.
    """

    def __init__(self):
        """Initialize the context adapter."""
        self.config_cache: Dict[str, Any] = {}

    def transform_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform general context for optimal utilization.

        Args:
            context: The general context dictionary

        Returns:
            The transformed context dictionary
        """
        transformed = context.copy()

        # Add context metadata if not present
        if "metadata" not in transformed:
            transformed["metadata"] = {}

        # Detect primary language and patterns
        code_context = context.get("code_context", {})
        structures = self._extract_key_structures(code_context)

        # Add detected structures
        transformed["code_structures"] = structures

        # Process historical context if available
        if "historical_context" in context:
            historical = context["historical_context"]
            transformed["historical_data"] = self._process_historical_context(historical)

        # Process file metadata if available
        if "file_metadata" in context:
            transformed["file_metadata"] = self._process_file_metadata(context["file_metadata"])

        # Process related features if available
        if "related_features" in context:
            transformed["related_features"] = self._process_related_features(context["related_features"])

        # Add token allocation suggestions
        if "token_allocation" in transformed:
            alloc = transformed["token_allocation"]
            # Prioritize important structures
            if structures["component_files"]:
                alloc["components"] = alloc.get("components", 0) + 0.2
            if structures["model_files"]:
                alloc["models"] = alloc.get("models", 0) + 0.2
            if structures["route_files"]:
                alloc["routes"] = alloc.get("routes", 0) + 0.15
            if structures["test_files"]:
                alloc["tests"] = alloc.get("tests", 0) + 0.1

            # Add allocation for historical context
            if "historical_data" in transformed:
                alloc["historical"] = alloc.get("historical", 0) + 0.15

            # Add allocation for file metadata
            if "file_metadata" in transformed:
                alloc["metadata"] = alloc.get("metadata", 0) + 0.1

            # Add allocation for related features
            if "related_features" in transformed:
                alloc["related_features"] = alloc.get("related_features", 0) + 0.15

            transformed["token_allocation"] = alloc

        return transformed

    def _extract_key_structures(self, file_contents: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract key code structures from file contents.

        Args:
            file_contents: Dictionary mapping file paths to their contents

        Returns:
            Dictionary with extracted code structures
        """
        # Initialize structures
        structures = {
            "component_files": [],
            "model_files": [],
            "route_files": [],
            "test_files": [],
            "config_files": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "language_stats": {
                "python": 0,
                "javascript": 0,
                "typescript": 0,
                "markup": 0
            }
        }

        # Pattern recognition across languages
        component_patterns = [
            # React/Vue/Angular components
            r'class\s+([A-Z][a-zA-Z0-9_]*Component)\s*',
            r'function\s+([A-Z][a-zA-Z0-9_]*)\s*\(props',
            r'const\s+([A-Z][a-zA-Z0-9_]*)\s*=\s*(?:React\.)?(?:memo|forwardRef|createContext)',
            # Python classes that might be components
            r'class\s+([A-Z][a-zA-Z0-9_]*View)\s*\(',
            r'class\s+([A-Z][a-zA-Z0-9_]*Component)\s*\('
        ]

        model_patterns = [
            # ORM models
            r'class\s+([A-Z][a-zA-Z0-9_]*)\s*\(\s*(?:models\.Model|Model|db\.Model)',
            # Schema definitions
            r'class\s+([A-Z][a-zA-Z0-9_]*Schema)\s*\(',
            # TypeScript interfaces and types
            r'interface\s+([A-Z][a-zA-Z0-9_]*)',
            r'type\s+([A-Z][a-zA-Z0-9_]*)\s*=',
            # Mongoose/ODM schemas
            r'const\s+([a-zA-Z0-9_]+Schema)\s*=\s*new\s+Schema\s*\('
        ]

        route_patterns = [
            # Express/Koa/FastAPI routes
            r'(?:app|router|api_router)\.(get|post|put|delete|patch)\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            # Flask routes
            r'@(?:app|blueprint|bp)\.route\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
            # Django URLs
            r'path\s*\(\s*[\'"`]([^\'"`]+)[\'"`],\s*([a-zA-Z0-9_\.]+)',
            # Controllers with routing decorators
            r'@(?:RequestMapping|GetMapping|PostMapping|PutMapping)\s*\(\s*[\'"`]?([^\'"`\)]+
                )[\'"`]?'        ]

        # Process each file
        for file_path, content in file_contents.items():
            # Skip binary or very large files
            if not isinstance(content, str) or len(content) > 1000000:
                continue

            ext = os.path.splitext(file_path)[1].lower()
            file_struct = {"path": file_path, "elements": []}

            # Increment language stats
            if ext in ['.py']:
                structures["language_stats"]["python"] += 1
            elif ext in ['.js', '.jsx']:
                structures["language_stats"]["javascript"] += 1
            elif ext in ['.ts', '.tsx']:
                structures["language_stats"]["typescript"] += 1
            elif ext in ['.html', '.xml', '.jsx', '.tsx']:
                structures["language_stats"]["markup"] += 1

            # Check for component patterns
            for pattern in component_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    component_name = match.group(1)
                    file_struct["elements"].append({
                        "type": "component",
                        "name": component_name
                    })

            # Check if this is a component file
            if file_struct["elements"] or any(x in file_path.lower() for x in ['component', 'view', 'page']):
                structures["component_files"].append(file_struct)

            # Reset elements for model check
            file_struct = {"path": file_path, "elements": []}

            # Check for model patterns
            for pattern in model_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    model_name = match.group(1)
                    file_struct["elements"].append({
                        "type": "model",
                        "name": model_name
                    })

            # Check if this is a model file
            if file_struct["elements"] or any(x in file_path.lower() for x in ['model', 'schema', 'entity']):
                structures["model_files"].append(file_struct)

            # Reset elements for route check
            file_struct = {"path": file_path, "elements": []}

            # Check for route patterns
            for pattern in route_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    endpoint = match.group(1) if len(match.groups()) == 1 else match.group(2)
                    file_struct["elements"].append({
                        "type": "route",
                        "endpoint": endpoint
                    })

            # Check if this is a route file
            if file_struct["elements"] or any(x in file_path.lower() for x in ['route', 'url', 'controller', 'api']):
                structures["route_files"].append(file_struct)

            # Check if this is a test file
            if 'test' in file_path.lower() or file_path.lower().startswith('test_') or file_path.lower().endswith('_test.py'):
                structures["test_files"].append({"path": file_path})

            # Check if this is a config file
            if any(x in file_path.lower() for x in ['config', 'settings', '.env', '.toml', '.ini', '.yml']):
                # Try to cache config content
                self._cache_config_file(file_path, content)
                structures["config_files"].append({"path": file_path})

            # Extract functions regardless of file type (simplified)
            func_matches = re.finditer(r'(?:function|def)\s+([a-zA-Z0-9_]+)\s*\(', content)
            for match in func_matches:
                func_name = match.group(1)
                structures["functions"].append({
                    "name": func_name,
                    "file": file_path
                })

            # Extract classes regardless of file type (simplified)
            class_matches = re.finditer(r'class\s+([a-zA-Z0-9_]+)', content)
            for match in class_matches:
                class_name = match.group(1)
                structures["classes"].append({
                    "name": class_name,
                    "file": file_path
                })

            # Extract imports (simplified)
            import_patterns = [
                r'import\s+([a-zA-Z0-9_., {}]+)\s+from\s+[\'"]([^\'"]+)[\'"]',  # JS/TS
                r'from\s+([^\s]+)\s+import\s+([a-zA-Z0-9_., {}]+)'  # Python
            ]
            for pattern in import_patterns:
                for match in re.finditer(pattern, content):
                    structures["imports"].append({
                        "module": match.group(1) if pattern.startswith('import') else match.group(2),
                        "from": match.group(2) if pattern.startswith('import') else match.group(1),
                        "file": file_path
                    })

        return structures

    def _cache_config_file(self, file_path: str, content: str) -> None:
        """
        Cache a configuration file for later use.

        Args:
            file_path: Path to the configuration file
            content: The file content
        """
        try:
            filename = os.path.basename(file_path)
            if filename.endswith('.json'):
                self.config_cache[filename] = json.loads(content)
            elif filename.endswith(('.yaml', '.yml')):
                import yaml
                self.config_cache[filename] = yaml.safe_load(content)
            else:
                # Just store as text for other file types
                self.config_cache[filename] = content
        except Exception as e:
            logger.warning("%s", Failed to cache config file {file_path}: {e})

    def _process_historical_context(self, historical: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process historical context data for optimal use.

        Args:
            historical: Historical context data dictionary

        Returns:
            Processed historical context ready for LLM consumption
        """
        processed = {}

        # Process recent changes
        if "previous_changes" in historical:
            processed["recent_changes"] = historical["previous_changes"][:5]  # Limit to 5 recent changes

        # Process file change frequency
        if "file_change_frequency" in historical:
            # Sort by frequency and limit to top 5
            sorted_files = sorted(
                historical["file_change_frequency"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            processed["frequently_modified_files"] = {file: freq for file, freq in sorted_files}

        # Process code ownership
        if "code_ownership" in historical:
            processed["code_ownership"] = historical["code_ownership"]

        return processed

    def _process_file_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process file metadata for optimal use.

        Args:
            metadata: File metadata dictionary

        Returns:
            Processed file metadata ready for LLM consumption
        """
        # Currently just passing through, but could add optimizations like
        # filtering to most important files or truncating large sections
        processed = {}

        # Keep only the most important file metadata fields
        if "file_types" in metadata:
            processed["file_types"] = metadata["file_types"]

        if "directory_structure" in metadata:
            processed["directory_structure"] = metadata["directory_structure"]

        if "module_dependencies" in metadata:
            processed["module_dependencies"] = metadata["module_dependencies"]

        return processed

    def _process_related_features(self, related_features: List[str]) -> List[str]:
        """
        Process related features for optimal use.

        Args:
            related_features: List of related features

        Returns:
            Processed list of related features ready for LLM consumption
        """
        # Limit to top 3 most relevant
        return related_features[:3] if related_features else []

    def prioritize_files(self, files: List[str]) -> List[str]:
        """
        Prioritize files based on general code importance.

        Args:
            files: List of file paths

        Returns:
            Prioritized list of file paths
        """
        # Define priority patterns (framework-agnostic)
        high_priority = [
            # Entry points
            r'(^|/)(?:main|app|index|server)\.(?:py|js|ts)$',
            # Core config
            r'(^|/)(?:settings|config)\.(?:py|js|ts)$',
            # Core model/schema
            r'(^|/)(?:models|schemas|entities)\.(?:py|js|ts)$'
        ]

        medium_priority = [
            # Routes/controllers/views
            r'(^|/)(?:routes|controllers|views|urls)\.(?:py|js|ts)$',
            # Components/forms
            r'(^|/)(?:components|forms|fragments)/',
            # Middleware/utils
            r'(^|/)(?:middleware|utils|helpers)/'
        ]

        low_priority = [
            # Test files
            r'(^|/)(?:test_|.*\.spec\.|.*\.test\.|tests/)',
            # Migration/fixtures
            r'(^|/)(?:migrations|fixtures)/',
            # Documentation
            r'(^|/)(?:docs|documentation)/',
            # Build tools
            r'(^|/)(?:webpack|babel|rollup|setup)\.(?:config|py|js)$'
        ]

        # Sort files by priority
        priority_map = {}

        for file_path in files:
            # Default priority is medium (5)
            priority = 5

            # Check high priority patterns
            if any(re.search(pattern, file_path) for pattern in high_priority):
                priority = 9
            # Check medium priority patterns
            elif any(re.search(pattern, file_path) for pattern in medium_priority):
                priority = 7
            # Check low priority patterns
            elif any(re.search(pattern, file_path) for pattern in low_priority):
                priority = 2

            # Store priority
            priority_map[file_path] = priority

        # Sort files by priority (highest first)
        return sorted(files, key=lambda f: priority_map.get(f, 5), reverse=True)
