"""
SummaryValidator: Validates LLM-generated summaries for faithfulness, detail preservation, and structure.
"""
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

from agent_s3.tools.summarization.validation_config import SummaryValidationConfig
from agent_s3.tools.summarization.validation_metrics import compute_overall_quality

class SummaryValidator:
    """Validates LLM-generated summaries against source content."""
    def __init__(self, config: Optional[Union[Dict[str, Any], SummaryValidationConfig]] = None):
        """Create a ``SummaryValidator``.

        Parameters
        ----------
        config : Optional[Union[Dict[str, Any], SummaryValidationConfig]]
            Configuration for validation thresholds. If ``None`` a default
            :class:`SummaryValidationConfig` is used. ``SummaryValidationConfig``
            instances are converted to the internal dictionary format so that
            existing ``dict`` based configuration remains supported.
        """

        if config is None:
            config = SummaryValidationConfig()

        if isinstance(config, SummaryValidationConfig):
            self.config = {
                "min_faithfulness": config.faithfulness_threshold,
                "min_detail_preservation": config.detail_preservation_threshold,
                "min_structural_coherence": config.structural_coherence_threshold,
                "min_overall_quality": (config.faithfulness_threshold * 0.5
                                        + config.detail_preservation_threshold * 0.3
                                        + config.structural_coherence_threshold * 0.2),
            }
        elif isinstance(config, dict):
            self.config = config
        else:
            raise TypeError(
                "config must be a dict or SummaryValidationConfig instance"
            )

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
