import json
import subprocess

from agent_s3.tools.code_analysis_tool import CodeAnalysisTool

class DummyResultNoOutput:
    stdout = ''

class DummyResultWithOutput:
    stdout = json.dumps([{'code':'E001','line':10,'message':'error'}])

def test_lint_no_violations(monkeypatch):
    # Simulate ruff returning no JSON output
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: DummyResultNoOutput())
    tool = CodeAnalysisTool()
    violations = tool.lint(paths=['.'])
    assert violations == []

def test_lint_with_violations(monkeypatch):
    # Simulate ruff returning violations
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kwargs: DummyResultWithOutput())
    tool = CodeAnalysisTool()
    violations = tool.lint()
    assert isinstance(violations, list)
    assert violations[0]['code'] == 'E001'
