import importlib.util
from pathlib import Path
import sys
import types

def load_token_budget(monkeypatch):
    """Load token_budget module with a dummy tiktoken implementation."""
    class DummyEncoding:
        def encode(self, text):
            return text.split()

    dummy_tiktoken = types.SimpleNamespace(
        encoding_for_model=lambda name: DummyEncoding(),
        get_encoding=lambda name: DummyEncoding(),
        __version__="0.0.0",
    )
    monkeypatch.setitem(sys.modules, "tiktoken", dummy_tiktoken)

    module_path = Path(__file__).resolve().parents[3] / "agent_s3" / "tools" / "context_management" / "token_budget.py"
    spec = importlib.util.spec_from_file_location("token_budget", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_allocate_tokens_truncates_important_files(monkeypatch):
    tb = load_token_budget(monkeypatch)
    TokenBudgetAnalyzer = tb.TokenBudgetAnalyzer

    analyzer = TokenBudgetAnalyzer(max_tokens=50, reserved_tokens=0)

    important_content = "\n".join(["def main():", "    pass"] * 50)
    other_content = "\n".join(["print('hi')"] * 100)

    context = {"code_context": {"main.py": important_content, "utils.py": other_content}}

    result, scores = analyzer.allocate_tokens(context, force_optimization=True)
    optimized = result["optimized_context"]
    report = result["allocation_report"]

    assert report["optimization_applied"] is True
    assert "main.py" in optimized["code_context"]
    assert "truncated" in optimized["code_context"]["main.py"]
    assert report["file_allocations"]["main.py"]["importance_score"] > 1

    if "utils.py" in optimized["code_context"]:
        assert "truncated" in optimized["code_context"]["utils.py"] or optimized["code_context"]["utils.py"] != other_content

