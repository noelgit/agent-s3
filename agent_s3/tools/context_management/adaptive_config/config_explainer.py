"""
Configuration Explainer for Adaptive Configuration.

This module provides transparency and observability for adaptive configuration decisions.
"""

import logging
import json
import os
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ConfigExplainer:
    """
    Provides explanations for configuration decisions and changes in the adaptive system.
    """

    def __init__(self, adaptive_config_manager=None):
        """
        Initialize the configuration explainer.

        Args:
            adaptive_config_manager: Optional reference to AdaptiveConfigManager instance
        """
        self.config_manager = adaptive_config_manager

    def explain_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a human-readable explanation of a configuration.

        Args:
            config: Configuration dictionary to explain

        Returns:
            Dictionary with explanations of key configuration parameters
        """
        result = {
            "overview": "This is the context management configuration that optimizes how code is processed and retrieved.",
            "parameters": {},
            "performance_impact": {}
        }

        cm_config = config.get("context_management", {})

        # Explain embedding parameters
        embedding_config = cm_config.get("embedding", {})
        chunk_size = embedding_config.get("chunk_size")
        chunk_overlap = embedding_config.get("chunk_overlap")

        if chunk_size:
            result["parameters"]["chunk_size"] = {
                "value": chunk_size,
                "explanation": f"Code is divided into chunks of approximately {chunk_size} tokens. " +
                                                                                self._get_chunk_size_impact(chunk_size)
            }

        if chunk_overlap:
            result["parameters"]["chunk_overlap"] = {
                "value": chunk_overlap,
                "explanation": f"Chunks overlap by {chunk_overlap} tokens to maintain continuity. " +
                                                                                self._get_chunk_overlap_impact(chunk_overlap, chunk_size)
            }

        # Explain search parameters
        search_config = cm_config.get("search", {})
        bm25_config = search_config.get("bm25", {})
        k1 = bm25_config.get("k1")
        b = bm25_config.get("b")

        if k1 is not None:
            result["parameters"]["bm25_k1"] = {
                "value": k1,
                "explanation": f"The BM25 k1 parameter is set to {k1}. " +
                    self._get_bm25_k1_impact(k1)
            }

        if b is not None:
            result["parameters"]["bm25_b"] = {
                "value": b,
                "explanation": f"The BM25 b parameter is set to {b}. " +
                    self._get_bm25_b_impact(b)
            }

        # Explain summarization parameters
        summarization_config = cm_config.get("summarization", {})
        threshold = summarization_config.get("threshold")
        compression_ratio = summarization_config.get("compression_ratio")

        if threshold:
            result["parameters"]["summary_threshold"] = {
                "value": threshold,
                "explanation": f"Summarization is triggered when context exceeds {threshold} tokens. " +
                                                                                self._get_summary_threshold_impact(threshold)
            }

        if compression_ratio:
            result["parameters"]["compression_ratio"] = {
                "value": compression_ratio,
                "explanation": f"Content is compressed to approximately {int(compression_ratio * 100)}% of its original size. " +
                                                                                self._get_compression_ratio_impact(compression_ratio)
            }

        # Explain importance scoring parameters
        scoring_config = cm_config.get("importance_scoring", {})
        code_weight = scoring_config.get("code_weight")
        comment_weight = scoring_config.get("comment_weight")
        metadata_weight = scoring_config.get("metadata_weight")
        framework_weight = scoring_config.get("framework_weight")

        if code_weight:
            result["parameters"]["code_weight"] = {
                "value": code_weight,
                "explanation": f"Code has a relative importance weight of {code_weight}. " +
                    self._get_weight_impact("code", code_weight)
            }

        if comment_weight:
            result["parameters"]["comment_weight"] = {
                "value": comment_weight,
                "explanation": f"Comments have a relative importance weight of {comment_weight}. " +
                    self._get_weight_impact("comments", comment_weight)
            }

        if metadata_weight:
            result["parameters"]["metadata_weight"] = {
                "value": metadata_weight,
                "explanation": f"Metadata has a relative importance weight of {metadata_weight}. " +
                    self._get_weight_impact("metadata", metadata_weight)
            }

        if framework_weight:
            result["parameters"]["framework_weight"] = {
                "value": framework_weight,
                "explanation": f"Framework code has a relative importance weight of {framework_weight}. " +
                                                                                self._get_weight_impact("framework", framework_weight)
            }

        # Overall performance impact
        result["performance_impact"] = self._get_overall_performance_impact(config)

        return result

    def explain_config_change(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a human-readable explanation of configuration changes.

        Args:
            old_config: Previous configuration
            new_config: New configuration

        Returns:
            Dictionary with explanations of changes
        """
        result = {
            "overview": "This explains the changes made to the context management configuration.",
            "changes": [],
            "impact": {}
        }

        # Detect changes
        changes = self._detect_config_changes(old_config, new_config)

        # Generate explanations for each change
        for change in changes:
            param_path = change["path"]
            old_value = change["old_value"]
            new_value = change["new_value"]

            explanation = self._explain_parameter_change(param_path, old_value, new_value)

            result["changes"].append({
                "parameter": param_path,
                "old_value": old_value,
                "new_value": new_value,
                "explanation": explanation,
                "impact": self._get_change_impact(param_path, old_value, new_value)
            })

        # Overall impact assessment
        if len(changes) > 0:
            result["impact"] = self._assess_overall_impact(changes)
        else:
            result["impact"] = {
                "description": "No configuration changes detected.",
                "performance_effect": "neutral"
            }

        return result

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive configuration report.

        Returns:
            Dictionary with configuration report
        """
        if not self.config_manager:
            return {"error": "No configuration manager available"}

        try:
            current_config = self.config_manager.get_current_config()
            config_history = self.config_manager.get_config_history()
            performance_summary = self.config_manager.get_performance_summary()

            # Generate explanations
            config_explanation = self.explain_config(current_config)

            # Recent changes
            recent_changes = []
            if len(config_history) > 1:
                # Only process if we have at least 2 versions
                latest_version = config_history[0].get("version")
                previous_version = config_history[1].get("version")

                if latest_version and previous_version:
                    recent_changes = {
                        "from_version": previous_version,
                        "to_version": latest_version,
                        "timestamp": config_history[0].get("timestamp"),
                        "reason": config_history[0].get("reason"),
                        "change_details": self._get_version_changes(previous_version, latest_version)
                    }

            # Assemble report
            report = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "current_version": self.config_manager.get_config_version(),
                "total_versions": len(config_history),
                "configuration_explanation": config_explanation,
                "recent_changes": recent_changes,
                "performance_metrics": self._summarize_performance(performance_summary),
                "recommendations": self._get_recommendations(current_config, performance_summary)
            }

            return report

        except Exception as e:
            logger.error("%s", "Error generating configuration report: %s", e)
            return {"error": str(e)}

    def get_human_readable_report(self) -> str:
        """
        Generate a human-readable configuration report.

        Returns:
            String with formatted report
        """
        try:
            report = self.generate_report()

            if "error" in report:
                return f"Error generating report: {report['error']}"

            lines = [
                "# Context Management Configuration Report",
                f"Generated on: {report.get('timestamp')}",
                f"Configuration Version: {report.get('current_version')}",
                "",
                "## Configuration Overview",
                ""
            ]

            # Add configuration explanation
            config_explanation = report.get("configuration_explanation", {})
            lines.append(config_explanation.get("overview", ""))
            lines.append("")
            lines.append("### Key Parameters")
            lines.append("")

            for param_name, param_info in config_explanation.get("parameters", {}).items():
                lines.append(f"- **{param_name}**: {param_info.get('value')}")
                lines.append(f"  {param_info.get('explanation')}")
                lines.append("")

            # Add recent changes
            recent_changes = report.get("recent_changes")
            if recent_changes:
                lines.append("## Recent Changes")
                lines.append("")
                lines.append(f"From Version {recent_changes.get('from_version')} to {recent_changes.get('to_version')}")
                lines.append(f"Reason: {recent_changes.get('reason')}")
                lines.append("")

                for change in recent_changes.get("change_details", {}).get("changes", []):
                    lines.append(f"- Changed **{change.get('parameter')}** from {change.get('old_value')} to {change.get('new_value')}")
                    lines.append(f"  {change.get('explanation')}")
                    lines.append("")

            # Add performance metrics
            metrics = report.get("performance_metrics", {})
            lines.append("## Performance Metrics")
            lines.append("")

            for metric_name, metric_info in metrics.items():
                if isinstance(metric_info, dict):
                    lines.append(f"### {metric_name.replace('_', ' ').title()}")
                    for k, v in metric_info.items():
                        lines.append(f"- {k.replace('_', ' ').title()}: {v}")
                else:
                    lines.append(f"- {metric_name.replace('_', ' ').title()}: {metric_info}")
                lines.append("")

            # Add recommendations
            recommendations = report.get("recommendations", [])
            if recommendations:
                lines.append("## Recommendations")
                lines.append("")

                for i, rec in enumerate(recommendations, 1):
                    lines.append(f"{i}. {rec.get('recommendation')}")
                    if "rationale" in rec:
                        lines.append(f"   Rationale: {rec.get('rationale')}")
                    lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Error generating human-readable report: %s", e)
            return f"Error generating report: {e}"

    def _detect_config_changes(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect changes between two configurations.

        Args:
            old_config: Previous configuration
            new_config: New configuration

        Returns:
            List of changes
        """
        changes = []

        # Check context management section
        old_cm = old_config.get("context_management", {})
        new_cm = new_config.get("context_management", {})

        # Check embedding parameters
        old_embedding = old_cm.get("embedding", {})
        new_embedding = new_cm.get("embedding", {})

        for param in ["chunk_size", "chunk_overlap"]:
            if param in old_embedding and param in new_embedding and old_embedding[param] != new_embedding[param]:
                changes.append({
                    "path": f"context_management.embedding.{param}",
                    "old_value": old_embedding[param],
                    "new_value": new_embedding[param]
                })

        # Check search parameters
        old_search = old_cm.get("search", {}).get("bm25", {})
        new_search = new_cm.get("search", {}).get("bm25", {})

        for param in ["k1", "b"]:
            if param in old_search and param in new_search and old_search[param] != new_search[param]:
                changes.append({
                    "path": f"context_management.search.bm25.{param}",
                    "old_value": old_search[param],
                    "new_value": new_search[param]
                })

        # Check summarization parameters
        old_summarization = old_cm.get("summarization", {})
        new_summarization = new_cm.get("summarization", {})

        for param in ["threshold", "compression_ratio"]:
            if param in old_summarization and param in new_summarization and old_summarization[param] != new_summarization[param]:
                changes.append({
                    "path": f"context_management.summarization.{param}",
                    "old_value": old_summarization[param],
                    "new_value": new_summarization[param]
                })

        # Check importance scoring parameters
        old_scoring = old_cm.get("importance_scoring", {})
        new_scoring = new_cm.get("importance_scoring", {})

        for param in ["code_weight", "comment_weight", "metadata_weight", "framework_weight"]:
            if param in old_scoring and param in new_scoring and old_scoring[param] != new_scoring[param]:
                changes.append({
                    "path": f"context_management.importance_scoring.{param}",
                    "old_value": old_scoring[param],
                    "new_value": new_scoring[param]
                })

        return changes

    def _explain_parameter_change(self, param_path: str, old_value: Any, new_value: Any) -> str:
        """
        Generate an explanation for a parameter change.

        Args:
            param_path: Parameter path (dot notation)
            old_value: Previous value
            new_value: New value

        Returns:
            Explanation string
        """
        # Extract parameter name from path
        param_name = param_path.split('.')[-1]

        # Calculate change percentage
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)) and old_value != 0:
            change_pct = ((new_value - old_value) / old_value) * 100
            direction = "increased" if new_value > old_value else "decreased"
            magnitude = abs(change_pct)

            if magnitude < 5:
                adj = "slightly"
            elif magnitude < 15:
                adj = "moderately"
            elif magnitude < 30:
                adj = "significantly"
            else:
                adj = "dramatically"

            change_desc = f"{adj} {direction} by {magnitude:.1f}%"
        else:
            change_desc = "changed"

        # Generate explanation based on parameter
        if "chunk_size" in param_path:
            if new_value > old_value:
                return f"Chunk size {change_desc}. Larger chunks capture more context in each embedding but may reduce precision."
            else:
                return f"Chunk size {change_desc}. Smaller chunks provide more granular context retrieval but may miss broader patterns."

        elif "chunk_overlap" in param_path:
            if new_value > old_value:
                return f"Chunk overlap {change_desc}. Greater overlap improves continuity between chunks but increases storage requirements."
            else:
                return f"Chunk overlap {change_desc}. Reduced overlap optimizes storage but may create discontinuities between chunks."

        elif "bm25.k1" in param_path:
            if new_value > old_value:
                return f"BM25 k1 parameter {change_desc}. Higher values give more weight to term frequency, improving results for repeated terms."
            else:
                return f"BM25 k1 parameter {change_desc}. Lower values reduce the impact of term frequency, which can help with keyword matching."

        elif "bm25.b" in param_path:
            if new_value > old_value:
                return f"BM25 b parameter {change_desc}. Higher values increase document length normalization, favoring shorter documents."
            else:
                return f"BM25 b parameter {change_desc}. Lower values reduce length normalization, potentially favoring longer, more detailed documents."

        elif "threshold" in param_path:
            if new_value > old_value:
                return f"Summarization threshold {change_desc}. Higher threshold means summarization happens less frequently, retaining more detail."
            else:
                return f"Summarization threshold {change_desc}. Lower threshold triggers summarization more frequently, potentially improving token efficiency."

        elif "compression_ratio" in param_path:
            if new_value > old_value:
                return f"Compression ratio {change_desc}. Higher ratio retains more content during summarization but uses more tokens."
            else:
                return f"Compression ratio {change_desc}. Lower ratio produces more concise summaries, optimizing token usage."

        elif "code_weight" in param_path:
            if new_value > old_value:
                return f"Code importance weight {change_desc}. Higher weight prioritizes actual code over other content types."
            else:
                return f"Code importance weight {change_desc}. Lower weight gives relatively more importance to non-code content."

        elif "comment_weight" in param_path:
            if new_value > old_value:
                return f"Comment importance weight {change_desc}. Higher weight prioritizes code comments for better documentation context."
            else:
                return f"Comment importance weight {change_desc}. Lower weight reduces the relative importance of comments compared to code."

        elif "metadata_weight" in param_path:
            if new_value > old_value:
                return f"Metadata importance weight {change_desc}. Higher weight prioritizes file metadata for better file relationship understanding."
            else:
                return f"Metadata importance weight {change_desc}. Lower weight reduces the relative importance of metadata in the context."

        elif "framework_weight" in param_path:
            if new_value > old_value:
                return f"Framework code importance weight {change_desc}. Higher weight prioritizes framework-related code for better API understanding."
            else:
                return f"Framework code importance weight {change_desc}. Lower weight reduces focus on framework code to prioritize application logic."

        else:
            return f"Parameter {param_name} {change_desc} from {old_value} to {new_value}."

    def _get_change_impact(self, param_path: str, old_value: Any, new_value: Any) -> Dict[str, Any]:
        """
        Assess the impact of a parameter change.

        Args:
            param_path: Parameter path (dot notation)
            old_value: Previous value
            new_value: New value

        Returns:
            Dictionary with impact assessment
        """
        result = {
            "aspect": "unknown",
            "effect": "neutral",
            "confidence": "low"
        }

        # Determine the affected aspect
        if "chunk_size" in param_path or "chunk_overlap" in param_path:
            result["aspect"] = "context_segmentation"
        elif "bm25" in param_path:
            result["aspect"] = "search_relevance"
        elif "summarization" in param_path:
            result["aspect"] = "summarization_quality"
        elif "weight" in param_path:
            result["aspect"] = "content_prioritization"

        # Determine the effect and confidence
        if "chunk_size" in param_path:
            if new_value > old_value:
                result["effect"] = "more_broad_context"
                result["confidence"] = "medium"
            else:
                result["effect"] = "more_precise_context"
                result["confidence"] = "medium"

        elif "chunk_overlap" in param_path:
            if new_value > old_value:
                result["effect"] = "improved_continuity"
                result["confidence"] = "high"
            else:
                result["effect"] = "improved_efficiency"
                result["confidence"] = "medium"

        elif "bm25.k1" in param_path:
            if new_value > old_value:
                result["effect"] = "improved_term_frequency_sensitivity"
                result["confidence"] = "medium"
            else:
                result["effect"] = "improved_rare_term_matching"
                result["confidence"] = "medium"

        elif "bm25.b" in param_path:
            if new_value > old_value:
                result["effect"] = "favors_shorter_documents"
                result["confidence"] = "medium"
            else:
                result["effect"] = "favors_longer_documents"
                result["confidence"] = "medium"

        elif "threshold" in param_path:
            if new_value > old_value:
                result["effect"] = "more_detail_retention"
                result["confidence"] = "high"
            else:
                result["effect"] = "more_token_efficiency"
                result["confidence"] = "high"

        elif "compression_ratio" in param_path:
            if new_value > old_value:
                result["effect"] = "more_detail_in_summaries"
                result["confidence"] = "high"
            else:
                result["effect"] = "more_concise_summaries"
                result["confidence"] = "high"

        elif "code_weight" in param_path:
            if new_value > old_value:
                result["effect"] = "prioritize_code"
                result["confidence"] = "medium"
            else:
                result["effect"] = "deprioritize_code"
                result["confidence"] = "medium"

        elif "comment_weight" in param_path:
            if new_value > old_value:
                result["effect"] = "prioritize_documentation"
                result["confidence"] = "medium"
            else:
                result["effect"] = "deprioritize_documentation"
                result["confidence"] = "medium"

        return result

    def _assess_overall_impact(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assess overall impact of multiple changes.

        Args:
            changes: List of detected changes

        Returns:
            Dictionary with overall impact assessment
        """
        aspects = set()
        effects = []
        total_magnitude = 0

        for change in changes:
            param_path = change["path"]
            old_value = change["old_value"]
            new_value = change["new_value"]

            impact = self._get_change_impact(param_path, old_value, new_value)
            aspects.add(impact["aspect"])
            effects.append(impact["effect"])

            # Calculate magnitude of change
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)) and old_value != 0:
                magnitude = abs((new_value - old_value) / old_value)
                total_magnitude += magnitude

        # Generate overall impact description
        if len(changes) == 1:
            description = f"This change affects {list(aspects)[0]}."
        else:
            description = f"These changes affect {', '.join(aspects)}."

        # Assess performance effect
        if total_magnitude < 0.1:
            performance_effect = "minor"
        elif total_magnitude < 0.3:
            performance_effect = "moderate"
        else:
            performance_effect = "significant"

        return {
            "description": description,
            "affected_aspects": list(aspects),
            "effects": effects,
            "performance_effect": performance_effect,
            "change_count": len(changes)
        }

    def _get_version_changes(self, from_version: int, to_version: int) -> Dict[str, Any]:
        """
        Get changes between two configuration versions.

        Args:
            from_version: Previous version number
            to_version: Current version number

        Returns:
            Dictionary with change information

        Note:
            Requires access to AdaptiveConfigManager
        """
        if not self.config_manager:
            return {"error": "No configuration manager available"}

        try:
            # Find configuration files
            config_files = {}
            for filename in os.listdir(self.config_manager.config_dir):
                if filename.startswith(f"config_v{from_version}_") or filename.startswith(f"config_v{to_version}_"):
                    version = int(filename.split('_')[1][1:])  # Extract version number
                    config_files[version] = os.path.join(self.config_manager.config_dir, filename)

            if from_version not in config_files or to_version not in config_files:
                return {"error": "One or both versions not found"}

            # Load configurations
            with open(config_files[from_version], 'r') as f:
                from_data = json.load(f)

            with open(config_files[to_version], 'r') as f:
                to_data = json.load(f)

            # Extract actual configs
            old_config = from_data.get("config", {})
            new_config = to_data.get("config", {})

            # Detect changes
            changes = self._detect_config_changes(old_config, new_config)

            # Generate explanations for each change
            explained_changes = []
            for change in changes:
                param_path = change["path"]
                old_value = change["old_value"]
                new_value = change["new_value"]

                explanation = self._explain_parameter_change(param_path, old_value, new_value)
                impact = self._get_change_impact(param_path, old_value, new_value)

                explained_changes.append({
                    "parameter": param_path,
                    "old_value": old_value,
                    "new_value": new_value,
                    "explanation": explanation,
                    "impact": impact
                })

            # Overall impact assessment
            overall_impact = self._assess_overall_impact(changes)

            return {
                "from_version": from_version,
                "to_version": to_version,
                "changes": explained_changes,
                "overall_impact": overall_impact
            }

        except Exception as e:
            logger.error("%s", Error getting version changes: {e})
            return {"error": str(e)}

    def _get_chunk_size_impact(self, chunk_size: int) -> str:
        """Get explanation of chunk size impact."""
        if chunk_size <= 500:
            return "This small chunk size focuses on precise context retrieval but may miss broader relationships."
        elif chunk_size <= 800:
            return "This moderate chunk size balances precision with sufficient context for most code snippets."
        elif chunk_size <= 1200:
            return "This balanced chunk size captures enough context for functions and related code blocks."
        elif chunk_size <= 1500:
            return "This larger chunk size captures broad context but may reduce precision for specific queries."
        else:
            return "This very large chunk size maximizes context but may reduce precision and increase token usage."

    def _get_chunk_overlap_impact(self, overlap: int, chunk_size: int) -> str:
        """Get explanation of chunk overlap impact."""
        if chunk_size:
            ratio = overlap / chunk_size
            if ratio <= 0.1:
                return "This minimal overlap conserves tokens but may create discontinuities between chunks."
            elif ratio <= 0.2:
                return "This moderate overlap provides decent continuity between chunks while optimizing token usage."
            elif ratio <= 0.3:
                return "This substantial overlap ensures good continuity between chunks for better context retrieval."
            else:
                return "This large overlap maximizes continuity but significantly increases storage requirements."
        return ""

    def _get_bm25_k1_impact(self, k1: float) -> str:
        """Get explanation of BM25 k1 impact."""
        if k1 <= 0.5:
            return "This low value reduces the impact of term frequency, which is good for keyword matching."
        elif k1 <= 1.0:
            return "This moderate value balances term frequency with other factors for general code search."
        elif k1 <= 1.5:
            return "This higher value gives more weight to term frequency, improving results for repeated terms."
        else:
            return "This very high value strongly emphasizes term frequency, which helps with highly repetitive patterns."

    def _get_bm25_b_impact(self, b: float) -> str:
        """Get explanation of BM25 b impact."""
        if b <= 0.5:
            return "This low value reduces document length normalization, potentially favoring longer, more detailed documents."
        elif b <= 0.7:
            return "This moderate value applies some length normalization for balanced search results."
        elif b <= 0.85:
            return "This higher value emphasizes document length normalization for more balanced comparison across different file sizes."
        else:
            return "This very high value strongly normalizes for document length, which may favor shorter, more concise documents."

    def _get_summary_threshold_impact(self, threshold: int) -> str:
        """Get explanation of summarization threshold impact."""
        if threshold <= 1000:
            return "This low threshold triggers summarization frequently, optimizing token usage but potentially reducing detail."
        elif threshold <= 2000:
            return "This moderate threshold provides a good balance between detail preservation and token optimization."
        elif threshold <= 3000:
            return "This higher threshold preserves more detail by summarizing less frequently, but may use more tokens."
        else:
            return "This very high threshold strongly prioritizes detail preservation over token optimization."

    def _get_compression_ratio_impact(self, ratio: float) -> str:
        """Get explanation of compression ratio impact."""
        if ratio <= 0.3:
            return "This aggressive compression significantly reduces token usage but may lose important details."
        elif ratio <= 0.5:
            return "This moderate compression provides a good balance between conciseness and detail preservation."
        elif ratio <= 0.7:
            return "This lighter compression preserves most details while still reducing token usage."
        else:
            return "This minimal compression preserves nearly all details but offers limited token optimization."

    def _get_weight_impact(self, content_type: str, weight: float) -> str:
        """Get explanation of importance weight impact."""
        if weight <= 0.5:
            return f"This low weight means {content_type} are considered less important relative to other content types."
        elif weight <= 0.8:
            return f"This moderate weight gives {content_type} standard importance in the context mixture."
        elif weight <= 1.2:
            return f"This balanced weight treats {content_type} with standard importance for most use cases."
        elif weight <= 1.5:
            return f"This higher weight prioritizes {content_type} over other content types when optimizing context."
        else:
            return f"This very high weight strongly favors {content_type} when making context optimization decisions."

    def _get_overall_performance_impact(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Assess overall performance impact of configuration."""
        cm_config = config.get("context_management", {})

        # Extract key parameters
        chunk_size = cm_config.get("embedding", {}).get("chunk_size", 1000)
        chunk_overlap = cm_config.get("embedding", {}).get("chunk_overlap", 200)
        threshold = cm_config.get("summarization", {}).get("threshold", 2000)
        compression = cm_config.get("summarization", {}).get("compression_ratio", 0.5)

        # Assess token efficiency
        if chunk_size <= 800 and compression <= 0.4 and threshold <= 1500:
            token_efficiency = "optimized for token efficiency at the potential cost of detail"
        elif chunk_size >= 1200 and compression >= 0.6 and threshold >= 2500:
            token_efficiency = "optimized for detail preservation at the potential cost of token efficiency"
        else:
            token_efficiency = "balanced between token efficiency and detail preservation"

        # Assess context continuity
        overlap_ratio = chunk_overlap / chunk_size if chunk_size > 0 else 0
        if overlap_ratio >= 0.25:
            continuity = "optimized for strong context continuity"
        elif overlap_ratio <= 0.15:
            continuity = "optimized for storage efficiency with potential continuity gaps"
        else:
            continuity = "balanced between continuity and storage efficiency"

        # Assess search optimization
        k1 = cm_config.get("search", {}).get("bm25", {}).get("k1", 1.2)
        b = cm_config.get("search", {}).get("bm25", {}).get("b", 0.75)

        if k1 >= 1.4:
            search = "optimized for term frequency sensitivity"
        elif b >= 0.85:
            search = "optimized for document length normalization"
        elif b <= 0.6:
            search = "optimized for detailed document matching"
        else:
            search = "balanced for general code search performance"

        return {
            "token_efficiency": token_efficiency,
            "context_continuity": continuity,
            "search_optimization": search
        }

    def _summarize_performance(self, performance_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Create a simplified performance summary."""
        result = {}

        # Extract key metrics
        if "token_usage" in performance_summary:
            token_usage = performance_summary["token_usage"]
            result["token_utilization"] = {
                "average": f"{token_usage.get('avg_utilization', 0) * 100:.1f}%",
                "max": f"{token_usage.get('max_utilization', 0) * 100:.1f}%"
            }

        if "search_relevance" in performance_summary:
            search = performance_summary["search_relevance"]
            result["search_relevance"] = {
                "top_result": f"{search.get('avg_top_relevance', 0) * 100:.1f}%",
                "average": f"{search.get('avg_overall_relevance', 0) * 100:.1f}%"
            }

        if "context_relevance" in performance_summary:
            context = performance_summary["context_relevance"]
            result["context_relevance"] = {
                "overall": f"{context.get('avg_relevance', 0) * 100:.1f}%"
            }

            # Add task-specific relevance
            by_task = context.get("by_task_type", {})
            if by_task:
                task_relevance = {}
                for task, score in by_task.items():
                    task_relevance[task] = f"{score * 100:.1f}%"
                result["task_relevance"] = task_relevance

        if "response_latency" in performance_summary:
            latency = performance_summary["response_latency"]
            result["response_times"] = {
                "average": f"{latency.get('avg_latency_ms', 0):.1f}ms",
                "median": f"{latency.get('median_latency_ms', 0):.1f}ms"
            }

        return result

    def _get_recommendations(
        self,
        current_config: Dict[str, Any],
        performance: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate configuration recommendations based on performance metrics."""
        recommendations = []

        # Check if we have enough performance data
        if not performance or "context_relevance" not in performance:
            return [{
                "recommendation": "Collect more usage data for configuration optimization recommendations",
                "rationale": "Insufficient performance metrics available for analysis"
            }]

        # Extract key metrics
        token_usage = performance.get("token_usage", {})
        search_relevance = performance.get("search_relevance", {})
        context_relevance = performance.get("context_relevance", {})

        # Check token utilization
        avg_utilization = token_usage.get("avg_utilization", 0)
        if avg_utilization > 0.95:
            recommendations.append({
                "recommendation": "Consider increasing summarization threshold or reducing chunk size",
                "rationale": f"Current token utilization is very high ({avg_utilization:.1%})"
            })
        elif avg_utilization < 0.6:
            recommendations.append({
                "recommendation": "Consider decreasing summarization threshold or increasing chunk size",
                "rationale": f"Current token utilization is low ({avg_utilization:.1%})"
            })

        # Check search relevance
        avg_top_relevance = search_relevance.get("avg_top_relevance", 0)
        if avg_top_relevance < 0.7:
            recommendations.append({
                "recommendation": "Consider adjusting BM25 parameters to improve search relevance",
                "rationale": f"Current top search relevance is suboptimal ({avg_top_relevance:.1%})"
            })

        # Check context relevance
        avg_relevance = context_relevance.get("avg_relevance", 0)
        if avg_relevance < 0.7:
            recommendations.append({
                "recommendation": "Consider increasing chunk overlap to improve context continuity",
                "rationale": f"Current context relevance is suboptimal ({avg_relevance:.1%})"
            })

        # Check task-specific relevance
        by_task = context_relevance.get("by_task_type", {})
        for task, score in by_task.items():
            if score < 0.65:
                recommendations.append({
                    "recommendation": f"Consider adjusting importance weights for {task} tasks",
                    "rationale": f"Current relevance for {task} tasks is low ({score:.1%})"
                })

        return recommendations
