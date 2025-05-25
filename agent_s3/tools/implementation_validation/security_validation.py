"""Security validation helpers for implementation validation.

This module contains functions for validating security aspects of implementation plans,
including authentication, authorization, data protection, and other security best practices.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def validate_implementation_security(
    implementation_plan: Dict[str, Any],
    architecture_issues: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validate that the implementation properly addresses security issues identified in the architecture review
    and follows security best practices.

    Args:
        implementation_plan: The implementation plan to validate
        architecture_issues: List of architecture issues from review

    Returns:
        List of validation issues related to security
    """
    issues = []

    # Extract security concerns from architecture issues
    security_concerns = [issue for issue in architecture_issues if issue.get("issue_type") == "security_concern"]

    # Map security concerns by ID
    security_concerns_by_id = {concern["id"]: concern for concern in security_concerns if "id" in concern} if security_concerns else {}

    # Track which security concerns are addressed
    addressed_concerns = set()

    # Define security best practices categories with corresponding keywords and patterns
    security_best_practices = {
        "input_validation": {
            "keywords": ["validate", "sanitize", "escape", "filter", "clean", "parse", "encoding"],
            "patterns": [r"input.*validat", r"validat.*input", r"sanitiz.*input", r"input.*sanitiz",
                         r"check.*parameter", r"parameter.*check", r"validate.*(?:param|arg|input|data)"],
            "owasp_category": "A03:2021-Injection",
            "required_coverage": 0.8  # 80% of functions that handle external input should have input validation
        },
        "authentication": {
            "keywords": ["authenticate", "login", "password", "credential", "token", "session", "jwt", "oauth"],
            "patterns": [r"auth[a-z]*", r"check.*credent", r"credent.*check", r"verif.*(?:user|login|token)"],
            "owasp_category": "A07:2021-Identification and Authentication Failures",
            "required_coverage": 0.9  # 90% of auth-related functions should have proper security measures
        },
        "authorization": {
            "keywords": ["authorize", "permission", "access control", "rbac", "acl", "role", "privilege"],
            "patterns": [r"auth[a-z]*", r"check.*(?:permission|access|role)", r"(?:permission|access|role).*check"],
            "owasp_category": "A01:2021-Broken Access Control",
            "required_coverage": 0.9  # 90% of functions that require authorization should have proper checks
        },
        "data_protection": {
            "keywords": ["encrypt", "hash", "salt", "pbkdf2", "bcrypt", "argon2", "sha", "hmac", "sensitive", "pii"],
            "patterns": [r"encrypt.*data", r"data.*encrypt", r"hash.*password", r"password.*hash",
                         r"protect.*(?:data|info)", r"sensitive.*data"],
            "owasp_category": "A02:2021-Cryptographic Failures",
            "required_coverage": 1.0  # 100% of functions handling sensitive data should have protection
        },
        "secure_communication": {
            "keywords": ["tls", "ssl", "https", "encrypt", "secure", "certificate", "key exchange"],
            "patterns": [r"secure.*(?:connection|communication)", r"(?:tls|ssl).*config", r"encrypt.*transport"],
            "owasp_category": "A02:2021-Cryptographic Failures",
            "required_coverage": 1.0  # 100% of external communication should be secure
        }
    }

    # Validate security best practices implementation
    security_issues = []
    for category, config in security_best_practices.items():
        category_issues = _check_security_category(implementation_plan, category, config)
        security_issues.extend(category_issues)

    # Check specific security validations
    input_validation_issues = check_input_validation(implementation_plan)
    auth_issues = check_authentication_requirements(implementation_plan)
    data_sanitization_issues = check_data_sanitization(implementation_plan)
    secure_comm_issues = check_secure_communication(implementation_plan)
    access_control_issues = check_access_control(implementation_plan)

    # Combine all security issues
    all_security_issues = (security_issues + input_validation_issues + auth_issues + 
                          data_sanitization_issues + secure_comm_issues + access_control_issues)

    # Check if security concerns from architecture review are addressed
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            # Check if function addresses any security concerns
            architecture_issues_addressed = function.get("architecture_issues_addressed", [])
            for issue_id in architecture_issues_addressed:
                if issue_id in security_concerns_by_id:
                    addressed_concerns.add(issue_id)

    # Check for unaddressed security concerns
    unaddressed_concerns = set(security_concerns_by_id.keys()) - addressed_concerns
    if unaddressed_concerns:
        issues.append({
            "type": "unaddressed_security_concerns",
            "severity": "high",
            "message": f"{len(unaddressed_concerns)} security concerns from architecture review not addressed",
            "details": {
                "unaddressed_concern_ids": list(unaddressed_concerns),
                "unaddressed_concerns": [security_concerns_by_id[cid] for cid in unaddressed_concerns],
                "recommendation": "Ensure all security concerns from architecture review are properly addressed"
            }
        })

    # Add all collected security issues
    issues.extend(all_security_issues)

    return issues


def check_input_validation(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check for proper input validation in implementation plan."""
    issues = []
    
    functions_with_external_input = []
    functions_with_validation = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            function_sig = function.get("function", "")
            description = function.get("description", "")
            impl_steps = function.get("implementation_steps", [])

            # Check if function handles external input
            if _handles_external_input(function_sig, description, impl_steps):
                functions_with_external_input.append(f"{file_path}::{function_sig}")

                # Check if it has validation
                if _has_input_validation(description, impl_steps):
                    functions_with_validation.append(f"{file_path}::{function_sig}")

    # Calculate validation coverage
    if functions_with_external_input:
        validation_coverage = len(functions_with_validation) / len(functions_with_external_input)
        
        if validation_coverage < 0.8:  # Less than 80% coverage
            issues.append({
                "type": "insufficient_input_validation",
                "severity": "high",
                "message": f"Only {validation_coverage:.0%} of functions with external input have validation",
                "details": {
                    "functions_needing_validation": len(functions_with_external_input),
                    "functions_with_validation": len(functions_with_validation),
                    "missing_validation": [f for f in functions_with_external_input if f not in functions_with_validation][:5],
                    "recommendation": "Add input validation to all functions handling external data"
                }
            })

    return issues


def check_authentication_requirements(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check for proper authentication implementation."""
    issues = []
    
    auth_related_functions = []
    secure_auth_functions = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            function_sig = function.get("function", "")
            description = function.get("description", "")
            impl_steps = function.get("implementation_steps", [])

            # Check if function is authentication-related
            if _is_auth_related(function_sig, description):
                auth_related_functions.append(f"{file_path}::{function_sig}")

                # Check if it implements secure authentication
                if _has_secure_authentication(description, impl_steps):
                    secure_auth_functions.append(f"{file_path}::{function_sig}")

    # Check authentication security coverage
    if auth_related_functions:
        auth_coverage = len(secure_auth_functions) / len(auth_related_functions)
        
        if auth_coverage < 0.9:  # Less than 90% coverage
            issues.append({
                "type": "insecure_authentication",
                "severity": "high",
                "message": f"Only {auth_coverage:.0%} of auth functions implement secure authentication",
                "details": {
                    "auth_functions": len(auth_related_functions),
                    "secure_auth_functions": len(secure_auth_functions),
                    "recommendation": "Implement secure authentication for all auth-related functions"
                }
            })

    return issues


def check_data_sanitization(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check for proper data sanitization."""
    issues = []
    
    data_handling_functions = []
    sanitizing_functions = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            description = function.get("description", "")
            impl_steps = function.get("implementation_steps", [])

            # Check if function handles user data
            if _handles_user_data(description, impl_steps):
                data_handling_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

                # Check if it sanitizes data
                if _has_data_sanitization(description, impl_steps):
                    sanitizing_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

    # Check sanitization coverage
    if data_handling_functions:
        sanitization_coverage = len(sanitizing_functions) / len(data_handling_functions)
        
        if sanitization_coverage < 0.7:  # Less than 70% coverage
            issues.append({
                "type": "insufficient_data_sanitization",
                "severity": "medium",
                "message": f"Only {sanitization_coverage:.0%} of data handling functions sanitize inputs",
                "details": {
                    "data_handling_functions": len(data_handling_functions),
                    "sanitizing_functions": len(sanitizing_functions),
                    "recommendation": "Add data sanitization to all functions handling user input"
                }
            })

    return issues


def check_secure_communication(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check for secure communication practices."""
    issues = []
    
    communication_functions = []
    secure_communication_functions = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            description = function.get("description", "")
            impl_steps = function.get("implementation_steps", [])

            # Check if function handles external communication
            if _handles_external_communication(description, impl_steps):
                communication_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

                # Check if it uses secure communication
                if _uses_secure_communication(description, impl_steps):
                    secure_communication_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

    # Check secure communication coverage
    if communication_functions:
        secure_comm_coverage = len(secure_communication_functions) / len(communication_functions)
        
        if secure_comm_coverage < 1.0:  # Should be 100%
            issues.append({
                "type": "insecure_communication",
                "severity": "high",
                "message": f"Only {secure_comm_coverage:.0%} of communication functions use secure protocols",
                "details": {
                    "communication_functions": len(communication_functions),
                    "secure_functions": len(secure_communication_functions),
                    "recommendation": "Ensure all external communication uses secure protocols (HTTPS, TLS)"
                }
            })

    return issues


def check_access_control(implementation_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check for proper access control implementation."""
    issues = []
    
    protected_functions = []
    access_controlled_functions = []

    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue

        for function in functions:
            if not isinstance(function, dict):
                continue

            description = function.get("description", "")
            impl_steps = function.get("implementation_steps", [])

            # Check if function needs access control
            if _needs_access_control(description, impl_steps):
                protected_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

                # Check if it implements access control
                if _has_access_control(description, impl_steps):
                    access_controlled_functions.append(f"{file_path}::{function.get('function', 'unknown')}")

    # Check access control coverage
    if protected_functions:
        access_control_coverage = len(access_controlled_functions) / len(protected_functions)
        
        if access_control_coverage < 0.9:  # Less than 90% coverage
            issues.append({
                "type": "insufficient_access_control",
                "severity": "high",
                "message": f"Only {access_control_coverage:.0%} of protected functions implement access control",
                "details": {
                    "protected_functions": len(protected_functions),
                    "access_controlled_functions": len(access_controlled_functions),
                    "recommendation": "Implement proper access control for all protected functions"
                }
            })

    return issues


def _check_security_category(implementation_plan: Dict[str, Any], category: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check a specific security category against the implementation plan."""
    issues = []
    
    relevant_functions = []
    compliant_functions = []
    
    keywords = config["keywords"]
    patterns = config["patterns"]
    
    for file_path, functions in implementation_plan.items():
        if not isinstance(functions, list):
            continue
            
        for function in functions:
            if not isinstance(function, dict):
                continue
                
            # Check if function is relevant to this security category
            if _is_relevant_to_security_category(function, keywords, patterns):
                relevant_functions.append(f"{file_path}::{function.get('function', 'unknown')}")
                
                # Check if it properly implements security measures
                if _implements_security_measures(function, keywords, patterns):
                    compliant_functions.append(f"{file_path}::{function.get('function', 'unknown')}")
    
    # Check coverage
    if relevant_functions:
        coverage = len(compliant_functions) / len(relevant_functions)
        required_coverage = config["required_coverage"]
        
        if coverage < required_coverage:
            issues.append({
                "type": f"insufficient_{category}",
                "severity": "high" if required_coverage == 1.0 else "medium",
                "message": f"Only {coverage:.0%} of {category} functions meet security requirements",
                "details": {
                    "owasp_category": config["owasp_category"],
                    "relevant_functions": len(relevant_functions),
                    "compliant_functions": len(compliant_functions),
                    "required_coverage": f"{required_coverage:.0%}",
                    "recommendation": f"Improve {category} implementation to meet security standards"
                }
            })
    
    return issues


# Helper functions for security checks
def _handles_external_input(function_sig: str, description: str, impl_steps: List[str]) -> bool:
    """Check if function handles external input."""
    text = f"{function_sig} {description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"user.*input", r"external.*data", r"request.*param", r"form.*data", r"query.*param"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _has_input_validation(description: str, impl_steps: List[str]) -> bool:
    """Check if function has input validation."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"validat.*input", r"check.*param", r"sanitiz.*data", r"clean.*input"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _is_auth_related(function_sig: str, description: str) -> bool:
    """Check if function is authentication-related."""
    text = f"{function_sig} {description}"
    keywords = ["login", "authenticate", "password", "credential", "token", "session"]
    return any(keyword in text.lower() for keyword in keywords)


def _has_secure_authentication(description: str, impl_steps: List[str]) -> bool:
    """Check if function implements secure authentication."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"hash.*password", r"bcrypt", r"argon2", r"secure.*token", r"jwt.*verify"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _handles_user_data(description: str, impl_steps: List[str]) -> bool:
    """Check if function handles user data."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"user.*data", r"process.*input", r"handle.*form", r"store.*data"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _has_data_sanitization(description: str, impl_steps: List[str]) -> bool:
    """Check if function sanitizes data."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"sanitiz.*data", r"clean.*input", r"escape.*html", r"filter.*data"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _handles_external_communication(description: str, impl_steps: List[str]) -> bool:
    """Check if function handles external communication."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"http.*request", r"api.*call", r"external.*service", r"network.*request"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _uses_secure_communication(description: str, impl_steps: List[str]) -> bool:
    """Check if function uses secure communication."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"https", r"tls", r"ssl", r"secure.*protocol", r"encrypt.*transport"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _needs_access_control(description: str, impl_steps: List[str]) -> bool:
    """Check if function needs access control."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"admin.*function", r"privileged.*operation", r"restricted.*access", r"protected.*resource"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _has_access_control(description: str, impl_steps: List[str]) -> bool:
    """Check if function implements access control."""
    text = f"{description} {' '.join(impl_steps) if impl_steps else ''}"
    patterns = [r"check.*permission", r"verify.*role", r"access.*control", r"authorize.*user"]
    return any(re.search(pattern, text.lower()) for pattern in patterns)


def _is_relevant_to_security_category(function: Dict[str, Any], keywords: List[str], patterns: List[str]) -> bool:
    """Check if function is relevant to a security category."""
    text = f"{function.get('function', '')} {function.get('description', '')}"
    
    # Check keywords
    if any(keyword in text.lower() for keyword in keywords):
        return True
    
    # Check patterns
    if any(re.search(pattern, text.lower()) for pattern in patterns):
        return True
    
    return False


def _implements_security_measures(function: Dict[str, Any], keywords: List[str], patterns: List[str]) -> bool:
    """Check if function implements appropriate security measures."""
    impl_steps = function.get("implementation_steps", [])
    security_text = " ".join(impl_steps) if impl_steps else ""
    
    # Look for security-related implementation
    security_patterns = [r"implement.*security", r"add.*validation", r"secure.*implement", r"protect.*against"]
    return any(re.search(pattern, security_text.lower()) for pattern in security_patterns)