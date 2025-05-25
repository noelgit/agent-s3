import types
from pathlib import Path


def load_partial_static_analysis():
    path = Path(__file__).resolve().parents[1] / "agent_s3" / "tools" / "test_critic" / "static_analysis.py"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[:745]
    module = types.ModuleType("static_analysis_partial")
    module.__package__ = "agent_s3.tools.test_critic"
    exec("".join(lines), module.__dict__)
    return module


def test_detect_test_type_invalid_string():
    mod = load_partial_static_analysis()
    analyzer = mod.CriticStaticAnalyzer()
    result = analyzer._detect_test_type("def foo(): pass", "invalid_type", "python")
    assert result is False
