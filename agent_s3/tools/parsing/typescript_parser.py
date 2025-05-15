"""
Parser for TypeScript code using tree-sitter.
"""
from typing import Dict, Any, List, Optional
from tree_sitter import Parser, Language
import tree_sitter_typescript
from .base_parser import LanguageParser
from .treesitter_utils import execute_query
from ..parsing.framework_extractors.base_extractor import FrameworkExtractor

class TypeScriptTreeSitterParser(LanguageParser):
    def __init__(self, framework_extractors=None):
        # Using direct capsule-based approach with tree_sitter_typescript package
        self.grammar = Language(tree_sitter_typescript.language_typescript())
        self.parser = Parser()
        self.parser.language = self.grammar
        self.framework_extractors = framework_extractors or []

    def get_supported_extensions(self) -> List[str]:
        return ['.ts', '.tsx']

    def analyze(self, code_str: str, file_path: str, tech_stack: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        nodes = []
        edges = []
        try:
            tree = self.parser.parse(bytes(code_str, 'utf8'))
            root_node = tree.root_node
        except Exception as e:
            return {'nodes': nodes, 'edges': edges, 'error': str(e)}

        # Example queries (should be refined for real use)
        FUNC_QUERY = '((function_declaration name: (identifier) @name))'
        CLASS_QUERY = '((class_declaration name: (identifier) @name))'
        for query, typ in [(FUNC_QUERY, 'function'), (CLASS_QUERY, 'class')]:
            for capture in execute_query(self.grammar, root_node, query):
                node = capture["node"]
                nodes.append({'type': typ, 'name': node.text.decode(), 'start_byte': node.start_byte, 'end_byte': node.end_byte})
        for fe in self.framework_extractors:
            if fe.is_relevant_framework(tech_stack or {}, file_path, code_str):
                results = fe.extract(root_node, file_path, code_str, 'typescript', tech_stack)
                for item in results:
                    if 'target' in item:
                        edges.append(item)
                    else:
                        nodes.append(item)
        return {'nodes': nodes, 'edges': edges}
