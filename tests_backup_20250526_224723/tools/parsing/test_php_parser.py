import pytest

# Skip if tree-sitter parsers aren't installed
pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_php")
from agent_s3.tools.parsing.php_parser import PHPTreeSitterParser

def test_analyze_php_function():
    code = '''
<?php
function foo($bar) {
    return $bar;
}
'''
    parser = PHPTreeSitterParser()
    result = parser.analyze(code, 'test.php')
    assert any(n['type'] == 'function' and n['name'] == 'foo' for n in result['nodes'])
