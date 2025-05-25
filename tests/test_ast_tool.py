"""
Unit tests for ASTTool.
"""
from agent_s3.tools.ast_tool import ASTTool

def test_extract_imports_from_code_basic():
    code = """
import os\nimport sys\nfrom math import sqrt\nfrom foo import bar\n"""
    ast_tool = ASTTool()
    imports = ast_tool.extract_imports_from_code(code)
    assert "os" in imports
    assert "sys" in imports
    assert "math" in imports
    assert "foo" in imports

def test_extract_imports_from_code_handles_syntax_error():
    code = "import os\ndef foo(:\n    pass"
    ast_tool = ASTTool()
    imports = ast_tool.extract_imports_from_code(code)
    assert isinstance(imports, set)
    assert "os" in imports
