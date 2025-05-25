"""
Laravel framework extractor for PHP ASTs using tree-sitter.
"""
from typing import Any, Dict, List, Optional
from tree_sitter import Query
from .base_extractor import FrameworkExtractor

class LaravelExtractor(FrameworkExtractor):
    def extract(self, root_node: Any, file_path: str, content: str, language: str,
                tech_stack: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        nodes = []
        edges = []
        if root_node is None:
            return []
        # Query for Laravel Route definitions
        route_query = """
            (scoped_call_expression
                scope: (name) @scope (#eq? @scope "Route")
                method: (name) @method
                arguments: (arguments (string (string_content) @route_path) . (name) @controller)
            )
        """
        # Query for Controller classes
        controller_query = """
            (class_declaration name: (name) @controller_name
                (base_clause (qualified_name (name) @base (#eq? @base "Controller"))))
        """
        try:
            route_q = Query(root_node.tree.parser.language, route_query)
            controller_q = Query(root_node.tree.parser.language, controller_query)
            # Routes
            for node, cap in route_q.captures(root_node):
                if cap == 'route_path':
                    nodes.append({'type': 'laravel_route', 'path': node.text.decode(), 'start_byte': node.start_byte, 'end_byte': node.end_byte})
                if cap == 'controller':
                    edges.append({'type': 'route_handler', 'target': node.text.decode(), 'start_byte': node.start_byte, 'end_byte': node.end_byte})
            # Controllers
            for node, cap in controller_q.captures(root_node):
                if cap == 'controller_name':
                    nodes.append({'type': 'laravel_controller', 'name': node.text.decode(), 'start_byte': node.start_byte, 'end_byte': node.end_byte})
        except Exception:
            pass
        return nodes + edges

    def is_relevant_framework(self, tech_stack: Dict[str, Any], file_path: str, content: str) -> bool:
        # Heuristic: .php extension and 'laravel' in tech_stack or use of Laravel classes
        if file_path.endswith('.php'):
            if tech_stack and 'laravel' in (tech_stack.get('frameworks') or []):
                return True
            if 'Illuminate\\' in content or 'namespace App\\' in content or 'use Illuminate' in content:
                return True
        return False
