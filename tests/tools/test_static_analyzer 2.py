import pytest
from agent_s3.tools.static_analyzer import StaticAnalyzer

PHP_SNIPPET_CLASS = '''
<?php
namespace MyApp;
use OtherApp\BaseClass;
class Foo extends BaseClass implements IFoo, IBar {
    public function bar() { baz(); }
}
function baz() { }
include 'other.php';
'''

PHP_SNIPPET_FUNCTION = '''
<?php
function hello() { return 'world'; }
'''

@pytest.mark.skipif(not hasattr(StaticAnalyzer, 'php_parser') or StaticAnalyzer().php_parser is None, reason='phply not installed')
def test_parse_php_ast_class():
    analyzer = StaticAnalyzer()
    tree = analyzer._parse_php(PHP_SNIPPET_CLASS, 'foo.php')
    assert tree is not None
    nodes = analyzer._extract_php_classes_ast(tree, 'foo.php')
    assert any(n['name'] == 'Foo' for n in nodes)
    edges = analyzer._extract_php_inheritance_ast(tree, 'foo.php')
    assert any(e['type'] == 'inherit' and e['target'] == 'BaseClass' for e in edges)
    assert any(e['type'] == 'implement' and e['target'] == 'IFoo' for e in edges)
    assert any(e['type'] == 'implement' and e['target'] == 'IBar' for e in edges)
    use_edges = analyzer._extract_php_namespaces_uses_ast(tree, 'foo.php')
    assert any(e['type'] == 'use' and e['target'] == 'OtherApp\\BaseClass' for e in use_edges)
    include_edges = analyzer._extract_php_includes_requires_ast(tree, 'foo.php')
    assert any(e['type'] == 'include' for e in include_edges)
    call_edges = analyzer._extract_php_call_graph_ast(tree, 'foo.php')
    assert any(e['type'] == 'call' and e['target'] == 'baz' for e in call_edges)

def test_parse_php_ast_function():
    analyzer = StaticAnalyzer()
    tree = analyzer._parse_php(PHP_SNIPPET_FUNCTION, 'bar.php')
    assert tree is not None
    nodes = analyzer._extract_php_functions_ast(tree, 'bar.php')
    assert any(n['name'] == 'hello' for n in nodes)

def test_django_framework_roles():
    analyzer = StaticAnalyzer()
    code = """
from django.urls import path
from . import views

urlpatterns = [
    path('home/', views.home_view, name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
]
"""
    results = analyzer.analyze_file("app/urls.py", content=code)
    
    # Verify view functions get framework_role='view'
    view_functions = [
        n for n in results['nodes'] 
        if n.get('framework_role') == 'view'
    ]
    assert len(view_functions) == 2, "Should detect both function and class views"
    
    # Verify route_handler edges are resolved
    route_edges = [
        e for e in results['edges']
        if e['type'] == 'route_handler' and e['resolved']
    ]
    assert len(route_edges) == 2, "Both routes should be resolved"
    
    # Verify Flask-style detection (negative test)
    flask_code = '''
from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Hello"
'''
    flask_results = analyzer.analyze_file("flask_app.py", content=flask_code)
    flask_routes = [n for n in flask_results['nodes'] if n.get('framework_role') == 'route_handler']
    assert len(flask_routes) == 1, "Should detect Flask route handler"
