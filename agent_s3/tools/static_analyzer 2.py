import os
import re
import ast
import logging
import json
from typing import Any, Dict, List, Optional, Tuple

from .file_tool import FileTool
from .parsing.parser_registry import ParserRegistry
from .parsing.base_parser import LanguageParser

logger = logging.getLogger(__name__)

class StaticAnalyzer:
    """
    StaticAnalyzer provides static code analysis for Python, JavaScript/TypeScript, and PHP files.
    - Uses a pluggable parsing framework for robust dependency graph extraction.
    - Security, performance, and code quality best practices are followed throughout.
    """

    def __init__(self, file_tool: FileTool = None, project_root=None, parser_registry: ParserRegistry = None):
        self.file_tool = file_tool
        self.project_root = project_root or self._get_project_root()
        self.parser_registry = parser_registry or ParserRegistry()
        self.php_parser = None  # Deprecated

    def _get_project_root(self):
        if self.file_tool and hasattr(self.file_tool, 'workspace_root'):
            return self.file_tool.workspace_root
        return os.getcwd()

    def _create_name_to_id_map(self, nodes: List[Dict[str, Any]]) -> Dict[str, list]:
        """
        Create a mapping from node names to their IDs for target resolution.
        Handles duplicate names across files by mapping to a list of candidates.
        Stores language and type for better resolution.
        """
        name_to_id = {}
        for node in nodes:
            name = node.get('name')
            if not name:
                continue
            key = (name, node.get('type'), node.get('language'))
            if key not in name_to_id:
                name_to_id[key] = []
            name_to_id[key].append(node['id'])
        return name_to_id

    def resolve_dependency_targets(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], 
                                 external_deps: Optional[Dict[str, List[str]]] = None,
                                 stdlib_modules: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Enhanced resolution with external dependency information.
        
        Args:
            nodes: List of dependency nodes
            edges: List of dependency edges
            external_deps: Dict mapping language to list of installed external packages (optional)
            stdlib_modules: Dict mapping language to list of standard library modules (optional)
        
        Returns:
            Updated edges with resolved targets and dependency classification
        """
        # Detect framework roles during resolution
        nodes = self._detect_framework_roles(nodes, edges)
        
        # Default empty dependency information if not provided
        if external_deps is None:
            external_deps = {
                'python': [], 'javascript': [], 'php': []
            }
        if stdlib_modules is None:
            stdlib_modules = {
                'python': [], 'javascript': [], 'php': []
            }
        
        name_to_id = self._create_name_to_id_map(nodes)
        resolved_edges = []
        
        for edge in edges:
            edge = edge.copy()
            target = edge.get('target')
            edge_type = edge.get('type')
            resolved = False
            source_node = next((n for n in nodes if n['id'] == edge['source']), None)

            # Get source file path for prioritization
            source_file_path = None
            if source_node and 'path' in source_node:
                source_file_path = source_node['path']
            elif source_node and 'id' in source_node:
                source_file_path = source_node['id'].split(":")[0]

            if edge_type == 'import' and source_node:
                # Get source file path from node ID (format is "path:name@line")
                source_path = source_node['id'].split(":")[0]
                
                # Language-specific import resolution with enhanced fallback logic
                if source_path.endswith('.py'):
                    resolved_path = self._resolve_python_import_path(target, source_path, self.project_root)
                    # Python-specific fallback to same-directory modules
                    if not resolved_path and '.' not in target:
                        candidate = os.path.join(os.path.dirname(source_path), f"{target}.py")
                        if os.path.exists(candidate):
                            resolved_path = candidate
                elif source_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
                    resolved_path = self._resolve_js_import_path(target, source_path, self.project_root)
                    # JS/TS fallback to index files
                    if not resolved_path and os.path.isdir(os.path.join(os.path.dirname(source_path), target)):
                        index_candidate = os.path.join(os.path.dirname(source_path), target, 'index.js')
                        if os.path.exists(index_candidate):
                            resolved_path = index_candidate
                elif source_path.endswith('.php'):
                    resolved_path = self._resolve_php_import_path(target, source_path, self.project_root)
                    # PHP fallback to same-directory includes
                    if not resolved_path and not target.startswith(('http://', 'https://')):
                        candidate = os.path.join(os.path.dirname(source_path), target)
                        if os.path.exists(candidate):
                            resolved_path = candidate
                
                if resolved_path:
                    # Find matching file node with priority to exact matches
                    file_node = next((n for n in nodes if n.get('path') == resolved_path), None)
                    if not file_node:
                        # Fallback to directory matches for index files
                        dir_node = next((n for n in nodes if n.get('path') == os.path.dirname(resolved_path)), None)
                        if dir_node:
                            resolved_path = dir_node['path']
                            file_node = dir_node
                    if file_node:
                        edge['target'] = file_node['id']
                        resolved = True
                        edge['resolved_path'] = resolved_path  # Add debug info

            # Handle Django route_handler resolution
            elif edge_type == 'route_handler' and not edge.get('resolved', False):
                # Try to resolve Django view references like "views.ClassName.as_view"
                if '.' in edge['source'] and not edge['source'].startswith('views.'):
                    parts = edge['source'].split('.')
                    if len(parts) >= 2 and parts[0] == 'views':
                        # Look for class-based views
                        class_name = parts[1]
                        view_node = next((n for n in nodes 
                                        if n.get('name') == class_name 
                                        and n.get('type') in ('class', 'function')
                                        and n.get('language') == 'python'), None)
                        if view_node:
                            edge['source'] = view_node['id']
                            resolved = True
                        else:
                            # Look for function-based views
                            func_name = parts[1]
                            view_node = next((n for n in nodes 
                                            if n.get('name') == func_name 
                                            and n.get('type') == 'function'
                                            and n.get('language') == 'python'), None)
                            if view_node:
                                edge['source'] = view_node['id']
                                resolved = True

            # PHP-specific resolution for other edge types
            elif edge_type in {'use', 'include', 'inherit', 'implement'} and source_node:
                php_result = self._resolve_php_target(target, source_node['id'], edge_type, name_to_id, nodes, edges)
                if php_result:
                    edge['target'] = php_result
                    resolved = True

            # General resolution fallback with prioritization
            if not resolved and target:
                # Collect all possible candidates
                all_candidates = []
                for t in ['class', 'function', 'method']:
                    for lang in ['python', 'php', 'javascript']:
                        key = (target, t, lang)
                        if key in name_to_id:
                            all_candidates.extend(name_to_id[key])
                
                if all_candidates:
                    # Prioritize same-file candidates
                    same_file_candidates = [
                        c for c in all_candidates 
                        if source_file_path and c.startswith(f"{source_file_path}:")
                    ]
                    
                    if same_file_candidates:
                        edge['target'] = same_file_candidates[0]
                        resolved = True
                    elif len(all_candidates) == 1:
                        edge['target'] = all_candidates[0]
                        resolved = True
                    else:
                        # Multiple candidates across files - log warning
                        logger.warning(f"Ambiguous resolution for '{target}' from {edge['source']}. Candidates: {all_candidates}")
                        edge['resolved'] = False
                else:
                    # Check if import is from external package or standard library
                    if edge_type == 'import' and source_node:
                        source_lang = None
                        if source_path.endswith('.py'):
                            source_lang = 'python'
                            import_parts = target.split('.')
                            top_level = import_parts[0]
                        elif source_path.endswith(('.js', '.jsx', '.ts', '.tsx')):
                            source_lang = 'javascript'
                            # For JS, use the whole package name as top_level
                            if '/' in target:
                                top_level = target.split('/')[0]
                            else:
                                top_level = target
                        elif source_path.endswith('.php'):
                            source_lang = 'php'
                            if '\\' in target:
                                top_level = target.split('\\')[0]
                            else:
                                top_level = target
                        
                        if source_lang:
                            # Check if it's a standard library module
                            if top_level in stdlib_modules.get(source_lang, []):
                                edge['dependency_type'] = 'stdlib'
                                edge['resolved'] = True
                                edge['resolved_path'] = f"stdlib:{target}"
                                resolved = True
                            # Check if it's an external package
                            elif top_level in external_deps.get(source_lang, []):
                                edge['dependency_type'] = 'external'
                                edge['resolved'] = True
                                edge['resolved_path'] = f"external:{target}"
                                resolved = True
                            else:
                                edge['dependency_type'] = 'unresolved'
                                edge['resolved'] = False

            edge['resolved'] = resolved
            resolved_edges.append(edge)

        return resolved_edges

    def analyze_file(self, file_path: str, tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze a single file for dependency graph nodes and edges.
        Uses the pluggable parsing framework for Python, JS/TS, and PHP files.
        Returns a dict with 'nodes' and 'edges' lists.
        """
        try:
            content = self.file_tool.read_file(file_path) if self.file_tool else open(file_path).read()
            if content is None:
                return {"nodes": [], "edges": []}
            parser = self.parser_registry.get_parser(file_path=file_path)
            if not parser:
                logger.debug(f"Unsupported file extension for analysis: {file_path}")
                return {"nodes": [], "edges": []}
            result = parser.analyze(content, file_path, tech_stack)
            nodes = result.get('nodes', [])
            edges = result.get('edges', [])
            resolved_edges = self.resolve_dependency_targets(nodes, edges)
            nodes = self._detect_framework_roles(nodes, resolved_edges)
            return {'nodes': nodes, 'edges': resolved_edges}
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return {"nodes": [], "edges": []}
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {e}", exc_info=True)
            return {"nodes": [], "edges": []}
        return {"nodes": [], "edges": []} # Default return

    def _detect_framework_roles(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify framework-specific roles based on dependency edges"""
        # Detect Django views from route handlers
        for edge in edges:
            if edge.get('type') == 'route_handler' and edge.get('resolved'):
                source_node = next((n for n in nodes if n['id'] == edge['source']), None)
                if source_node:
                    source_node['framework_role'] = 'view'
        
        # Detect Flask/FastAPI route handlers
        for node in nodes:
            if node.get('type') == 'function' and any('route' in deco for deco in node.get('decorators', [])):
                node['framework_role'] = 'route_handler'
        
        return nodes

    def validate_architecture_implementation(self, architecture: Dict[str, Any], 
                                          implementation: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate that implementation components align with architecture design.
        
        Args:
            architecture: Architecture review dictionary
            implementation: Implementation plan dictionary
            
        Returns:
            Tuple of (is_valid, error_message, validation_details)
        """
        from agent_s3.tools.phase_validator import validate_architecture_implementation as validate_impl
        
        try:
            # Use our dedicated validator from phase_validator.py
            is_valid, error_message, validation_details = validate_impl(architecture, implementation)
            
            # Log validation result
            if is_valid:
                logger.info("Architecture-implementation validation passed")
            else:
                logger.warning(f"Architecture-implementation validation failed: {error_message}")
                
            return is_valid, error_message, validation_details
            
        except Exception as e:
            logger.error(f"Error validating architecture-implementation consistency: {e}", exc_info=True)
            
            # Fallback to minimal validation in case of error
            validation_details = {
                "error": str(e),
                "components_in_architecture": [],
                "components_in_implementation": list(implementation.keys()),
                "unaddressed_gaps": [],
                "unaddressed_optimizations": []
            }
            
            # Try to extract components from architecture
            for gap in architecture.get("logical_gaps", []):
                components = gap.get("affected_components", [])
                if isinstance(components, list):
                    validation_details["components_in_architecture"].extend(components)
            
            # Extract from optimization suggestions
            for suggestion in architecture.get("optimization_suggestions", []):
                components = suggestion.get("affected_components", [])
                if isinstance(components, list):
                    for comp in components:
                        if comp not in validation_details["components_in_architecture"]:
                            validation_details["components_in_architecture"].append(comp)
            
            return False, f"Validation error: {str(e)}", validation_details
    
    def validate_test_coverage_against_risk(self, 
                                          tests: Dict[str, Any],
                                          risk_assessment: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate that tests provide adequate coverage for identified risks.
        
        Args:
            tests: Test suite dictionary with test types and implementations
            risk_assessment: Risk assessment dictionary with critical files and concerns
            
        Returns:
            Tuple of (is_valid, error_message, validation_details)
        """
        from agent_s3.tools.phase_validator import validate_test_coverage_against_risk as validate_test_coverage
        
        try:
            # Use our dedicated validator from phase_validator.py
            is_valid, error_message, validation_details = validate_test_coverage(tests, risk_assessment)
            
            # Log validation result
            if is_valid:
                logger.info("Test coverage validation passed")
            else:
                logger.warning(f"Test coverage validation failed: {error_message}")
                
            return is_valid, error_message, validation_details
            
        except Exception as e:
            logger.error(f"Error validating test coverage against risk: {e}", exc_info=True)
            
            # Fallback to minimal validation in case of error
            validation_details = {
                "error": str(e),
                "critical_files": risk_assessment.get("critical_files", []),
                "tested_files": [],
                "untested_critical_files": []
            }
            
            # Extract all tested files from the tests
            tested_files = set()
            for test_type, test_list in tests.items():
                for test in test_list:
                    if "implementation_file" in test:
                        tested_files.add(test["implementation_file"])
            
            validation_details["tested_files"] = list(tested_files)
            
            # Find critical files without tests
            critical_files = risk_assessment.get("critical_files", [])
            untested_critical = [f for f in critical_files if f not in tested_files]
            validation_details["untested_critical_files"] = untested_critical
            
            return False, f"Validation error: {str(e)}", validation_details
    
    def analyze_project(self, root_path: str, tech_stack: Optional[Dict[str, Any]] = None, 
                      dependency_analyzer=None) -> Dict[str, Any]:
        """
        Analyze entire project and build complete dependency graph.
        Scans all relevant files recursively, merges fragments, and resolves cross-file references.
        
        Args:
            root_path: Path to the project root directory
            tech_stack: Tech stack information for framework-specific analysis
            dependency_analyzer: Optional DependencyAnalyzer instance for external dependency info
        
        Returns:
            Dict with 'nodes' and 'edges' representing the dependency graph
        """
        all_nodes = []
        all_edges = []
        
        # Get external dependencies and standard library information if available
        external_deps = {
            'python': [], 'javascript': [], 'php': []
        }
        stdlib_modules = {
            'python': [], 'javascript': [], 'php': []
        }
        
        # Populate standard library modules
        stdlib_modules['python'] = [
            'os', 'sys', 'json', 're', 'math', 'time', 'datetime', 'random', 'logging',
            'collections', 'itertools', 'functools', 'types', 'typing', 'pathlib',
            'argparse', 'abc', 'ast', 'asyncio', 'concurrent', 'contextlib', 'csv',
            'dataclasses', 'decimal', 'enum', 'http', 'io', 'multiprocessing', 'pickle',
            'sockets', 'sqlite3', 'statistics', 'subprocess', 'tempfile', 'unittest'
        ]
        stdlib_modules['javascript'] = [
            'assert', 'buffer', 'child_process', 'cluster', 'console', 'crypto',
            'dgram', 'dns', 'domain', 'events', 'fs', 'http', 'https', 'net',
            'os', 'path', 'punycode', 'querystring', 'readline', 'stream', 
            'string_decoder', 'timers', 'tls', 'tty', 'url', 'util', 'v8', 'vm', 'zlib'
        ]
        
        # Get installed packages from dependency_analyzer if available
        if dependency_analyzer:
            try:
                python_packages = dependency_analyzer.get_python_packages()
                external_deps['python'] = [pkg.split('==')[0].lower() for pkg in python_packages]
                
                js_packages = dependency_analyzer.get_js_packages()
                external_deps['javascript'] = list(js_packages.keys())
                
                # PHP packages if available
                php_packages = getattr(dependency_analyzer, 'get_php_packages', lambda: [])()
                if php_packages:
                    external_deps['php'] = [pkg.split('/')[1] if '/' in pkg else pkg for pkg in php_packages]
            except Exception as e:
                logger.warning(f"Error getting external dependencies: {e}")
        
        # Analyze files
        for dirpath, _, filenames in os.walk(root_path):
            for fname in filenames:
                if fname.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.php')):
                    fpath = os.path.join(dirpath, fname)
                    result = self.analyze_file_with_tech_stack(fpath, tech_stack)
                    all_nodes.extend(result['nodes'])
                    all_edges.extend(result['edges'])
        
        # Final cross-file target resolution with external dependency info
        all_edges = self.resolve_dependency_targets(
            all_nodes, all_edges, 
            external_deps=external_deps,
            stdlib_modules=stdlib_modules
        )
        all_nodes = self._detect_framework_roles(all_nodes, all_edges, tech_stack)
        
        return {'nodes': all_nodes, 'edges': all_edges}
