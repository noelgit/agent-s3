"""
SummaryValidator: Validates LLM-generated summaries for faithfulness, detail preservation, and structure.
"""
from typing import Optional, Dict, Any
from agent_s3.tools.summarization.validation_metrics import compute_overall_quality

class SummaryValidator:
    """Validates LLM-generated summaries against source content."""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {
            "min_faithfulness": 0.7,
            "min_detail_preservation": 0.6,
            "min_structural_coherence": 0.7,
            "min_overall_quality": 0.7
        }

    def validate(self, source: str, summary: str, language: Optional[str] = None) -> Dict[str, Any]:
        metrics = compute_overall_quality(source, summary, language)
        passed = (
            metrics["faithfulness"] >= self.config["min_faithfulness"] and
            metrics["detail_preservation"] >= self.config["min_detail_preservation"] and
            metrics["structural_coherence"] >= self.config["min_structural_coherence"] and
            metrics["overall"] >= self.config["min_overall_quality"]
        )
        issues = []
        if metrics["faithfulness"] < self.config["min_faithfulness"]:
            issues.append("Low faithfulness - summary may contain inaccurate information")
        if metrics["detail_preservation"] < self.config["min_detail_preservation"]:
            issues.append("Low detail preservation - important details are missing")
        if metrics["structural_coherence"] < self.config["min_structural_coherence"]:
            issues.append("Low structural coherence - code structure not preserved")
        return {
            "passed": passed,
            "metrics": metrics,
            "issues": issues
        }
