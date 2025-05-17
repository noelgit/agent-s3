"""
Test that ContextManager._optimize_context correctly propagates task-keyword-boosted importance scores to ContentPruningManager,
and that pruning decisions respect these scores (i.e., high-importance files are not pruned).
"""
import pytest
from unittest.mock import Mock
from agent_s3.tools.context_management.context_manager import ContextManager
from agent_s3.tools.context_management.content_pruning_manager import ContentPruningManager
from agent_s3.tools.context_management.token_budget import TokenBudgetAnalyzer

class DummyEstimator:
    def estimate_tokens_for_context(self, context):
        # Simulate token estimates for two files
        return {
            "total": 300,
            "code_context": {
                "total": 300,
                "files": {"fileA.py": 150, "fileB.py": 150}
            }
        }
    def estimate_tokens_for_text(self, text, language=None):
        return 150
    @property
    def encoding(self):
        class DummyEncoding:
            def encode(self, line):
                return list(line)
        return DummyEncoding()
    def get_total_token_count(self, context):
        # Return a plausible total token count for the test
        return 300
    def get_token_count(self, text):
        # Return a plausible token count for a string
        return len(text)

@pytest.fixture
def context_manager_with_importance():
    cm = ContextManager()
    # Construct TokenBudgetAnalyzer with correct arguments, then patch estimator
    tba = TokenBudgetAnalyzer(model_name="gpt-4", max_tokens=200, reserved_tokens=0)
    tba.estimator = DummyEstimator()
    cm.token_budget_analyzer = tba
    cm._pruning_manager = ContentPruningManager(token_analyzer=DummyEstimator())
    cm.current_context = {
        "code_context": {
            "fileA.py": "# Important file\nprint('A')",
            "fileB.py": "# Less important file\nprint('B')"
        }
    }
    # Simulate task keywords that boost fileA.py
    cm.current_task_keywords = ["Important"]
    return cm

def test_importance_propagation_and_pruning(context_manager_with_importance):
    cm = context_manager_with_importance
    # Patch TokenBudgetAnalyzer to boost fileA.py
    def fake_calculate_importance_scores(context, task_type=None, task_keywords=None):
        return {"code_context": {"fileA.py": 2.0, "fileB.py": 0.1}}
    cm.token_budget_analyzer.calculate_importance_scores = fake_calculate_importance_scores
    # Force optimization (simulate over-budget)
    cm._context_size_monitor.current_usage = 300
    cm.config["CONTEXT_BACKGROUND_OPT_TARGET_TOKENS"] = 200
    cm._optimize_context()
    # fileA.py should have high importance in pruning manager, fileB.py low
    assert cm._pruning_manager._importance_overrides["code_context.fileA.py"] == 1.0  # clamped
    assert cm._pruning_manager._importance_overrides["code_context.fileB.py"] == 0.1
    # fileA.py should not be pruned, fileB.py should be prunable
    candidates = cm._pruning_manager.identify_pruning_candidates(cm.current_context, 300, 200)
    pruned = [c[0] for c in candidates if c[1] < 0.7]
    assert "code_context.fileB.py" in pruned
    assert "code_context.fileA.py" not in pruned
