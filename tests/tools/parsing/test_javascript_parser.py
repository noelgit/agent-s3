import pytest
from agent_s3.tools.parsing.javascript_parser import JavaScriptTreeSitterParser

def test_analyze_js_es6_class():
    code = '''
class MyClass {
  constructor() {}
  myMethod() {}
}
'''
    parser = JavaScriptTreeSitterParser()
    result = parser.analyze(code, 'test.js')
    assert any(n['type'] == 'class' and n['name'] == 'MyClass' for n in result['nodes'])
