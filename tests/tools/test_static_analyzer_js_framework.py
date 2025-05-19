import pytest

# These tests rely on the optional ``esprima`` package for JavaScript
# parsing. Skip the module import and the tests gracefully when it is not
# installed instead of failing with ``ImportError``.
esprima = pytest.importorskip("esprima")

from agent_s3.tools.static_analyzer import StaticAnalyzer  # noqa: E402

# Ensure esprima is available for JS parsing tests

@pytest.fixture(autouse=True)
def esprima_available(monkeypatch):
    monkeypatch.setattr('agent_s3.tools.static_analyzer.ESPRIMA_AVAILABLE', True)
    # ``esprima`` was imported above using ``importorskip``. Reuse that module
    # object and inject it so the analyzer can access it.
    monkeypatch.setitem(__import__('sys').modules, 'esprima', esprima)


def test_extract_js_call_graph_simple():
    code = '''
function foo() {
  bar();
  baz(1);
}
function bar() {}
'''
    analyzer = StaticAnalyzer()
    graph = analyzer._extract_js_call_graph(code)
    # foo should call bar and baz
    assert 'foo' in graph
    called = {c['name'] for c in graph['foo']}
    assert 'bar' in called and 'baz' in called


def test_extract_react_component_usage():
    jsx = '''
import React from 'react';
export default function App() {
  return (
    <div>
      <MyComponent prop="x" />
      <ns.Another />
    </div>
  );
}
'''
    analyzer = StaticAnalyzer()
    tree = __import__('esprima').parseModule(jsx, {'loc': True})
    edges = analyzer._extract_react_component_usage(tree, 'App.js')
    names = {e['target'].split(':')[1] for e in edges}
    assert 'MyComponent' in names and 'Another' in names
    assert all(e['type']=='component_usage' for e in edges)


def test_extract_vue_component_usage():
    analyzer = StaticAnalyzer()
    edges = analyzer._extract_vue_component_usage(None, 'Comp.vue')
    targets = {e['target'].split(':')[1] for e in edges}
    assert 'MyComponent' in targets and 'AnotherComp' in targets
    assert all(e['type']=='component_usage' for e in edges)


def test_extract_angular_modules_components():
    analyzer = StaticAnalyzer()
    edges = analyzer._extract_angular_modules_components(None, 'app.module.ts')
    types = {e['type'] for e in edges}
    assert 'module_dependency' in types and 'di_injection' in types


def test_extract_nextjs_routing():
    analyzer = StaticAnalyzer()
    edges = analyzer._extract_nextjs_routing(None, 'pages/index.js')
    types = {e['type'] for e in edges}
    assert 'data_fetcher' in types
