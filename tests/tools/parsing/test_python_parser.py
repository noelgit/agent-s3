import pytest
from agent_s3.tools.parsing.python_parser import PythonNativeParser

def test_analyze_python_function():
    code = '''
def foo(a: int, b: str) -> bool:
    """This is a test function."""
    return True
'''
    parser = PythonNativeParser()
    result = parser.analyze(code, 'test.py')
    assert len(result['nodes']) >= 1
    func_node = next(n for n in result['nodes'] if n['type'] == 'function')
    assert func_node['name'] == 'foo'
    assert 'a' in func_node['signature']
    assert func_node['docstring'] == 'This is a test function.'
