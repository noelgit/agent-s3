"""
Test critic adapters for agent-s3.

This package contains adapters for various testing frameworks:
- PythonPytestAdapter: for Python pytest
- JsJestAdapter: for JavaScript/TypeScript Jest
- PhpPestAdapter: for PHP Pest/PHPUnit
"""

from .base import Adapter

__all__ = ['Adapter', 'PythonPytestAdapter', 'JsJestAdapter', 'PhpPestAdapter']
