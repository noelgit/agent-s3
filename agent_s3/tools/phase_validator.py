"""Cross-phase validator to ensure consistency across workflow phases.

This module provides validation functions to check for consistency between:
- Pre-planning and planning phases
- Architecture and implementation
- Test coverage and risk assessment
- User modifications and existing plans
"""

import os
import logging
from typing import Dict, List, Any, Tuple, Optional
import re

logger = logging.getLogger(__name__)


def validate_phase_transition(pre_plan_data: Dict[str, Any], feature_group: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate the transition from pre-planning to planning phase.

    Checks if feature group is consistent with pre-planning constraints.

    Args:
        pre_plan_data: The pre-planning data containing constraints
        feature_group: The feature group to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Initialize validation state
    is_valid = True
    error_messages = []

    # Check if feature group has required fields
    required_fields = ["group_name", "group_description", "features"]
    missing_fields = [field for field in required_fields if field not in feature_group]

    if missing_fields:
        error_messages.append(f"Missing required fields in feature group: {', '.join(missing_fields)}")
        is_valid = False

    # Check features list is not empty
    if "features" in feature_group and not feature_group["features"]:
        error_messages.append("Feature group has empty features list")
        is_valid = False

    # Validate against technical constraints
    if "technical_constraints" in pre_plan_data:
        tech_constraints = pre_plan_data["technical_constraints"]

        # Check file exclusions
        if "file_exclusions" in tech_constraints and "features" in feature_group:
            excluded_patterns = tech_constraints["file_exclusions"]

            for feature in feature_group["features"]:
                if "files_affected" in feature:
                    for file_path in feature["files_affected"]:
                        for pattern in excluded_patterns:
                            if re.search(pattern, file_path):
                                error_messages.append(
                                    f"Feature {feature.get('name', 'Unknown')} affects excluded file: {file_path} (matches pattern: {pattern})"
                                )
                                is_valid = False

    # Validate file references if files_affected are present
    for feature in feature_group.get("features", []):
        for file_path in feature.get("files_affected", []):
            # Skip files with wildcards or common new file patterns
            if "*" in file_path or "?" in file_path:
                continue
            if any(pattern in file_path.lower() for pattern in ["new_", "to_be_created", "create_"]):
                continue

            # Check if file exists (can't do actual validation here since we don't have file_tool)
            # This will be done in the coordinator when this function is called

    # Return validation result
    return is_valid, "; ".join(error_messages) if error_messages else "Valid"


def validate_user_modifications(modification_text: str, plan: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """Validate user modifications to ensure they don't invalidate the existing plan.

    Args:
        modification_text: The user's modification text
        plan: Optional dictionary of the existing plan. When provided, referenced
            features and files in ``modification_text`` are checked against this
            plan to ensure the modification targets valid items.

    Returns:
        Tuple of ``(is_valid, error_message)`` summarizing the validation result.
    """
    # Initialize validation state
    is_valid = True
    error_messages = []

    # Check for problematic patterns in modification text
    problematic_patterns = [
        (r"remove all", "Modification suggests removing everything"),
        (r"delete (everything|all)", "Modification suggests deleting everything"),
        (r"start over", "Modification suggests starting over"),
        (r"redo (everything|all|the plan)", "Modification suggests redoing everything"),
        (r"completely change", "Modification suggests completely changing the plan")
    ]

    for pattern, error_msg in problematic_patterns:
        if re.search(pattern, modification_text, re.IGNORECASE):
            error_messages.append(error_msg)
            is_valid = False

    # Detect references to unknown features
    unknown_feature_match = re.search(
        r"unknown feature ([^\n\.\!\?]+)", modification_text, re.IGNORECASE
    )
    if unknown_feature_match:
        feature_name = unknown_feature_match.group(1).strip()
        error_messages.append(f"Unknown feature: {feature_name}")
        is_valid = False

    # Check if modification text is too short or empty
    if len(modification_text.strip()) < 5:
        error_messages.append("Modification text is too short or empty")
        is_valid = False

    # Return validation result
    return is_valid, "; ".join(error_messages) if error_messages else "Valid"


def validate_architecture_implementation(architecture_review: Dict[str, Any],
                                        implementation_plan: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate that implementation components align with architecture design.

    Args:
        architecture_review: The architecture review data
        implementation_plan: The implementation plan data

    Returns:
        Tuple of (is_valid, error_message, validation_details)
    """
    # Initialize validation state
    is_valid = True
    error_messages = []
    validation_details = {
        "unaddressed_gaps": [],
        "unaddressed_optimizations": [],
        "missing_components": []
    }

    # Check if logical gaps are addressed in implementation
    logical_gaps = architecture_review.get("logical_gaps", [])
    for gap in logical_gaps:
        # Extract affected components from logical gap
        affected_components = gap.get("affected_components", [])

        # Check if those components appear in implementation plan
        gap_addressed = False
        for component in affected_components:
            # Check if component is a file path
            if os.path.basename(component) in [os.path.basename(file) for file in implementation_plan.keys()]:
                gap_addressed = True
                break

        if not gap_addressed and affected_components:
            validation_details["unaddressed_gaps"].append({
                "description": gap.get("description", "Unknown gap"),
                "affected_components": affected_components
            })
            error_messages.append(f"Logical gap not addressed: {gap.get('description', 'Unknown gap')}")
            is_valid = False

    # Check if optimization suggestions are incorporated
    optimization_suggestions = architecture_review.get("optimization_suggestions", [])
    for suggestion in optimization_suggestions:
        # Extract affected components from suggestion
        affected_components = suggestion.get("affected_components", [])

        # Precompute keywords outside the loop so they're always defined
        suggestion_keywords = _extract_keywords(suggestion.get("description", ""))

        # Check if those components appear in implementation plan with the optimization
        suggestion_addressed = False
        for component in affected_components:
            # Check if component is a file path
            if os.path.basename(component) in [os.path.basename(file) for file in implementation_plan.keys()]:
                # Look for keywords from suggestion in implementation steps
                for file_path, implementations in implementation_plan.items():
                    if os.path.basename(component) == os.path.basename(file_path):
                        for impl in implementations:
                            steps_text = " ".join(impl.get("steps", []))
                            if any(keyword in steps_text.lower() for keyword in suggestion_keywords):
                                suggestion_addressed = True
                                break

            if suggestion_addressed:
                break

        if not suggestion_addressed and affected_components and suggestion_keywords:
            validation_details["unaddressed_optimizations"].append({
                "description": suggestion.get("description", "Unknown suggestion"),
                "affected_components": affected_components
            })
            error_messages.append(f"Optimization not incorporated: {suggestion.get('description', 'Unknown suggestion')}")
            is_valid = False

    # Check for components in architecture review but missing in implementation
    all_components = set()
    for gap in logical_gaps:
        all_components.update(gap.get("affected_components", []))
    for suggestion in optimization_suggestions:
        all_components.update(suggestion.get("affected_components", []))

    # Filter actual file paths (not feature names)
    file_components = {c for c in all_components if os.path.basename(c) != c}
    implemented_files = {os.path.basename(f) for f in implementation_plan.keys()}

    missing_components = []
    for component in file_components:
        base_name = os.path.basename(component)
        if base_name not in implemented_files:
            missing_components.append(component)

    if missing_components:
        validation_details["missing_components"] = missing_components
        error_messages.append(f"Components mentioned in architecture but missing in implementation: {', '.join(missing_components)}")
        is_valid = False

    # Return validation result
    return is_valid, "; ".join(error_messages) if error_messages else "Valid", validation_details


def validate_test_coverage_against_risk(tests: Dict[str, Any], risk_assessment: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate that tests provide adequate coverage for identified risks.

    Args:
        tests: The test plan data
        risk_assessment: The risk assessment data

    Returns:
        Tuple of (is_valid, error_message, validation_details)
    """
    # Initialize validation state
    is_valid = True
    error_messages = []
    validation_details = {
        "uncovered_critical_files": [],
        "uncovered_high_risk_areas": [],
        "missing_required_types": [],
        "missing_required_keywords": [],
        "missing_suggested_libraries": [],
        "total_risk_areas": 0,
        "covered_risk_areas": 0
    }

    # Extract critical files from risk assessment
    critical_files = risk_assessment.get("critical_files", [])
    high_risk_areas = risk_assessment.get("high_risk_areas", [])

    validation_details["total_risk_areas"] = len(high_risk_areas)

    # Check if critical files are tested
    all_test_files = set()
    for test_type, test_list in tests.items():
        for test in test_list:
            if "implementation_file" in test:
                all_test_files.add(test["implementation_file"])

    # Find critical files without tests
    uncovered_critical = []
    for critical_file in critical_files:
        if critical_file not in all_test_files:
            uncovered_critical.append(critical_file)

    if uncovered_critical:
        validation_details["uncovered_critical_files"] = uncovered_critical
        error_messages.append(f"Critical files without tests: {', '.join(uncovered_critical)}")
        is_valid = False

    # Check high risk areas coverage
    covered_risk_areas = []
    uncovered_risk_areas = []

    for risk_area in high_risk_areas:
        area_name = risk_area.get("name", "Unknown risk area")
        area_components = risk_area.get("components", [])

        # Check if any components are tested
        area_covered = False
        for component in area_components:
            if component in all_test_files:
                area_covered = True
                covered_risk_areas.append(area_name)
                break

        if not area_covered:
            uncovered_risk_areas.append({
                "name": area_name,
                "components": area_components
            })

    validation_details["covered_risk_areas"] = len(covered_risk_areas)

    if uncovered_risk_areas:
        validation_details["uncovered_high_risk_areas"] = uncovered_risk_areas
        error_messages.append(f"High risk areas without test coverage: {', '.join([area['name'] for area in uncovered_risk_areas])}")
        is_valid = False

    # Check test types coverage relative to risk assessment
    property_based_needed = "edge_cases" in risk_assessment and risk_assessment["edge_cases"]
    if property_based_needed and not tests.get("property_based_tests", []):
        error_messages.append("Risk assessment indicates edge cases, but no property-based tests found")
        is_valid = False


    # Check required test characteristics if present
    required_test_characteristics = risk_assessment.get("required_test_characteristics", {})
    if required_test_characteristics:
        # 1. Check for required test types
        required_types = required_test_characteristics.get("required_types", [])
        if required_types:
            # For each required type, check if it exists in the tests
            missing_types = []
            for req_type in required_types:
                # Supported core test types: unit, property-based, acceptance
                # Security and performance tests must be represented as unit tests
                if req_type in ["security", "security_tests", "performance", "performance_tests"]:
                    # Map security and performance to their corresponding core types
                    if req_type.startswith("security"):
                        # Check if any tests address security concerns
                        security_concern_addressed = False
                        for test_list in tests.values():
                            for test in test_list:
                                if "security" in test.get("description", "").lower() or "security" in test.get("test_name", "").lower():
                                    security_concern_addressed = True
                                    break
                            if security_concern_addressed:
                                break
                        if not security_concern_addressed:
                            missing_types.append("security_tests")
                    elif req_type.startswith("performance"):
                        # Check if any tests address performance concerns
                        performance_concern_addressed = False
                        for test_list in tests.values():
                            for test in test_list:
                                if "performance" in test.get("description", "").lower() or "performance" in test.get("test_name", "").lower():
                                    performance_concern_addressed = True
                                    break
                            if performance_concern_addressed:
                                break
                        if not performance_concern_addressed:
                            missing_types.append("performance_tests")
                else:
                    # Normalize type name for the core test types
                    normalized_type = f"{req_type}_tests" if not req_type.endswith("_tests") else req_type

                    # Check if we have this test type
                    if not tests.get(normalized_type, []):
                        missing_types.append(req_type)

            if missing_types:
                validation_details["missing_required_types"] = missing_types
                error_messages.append(f"Missing required test types: {', '.join(missing_types)}")
                is_valid = False

        # 2. Check for required keywords in test names/descriptions
        required_keywords = required_test_characteristics.get("required_keywords", [])
        if required_keywords:
            # For each required keyword, check if it appears in any test name or description
            missing_keywords = []
            for keyword in required_keywords:
                keyword_found = False

                # Check across all test types
                for test_type, test_list in tests.items():
                    for test in test_list:
                        # Look in test_name, description or test code
                        test_name = test.get("test_name", "").lower()
                        description = test.get("description", "").lower()
                        code = test.get("code", "").lower()

                        if (keyword.lower() in test_name or
                            keyword.lower() in description or
                            keyword.lower() in code):
                            keyword_found = True
                            break

                    if keyword_found:
                        break

                if not keyword_found:
                    missing_keywords.append(keyword)

            if missing_keywords:
                validation_details["missing_required_keywords"] = missing_keywords
                error_messages.append(f"Missing required test keywords: {', '.join(missing_keywords)}")
                is_valid = False

        # 3. Check for suggested libraries (if we have import/library information)
        suggested_libraries = required_test_characteristics.get("suggested_libraries", [])
        if suggested_libraries:
            missing_libraries = []
            for library in suggested_libraries:
                library_found = False

                # Look for library references across all tests
                for test_type, test_list in tests.items():
                    for test in test_list:
                        # Check in test code if available
                        code = test.get("code", "").lower()
                        setup = test.get("setup_requirements", "").lower()

                        if (f"import {library.lower()}" in code or
                            library.lower() in setup or
                            f"from {library.lower()}" in code):
                            library_found = True
                            break

                    if library_found:
                        break

                if not library_found:
                    missing_libraries.append(library)

            if missing_libraries:
                validation_details["missing_suggested_libraries"] = missing_libraries
                error_messages.append(f"Missing suggested test libraries: {', '.join(missing_libraries)}")
                is_valid = False

    # Return validation result
    return is_valid, "; ".join(error_messages) if error_messages else "Valid", validation_details


def validate_security_concerns(architecture_review: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate that security concerns in architecture review are properly addressed.

    Args:
        architecture_review: The architecture review data

    Returns:
        Tuple of (is_valid, error_message, validation_details)
    """
    # Initialize validation state
    is_valid = True
    error_messages = []
    validation_details = {
        "missing_critical_security_aspects": [],
        "incomplete_security_concerns": [],
        "severity_issues": [],
        "total_security_concerns": 0,
        "properly_documented_concerns": 0
    }

    # Common OWASP Top 10 and other security concerns that should be considered
    common_security_aspects = [
        {"name": "Authentication", "keywords": ["auth", "login", "credentials", "password", "jwt", "token"]},
        {"name": "Authorization", "keywords": ["permission", "access control", "rbac", "acl", "privilege"]},
        {"name": "Data Validation", "keywords": ["input", "validation", "sanitize", "escape", "filter"]},
        {"name": "Injection Protection", "keywords": ["sql", "injection", "xss", "script", "sanitize", "escape"]},
        {"name": "Sensitive Data Exposure", "keywords": ["encrypt", "sensitive", "pii", "personal", "data", "leak"]},
        {"name": "CSRF Protection", "keywords": ["csrf", "forgery", "cross-site", "token"]},
        {"name": "Security Headers", "keywords": ["headers", "csp", "content-security", "hsts"]},
        {"name": "Session Management", "keywords": ["session", "cookie", "token", "timeout", "expire"]},
        {"name": "Error Handling", "keywords": ["error", "exception", "log", "trace", "debug"]},
        {"name": "Secure Communication", "keywords": ["tls", "ssl", "https", "encrypt", "certificate"]}
    ]

    # Extract security concerns from the architecture review
    security_concerns = architecture_review.get("security_concerns", [])
    validation_details["total_security_concerns"] = len(security_concerns)

    # Check if security concerns section exists and is not empty
    if not security_concerns:
        error_messages.append("No security concerns documented in architecture review")
        is_valid = False

        # Check if there are indications of security needs in other parts of the review
        other_sections = [
            "logical_gaps",
            "optimization_suggestions",
            "additional_considerations"
        ]

        security_keywords_found = False
        for section in other_sections:
            for item in architecture_review.get(section, []):
                item_text = item.get("description", "") + " " + item.get("recommendation", "")
                for aspect in common_security_aspects:
                    if any(keyword.lower() in item_text.lower() for keyword in aspect["keywords"]):
                        validation_details["missing_critical_security_aspects"].append(
                            f"{aspect['name']} (found in {section})"
                        )
                        security_keywords_found = True
                        break

        if security_keywords_found:
            error_messages.append(
                "Security concerns found in other sections but missing from security_concerns section"
            )

    # Check each security concern for completeness and proper severity
    for concern in security_concerns:
        # Check for required fields
        required_fields = ["description", "impact", "severity", "recommendation"]
        missing_fields = [field for field in required_fields if field not in concern or not concern[field]]

        if missing_fields:
            validation_details["incomplete_security_concerns"].append({
                "description": concern.get("description", "Unknown security concern"),
                "missing_fields": missing_fields
            })
            error_messages.append(
                f"Security concern '{concern.get('description', 'Unknown')}' is missing required fields: {', '.join(missing_fields)}"
            )
            is_valid = False
        else:
            validation_details["properly_documented_concerns"] += 1

        # Check severity appropriateness based on keywords
        description = concern.get("description", "").lower()
        impact = concern.get("impact", "").lower()
        severity = concern.get("severity", "Medium").lower()

        # Check if critical security issues have appropriate severity
        critical_keywords = ["critical", "severe", "high", "remote code execution", "rce", "data breach",
                            "authentication bypass", "privilege escalation", "unauthorized access"]

        critical_issue = any(keyword in description or keyword in impact for keyword in critical_keywords)
        if critical_issue and severity not in ["critical", "high"]:
            validation_details["severity_issues"].append({
                "description": concern.get("description", "Unknown security concern"),
                "current_severity": severity,
                "recommended_severity": "High or Critical"
            })
            error_messages.append(
                f"Security concern '{concern.get('description', 'Unknown')}' appears to be critical but has {severity} severity"
            )
            is_valid = False

    # Check for missing common security concerns
    if security_concerns:
        # Extract all text from security concerns
        all_security_text = " ".join([
            f"{concern.get('description', '')} {concern.get('impact', '')} {concern.get('recommendation', '')}"
            for concern in security_concerns
        ]).lower()

        # Check which common security aspects are not covered
        for aspect in common_security_aspects:
            aspect_covered = any(keyword.lower() in all_security_text for keyword in aspect["keywords"])
            if not aspect_covered:
                validation_details["missing_critical_security_aspects"].append(aspect["name"])

        # If critical security aspects are missing, add as error
        if validation_details["missing_critical_security_aspects"]:
            missing_aspects = ", ".join(validation_details["missing_critical_security_aspects"])
            error_messages.append(f"Missing critical security aspects in review: {missing_aspects}")
            is_valid = False

    # Return validation result
    return is_valid, "; ".join(error_messages) if error_messages else "Valid", validation_details


def _extract_keywords(text: str, min_length: int = 4) -> List[str]:
    """Extract meaningful keywords from text for pattern matching.

    Args:
        text: Text to extract keywords from
        min_length: Minimum length of keywords to include

    Returns:
        List of extracted keywords
    """
    # Split by non-alphanumeric characters and convert to lowercase
    words = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())

    # Filter out common words and short words
    common_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'with', 'by', 'about', 'from', 'as', 'into', 'like', 'through', 'after',
        'over', 'between', 'out', 'against', 'during', 'without', 'before',
        'under', 'around', 'among', 'than', 'within', 'along', 'across', 'behind',
        'beyond', 'plus', 'except', 'but', 'up', 'down', 'off', 'above', 'below',
        'should', 'would', 'could', 'may', 'might', 'must', 'can', 'will',
        'that', 'this', 'these', 'those', 'it', 'they', 'them', 'their', 'what',
        'which', 'who', 'whom', 'whose', 'when', 'where', 'why', 'how'
    }

    keywords = [word for word in words if word not in common_words and len(word) >= min_length]

    # Add special handling for security terminology - preserve important security terms even if short
    security_terms = {
        'xss', 'csrf', 'ssrf', 'sqli', 'rce', 'dos', 'jwt', 'auth', 'acl', 'rbac',
        'idor', 'cwe', 'owasp', 'csp', 'cors', 'tls', 'ssl', 'hash', 'salt',
        'mitm', 'csrf', 'xxe'
    }

    # Add specific security terms from the text, even if shorter than min_length
    security_keywords = re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())
    security_matches = [word for word in security_keywords if word in security_terms]

    # Combine regular keywords with security terms
    keywords = list(set(keywords + security_matches))

    return keywords
