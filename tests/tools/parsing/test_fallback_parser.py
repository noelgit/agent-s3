from agent_s3.tools.parsing.fallback_parser import EnhancedRegexParser


def test_fallback_parser_basic():
    code = """
import os
from sys import path as sys_path
#include <stdio.h>
require('mod')

class Foo:
    pass

function bar() {}

def baz(x, y):
    return x + y

x = 1
"""
    parser = EnhancedRegexParser()
    result = parser.parse_code(code, "example.txt")
    assert any(imp.module == "os" for imp in result.imports)
    assert any(cls.name == "Foo" for cls in result.classes)
    assert any(fn.name == "baz" for fn in result.functions)
    assert any(var.name == "x" for var in result.variables)
