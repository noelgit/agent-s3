"""
Utility functions for tree-sitter grammar loading and query execution.
"""
from typing import Any, List, Dict, Generator

GRAMMAR_CACHE = {}

def get_language(language_name: str) -> Any:
    """
    Gets a tree-sitter language using the modern capsule API approach.
    
    Args:
        language_name: The language name (e.g., 'python', 'javascript')
        
    Returns:
        The tree-sitter Language object
    """
    if language_name in GRAMMAR_CACHE:
        return GRAMMAR_CACHE[language_name]
        
    try:
        from tree_sitter import Language
        
        if language_name == "javascript":
            import tree_sitter_javascript
            grammar = Language(tree_sitter_javascript.language())
            GRAMMAR_CACHE[language_name] = grammar
            return grammar
        elif language_name == "typescript":
            import tree_sitter_typescript
            grammar = Language(tree_sitter_typescript.language_typescript())
            GRAMMAR_CACHE[language_name] = grammar
            return grammar
        elif language_name == "php":
            import tree_sitter_php
            grammar = Language(tree_sitter_php.language_php())
            GRAMMAR_CACHE[language_name] = grammar
            return grammar
        elif language_name == "python":
            import tree_sitter_python
            grammar = Language(tree_sitter_python.language())
            GRAMMAR_CACHE[language_name] = grammar
            return grammar
        else:
            raise ValueError(f"Language '{language_name}' is not supported. Only 'javascript', 'typescript', 'php', and 'python' are supported.")
    except ImportError as e:
        raise ImportError(f"Failed to load tree-sitter module for {language_name}: {e}")

def execute_query(grammar: Any, node: Any, query_string: str) -> List[Dict[str, Any]]:
    """
    Executes a tree-sitter query against a given AST node using the specified grammar.
    Returns a list of dictionaries with node information and capture name.
    
    Example return value:
    [
        {"node": <node_object>, "capture_name": "name"},
        ...
    ]
    """
    from tree_sitter import Query
    try:
        query = Query(grammar, query_string)
        matches = query.matches(node)
        result = []
        
        # Based on debug output, matches is a list of (pattern_idx, captures_dict) tuples
        # where captures_dict maps capture names to lists of nodes
        for _, captures_dict in matches:
            for capture_name, nodes in captures_dict.items():
                for capture_node in nodes:
                    result.append({
                        "node": capture_node,
                        "capture_name": capture_name
                    })
                
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to execute query: {e}")
