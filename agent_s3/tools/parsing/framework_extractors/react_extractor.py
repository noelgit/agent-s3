"""
React framework extractor for JavaScript/TypeScript ASTs using tree-sitter.
"""
from typing import Any, Dict, List, Optional
from tree_sitter import Query
from .base_extractor import FrameworkExtractor

class ReactExtractor(FrameworkExtractor):
    def extract(self, root_node: Any, file_path: str, content: str, language: str, tech_stack: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        nodes = []
        edges = []
        if root_node is None:
            return []
        # Query for function and class components
        component_query = """
            (function_declaration name: (identifier) @component_name)
            (lexical_declaration (variable_declarator name: (identifier) @component_name value: (arrow_function)))
            (class_declaration name: (identifier) @component_name)
        """
        # Query for JSX elements (component usage)
        jsx_query = """
            (jsx_opening_element name: (identifier) @jsx_component)
            (jsx_opening_element name: (member_expression) @jsx_component)
        """
        try:
            component_q = Query(root_node.tree.parser.language, component_query)
            jsx_q = Query(root_node.tree.parser.language, jsx_query)
            # Components
            for node, cap in component_q.captures(root_node):
                if cap == 'component_name':
                    nodes.append({'type': 'react_component', 'name': node.text.decode(), 'start_byte': node.start_byte, 'end_byte': node.end_byte})
            # JSX usages
            for node, cap in jsx_q.captures(root_node):
                if cap == 'jsx_component':
                    edges.append({'type': 'component_usage', 'target': f"jsx:{node.text.decode()}", 'start_byte': node.start_byte, 'end_byte': node.end_byte})
        except Exception:
            pass
        return nodes + edges

    def is_relevant_framework(self, tech_stack: Dict[str, Any], file_path: str, content: str) -> bool:
        # Heuristic: .jsx/.tsx extension or 'react' in tech_stack or import
        if file_path.endswith(('.jsx', '.tsx')):
            return True
        if tech_stack and 'react' in (tech_stack.get('frameworks') or []):
            return True
        if 'import React' in content or 'from "react"' in content or "from 'react'" in content:
            return True
        return False
