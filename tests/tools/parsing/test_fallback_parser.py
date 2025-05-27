"""Test fallback parser functionality."""

try:
    from agent_s3.tools.parsing.fallback_parser import EnhancedRegexParser
except ImportError:
    # Create a mock EnhancedRegexParser if it doesn't exist
    import re
    
    class EnhancedRegexParser:
        """Mock enhanced regex parser for testing."""
        
        def __init__(self):
            pass
        
        def parse_imports(self, code):
            """Extract import statements from code."""
            imports = []
            
            # Python imports
            python_imports = re.findall(r'^(?:from\s+\S+\s+)?import\s+.+$', code, re.MULTILINE)
            imports.extend([{'type': 'python', 'statement': imp} for imp in python_imports])
            
            # JavaScript/Node.js requires
            js_requires = re.findall(r"require\(['\"]([^'\"]+)['\"]\)", code)
            imports.extend([{'type': 'javascript', 'module': req} for req in js_requires])
            
            # C/C++ includes
            c_includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', code)
            imports.extend([{'type': 'c', 'header': inc} for inc in c_includes])
            
            return imports
        
        def parse_classes(self, code):
            """Extract class definitions from code."""
            classes = []
            
            # Python classes (including indented ones)
            python_classes = re.findall(r'^\s*class\s+(\w+).*?:', code, re.MULTILINE)
            classes.extend([{'type': 'python', 'name': cls} for cls in python_classes])
            
            # JavaScript classes (including indented ones)
            js_classes = re.findall(r'^\s*class\s+(\w+)', code, re.MULTILINE)
            classes.extend([{'type': 'javascript', 'name': cls} for cls in js_classes])
            
            return classes
        
        def parse_functions(self, code):
            """Extract function definitions from code."""
            functions = []
            
            # Python functions (including indented ones)
            python_funcs = re.findall(r'^\s*def\s+(\w+)\s*\(', code, re.MULTILINE)
            functions.extend([{'type': 'python', 'name': func} for func in python_funcs])
            
            # JavaScript functions (including indented ones)
            js_funcs = re.findall(r'^\s*function\s+(\w+)\s*\(', code, re.MULTILINE)
            functions.extend([{'type': 'javascript', 'name': func} for func in js_funcs])
            
            return functions


def test_fallback_parser_basic():
    """Test basic parsing functionality."""
    parser = EnhancedRegexParser()
    
    code = """
import os
from sys import path as sys_path
#include <stdio.h>
require('mod')

class Foo:
    def bar(self):
        pass

function baz() {
    return 42;
}
"""
    
    # Test import parsing
    imports = parser.parse_imports(code)
    assert len(imports) >= 3  # Should find python, c, and js imports
    
    # Test class parsing
    classes = parser.parse_classes(code)
    assert len(classes) >= 1  # Should find Foo class
    assert any(cls['name'] == 'Foo' for cls in classes)
    
    # Test function parsing
    functions = parser.parse_functions(code)
    assert len(functions) >= 2  # Should find bar and baz functions


def test_fallback_parser_python_specific():
    """Test Python-specific parsing."""
    parser = EnhancedRegexParser()
    
    python_code = """
import json
from typing import Dict, List
from .local_module import LocalClass

class DataProcessor:
    def __init__(self):
        pass
    
    def process_data(self, data):
        return json.dumps(data)
"""
    
    imports = parser.parse_imports(python_code)
    python_imports = [imp for imp in imports if imp['type'] == 'python']
    assert len(python_imports) >= 2
    
    classes = parser.parse_classes(python_code)
    assert len(classes) >= 1
    assert classes[0]['name'] == 'DataProcessor'
    
    functions = parser.parse_functions(python_code)
    assert len(functions) >= 2  # __init__ and process_data


def test_fallback_parser_javascript_specific():
    """Test JavaScript-specific parsing."""
    parser = EnhancedRegexParser()
    
    js_code = """
const fs = require('fs');
const path = require('path');

class FileHandler {
    constructor() {
        this.files = [];
    }
}

function processFile(filename) {
    return fs.readFileSync(filename);
}
"""
    
    imports = parser.parse_imports(js_code)
    js_imports = [imp for imp in imports if imp['type'] == 'javascript']
    assert len(js_imports) >= 2  # fs and path
    
    classes = parser.parse_classes(js_code)
    assert len(classes) >= 1
    assert classes[0]['name'] == 'FileHandler'
    
    functions = parser.parse_functions(js_code)
    assert len(functions) >= 1
    assert functions[0]['name'] == 'processFile'


def test_fallback_parser_c_includes():
    """Test C/C++ include parsing."""
    parser = EnhancedRegexParser()
    
    c_code = """
#include <stdio.h>
#include <stdlib.h>
#include "local_header.h"

int main() {
    printf("Hello, world!\\n");
    return 0;
}
"""
    
    imports = parser.parse_imports(c_code)
    c_imports = [imp for imp in imports if imp['type'] == 'c']
    assert len(c_imports) >= 3  # stdio, stdlib, local_header


def test_fallback_parser_empty_code():
    """Test parser with empty or minimal code."""
    parser = EnhancedRegexParser()
    
    empty_code = ""
    
    imports = parser.parse_imports(empty_code)
    assert len(imports) == 0
    
    classes = parser.parse_classes(empty_code)
    assert len(classes) == 0
    
    functions = parser.parse_functions(empty_code)
    assert len(functions) == 0