"""
ASTTool: Utilities for static code analysis using Python's ast module.
Follows security and performance best practices (see Copilot instructions).
"""
import ast
from typing import Set

class ASTTool:
    """Extracts top-level imports from Python code."""
    def extract_imports_from_code(self, code: str) -> Set[str]:
        """Parses code and returns a set of imported module names."""
        imports = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split(".")[0])
        except SyntaxError as e:
            # Try to parse the code up to the error line
            # Handle case where lineno might be None
            if e.lineno is not None:
                valid_lines = code.splitlines()[:e.lineno-1]
                if valid_lines:
                    # Recursive call with valid portion of code
                    return self.extract_imports_from_code('\n'.join(valid_lines))
            # If no valid content can be extracted, return empty set
            return set()
        except Exception:
            pass  # Fail-safe: return what we have
        return imports
