# tests/mock_responses/llm_responses.py

"""Aggregated mock LLM responses grouped by feature area."""

from .feature_responses import FEATURE_IMPLEMENTATION_RESPONSES
from .refactoring_responses import REFACTORING_RESPONSES
from .debugging_responses import DEBUGGING_RESPONSES
from .multi_step_responses import MULTI_STEP_RESPONSES
from .edge_case_responses import EDGE_CASE_RESPONSES

MOCK_RESPONSES = {
    "feature_implementation": FEATURE_IMPLEMENTATION_RESPONSES,
    "refactoring": REFACTORING_RESPONSES,
    "debugging": DEBUGGING_RESPONSES,
    "multi_step": MULTI_STEP_RESPONSES,
    "edge_case": EDGE_CASE_RESPONSES,
}

__all__ = [
    "FEATURE_IMPLEMENTATION_RESPONSES",
    "REFACTORING_RESPONSES",
    "DEBUGGING_RESPONSES",
    "MULTI_STEP_RESPONSES",
    "EDGE_CASE_RESPONSES",
    "MOCK_RESPONSES",
]
