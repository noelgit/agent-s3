from agent_s3.tools.parsing.parser_registry import ParserRegistry

def test_parser_registry_dispatch():
    registry = ParserRegistry()
    py_parser = registry.get_parser(file_path='foo.py')
    js_parser = registry.get_parser(file_path='foo.js')
    php_parser = registry.get_parser(file_path='foo.php')
    assert py_parser is not None
    assert js_parser is not None
    assert php_parser is not None
    assert py_parser.get_supported_extensions() == ['.py', '.pyw']
    assert '.js' in js_parser.get_supported_extensions()
    assert '.php' in php_parser.get_supported_extensions()
