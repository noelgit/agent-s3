"""
Parser for Python code using the built-in ast module.
"""
import ast
from typing import Dict, Any, List, Optional
from .base_parser import LanguageParser
from ..parsing.framework_extractors.base_extractor import FrameworkExtractor

class PythonNativeParser(LanguageParser):
    def __init__(self, framework_extractors: Optional[List[FrameworkExtractor]] = None):
        self.framework_extractors = framework_extractors or []

    def get_supported_extensions(self) -> List[str]:
        return ['.py', '.pyw']

    def analyze(self, code_str: str, file_path: str, tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nodes = []
        edges = []
        try:
            tree = ast.parse(code_str, filename=file_path)
        except SyntaxError as e:
            return {'nodes': nodes, 'edges': edges, 'error': str(e)}

        class Visitor(ast.NodeVisitor):
            def visit_Import(self, node):
                for alias in node.names:
                    nodes.append({'type': 'import', 'name': alias.name, 'lineno': node.lineno})
            def visit_ImportFrom(self, node):
                for alias in node.names:
                    nodes.append({'type': 'importfrom', 'module': node.module, 'name': alias.name, 'lineno': node.lineno})
            def visit_FunctionDef(self, node):
                nodes.append({'type': 'function', 'name': node.name, 'lineno': node.lineno, 'signature': ast.unparse(node.args) if hasattr(ast, 'unparse') else '', 'docstring': ast.get_docstring(node)})
                self.generic_visit(node)
            def visit_AsyncFunctionDef(self, node):
                nodes.append({'type': 'asyncfunction', 'name': node.name, 'lineno': node.lineno, 'signature': ast.unparse(node.args) if hasattr(ast, 'unparse') else '', 'docstring': ast.get_docstring(node)})
                self.generic_visit(node)
            def visit_ClassDef(self, node):
                nodes.append({'type': 'class', 'name': node.name, 'lineno': node.lineno, 'docstring': ast.get_docstring(node)})
                self.generic_visit(node)
        Visitor().visit(tree)

        for fe in self.framework_extractors:
            if fe.is_relevant_framework(tech_stack or {}, file_path, code_str):
                results = fe.extract(tree, file_path, code_str, 'python', tech_stack)
                for item in results:
                    if 'target' in item:
                        edges.append(item)
                    else:
                        nodes.append(item)
        return {'nodes': nodes, 'edges': edges}
