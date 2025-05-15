"""
Test critic adapters for agent-s3.

This package contains adapters for various testing frameworks:
- PythonPytestAdapter: for Python pytest
- JsJestAdapter: for JavaScript/TypeScript Jest
- PhpPestAdapter: for PHP Pest/PHPUnit
"""

from .python_pytest import PythonPytestAdapter
from .js_jest import JsJestAdapter
from .php_pest import PhpPestAdapter

__all__ = ['PythonPytestAdapter', 'JsJestAdapter', 'PhpPestAdapter']
