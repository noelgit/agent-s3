"""
Pre-planning validation module.

This module provides structured validation for feature-based pre-planning data.
It validates structure, semantic coherence, and security aspects of pre-planning data.
"""

from typing import Any, Dict, List, Tuple
import logging
from .pattern_constants import (
    SECURITY_CONCERN_PATTERN,
    SECURITY_KEYWORD_PATTERNS,
)
from .pre_planner_json_validator import PrePlannerJsonValidator

logger = logging.getLogger(__name__)


class PrePlanningValidator:
    """Centralized validation for pre-planning data with different validation levels."""

    def validate_structure(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate the basic structure of pre-planning data.

        Args:
            data: Pre-planning data to validate

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Basic type check
        if not isinstance(data, dict):
            errors.append("Pre-planning data must be a dictionary")
            return False, errors

        # Required top-level fields
        required_fields = {"feature_groups"}
        missing_fields = required_fields - set(data.keys())
        if missing_fields:
            errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            return False, errors

        # Validate feature_groups structure
        if not isinstance(data.get("feature_groups"), list) or not data.get(
            "feature_groups"
        ):
            errors.append("feature_groups must be a non-empty list")
            return False, errors

        # Validate each feature group
        for i, group in enumerate(data.get("feature_groups", [])):
            group_errors = self._validate_feature_group(group, i)
            errors.extend(group_errors)

        return len(errors) == 0, errors

    def _validate_feature_group(self, group: Dict[str, Any], index: int) -> List[str]:
        """Validate an individual feature group."""
        errors = []

        if not isinstance(group, dict):
            errors.append(f"Feature group {index} must be a dictionary")
            return errors

        # Required feature group fields
        required_fields = {"group_name", "group_description", "features"}
        missing_fields = required_fields - set(group.keys())
        if missing_fields:
            errors.append(
                f"Feature group {index} missing fields: {', '.join(missing_fields)}"
            )

        # Validate features
        if not isinstance(group.get("features"), list) or not group.get("features"):
            errors.append(f"Feature group {index}: features must be a non-empty list")
        else:
            # Validate each feature
            for j, feature in enumerate(group.get("features", [])):
                feature_errors = self._validate_feature(feature, index, j)
                errors.extend(feature_errors)

        return errors

    def _validate_feature(
        self, feature: Dict[str, Any], group_index: int, feature_index: int
    ) -> List[str]:
        """Validate an individual feature."""
        errors = []
        prefix = f"Feature group {group_index}, feature {feature_index}"

        if not isinstance(feature, dict):
            errors.append(f"{prefix} must be a dictionary")
            return errors

        # Required feature fields
        required_fields = {"name", "description", "complexity"}
        missing_fields = required_fields - set(feature.keys())
        if missing_fields:
            errors.append(f"{prefix} missing fields: {', '.join(missing_fields)}")

        # Validate complexity
        if "complexity" in feature and not 1 <= feature.get("complexity", 0) <= 5:
            errors.append(
                f"{prefix} has invalid complexity: {feature.get('complexity')}. Must be between 1-5."
            )

        # Validate implementation steps if present
        if "implementation_steps" in feature:
            if not isinstance(feature["implementation_steps"], list):
                errors.append(f"{prefix} implementation_steps must be a list")
            else:
                # Check steps based on complexity level
                steps_count = len(feature["implementation_steps"])
                min_steps = max(1, feature.get("complexity", 1))
                if steps_count < min_steps:
                    errors.append(
                        f"{prefix} has complexity {feature.get('complexity')} but only {steps_count} steps"
                    )

        # Validate test requirements if present
        if "test_requirements" in feature:
            test_errors = self._validate_test_requirements(
                feature["test_requirements"], group_index, feature_index
            )
            errors.extend(test_errors)

        # Validate risk assessment if present
        if "risk_assessment" in feature:
            risk_errors = self._validate_risk_assessment(
                feature["risk_assessment"], group_index, feature_index
            )
            errors.extend(risk_errors)

        return errors

    def _validate_test_requirements(
        self, test_reqs: Dict[str, Any], group_index: int, feature_index: int
    ) -> List[str]:
        """Validate test requirements structure."""
        errors = []
        prefix = (
            f"Feature group {group_index}, feature {feature_index}, test_requirements"
        )

        if not isinstance(test_reqs, dict):
            errors.append(f"{prefix} must be a dictionary")
            return errors

        # Check for at least one test type
        test_types = {"unit_tests", "integration_tests", "acceptance_tests"}
        if not any(test_type in test_reqs for test_type in test_types):
            errors.append(f"{prefix} must include at least one test type")

        return errors

    def _validate_risk_assessment(
        self, risk_assessment: Dict[str, Any], group_index: int, feature_index: int
    ) -> List[str]:
        """Validate risk assessment structure."""
        errors = []
        prefix = (
            f"Feature group {group_index}, feature {feature_index}, risk_assessment"
        )

        if not isinstance(risk_assessment, dict):
            errors.append(f"{prefix} must be a dictionary")
            return errors

        # Required risk assessment fields
        required_fields = {"risk_level", "concerns"}
        missing_fields = required_fields - set(risk_assessment.keys())
        if missing_fields:
            errors.append(f"{prefix} missing fields: {', '.join(missing_fields)}")

        # Validate risk level
        if "risk_level" in risk_assessment and risk_assessment["risk_level"] not in {
            "low",
            "medium",
            "high",
        }:
            errors.append(
                f"{prefix} has invalid risk_level: {risk_assessment.get('risk_level')}. Must be one of: low, medium, high"
            )

        return errors

    def validate_semantic_coherence(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Perform semantic validation beyond structure checking."""
        errors = []

        # 1. Check for duplicate feature names across all groups
        feature_names = {}
        for i, group in enumerate(data.get("feature_groups", [])):
            for j, feature in enumerate(group.get("features", [])):
                name = feature.get("name")
                if name in feature_names:
                    prev_group, prev_index = feature_names[name]
                    errors.append(
                        f"Duplicate feature name '{name}' found in group {i} and group {prev_group}"
                    )
                else:
                    feature_names[name] = (i, j)

        # 2. Check for consistency between complexity and description length
        for i, group in enumerate(data.get("feature_groups", [])):
            for j, feature in enumerate(group.get("features", [])):
                desc_length = len(feature.get("description", ""))
                complexity = feature.get("complexity", 1)

                # Very complex features should have substantial descriptions
                if complexity >= 4 and desc_length < 100:
                    errors.append(
                        f"Feature '{feature.get('name')}' has high complexity ({complexity}) but short description ({desc_length} chars)"
                    )

                # Simple features with very long descriptions may be more complex than rated
                if complexity == 1 and desc_length > 300:
                    errors.append(
                        f"Feature '{feature.get('name')}' has low complexity (1) but very detailed description ({desc_length} chars)"
                    )

        # 3. Validate coherence between risk assessment and test requirements
        for i, group in enumerate(data.get("feature_groups", [])):
            for j, feature in enumerate(group.get("features", [])):
                risk = feature.get("risk_assessment", {}).get("risk_level")
                test_reqs = feature.get("test_requirements", {})

                if risk == "high" and (
                    not test_reqs or not test_reqs.get("unit_tests")
                ):
                    errors.append(
                        f"Feature '{feature.get('name')}' has high risk but insufficient test requirements"
                    )

        return len(errors) == 0, errors

    def validate_security(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate security aspects of the pre-planning data."""
        errors = []

        # Security keywords that should trigger additional scrutiny
        security_keywords = SECURITY_KEYWORD_PATTERNS

        # Check for security-related features without proper risk assessment
        for i, group in enumerate(data.get("feature_groups", [])):
            for j, feature in enumerate(group.get("features", [])):
                name = feature.get("name", "").lower()
                desc = feature.get("description", "").lower()

                # Check if this is security-related feature
                is_security_feature = any(
                    pattern.search(name) or pattern.search(desc)
                    for pattern in security_keywords
                )

                if is_security_feature:
                    risk = feature.get("risk_assessment", {})

                    # Security features should have risk assessment
                    if not risk:
                        errors.append(
                            f"Security-related feature '{feature.get('name')}' lacks risk assessment"
                        )
                    elif risk.get("risk_level") not in {"medium", "high"}:
                        errors.append(
                            f"Security-related feature '{feature.get('name')}' has inappropriately low risk level"
                        )

                    # Security features should have specific security concerns
                    concerns = risk.get("concerns", [])
                    has_security_concern = any(
                        SECURITY_CONCERN_PATTERN.search(str(c)) for c in concerns
                    )
                    if not has_security_concern:
                        errors.append(
                            f"Security-related feature '{feature.get('name')}' has no explicit security concerns in risk assessment"
                        )

        return len(errors) == 0, errors

    def validate_all(self, data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Perform all validation checks and return comprehensive results.

        This includes structural, semantic, security, cross-reference, and
        content validations. Any errors from the extended checks are aggregated
        under ``other`` in the returned dictionary.
        """
        result = {
            "valid": True,
            "errors": {"structure": [], "semantic": [], "security": [], "other": []},
            "warnings": [],
            "metadata": {"feature_count": 0, "group_count": 0},
        }

        # Structure validation (critical - fail fast)
        structure_valid, structure_errors = self.validate_structure(data)
        result["errors"]["structure"] = structure_errors

        if not structure_valid:
            result["valid"] = False
            return result["valid"], result

        # Count metrics
        result["metadata"]["group_count"] = len(data.get("feature_groups", []))
        result["metadata"]["feature_count"] = sum(
            len(group.get("features", [])) for group in data.get("feature_groups", [])
        )

        # Semantic coherence validation
        semantic_valid, semantic_errors = self.validate_semantic_coherence(data)
        result["errors"]["semantic"] = semantic_errors

        # Security validation
        security_valid, security_errors = self.validate_security(data)
        result["errors"]["security"] = security_errors

        # Additional cross-reference and content validation using
        # PrePlannerJsonValidator for deeper checks
        other_errors: List[str] = []
        validator = PrePlannerJsonValidator()

        xref_valid, xref_errors, _ = validator.implement_cross_reference_validation(
            data
        )
        if not xref_valid:
            other_errors.extend(xref_errors)

        content_valid, content_errors, _ = validator.implement_content_validation(data)
        if not content_valid:
            other_errors.extend(content_errors)

        result["errors"]["other"] = other_errors

        # Update overall validity including new checks
        result["valid"] = (
            structure_valid
            and semantic_valid
            and security_valid
            and xref_valid
            and content_valid
        )

        return result["valid"], result
