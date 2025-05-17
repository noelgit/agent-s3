"""
Metrics for evaluating summary quality, including faithfulness and detail preservation.
"""
import numpy as np
from agent_s3.llm_utils import get_embedding

class SummaryMetrics:
    def measure_faithfulness(self, original_text: str, summary: str) -> float:
        """Measure how faithful the summary is to the original using embedding similarity."""
        src_emb = get_embedding(original_text)
        sum_emb = get_embedding(summary)
        if src_emb is None or sum_emb is None:
            return 0.0
        sim = np.dot(src_emb, sum_emb) / (np.linalg.norm(src_emb) * np.linalg.norm(sum_emb))
        return float(sim)

    def measure_detail_preservation(self, original_text: str, summary: str) -> float:
        """Measure how well important details are preserved using key term overlap."""
        src_terms = set(original_text.split())
        sum_terms = set(summary.split())
        if not src_terms:
            return 0.0
        overlap = src_terms & sum_terms
        return len(overlap) / len(src_terms)

    def measure_structural_coherence(self, original_text: str, summary: str) -> float:
        """Stub for structure-aware validation (returns 1.0 for now)."""
        return 1.0
