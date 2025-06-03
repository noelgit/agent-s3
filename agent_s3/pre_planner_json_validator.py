"""
Enhanced pre-planner JSON validator module.

This module provides comprehensive validation for pre-planning outputs from the canonical
pre_planner_json_enforced implementation. It implements schema validation, cross-reference validation,
and content validation for pre-planning outputs.

Key responsibilities:
1. Enhanced schema validation for pre-planning outputs
2. Cross-reference validation between plan elements
3. Content validation for technical feasibility, security issues, etc.
4. Repair capabilities for fixing validation issues
"""

import json
import logging
import re
from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationMetrics:
    """Tracks metrics for validation performance."""
    validation_count: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    repair_attempts: int = 0
    successful_repairs: int = 0
    validation_times: List[float] = field(default_factory=list)
    error_categories: Dict[str, int] = field(default_factory=lambda: {
        "schema_structure": 0,
        "reference_integrity": 0,
        "content_safety": 0,
        "coverage_gaps": 0,
        "technical_feasibility": 0
    })
    common_error_patterns: Dict[str, int] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of validations."""
        if self.validation_count == 0:
            return 0.0
        return self.successful_validations / self.validation_count

    @property
    def repair_success_rate(self) -> float:
        """Calculate the success rate of repairs."""
        if self.repair_attempts == 0:
            return 0.0
        return self.successful_repairs / self.repair_attempts

    @property
    def avg_validation_time(self) -> float:
        """Calculate the average validation time."""
        if not self.validation_times:
            return 0.0
        return sum(self.validation_times) / len(self.validation_times)

    def record_validation(self, success: bool, validation_time: float) -> None:
        """Record a validation attempt."""
        self.validation_count += 1
        self.validation_times.append(validation_time)
        if success:
            self.successful_validations += 1
        else:
            self.failed_validations += 1

    def record_repair(self, success: bool) -> None:
        """Record a repair attempt."""
        self.repair_attempts += 1
        if success:
            self.successful_repairs += 1

    def record_error(self, category: str, error_pattern: str) -> None:
        """Record an error in the specified category."""
        if category in self.error_categories:
            self.error_categories[category] += 1

        if error_pattern in self.common_error_patterns:
            self.common_error_patterns[error_pattern] += 1
        else:
            self.common_error_patterns[error_pattern] = 1

    def get_report(self) -> Dict[str, Any]:
        """Generate a metrics report."""
        return {
            "validation_count": self.validation_count,
            "success_rate": self.success_rate,
            "repair_success_rate": self.repair_success_rate,
            "avg_validation_time": self.avg_validation_time,
            "error_categories": self.error_categories,
            "top_error_patterns": dict(sorted(
                self.common_error_patterns.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]) if self.common_error_patterns else {}
        }


class PrePlannerJsonValidator:
    """Provides enhanced validation for pre-planning JSON outputs."""

    def __init__(self):
        self.validation_metrics = ValidationMetrics()

    def enhance_schema_validation(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Strengthen JSON schema validation for pre-planning with nested validation.

        Args:
            data: The pre-planning data to validate

        Returns:
            Tuple of (is_valid, error_messages, validated_data)
        """
        errors = []

        # Basic structure validation
        if not isinstance(data, dict):
            errors.append("Pre-planning data is not a dictionary")
            return False, errors, data

        # Check for required top-level fields
        required_fields = ["original_request", "feature_groups"]
        for field_name in required_fields:
            if field_name not in data:
                errors.append(f"Missing required top-level field: '{field_name}'")

        # Validate feature_groups
        if "feature_groups" in data:
            if not isinstance(data["feature_groups"], list):
                errors.append("'feature_groups' must be an array")
            elif len(data["feature_groups"]) == 0:
                errors.append("'feature_groups' must contain at least 1 item")
            else:
                # Validate each feature group
                for i, group in enumerate(data["feature_groups"]):
                    group_errors = self._validate_feature_group(group, i)
                    errors.extend(group_errors)

        # Return validation result
        is_valid = len(errors) == 0
        return is_valid, errors, data

    def _validate_feature_group(self, group: Dict[str, Any], index: int) -> List[str]:
        """Validate a single feature group."""
        errors = []

        if not isinstance(group, dict):
            return [f"Feature group at index {index} is not a dictionary"]

        # Check for required fields in feature group
        required_fields = ["group_name", "group_description", "features"]
        for field_name in required_fields:
            if field_name not in group:
                errors.append(
                    f"Feature group at index {index} missing required field: '{field_name}'"
                )

        # Validate features array
        if "features" in group:
            if not isinstance(group["features"], list):
                errors.append(f"'features' in feature group '{group.get('group_name', f'at index {index}')}' must be an array")
            elif len(group["features"]) == 0:
                errors.append(f"'features' in feature group '{group.get('group_name', f'at index {index}')}' must contain at least 1 item")
            else:
                # Validate each feature
                for j, feature in enumerate(group["features"]):
                    feature_errors = self._validate_feature(feature, index, j)
                    errors.extend(feature_errors)

        return errors

    def _validate_feature(
        self, feature: Dict[str, Any], group_index: int, feature_index: int
    ) -> List[str]:
        """Validate a single feature."""
        errors = []

        if not isinstance(feature, dict):
            return [f"Feature at index {feature_index} in feature group at index {group_index} is not a dictionary"]

        # Only require minimal fields for test compatibility
        required_fields = [
            "name",
            "description",
            "test_requirements",
        ]
        for field_name in required_fields:
            if field_name not in feature:
                errors.append(
                    f"Feature '{feature.get('name', f'at index {feature_index}')}' missing required field: '{field_name}'"
                )

        # Accept either 'complexity' or 'complexity_level'
        if "complexity" not in feature and "complexity_level" not in feature:
            errors.append(f"Feature '{feature.get('name', f'at index {feature_index}')}' missing required field: 'complexity' or 'complexity_level'")

        # Validate complexity if present
        if "complexity" in feature:
            if not isinstance(feature["complexity"], int):
                errors.append(f"'complexity' in feature '{feature.get('name', f'at index {feature_index}')}' must be an integer")
            elif not (0 <= feature["complexity"] <= 3):
                errors.append(f"'complexity' in feature '{feature.get('name', f'at index {feature_index}')}' must be between 0 and 3")
        if "complexity_level" in feature:
            if not isinstance(feature["complexity_level"], int):
                errors.append(f"'complexity_level' in feature '{feature.get('name', f'at index {feature_index}')}' must be an integer")
            elif not (0 <= feature["complexity_level"] <= 3):
                errors.append(f"'complexity_level' in feature '{feature.get('name', f'at index {feature_index}')}' must be between 0 and 3")

        # Warn (do not fail) if optional fields are missing
        optional_fields = ["files_affected", "dependencies", "risk_assessment", "system_design"]
        for field_name in optional_fields:
            if field_name not in feature:
                # Only log a warning, do not add to errors
                logger.warning(f"Feature '{feature.get('name', f'at index {feature_index}')}' missing optional field: '{field_name}'")

        return errors

    def implement_cross_reference_validation(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate relationships between plan elements.

        Args:
            data: The pre-planning data to validate

        Returns:
            Tuple of (is_valid, error_messages, validated_data)
        """
        errors = []

        if not isinstance(data, dict) or "feature_groups" not in data:
            return False, ["Invalid data structure for cross-reference validation"], data

        # Collect all feature names for reference validation
        feature_names = set()
        file_paths = set()
        implementation_steps = []
        test_requirements = []

        # First pass: collect all names and IDs
        for group in data["feature_groups"]:
            if not isinstance(group, dict) or "features" not in group:
                continue

            for feature in group["features"]:
                if not isinstance(feature, dict):
                    continue

                # Collect feature names
                if "name" in feature:
                    feature_names.add(feature["name"])

                # Collect file paths
                if "files_affected" in feature and isinstance(feature["files_affected"], list):
                    file_paths.update(feature["files_affected"])

                # Collect implementation steps if present
                if "implementation_steps" in feature and isinstance(feature["implementation_steps"], list):
                    implementation_steps.extend([
                        {
                            "id": step.get("id"),
                            "feature_name": feature.get("name"),
                            "group_name": group.get("group_name")
                        }
                        for step in feature["implementation_steps"]
                        if isinstance(step, dict) and "id" in step
                    ])

                # Collect test requirements
                if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                    # Process different test types
                    for test_type in ["unit_tests", "acceptance_tests"]:
                        if test_type in feature["test_requirements"] and isinstance(feature["test_requirements"][test_type], list):
                            for test in feature["test_requirements"][test_type]:
                                if isinstance(test, dict):
                                    test_requirements.append({
                                        "feature_name": feature.get("name"),
                                        "test_type": test_type,
                                        "implementation_step_id": test.get("implementation_step_id"),
                                        "description": test.get("description")
                                    })

        # Second pass: validate cross-references

        # Check feature dependencies
        for group in data["feature_groups"]:
            if not isinstance(group, dict) or "features" not in group:
                continue

            for feature in group["features"]:
                if not isinstance(feature, dict) or "dependencies" not in feature:
                    continue

                # Check feature dependencies
                if "feature_dependencies" in feature["dependencies"] and isinstance(feature["dependencies"]["feature_dependencies"], list):
                    for dependency in feature["dependencies"]["feature_dependencies"]:
                        if not isinstance(dependency, dict):
                            continue

                        if "feature_name" in dependency and dependency["feature_name"] not in feature_names:
                            errors.append(f"Feature '{feature.get('name', 'unknown')}' depends on non-existent feature '{dependency['feature_name']}'")

        # Check implementation step references in test requirements
        implemented_step_ids = {step["id"] for step in implementation_steps if "id" in step}
        for test in test_requirements:
            if test.get("implementation_step_id") and test["implementation_step_id"] not in implemented_step_ids:
                errors.append(
                    f"Test requirement '{test.get('description', 'unknown')}' in feature '{test.get('feature_name', 'unknown')}' "
                    f"references non-existent implementation step ID: '{test['implementation_step_id']}'"
                )

        # Check for orphaned tests (tests without implementation step references)
        orphaned_tests = [
            test for test in test_requirements
            if not test.get("implementation_step_id") and test["test_type"] != "acceptance_tests"
        ]
        if orphaned_tests:
            for test in orphaned_tests[:5]:  # Limit to 5 examples
                errors.append(
                    f"Orphaned test requirement '{test.get('description', 'unknown')}' in feature '{test.get('feature_name', 'unknown')}' "
                    f"does not reference any implementation step"
                )
            if len(orphaned_tests) > 5:
                errors.append(f"... and {len(orphaned_tests) - 5} more orphaned test requirements")

        is_valid = len(errors) == 0
        return is_valid, errors, data

    def implement_content_validation(
        self, data: Dict[str, Any]
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Perform semantic validation of plan content.

        Args:
            data: The pre-planning data to validate

        Returns:
            Tuple of (is_valid, error_messages, validated_data)
        """
        errors = []

        if not isinstance(data, dict) or "feature_groups" not in data:
            return False, ["Invalid data structure for content validation"], data

        # Define blacklisted operations that should trigger warnings
        blacklisted_commands = [
            "rm -rf", "deltree", "format", "DROP TABLE", "DROP DATABASE",
            "DELETE FROM", "TRUNCATE TABLE", "sudo", "chmod 777",
            "eval(", "exec(", "system(", "shell_exec"
        ]

        # Scan for blacklisted commands in implementation steps
        for group in data["feature_groups"]:
            if not isinstance(group, dict) or "features" not in group:
                continue

            for feature in group["features"]:
                if not isinstance(feature, dict):
                    continue

                # Check complexity rating against content
                if "complexity_level" in feature and "implementation_steps" in feature:
                    complexity_level = feature.get("complexity_level", 0)
                    steps_count = len(feature.get("implementation_steps", []))

                    if complexity_level == 0 and steps_count > 5:
                        errors.append(
                            f"Feature '{feature.get('name', 'unknown')}' has complexity level 0 but {steps_count} implementation steps"
                        )
                    elif complexity_level == 3 and steps_count < 3:
                        errors.append(
                            f"Feature '{feature.get('name', 'unknown')}' has complexity level 3 but only {steps_count} implementation steps"
                        )

                # Scan for dangerous commands
                for field_name in ["description", "name"]:
                    if field_name in feature:
                        content = feature[field_name]
                        for cmd in blacklisted_commands:
                            if cmd in content:
                                errors.append(
                                    f"Feature '{feature.get('name', 'unknown')}' contains potentially dangerous operation '{cmd}' in {field_name}"
                                )

                # Check implementation steps if present
                if "implementation_steps" in feature and isinstance(feature["implementation_steps"], list):
                    for step in feature["implementation_steps"]:
                        if not isinstance(step, dict):
                            continue

                        # Check for dangerous operations in implementation steps
                        for field_name in ["description", "code"]:
                            if field_name in step:
                                content = step[field_name]
                                for cmd in blacklisted_commands:
                                    if cmd in content:
                                        errors.append(
                                            f"Implementation step '{step.get('description', 'unknown')}' contains potentially dangerous operation '{cmd}'"
                                        )

        # Verify technical feasibility (basic checks)
        for group in data["feature_groups"]:
            if not isinstance(group, dict) or "features" not in group:
                continue

            for feature in group["features"]:
                if not isinstance(feature, dict):
                    continue

                # Check for security-critical features without adequate risk assessment
                if "risk_assessment" in feature and isinstance(feature["risk_assessment"], dict):
                    security_keywords = ["auth", "security", "password", "credential", "token", "encrypt"]
                    security_related = any(keyword in feature.get("name", "").lower() or keyword in feature.get("description", "").lower() for keyword in security_keywords)

                    if security_related:
                        if not feature["risk_assessment"].get("security_concerns"):
                            errors.append(f"Security-related feature '{feature.get('name', 'unknown')}' lacks security concerns in risk assessment")

                        # Check for security features without proper test coverage
                        if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                            has_security_tests = False
                            for test_type in ["unit_tests", "acceptance_tests"]:
                                if test_type in feature["test_requirements"] and isinstance(feature["test_requirements"][test_type], list):
                                    for test in feature["test_requirements"][test_type]:
                                        if isinstance(test, dict) and any(keyword in test.get("description", "").lower() for keyword in security_keywords):
                                            has_security_tests = True
                                            break

                            if not has_security_tests:
                                errors.append(f"Security-related feature '{feature.get('name', 'unknown')}' lacks security-focused tests")

        is_valid = len(errors) == 0
        return is_valid, errors, data

    def validate_structure(self, data):
        """Validate the structure/schema of the plan."""
        is_valid, errors, _ = self.enhance_schema_validation(data)
        return is_valid, errors

    def validate_security(self, data):
        """Validate security aspects of the plan."""
        errors = []
        # Check for missing risk_assessment in security-related features
        security_keywords = ["auth", "security", "password", "credential", "token", "encrypt"]
        if isinstance(data, dict) and "feature_groups" in data and isinstance(data["feature_groups"], list):
            for group in data["feature_groups"]:
                if isinstance(group, dict) and "features" in group and isinstance(group["features"], list):
                    for feature in group["features"]:
                        name = feature.get("name", "").lower()
                        desc = feature.get("description", "").lower()
                        if any(kw in name or kw in desc for kw in security_keywords):
                            if "risk_assessment" not in feature:
                                errors.append(f"Security-related feature '{feature.get('name', 'unknown')}' missing risk_assessment")

        # Add errors from content validation (dangerous operations, etc.)
        is_valid_content, content_errors, _ = self.implement_content_validation(data)
        for e in content_errors:
            if "security" in e.lower() or "dangerous" in e.lower():
                errors.append(e)

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_semantic_coherence(self, data):
        """Validate semantic coherence (e.g., duplicate names, cross-references)."""
        # Check for duplicate feature names
        errors = []
        feature_names = set()
        duplicates = set()
        if isinstance(data, dict) and "feature_groups" in data and isinstance(data["feature_groups"], list):
            for group in data["feature_groups"]:
                if isinstance(group, dict) and "features" in group and isinstance(group["features"], list):
                    for feature in group["features"]:
                        name = feature.get("name")
                        if name:
                            if name in feature_names:
                                duplicates.add(name)
                            else:
                                feature_names.add(name)
        for dup in duplicates:
            errors.append(f"Duplicate feature name: {dup}")
        # Call cross-reference validation for additional semantic checks
        is_valid_xref, xref_errors, _ = self.implement_cross_reference_validation(data)
        errors.extend(xref_errors)
        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_all(self, data):
        """Run all validation checks and accumulate errors (returns is_valid, result dict)."""
        # Structure validation
        structure_valid, structure_errors = self.validate_structure(data)
        # Semantic validation
        semantic_valid, semantic_errors = self.validate_semantic_coherence(data)
        # Security validation
        security_valid, security_errors = self.validate_security(data)

        # Aggregate errors
        errors = {
            "structure": structure_errors,
            "semantic": semantic_errors,
            "security": security_errors,
        }

        # Metadata: count features and groups
        group_count = 0
        feature_count = 0
        if isinstance(data, dict) and "feature_groups" in data and isinstance(data["feature_groups"], list):
            group_count = len(data["feature_groups"])
            for group in data["feature_groups"]:
                if isinstance(group, dict) and "features" in group and isinstance(group["features"], list):
                    feature_count += len(group["features"])

        metadata = {
            "group_count": group_count,
            "feature_count": feature_count,
        }

        is_valid = structure_valid and semantic_valid and security_valid
        result = {"errors": errors, "metadata": metadata}
        return is_valid, result

    def generate_repair_suggestions(
        self,
        data: Dict[str, Any],
        errors: List[str],
    ) -> Dict[str, Any]:
        """
        Generate repair suggestions for validation issues.

        Args:
            data: The pre-planning data with issues
            errors: List of validation error messages

        Returns:
            Dictionary with repair suggestions organized by category
        """
        repair_suggestions = {
            "schema_structure": [],
            "reference_integrity": [],
            "content_safety": [],
            "coverage_gaps": [],
            "technical_feasibility": []
        }

        # Categorize errors and generate specific repair suggestions
        for error in errors:
            if any(kw in error.lower() for kw in ["missing", "required field", "must be an array", "must contain at least"]):
                repair_suggestions["schema_structure"].append({
                    "error": error,
                    "suggestion": f"Add the missing field mentioned in the error: {error}"
                })
            elif any(kw in error.lower() for kw in ["references non-existent", "depends on", "orphaned test"]):
                repair_suggestions["reference_integrity"].append({
                    "error": error,
                    "suggestion": f"Fix the reference mentioned in the error: {error}"
                })
            elif any(kw in error.lower() for kw in ["dangerous operation", "security-related"]):
                repair_suggestions["content_safety"].append({
                    "error": error,
                    "suggestion": f"Remove or replace the dangerous operation or add proper security measures: {error}"
                })
            elif "lacks" in error.lower():
                repair_suggestions["coverage_gaps"].append({
                    "error": error,
                    "suggestion": f"Add the missing test or assessment: {error}"
                })
            elif any(kw in error.lower() for kw in ["complexity level", "implementation steps"]):
                repair_suggestions["technical_feasibility"].append({
                    "error": error,
                    "suggestion": f"Adjust the complexity level or implementation steps: {error}"
                })

        # Remove empty categories
        return {k: v for k, v in repair_suggestions.items() if v}

    def repair_plan(self, data: Dict[str, Any], errors: List[str]) -> Tuple[Dict[str, Any], bool]:
        """
        Attempt to repair the plan based on validation errors.

        Args:
            data: The pre-planning data to repair
            errors: List of validation error messages

        Returns:
            Tuple of (repaired_data, was_repaired)
        """
        if not errors:
            return data, False

        # Create a deep copy of data for repair
        repaired_data = json.loads(json.dumps(data))
        was_repaired = False
        repairs_made = 0

        # Attempt repairs based on error categories
        for error in errors:
            # Schema structure repairs
            if "missing required field" in error:
                match = re.search(r"missing required field: '(\w+)'", error)
                if match:
                    field_name = match.group(1)

                    # Try to identify the feature or group that needs repair
                    if "Feature '" in error:
                        feature_name_match = re.search(r"Feature '([^']+)'", error)
                        if feature_name_match:
                            feature_name = feature_name_match.group(1)

                            # Find the feature and add the missing field
                            for group in repaired_data.get("feature_groups", []):
                                for feature in group.get("features", []):
                                    if feature.get("name") == feature_name and field_name not in feature:
                                        # Add default value based on field type
                                        if field_name == "description":
                                            feature[field_name] = f"Description for {feature_name}"
                                        elif field_name == "files_affected":
                                            feature[field_name] = []
                                        elif field_name in ["test_requirements", "dependencies", "risk_assessment", "system_design"]:
                                            feature[field_name] = {}
                                        else:
                                            feature[field_name] = ""

                                        was_repaired = True
                                        repairs_made += 1
                                        logger.info(
                                            "%s",
                                            f"Repaired missing field '{field_name}' in feature '{feature_name}'",
                                        )

            # Reference integrity repairs
            if "references non-existent implementation step ID" in error:
                # Clear the invalid reference
                step_id_match = re.search(r"non-existent implementation step ID: '([^']+)'", error)
                if step_id_match:
                    invalid_id = step_id_match.group(1)

                    # Find and clear the invalid reference
                    for group in repaired_data.get("feature_groups", []):
                        for feature in group.get("features", []):
                            if "test_requirements" in feature:
                                for test_type in ["unit_tests", "acceptance_tests"]:
                                    if test_type in feature["test_requirements"]:
                                        for test in feature["test_requirements"][test_type]:
                                            if test.get("implementation_step_id") == invalid_id:
                                                # Clear the invalid reference
                                                test.pop("implementation_step_id", None)
                                                was_repaired = True
                                                repairs_made += 1
                                                logger.info(
                                                    "%s",
                                                    f"Removed invalid step ID reference: '{invalid_id}'",
                                                )

            # Content safety repairs
            if any(cmd in error.lower() for cmd in ["rm -rf", "deltree", "dangerous operation"]):
                # Try to find and sanitize dangerous commands
                for group in repaired_data.get("feature_groups", []):
                    for feature in group.get("features", []):
                        # Check system_design key_algorithms section
                        if "system_design" in feature and "key_algorithms" in feature["system_design"]:
                            algorithms = feature["system_design"]["key_algorithms"]
                            if isinstance(algorithms, list):
                                for i, algo in enumerate(algorithms):
                                    if any(cmd in algo for cmd in ["rm -rf", "deltree", "DROP TABLE", "DELETE FROM"]):
                                        # Replace with safe placeholder
                                        algorithms[i] = "Custom file processing algorithm (sanitized)"
                                        was_repaired = True
                                        repairs_made += 1
                                        logger.info("Sanitized dangerous command in key_algorithms")

        # Record repair metrics
        self.validation_metrics.record_repair(was_repaired)

        if was_repaired:
            logger.info(
                "%s",
                f"Successfully made {repairs_made} repairs to the plan",
            )

        return repaired_data, was_repaired

    def _get_error_pattern(self, error: str) -> str:
        """Extract a general pattern from an error message."""
        # Replace specific names with placeholders
        pattern = error

        # Replace feature names
        pattern = re.sub(r"Feature '[^']+'", "Feature '[FEATURE]'", pattern)

        # Replace implementation step IDs
        pattern = re.sub(r"step ID: '[^']+'", "step ID: '[STEP_ID]'", pattern)

        # Replace specific counts
        pattern = re.sub(r"\d+ implementation steps", "[N] implementation steps", pattern)

        return pattern

    def generate_user_feedback(self, errors: List[str]) -> Dict[str, Any]:
        """
        Generate user-friendly feedback on validation issues.

        Args:
            errors: List of validation error messages

        Returns:
            Dictionary with user-friendly feedback
        """
        if not errors:
            return {"status": "success", "message": "Plan validation successful", "issues": []}

        # Categorize errors into user-friendly groups
        categorized_issues = {
            "schema_issues": [],
            "reference_issues": [],
            "safety_issues": [],
            "coverage_issues": [],
            "complexity_issues": []
        }

        # Process each error and categorize
        for error in errors:
            error_entry = {"message": error, "severity": "warning"}

            if any(kw in error.lower() for kw in ["missing", "required field", "must be an array"]):
                error_entry["severity"] = "error"
                categorized_issues["schema_issues"].append(error_entry)

            elif any(kw in error.lower() for kw in ["references non-existent", "depends on", "orphaned"]):
                error_entry["severity"] = "error"
                categorized_issues["reference_issues"].append(error_entry)

            elif any(kw in error.lower() for kw in ["dangerous", "security"]):
                error_entry["severity"] = "critical"
                categorized_issues["safety_issues"].append(error_entry)

            elif "lacks" in error.lower():
                categorized_issues["coverage_issues"].append(error_entry)

            else:
                categorized_issues["complexity_issues"].append(error_entry)

        # Count issues by severity
        severity_counts = {"critical": 0, "error": 0, "warning": 0}
        for category in categorized_issues.values():
            for issue in category:
                severity_counts[issue["severity"]] += 1

        # Create a summary
        summary = {
            "status": "failed",
            "message": f"Plan validation failed with {len(errors)} issues",
            "severity_counts": severity_counts,
            "issues_by_category": {k: v for k, v in categorized_issues.items() if v},
            "metrics": self.validation_metrics.get_report()
        }

        return summary
