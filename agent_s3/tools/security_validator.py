"""
Security Validator Module

This module provides cross-phase security validation functions for Agent S3.
It ensures security concerns identified in the architecture review are properly
addressed throughout the planning and implementation phases.

Features:
- Cross-phase security validation (architecture, implementation, testing)
- Security regression detection
- OWASP Top 10 compliance validation
- Security testing coverage validation

Note: This module has been simplified to focus on traceability rather than
attempting complex semantic validation. Instead of trying to determine whether
security concerns are semantically addressed (which could cause crashes and 
endless loops), the validation now focuses on ensuring that security concerns
are explicitly referenced in implementation plans and tests.
"""

import json
import logging
from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict

# Import validation functions from other modules for cross-phase validation
from agent_s3.tools.phase_validator import validate_security_concerns

logger = logging.getLogger(__name__)


class SecurityValidationError(Exception):
    """Exception raised when security validation fails."""
    pass


def _validate_implementation_security(
    implementation_plan: Dict[str, Any],
    security_concerns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Simplified security validation that focuses on traceability rather than complex semantic validation.
    This function validates that security concerns from architecture review are explicitly referenced
    in implementation plans.
    
    Args:
        implementation_plan: The implementation plan to validate
        security_concerns: List of security concerns from architecture review
        
    Returns:
        List of validation issues related to security
    """
    issues = []
    
    # Create a dictionary of security concerns by ID for easy lookup
    concerns_by_id = {concern["id"]: concern for concern in security_concerns if "id" in concern}
    
    # Track which security concerns are addressed in implementation
    addressed_concerns = set()
    
    # Check each function for explicit references to security concerns
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue
            
        for function in functions:
            if not isinstance(function, dict):
                continue
                
            # Check architecture_issues_addressed field for explicit references to security concerns
            arch_issues_addressed = function.get("architecture_issues_addressed", [])
            if isinstance(arch_issues_addressed, list):
                for issue_id in arch_issues_addressed:
                    if issue_id in concerns_by_id:
                        addressed_concerns.add(issue_id)
    
    # Report any security concerns that are not explicitly addressed
    for concern_id, concern in concerns_by_id.items():
        if concern_id not in addressed_concerns:
            severity = concern.get("severity", "Medium").lower()
            issue_severity = "critical" if severity in ["critical", "high"] else "high"
            
            issues.append({
                "issue_type": "unaddressed_security_issue",
                "severity": issue_severity,
                "description": f"Security concern not explicitly addressed in implementation: {concern_id} - {concern.get('description', 'No description')}",
                "arch_issue_id": concern_id
            })
    
    return issues


def validate_cross_phase_security(
    architecture_review: Dict[str, Any],
    implementation_plan: Dict[str, Any],
    test_implementations: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Perform cross-phase security validation between architecture, implementation, and testing.
    
    Args:
        architecture_review: The architecture review data containing security concerns
        implementation_plan: The implementation plan to validate against security concerns
        test_implementations: The test implementations data for security testing validation
    
    Returns:
        Tuple of (is_valid, validation_details, validation_issues)
    """
    issues = []
    is_valid = True
    
    # Collect validation details
    validation_details = {
        "phases": {
            "architecture": {},
            "implementation": {},
            "testing": {}
        },
        "security_concerns": {},
        "cross_phase_issues": [],
        "owasp_categories": {},
        "overall_security_score": 0.0
    }
    
    # Step 1: Validate architecture security concerns
    arch_valid, arch_message, arch_details = validate_security_concerns(architecture_review)
    if not arch_valid:
        is_valid = False
        
    validation_details["phases"]["architecture"] = arch_details
    
    # Extract security concerns for cross-phase tracking
    security_concerns = _extract_security_concerns(architecture_review)
    validation_details["security_concerns"] = {
        concern["id"]: {
            "description": concern.get("description", ""),
            "severity": concern.get("severity", "Low"),
            "addressed_in": set(),
            "tested": False
        } for concern in security_concerns
    }
    
    # Step 2: Validate implementation security using the simplified validation function
    implementation_issues = _validate_implementation_security(implementation_plan, security_concerns)
    
    # Update validation details with implementation results
    implemented_concerns = set()
    for issue in implementation_issues:
        if issue["issue_type"] == "unaddressed_security_issue" and "arch_issue_id" in issue:
            concern_id = issue["arch_issue_id"]
            if concern_id in validation_details["security_concerns"]:
                # This security issue is not addressed in implementation
                pass
        
    # Find addressed concerns (those not in the issues list)
    for concern_id in validation_details["security_concerns"].keys():
        if not any(issue["arch_issue_id"] == concern_id for issue in implementation_issues if "arch_issue_id" in issue):
            implemented_concerns.add(concern_id)
            validation_details["security_concerns"][concern_id]["addressed_in"].add("implementation")
    
    # Add all implementation issues to the overall issues list
    issues.extend(implementation_issues)
    
    # Prepare implementation phase summary
    validation_details["phases"]["implementation"] = {
        "addressed_concerns": len(implemented_concerns),
        "total_concerns": len(security_concerns),
        "coverage_ratio": len(implemented_concerns) / max(1, len(security_concerns))
    }
    
    # Step 3: Validate security testing coverage
    security_test_issues = validate_security_testing_coverage(test_implementations, security_concerns)
    issues.extend(security_test_issues)
    
    # Extract tested security concerns
    tested_concerns = _extract_tested_concerns(test_implementations, security_concerns)
    for concern_id in tested_concerns:
        if concern_id in validation_details["security_concerns"]:
            validation_details["security_concerns"][concern_id]["addressed_in"].add("testing")
            validation_details["security_concerns"][concern_id]["tested"] = True
    
    # Update testing phase summary
    validation_details["phases"]["testing"] = {
        "tested_concerns": len(tested_concerns),
        "total_concerns": len(security_concerns),
        "coverage_ratio": len(tested_concerns) / max(1, len(security_concerns))
    }
    
    # Step 4: Perform cross-phase validation
    cross_phase_issues = _validate_security_across_phases(
        validation_details["security_concerns"],
        architecture_review,
        implementation_plan,
        test_implementations
    )
    issues.extend(cross_phase_issues)
    validation_details["cross_phase_issues"] = [issue["description"] for issue in cross_phase_issues]
    
    # Step 5: Calculate overall security score
    validation_details["overall_security_score"] = _calculate_security_score(validation_details)
    
    # Update overall validation status
    if issues and any(issue["severity"] in ["critical", "high"] for issue in issues):
        is_valid = False
    
    return is_valid, validation_details, issues


def validate_security_testing_coverage(
    test_implementations: Dict[str, Any],
    security_concerns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate that security concerns have corresponding tests.
    
    Args:
        test_implementations: The test implementations data
        security_concerns: List of security concerns from architecture review
    
    Returns:
        List of validation issues
    """
    issues = []
    
    # Extract security concerns by ID
    concerns_by_id = {concern["id"]: concern for concern in security_concerns if "id" in concern}
    
    # Track which security concerns are tested
    tested_concerns = _extract_tested_concerns(test_implementations, security_concerns)
    
    # Check for untested critical/high security concerns
    for concern_id, concern in concerns_by_id.items():
        severity = concern.get("severity", "Medium").lower()
        if severity in ["critical", "high"] and concern_id not in tested_concerns:
            issues.append({
                "issue_type": "untested_security_concern",
                "severity": "high",
                "description": f"Critical security concern '{concern_id}' ({concern.get('description', '')}) has no tests",
                "concern_id": concern_id
            })
    
    # Check for security test cases without coverage of key security aspects
    security_test_coverage = _analyze_security_test_coverage(test_implementations)
    
    # Check coverage of OWASP Top 10 categories
    owasp_categories = {
        "A01": "Broken Access Control",
        "A02": "Cryptographic Failures",
        "A03": "Injection",
        "A04": "Insecure Design",
        "A05": "Security Misconfiguration",
        "A06": "Vulnerable Components",
        "A07": "Identification and Authentication Failures",
        "A08": "Software and Data Integrity Failures",
        "A09": "Security Logging and Monitoring Failures",
        "A10": "Server-Side Request Forgery"
    }
    
    # Get security concerns' OWASP categories
    concern_categories = set()
    for concern in security_concerns:
        concern_text = concern.get("description", "") + " " + concern.get("recommendation", "")
        for category_id, category_name in owasp_categories.items():
            if category_id in concern_text or category_name.lower() in concern_text.lower():
                concern_categories.add(category_id)
    
    # Check if security testing covers all relevant OWASP categories
    for category_id in concern_categories:
        if category_id not in security_test_coverage["owasp_categories"]:
            issues.append({
                "issue_type": "missing_owasp_category_testing",
                "severity": "medium",
                "description": f"No tests for OWASP category {category_id}: {owasp_categories[category_id]}",
                "owasp_category": category_id
            })
    
    return issues


def _extract_security_concerns(architecture_review: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract security concerns from architecture review.
    
    Args:
        architecture_review: The architecture review data
        
    Returns:
        List of security concerns
    """
    security_concerns = []
    
    # Extract explicit security concerns
    if "security_concerns" in architecture_review:
        for concern in architecture_review.get("security_concerns", []):
            if isinstance(concern, dict):
                # Ensure each concern has an ID
                if "id" not in concern:
                    concern = concern.copy()
                    concern["id"] = f"SC-{len(security_concerns) + 1}"
                
                # Add issue_type if not present
                if "issue_type" not in concern:
                    concern = concern.copy()
                    concern["issue_type"] = "security_concern"
                
                security_concerns.append(concern)
    
    # Check for security-related logical gaps
    security_keywords = [
        "security", "auth", "login", "password", "credential", "token", "session", 
        "jwt", "oauth", "permission", "access control", "rbac", "acl", "privilege", 
        "validate", "sanitize", "escape", "filter", "clean", "parse", "encoding", 
        "sql", "injection", "xss", "script", "csrf", "forgery", "cross-site", 
        "encrypt", "hash", "salt", "sensitive", "pii", "personal", "data", "leak",
        "tls", "ssl", "https", "certificate"
    ]
    
    for gap in architecture_review.get("logical_gaps", []):
        if isinstance(gap, dict):
            description = gap.get("description", "").lower()
            recommendation = gap.get("recommendation", "").lower()
            if any(keyword in description or keyword in recommendation for keyword in security_keywords):
                # This logical gap is security-related, treat as security concern
                security_concern = gap.copy()
                if "id" not in security_concern:
                    security_concern["id"] = f"SC-LGAP-{len(security_concerns) + 1}"
                security_concern["issue_type"] = "security_concern"
                security_concerns.append(security_concern)
    
    return security_concerns


def _extract_tested_concerns(
    test_implementations: Dict[str, Any],
    security_concerns: List[Dict[str, Any]]
) -> Set[str]:
    """
    Extract security concerns that have tests.
    
    Args:
        test_implementations: The test implementations data
        security_concerns: List of security concerns from architecture review
    
    Returns:
        Set of concern IDs that are tested
    """
    tested_concerns = set()
    concern_ids = {concern["id"] for concern in security_concerns if "id" in concern}
    
    # Check if test_implementations has the expected structure
    if "tests" not in test_implementations:
        return tested_concerns
    
    # Extract tests that address security concerns
    for test_type, tests in test_implementations.get("tests", {}).items():
        for test in tests:
            # Check explicit architecture issue addressal
            if "architecture_issues_addressed" in test:
                for issue_id in test.get("architecture_issues_addressed", []):
                    if issue_id in concern_ids:
                        tested_concerns.add(issue_id)
            
            # Check target element IDs
            target_elements = test.get("target_element_ids", [])
            for concern in security_concerns:
                affected_elements = concern.get("affected_elements", []) or concern.get("target_element_ids", [])
                if any(elem in target_elements for elem in affected_elements):
                    tested_concerns.add(concern["id"])
            
            # Check test code and description for security-related testing
            test_code = test.get("code", "").lower()
            test_desc = test.get("description", "").lower()
            if any(keyword in test_code or keyword in test_desc for keyword in [
                "security", "auth", "login", "password", "injection", "xss", "sql",
                "csrf", "forgery", "unauthorized", "permission", "encrypt", "hash"
            ]):
                # This looks like a security test, check which concerns it might address
                for concern in security_concerns:
                    concern_desc = concern.get("description", "").lower()
                    # Check if test description or code addresses the security concern
                    if (any(term in concern_desc and term in test_desc for term in [
                        "auth", "login", "password", "injection", "xss", "sql", "csrf"
                    ]) or any(term in concern_desc and term in test_code for term in [
                        "auth", "login", "password", "injection", "xss", "sql", "csrf"
                    ])):
                        tested_concerns.add(concern["id"])
    
    return tested_concerns


def _validate_security_across_phases(
    security_concerns: Dict[str, Any],
    architecture_review: Dict[str, Any],
    implementation_plan: Dict[str, Any],
    test_implementations: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Simplified validation of security consistency across all phases,
    focusing on traceability rather than semantic validation.
    
    Args:
        security_concerns: Dictionary of security concerns with their cross-phase status
        architecture_review: The architecture review data
        implementation_plan: The implementation plan data
        test_implementations: The test implementations data
    
    Returns:
        List of cross-phase validation issues
    """
    issues = []
    
    # Check that critical/high security concerns are addressed in both implementation and testing
    for concern_id, concern_status in security_concerns.items():
        severity = concern_status["severity"].lower()
        addressed_in = concern_status["addressed_in"]
        
        if severity in ["critical", "high"]:
            # Critical concerns must be addressed in both implementation and testing
            if "implementation" not in addressed_in:
                issues.append({
                    "issue_type": "critical_concern_not_implemented",
                    "severity": "critical",
                    "description": f"Critical security concern '{concern_id}' is not addressed in implementation",
                    "concern_id": concern_id
                })
            
            if "testing" not in addressed_in:
                issues.append({
                    "issue_type": "critical_concern_not_tested",
                    "severity": "critical",
                    "description": f"Critical security concern '{concern_id}' lacks test coverage",
                    "concern_id": concern_id
                })
        elif severity == "medium":
            # Medium concerns should be addressed in at least implementation
            if "implementation" not in addressed_in:
                issues.append({
                    "issue_type": "medium_concern_not_implemented",
                    "severity": "medium",
                    "description": f"Medium security concern '{concern_id}' is not addressed in implementation",
                    "concern_id": concern_id
                })
    
    # Check architecture-to-tests direct traceability for critical concerns
    architecture_elements_with_security = _extract_elements_with_security_concerns(architecture_review)
    tested_elements = _extract_tested_elements(test_implementations)
    
    for element_id in architecture_elements_with_security:
        if element_id not in tested_elements:
            issues.append({
                "issue_type": "security_element_not_tested",
                "severity": "high",
                "description": f"Element '{element_id}' has security concerns but lacks direct test coverage",
                "element_id": element_id
            })
    
    return issues


def _analyze_security_test_coverage(test_implementations: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze security test coverage from test implementations.
    
    Args:
        test_implementations: The test implementations data
    
    Returns:
        Dictionary with security test coverage statistics
    """
    coverage = {
        "owasp_categories": set(),
        "security_test_count": 0,
        "test_types": defaultdict(int)
    }
    
    # OWASP categories with keywords for detection
    owasp_detection = {
        "A01": ["access control", "authorization", "permission", "privilege", "rbac"],
        "A02": ["crypto", "encrypt", "hash", "tls", "ssl", "certificate"],
        "A03": ["injection", "sql", "xss", "script", "escape", "sanitize"],
        "A04": ["design", "architecture", "logic", "flow"],
        "A05": ["config", "misconfiguration", "default", "hardcoded"],
        "A06": ["component", "library", "dependency", "outdated", "version"],
        "A07": ["authentication", "login", "password", "credential", "session", "jwt", "token"],
        "A08": ["integrity", "signature", "verify", "deserialization"],
        "A09": ["log", "monitor", "audit", "trace", "debug"],
        "A10": ["ssrf", "request forgery", "server-side"]
    }
    
    # Check if test_implementations has the expected structure
    if "tests" not in test_implementations:
        return coverage
    
    # Analyze tests for security coverage
    for test_type, tests in test_implementations.get("tests", {}).items():
        for test in tests:
            # Detect if this is a security test
            test_code = test.get("code", "").lower()
            test_desc = test.get("description", "").lower()
            test_name = test.get("name", "").lower()
            
            is_security_test = (
                "security" in test_type or
                "security" in test_name or
                "security" in test_desc or
                any(keyword in test_desc or keyword in test_code for keyword in [
                    "auth", "login", "password", "injection", "xss", "sql",
                    "csrf", "forgery", "unauthorized", "permission", "encrypt", "hash"
                ])
            )
            
            if is_security_test:
                coverage["security_test_count"] += 1
                coverage["test_types"][test_type] += 1
                
                # Check which OWASP categories this test covers
                for category, keywords in owasp_detection.items():
                    if any(keyword in test_desc or keyword in test_code or keyword in test_name for keyword in keywords):
                        coverage["owasp_categories"].add(category)
    
    return coverage


def _extract_security_patterns(implementation_plan: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    A simplified stub function that returns an empty dictionary.
    This function is kept for backward compatibility but no longer performs complex pattern matching.
    
    Args:
        implementation_plan: The implementation plan data
    
    Returns:
        Empty dictionary as complex pattern matching is no longer performed
    """
    return {}


def _identify_inconsistent_security_patterns(patterns: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    A simplified stub function that returns an empty dictionary.
    This function is kept for backward compatibility but no longer performs complex pattern matching.
    
    Args:
        patterns: Dictionary mapping security patterns to lists of component paths
    
    Returns:
        Empty dictionary as complex pattern matching is no longer performed
    """
    return {}


def _extract_elements_with_security_concerns(architecture_review: Dict[str, Any]) -> Set[str]:
    """
    Extract elements that have security concerns in architecture review.
    
    Args:
        architecture_review: The architecture review data
    
    Returns:
        Set of element IDs with security concerns
    """
    elements = set()
    
    # Extract from explicit security concerns
    for concern in architecture_review.get("security_concerns", []):
        if isinstance(concern, dict):
            elements.update(concern.get("affected_elements", []) or concern.get("target_element_ids", []))
    
    # Extract from security-related logical gaps
    security_keywords = [
        "security", "auth", "login", "password", "credential", "token", "session", 
        "inject", "xss", "csrf", "encrypt", "hash"
    ]
    
    for gap in architecture_review.get("logical_gaps", []):
        if isinstance(gap, dict):
            description = gap.get("description", "").lower()
            if any(keyword in description for keyword in security_keywords):
                elements.update(gap.get("affected_elements", []) or gap.get("target_element_ids", []))
    
    return elements


def _extract_tested_elements(test_implementations: Dict[str, Any]) -> Set[str]:
    """
    Extract elements that have test coverage.
    
    Args:
        test_implementations: The test implementations data
    
    Returns:
        Set of element IDs with test coverage
    """
    elements = set()
    
    # Check if test_implementations has the expected structure
    if "tests" not in test_implementations:
        return elements
    
    # Extract tested elements
    for test_type, tests in test_implementations.get("tests", {}).items():
        for test in tests:
            elements.update(test.get("target_element_ids", []))
    
    return elements


def _calculate_security_score(validation_details: Dict[str, Any]) -> float:
    """
    Calculate overall security score based on validation details.
    
    Args:
        validation_details: Dictionary with validation details
    
    Returns:
        Float between 0.0 and 1.0 representing security score
    """
    # Start with a perfect score
    score = 1.0
    
    # Penalize for architecture phase issues
    architecture_details = validation_details["phases"]["architecture"]
    if "total_security_concerns" in architecture_details and architecture_details["total_security_concerns"] > 0:
        properly_documented = architecture_details.get("properly_documented_concerns", 0)
        documentation_ratio = properly_documented / architecture_details["total_security_concerns"]
        # Reduce score for poor documentation (up to 10%)
        score -= 0.1 * (1 - documentation_ratio)
    
    # Penalize for missing security aspects (5% each)
    for aspect in architecture_details.get("missing_critical_security_aspects", []):
        score -= 0.05
    
    # Penalize for implementation phase issues
    implementation_details = validation_details["phases"]["implementation"]
    if "coverage_ratio" in implementation_details:
        # Reduce score for low implementation coverage (up to 40%)
        score -= 0.4 * (1 - implementation_details["coverage_ratio"])
    
    # Penalize for testing phase issues
    testing_details = validation_details["phases"]["testing"]
    if "coverage_ratio" in testing_details:
        # Reduce score for low testing coverage (up to 30%)
        score -= 0.3 * (1 - testing_details["coverage_ratio"])
    
    # Penalize for cross-phase issues (5% each, up to 20%)
    cross_phase_penalty = min(0.2, 0.05 * len(validation_details.get("cross_phase_issues", [])))
    score -= cross_phase_penalty
    
    # Ensure score is between 0 and 1
    return max(0.0, min(1.0, score))


def generate_security_report(
    architecture_review: Dict[str, Any],
    implementation_plan: Dict[str, Any],
    test_implementations: Dict[str, Any],
    output_format: str = "json"
) -> str:
    """
    Generate a comprehensive security report.
    
    Args:
        architecture_review: The architecture review data
        implementation_plan: The implementation plan data
        test_implementations: The test implementations data
        output_format: The output format ("json" or "markdown")
    
    Returns:
        Security report string in the requested format
    """
    # Perform validation
    is_valid, validation_details, issues = validate_cross_phase_security(
        architecture_review, implementation_plan, test_implementations
    )
    
    # Prepare report data
    report = {
        "summary": {
            "is_valid": is_valid,
            "score": validation_details["overall_security_score"],
            "grade": _score_to_grade(validation_details["overall_security_score"]),
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i["severity"] == "critical"]),
            "high_issues": len([i for i in issues if i["severity"] == "high"]),
            "medium_issues": len([i for i in issues if i["severity"] == "medium"]),
            "low_issues": len([i for i in issues if i["severity"] == "low"])
        },
        "security_concerns": validation_details["security_concerns"],
        "phase_details": validation_details["phases"],
        "cross_phase_issues": validation_details["cross_phase_issues"],
        "issues": issues
    }
    
    # Format the report
    if output_format.lower() == "markdown":
        return _format_report_markdown(report)
    
    # Default to JSON format
    return json.dumps(report, indent=2, default=_set_serializer)


def _score_to_grade(score: float) -> str:
    """Convert security score to letter grade."""
    if score >= 0.9:
        return "A"
    elif score >= 0.8:
        return "B"
    elif score >= 0.7:
        return "C"
    elif score >= 0.6:
        return "D"
    else:
        return "F"


def _set_serializer(obj):
    """JSON serializer for sets."""
    if isinstance(obj, set):
        return list(obj)
    raise TypeError("Type not serializable")


def _format_report_markdown(report: Dict[str, Any]) -> str:
    """Format security report as Markdown."""
    md = ["# Security Validation Report\n"]
    
    # Summary section
    md.append("## Summary\n")
    md.append(f"- **Status**: {'✅ PASS' if report['summary']['is_valid'] else '❌ FAIL'}")
    md.append(f"- **Security Score**: {report['summary']['score']:.2f} ({report['summary']['grade']})")
    md.append(f"- **Total Issues**: {report['summary']['total_issues']}")
    md.append(f"- **Critical Issues**: {report['summary']['critical_issues']}")
    md.append(f"- **High Issues**: {report['summary']['high_issues']}")
    md.append(f"- **Medium Issues**: {report['summary']['medium_issues']}")
    md.append(f"- **Low Issues**: {report['summary']['low_issues']}\n")
    
    # Phase details
    md.append("## Phase Details\n")
    
    # Architecture phase
    arch = report["phase_details"]["architecture"]
    md.append("### Architecture Phase\n")
    md.append(f"- **Security Concerns**: {arch.get('total_security_concerns', 0)}")
    md.append(f"- **Properly Documented**: {arch.get('properly_documented_concerns', 0)}")
    
    missing_aspects = arch.get("missing_critical_security_aspects", [])
    if missing_aspects:
        md.append("\n**Missing Security Aspects:**\n")
        for aspect in missing_aspects:
            md.append(f"- {aspect}")
    
    # Implementation phase
    impl = report["phase_details"]["implementation"]
    md.append("\n### Implementation Phase\n")
    md.append(f"- **Addressed Concerns**: {impl.get('addressed_concerns', 0)}/{impl.get('total_concerns', 0)}")
    md.append(f"- **Coverage Ratio**: {impl.get('coverage_ratio', 0):.2f}")
    
    # Testing phase
    test = report["phase_details"]["testing"]
    md.append("\n### Testing Phase\n")
    md.append(f"- **Tested Concerns**: {test.get('tested_concerns', 0)}/{test.get('total_concerns', 0)}")
    md.append(f"- **Coverage Ratio**: {test.get('coverage_ratio', 0):.2f}")
    
    # Cross-phase issues
    if report["cross_phase_issues"]:
        md.append("\n## Cross-Phase Issues\n")
        for issue in report["cross_phase_issues"]:
            md.append(f"- {issue}")
    
    # Security issues
    if report["issues"]:
        md.append("\n## Security Issues\n")
        
        # Group issues by severity
        severity_groups = {"critical": [], "high": [], "medium": [], "low": []}
        for issue in report["issues"]:
            severity_groups[issue["severity"]].append(issue)
        
        for severity, issues in severity_groups.items():
            if not issues:
                continue
                
            md.append(f"\n### {severity.upper()} Issues\n")
            for i, issue in enumerate(issues):
                md.append(f"**{i+1}. {issue['issue_type']}**")
                md.append(f"- {issue['description']}")
    
    return "\n".join(md)
