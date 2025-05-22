"""
Test that ContextManager._optimize_context correctly propagates task-keyword-boosted importance scores for all top-level context sections (not just code_context) to ContentPruningManager, and that pruning decisions respect these scores.
"""
import pytest
from agent_s3.tools.context_management.context_manager import ContextManager
from agent_s3.tools.context_management.content_pruning_manager import ContentPruningManager
from agent_s3.tools.context_management.token_budget import TokenBudgetAnalyzer

class DummyEstimator:
    def estimate_tokens_for_context(self, context):
        # Simulate token estimates for two files and two sections
        return {
            "total": 500,
            "code_context": {
                "total": 300,
                "files": {"fileA.py": 150, "fileB.py": 150}
            },
            "metadata": 100,
            "framework_structures": 100
        }
    def estimate_tokens_for_text(self, text, language=None):
        return len(text)
    @property
    def encoding(self):
        class DummyEncoding:
            def encode(self, line):
                return list(line)
        return DummyEncoding()
    def get_total_token_count(self, context):
        return 500
    def get_token_count(self, text):
        return len(text)

@pytest.fixture
def context_manager_with_sections():
    cm = ContextManager()
    tba = TokenBudgetAnalyzer(model_name="gpt-4", max_tokens=500, reserved_tokens=0)
    tba.estimator = DummyEstimator()
    cm.token_budget_analyzer = tba
    cm._pruning_manager = ContentPruningManager(token_analyzer=DummyEstimator())
    cm.current_context = {
        "code_context": {
            "fileA.py": "# Important file\nprint('A')",
            "fileB.py": "# Less important file\nprint('B')"
        },
        "metadata": "Project metadata string",
        "framework_structures": "Framework info string"
    }
    cm.current_task_keywords = ["Important"]
    return cm

def test_importance_propagation_all_sections(context_manager_with_sections):
    cm = context_manager_with_sections
    # Patch TokenBudgetAnalyzer to return scores for all sections
    def fake_calculate_importance_scores(context, task_type=None, task_keywords=None):
        return {
            "code_context": {"fileA.py": 2.0, "fileB.py": 0.1},
            "metadata": 1.8,
            "framework_structures": 0.2
        }
    cm.token_budget_analyzer.calculate_importance_scores = fake_calculate_importance_scores
    cm._context_size_monitor.current_usage = 500
    cm.config["CONTEXT_BACKGROUND_OPT_TARGET_TOKENS"] = 200
    cm._optimize_context()
    # Check all importance overrides
    assert cm._pruning_manager._importance_overrides["code_context.fileA.py"] == 1.0  # clamped
    assert cm._pruning_manager._importance_overrides["code_context.fileB.py"] == 0.1
    assert cm._pruning_manager._importance_overrides["metadata"] == 1.0  # clamped
    assert cm._pruning_manager._importance_overrides["framework_structures"] == 0.2
    # Check pruning candidates reflect these scores
    candidates = cm._pruning_manager.identify_pruning_candidates(cm.current_context, 500, 200)
    pruned = [c[0] for c in candidates if c[1] < 0.7]
    assert "code_context.fileB.py" in pruned
    assert "framework_structures" in pruned
    assert "metadata" not in pruned
    assert "code_context.fileA.py" not in pruned
