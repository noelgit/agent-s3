from pathlib import Path

from agent_s3.tools.test_critic import static_analysis


def test_detect_test_type_invalid_string():
    """_detect_test_type should return False for an invalid test type string."""
    # Ensure module compiles without syntax errors before using it
    source_path = Path("agent_s3/tools/test_critic/static_analysis.py")
    source = source_path.read_text(encoding="utf-8")
    compile(source, str(source_path), "exec")

    analyzer = static_analysis.CriticStaticAnalyzer()
    assert analyzer._detect_test_type("def foo(): pass", "nonexistent", "python") is False
