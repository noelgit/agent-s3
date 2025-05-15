# Tree-sitter Grammar Setup for Agent-S3

To enable code parsing with tree-sitter, Agent-S3 uses the modern capsule-based API introduced in tree-sitter 0.22+. This approach removes the need to build grammars manually.

## Supported Languages

Agent-S3 only supports the following languages for tree-sitter parsing:
- JavaScript
- TypeScript
- PHP
- Python

## Required Packages

```bash
# Install the core tree-sitter library (minimum version 0.22.0)
pip install --upgrade tree-sitter>=0.22.0

# Install language-specific packages
pip install tree-sitter-python tree-sitter-javascript tree-sitter-php tree-sitter-typescript
```

## Implementation Approach

Agent-S3 uses the direct capsule-based API for each language parser:

```python
# JavaScript Parser
from tree_sitter import Language, Parser
import tree_sitter_javascript

js_grammar = Language(tree_sitter_javascript.language())
parser = Parser()
parser.set_language(js_grammar)
```

```python
# PHP Parser
from tree_sitter import Language, Parser
import tree_sitter_php

php_grammar = Language(tree_sitter_php.language())
parser = Parser()
parser.set_language(php_grammar)
```

```python
# TypeScript Parser
from tree_sitter import Language, Parser
import tree_sitter_typescript

ts_grammar = Language(tree_sitter_typescript.language_typescript())
parser = Parser()
parser.set_language(ts_grammar)
```

```python
# Python Parser
from tree_sitter import Language, Parser
import tree_sitter_python

python_grammar = Language(tree_sitter_python.language())
parser = Parser()
parser.set_language(python_grammar)
```

## Testing

To verify the parser implementations are working correctly:

```zsh
# Run all tree-sitter parser tests
pytest tests/tools/parsing/ --maxfail=3 --disable-warnings -q
```

---

**Troubleshooting:**
- If you see `AttributeError: type object 'tree_sitter.Language' has no attribute 'build_library'`, ensure you are using the latest `tree_sitter` Python package.
- If you see `OSError: ... .so: file too short`, ensure the build step completed successfully and the grammar repos are not empty.

---

**Security Note:**
- Only use official tree-sitter grammars or review third-party grammars for malicious code before building.

---

This setup is required for all developers and CI environments running Agent-S3 with JS/PHP parsing support.
