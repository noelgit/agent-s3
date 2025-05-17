"""
Unit tests for pre_planner_json_validator module.

Tests the enhanced validation, cross-reference validation, and repair functionality.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List

from agent_s3.pre_planner_json_validator import (
    PrePlannerJsonValidator,
    JSONValidationError
)


@pytest.fixture
def valid_pre_plan_data():
    """Create a valid pre-planning data structure for testing."""
    return {
        "original_request": "Implement a feature to validate JSON",
        "feature_groups": [
            {
                "group_name": "JSON Validation",
                "group_description": "Features for validating JSON data",
                "features": [
                    {
                        "name": "Schema Validation",
                        "description": "Validate JSON against a schema",
                        "files_affected": [
                            "validator.py",
                            "schema.py"
                        ],
                        "test_requirements": {
                            "unit_tests": [
                                {
                                    "description": "Test schema validation with valid data",
                                    "target_element": "SchemaValidator.validate",
                                    "target_element_id": "schema_validator_validate",
                                    "inputs": ["valid_json_data"],
                                    "expected_outcome": "Returns True"
                                }
                            ],
                            "integration_tests": []
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": []
                        },
                        "risk_assessment": {
                            "critical_files": [],
                            "potential_regressions": [],
                            "backward_compatibility_concerns": [],
                            "mitigation_strategies": [],
                            "required_test_characteristics": {
                                "required_types": [],
                                "required_keywords": [],
                                "suggested_libraries": []
                            }
                        },
                        "system_design": {
                            "overview": "Schema validation system",
                            "code_elements": [
                                {
                                    "element_type": "class",
                                    "name": "SchemaValidator",
                                    "element_id": "schema_validator_class",
                                    "signature": "class SchemaValidator:",
                                    "description": "Validates JSON against a schema",
                                    "key_attributes_or_methods": ["validate"],
                                    "target_file": "validator.py"
                                }
                            ],
                            "data_flow": "JSON input → Schema validation → Validation result",
                            "key_algorithms": ["Schema matching algorithm"]
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def invalid_pre_plan_data():
    """Create an invalid pre-planning data structure for testing."""
    return {
        "original_request": "Implement a feature to validate JSON",
        "feature_groups": [
            {
                "group_name": "JSON Validation",
                "group_description": "Features for validating JSON data",
                "features": [
                    {
                        "name": "Schema Validation",
                        "description": "Validate JSON against a schema",
                        # Missing files_affected field
                        "test_requirements": {
                            "unit_tests": [
                                {
                                    "description": "Test schema validation with valid data",
                                    "target_element": "SchemaValidator.validate",
                                    # Missing target_element_id that should match an element_id
                                    "inputs": ["valid_json_data"],
                                    "expected_outcome": "Returns True"
                                }
                            ],
                            "integration_tests": []
                        },
                        "dependencies": {
                            "internal": [],
                            "external": [],
                            "feature_dependencies": [
                                {
                                    "feature_name": "Non-existent Feature",
                                    "dependency_type": "blocks",
                                    "reason": "This feature depends on a non-existent feature"
                                }
                            ]
                        },
                        # Missing risk_assessment field
                        "system_design": {
                            "overview": "Schema validation system",
                            "code_elements": [
                                {
                                    "element_type": "class",
                                    "name": "SchemaValidator",
                                    "element_id": "schema_validator_class",
                                    "signature": "class SchemaValidator:",
                                    "description": "Validates JSON against a schema",
                                    "key_attributes_or_methods": ["validate"],
                                    "target_file": "validator.py"
                                }
                            ],
                            "data_flow": "JSON input → Schema validation → Validation result",
                            "key_algorithms": ["rm -rf / # Dangerous command"]
                        }
                    }
                ]
            }
        ]
    }


class TestPrePlannerJsonValidator:
    """Test class for PrePlannerJsonValidator."""

    def test_enhance_schema_validation_with_valid_data(self, valid_pre_plan_data):
        """Test schema validation with valid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.enhance_schema_validation(valid_pre_plan_data)
        assert is_valid is True
        assert len(errors) == 0
        assert validated_data == valid_pre_plan_data

    def test_enhance_schema_validation_with_invalid_data(self, invalid_pre_plan_data):
        """Test schema validation with invalid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.enhance_schema_validation(invalid_pre_plan_data)
        assert is_valid is False
        assert len(errors) > 0
        assert "missing required field" in errors[0].lower()
        assert validated_data == invalid_pre_plan_data

    def test_implement_cross_reference_validation_with_valid_data(self, valid_pre_plan_data):
        """Test cross-reference validation with valid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.implement_cross_reference_validation(valid_pre_plan_data)
        assert is_valid is True
        assert len(errors) == 0
        assert validated_data == valid_pre_plan_data

    def test_implement_cross_reference_validation_with_invalid_data(self, invalid_pre_plan_data):
        """Test cross-reference validation with invalid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.implement_cross_reference_validation(invalid_pre_plan_data)
        assert is_valid is False
        assert len(errors) > 0
        assert "depends on non-existent feature" in errors[0].lower() or "references non-existent" in errors[0].lower()
        assert validated_data == invalid_pre_plan_data

    def test_implement_content_validation_with_valid_data(self, valid_pre_plan_data):
        """Test content validation with valid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.implement_content_validation(valid_pre_plan_data)
        assert is_valid is True
        assert len(errors) == 0
        assert validated_data == valid_pre_plan_data

    def test_implement_content_validation_with_invalid_data(self, invalid_pre_plan_data):
        """Test content validation with invalid data that has dangerous commands."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.implement_content_validation(invalid_pre_plan_data)
        assert is_valid is False
        assert len(errors) > 0
        assert "dangerous operation" in errors[0].lower()
        assert validated_data == invalid_pre_plan_data

    def test_validate_all_with_valid_data(self, valid_pre_plan_data):
        """Test validate_all with valid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.validate_all(valid_pre_plan_data)
        assert is_valid is True
        assert len(errors) == 0
        assert validated_data == valid_pre_plan_data

    def test_validate_all_with_invalid_data(self, invalid_pre_plan_data):
        """Test validate_all with invalid data."""
        validator = PrePlannerJsonValidator()
        is_valid, errors, validated_data = validator.validate_all(invalid_pre_plan_data)
        assert is_valid is False
        assert len(errors) > 0
        assert validated_data == invalid_pre_plan_data

    def test_generate_repair_suggestions(self, invalid_pre_plan_data):
        """Test generate_repair_suggestions with invalid data."""
        validator = PrePlannerJsonValidator()
        _, errors, _ = validator.validate_all(invalid_pre_plan_data)
        suggestions = validator.generate_repair_suggestions(invalid_pre_plan_data, errors)
        assert len(suggestions) > 0
        # Check that we have suggestions for at least some of the categories
        categories_with_suggestions = 0
        for category in ["schema_structure", "reference_integrity", "content_safety", "coverage_gaps", "technical_feasibility"]:
            if category in suggestions and len(suggestions[category]) > 0:
                categories_with_suggestions += 1
        assert categories_with_suggestions > 0

    def test_repair_plan(self, invalid_pre_plan_data):
        """Test repair_plan with invalid data."""
        validator = PrePlannerJsonValidator()
        _, errors, _ = validator.validate_all(invalid_pre_plan_data)
        repaired_data, was_repaired = validator.repair_plan(invalid_pre_plan_data, errors)
        # Check that at least one repair was attempted
        assert was_repaired is True
        # Verify that the repaired data is different from the original
        assert repaired_data != invalid_pre_plan_data
        # Check if at least one of the missing fields was added
        features = repaired_data["feature_groups"][0]["features"][0]
        repairs_count = 0
        if "files_affected" in features:
            repairs_count += 1
        if "risk_assessment" in features:
            repairs_count += 1
        assert repairs_count > 0

    def test_metrics_tracking(self, valid_pre_plan_data, invalid_pre_plan_data):
        """Test that metrics are updated after validation."""
        validator = PrePlannerJsonValidator()
        # Validate both valid and invalid data to generate metrics
        validator.validate_all(valid_pre_plan_data)
        validator.validate_all(invalid_pre_plan_data)
        # Check that metrics were updated
        assert validator.validation_metrics["issues_per_plan"] > 0
        assert len(validator.validation_metrics["common_failure_patterns"]) > 0


if __name__ == "__main__":
    pytest.main(["-xvs", "test_pre_planner_json_validator.py"])
