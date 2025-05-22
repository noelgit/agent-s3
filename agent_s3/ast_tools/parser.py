"""
AST and CST parser wrappers for Python and JavaScript.
"""
from typing import Any

try:  # pragma: no cover - optional dependency
    import libcst
except Exception:  # pragma: no cover - optional for minimal tests
    libcst = None
from tree_sitter import Parser
import tree_sitter_javascript
import tree_sitter_python
from tree_sitter import Language

# Using modern capsule API
JS_LANGUAGE = Language(tree_sitter_javascript.language())
PY_LANGUAGE = Language(tree_sitter_python.language())

PY_PARSER = Parser()
try:  # Support tree-sitter >=0.22 where 'language' is a property
    PY_PARSER.language = PY_LANGUAGE
except AttributeError:  # pragma: no cover - legacy API
    PY_PARSER.set_language(PY_LANGUAGE)

JS_PARSER = Parser()
try:
    JS_PARSER.language = JS_LANGUAGE
except AttributeError:  # pragma: no cover - legacy API
    JS_PARSER.set_language(JS_LANGUAGE)

def parse_python(code: str) -> Any:
    """Parse Python code to a concrete syntax tree (CST) using LibCST."""
    if libcst is None:
        raise ImportError("libcst is required for parse_python")
    return libcst.parse_module(code)

def parse_js(code: str):
    """Parse JavaScript code to a syntax tree using Tree-sitter."""
    tree = JS_PARSER.parse(bytes(code, "utf8"))
    return tree
