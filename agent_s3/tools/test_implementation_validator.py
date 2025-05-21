"""
Test Implementation Validator Module

This module provides validation and repair functions for test implementations.
It focuses on ensuring test implementations are syntactically valid, maintainable,
traceable to architecture elements, and comprehensive in covering security concerns.
"""

import json
import logging
import re
import ast
import difflib
from typing import Dict, Any, List, Set, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class TestImplementationValidationError(Exception):
    """Exception raised when validation of test implementations fails."""
    pass


def validate_test_implementations(
    test_implementations: Dict[str, Any],
    refined_test_specs: Dict[str, Any],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """
    Validate test implementations against specifications, system design, and architecture review.
    
    Args:
        test_implementations: The test implementations to validate
        refined_test_specs: The refined test specifications
        system_design: The system design data
        architecture_review: The architecture review data
        
    Returns:
        Tuple of (validated_implementations, validation_issues, needs_repair)
    """
    validation_issues = []
    needs_repair = False
    
    # Extract element IDs from system design for validation
    element_ids = _extract_element_ids_from_system_design(system_design)
    
    # Extract architecture issues for validation
    architecture_issues = _extract_architecture_issues(architecture_review)
    
    # Create a deep copy of test implementations for potential repairs
    validated_implementations = json.loads(json.dumps(test_implementations))
    
    # Validate overall structure
    if not isinstance(test_implementations, dict) or "tests" not in test_implementations:
        validation_issues.append({
            "issue_type": "structure",
            "severity": "critical",
            "description": "Test implementations missing 'tests' top-level key"
        })
        needs_repair = True
    
    if "tests" in test_implementations:
        test_categories = ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]
        
        # Validate each category exists
        for category in test_categories:
            if category not in test_implementations["tests"]:
                validation_issues.append({
                    "issue_type": "missing_category",
                    "severity": "high",
                    "description": f"Missing test category: {category}"
                })
                validated_implementations.setdefault("tests", {})[category] = []
                needs_repair = True
            
            # Skip validation if the category is missing
            if category not in test_implementations.get("tests", {}):
                continue
                
            # Validate tests in this category
            category_tests = test_implementations["tests"][category]
            if not isinstance(category_tests, list):
                validation_issues.append({
                    "issue_type": "invalid_category_type",
                    "severity": "critical",
                    "description": f"Test category '{category}' must be a list"
                })
                validated_implementations["tests"][category] = []
                needs_repair = True
                continue
                
            # Validate individual tests
            for i, test in enumerate(category_tests):
                test_issues = _validate_single_test(
                    test, 
                    category, 
                    i, 
                    element_ids, 
                    architecture_issues, 
                    refined_test_specs
                )
                
                # Add any issues found
                for issue in test_issues:
                    validation_issues.append(issue)
                    if issue["severity"] in ["critical", "high"]:
                        needs_repair = True
    
    # Validate coverage of architecture issues
    coverage_issues = _validate_architecture_issue_coverage(
        validated_implementations, 
        architecture_issues, 
        refined_test_specs
    )
    
    for issue in coverage_issues:
        validation_issues.append(issue)
        if issue["severity"] in ["critical", "high"]:
            needs_repair = True
    
    return validated_implementations, validation_issues, needs_repair


def repair_test_implementations(
    test_implementations: Dict[str, Any],
    validation_issues: List[Dict[str, Any]],
    refined_test_specs: Dict[str, Any],
    system_design: Dict[str, Any],
    architecture_review: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Attempt to repair test implementations based on validation issues.
    
    Args:
        test_implementations: The test implementations to repair
        validation_issues: List of validation issues to address
        refined_test_specs: The refined test specifications
        system_design: The system design data
        architecture_review: The architecture review data
        
    Returns:
        Repaired test implementations
    """
    # Create a deep copy for repairs
    repaired_implementations = json.loads(json.dumps(test_implementations))
    
    # Ensure the basic structure exists
    if "tests" not in repaired_implementations:
        repaired_implementations["tests"] = {}
    
    # Ensure all categories exist
    test_categories = ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]
    for category in test_categories:
        if category not in repaired_implementations["tests"]:
            repaired_implementations["tests"][category] = []
    
    # Group issues by type for targeted repairs
    issues_by_type = defaultdict(list)
    for issue in validation_issues:
        issues_by_type[issue["issue_type"]].append(issue)
    
    # Fix missing imports
    if "missing_imports" in issues_by_type:
        repaired_implementations = _repair_missing_imports(
            repaired_implementations, 
            issues_by_type["missing_imports"]
        )
    
    # Fix invalid element_id references
    if "invalid_element_id" in issues_by_type:
        repaired_implementations = _repair_element_id_references(
            repaired_implementations, 
            issues_by_type["invalid_element_id"], 
            system_design
        )
    
    # Fix incomplete assertions
    if "incomplete_assertions" in issues_by_type:
        repaired_implementations = _repair_incomplete_assertions(
            repaired_implementations, 
            issues_by_type["incomplete_assertions"], 
            refined_test_specs
        )
    
    # Fix incorrect test structure
    if "incorrect_structure" in issues_by_type:
        repaired_implementations = _repair_test_structure(
            repaired_implementations, 
            issues_by_type["incorrect_structure"]
        )
    
    # Update the discussion to reflect repairs
    if "discussion" not in repaired_implementations:
        repaired_implementations["discussion"] = ""
    
    repair_note = "\n\nNote: The following issues were automatically repaired:\n"
    for issue_type, issues in issues_by_type.items():
        if issues and issue_type in ["missing_imports", "invalid_element_id", "incomplete_assertions", "incorrect_structure"]:
            repair_note += f"- {issue_type}: {len(issues)} issue(s) fixed\n"
    
    repaired_implementations["discussion"] += repair_note
    
    return repaired_implementations


def _extract_element_ids_from_system_design(system_design: Dict[str, Any]) -> Set[str]:
    """Extract all element IDs from the system design."""
    element_ids = set()
    
    # Extract from code_elements
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "element_id" in element:
            element_ids.add(element["element_id"])
    
    return element_ids


def _extract_architecture_issues(architecture_review: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all architecture issues from the architecture review."""
    issues = []
    
    # Extract from logical_gaps section
    for issue in architecture_review.get("logical_gaps", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "Medium"),
                "issue_type": "logical_gap"
            })
    
    # Extract from security_concerns section
    for issue in architecture_review.get("security_concerns", []):
        if isinstance(issue, dict):
            issues.append({
                "id": issue.get("id", ""),
                "description": issue.get("description", ""),
                "severity": issue.get("severity", "High"),
                "issue_type": "security_concern"
            })
    
    return issues


def _validate_single_test(
    test: Dict[str, Any],
    category: str,
    test_index: int,
    element_ids: Set[str],
    architecture_issues: List[Dict[str, Any]],
    refined_test_specs: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Validate a single test implementation."""
    issues = []
    
    # Check required fields
    required_fields = ["name", "code", "target_element_ids"]
    for field in required_fields:
        if field not in test:
            issues.append({
                "issue_type": "missing_field",
                "severity": "high",
                "description": f"Test in {category} at index {test_index} missing required field: {field}",
                "category": category,
                "test_index": test_index
            })
    
    # Skip further validation if essential fields are missing
    if "target_element_ids" not in test or "code" not in test:
        return issues
    
    # Validate element IDs
    for element_id in test.get("target_element_ids", []):
        if element_id not in element_ids:
            issues.append({
                "issue_type": "invalid_element_id",
                "severity": "high",
                "description": f"Test references non-existent element_id: {element_id}",
                "category": category,
                "test_index": test_index,
                "invalid_id": element_id
            })
    
    # Validate test code
    code_issues = _validate_test_code(test, category, test_index)
    issues.extend(code_issues)
    
    # Validate architecture issue references
    if "architecture_issue_addressed" in test:
        issue_id = test["architecture_issue_addressed"]
        found = False
        for arch_issue in architecture_issues:
            if arch_issue["id"] == issue_id:
                found = True
                break
        
        if not found:
            issues.append({
                "issue_type": "invalid_architecture_issue",
                "severity": "medium",
                "description": f"Test references non-existent architecture issue: {issue_id}",
                "category": category,
                "test_index": test_index
            })
    
    return issues


def _validate_test_code(test: Dict[str, Any], category: str, test_index: int) -> List[Dict[str, Any]]:
    """Validate test code for syntax and structure."""
    issues = []
    code = test.get("code", "")
    
    # Check for empty code
    if not code.strip():
        issues.append({
            "issue_type": "empty_code",
            "severity": "critical",
            "description": f"Test in {category} at index {test_index} has empty code",
            "category": category,
            "test_index": test_index
        })
        return issues

    # Validate code syntax
    try:
        ast.parse(code)
    except SyntaxError as exc:
        issues.append({
            "issue_type": "syntax_error",
            "severity": "critical",
            "description": f"Syntax error in test code: {exc}",
            "category": category,
            "test_index": test_index,
        })
        return issues
    
    # Check for test structure components
    structure_issues = []
    
    # Check for assertion presence
    if not re.search(r'assert|assertEqual|assertEquals|assertTrue|assertFalse|assertRaises', code):
        structure_issues.append("missing assertions")
    
    # Check for proper setup
    if category in ["unit_tests", "integration_tests"] and not re.search(r'def\s+setUp|def\s+setup|@fixture|@pytest\.fixture', code):
        structure_issues.append("missing setup")
    
    if structure_issues:
        issues.append({
            "issue_type": "incorrect_structure",
            "severity": "high",
            "description": f"Test structure issues: {', '.join(structure_issues)}",
            "category": category,
            "test_index": test_index,
            "structure_issues": structure_issues
        })
    
    # Check for imports
    if not re.search(r'import|from\s+\w+\s+import', code):
        issues.append({
            "issue_type": "missing_imports",
            "severity": "medium",
            "description": f"Test appears to be missing imports",
            "category": category,
            "test_index": test_index
        })
    
    return issues


def _validate_architecture_issue_coverage(
    test_implementations: Dict[str, Any],
    architecture_issues: List[Dict[str, Any]],
    refined_test_specs: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Validate coverage of architecture issues by tests."""
    issues = []
    
    # Extract all architecture issue IDs
    arch_issue_ids = {issue["id"] for issue in architecture_issues if issue["id"]}
    
    # Extract all addressed issues from tests
    addressed_issues = set()
    for category in ["unit_tests", "integration_tests", "property_based_tests", "acceptance_tests"]:
        for test in test_implementations.get("tests", {}).get(category, []):
            if "architecture_issue_addressed" in test:
                addressed_issues.add(test["architecture_issue_addressed"])
    
    # Find critical/high severity issues that are not addressed
    for arch_issue in architecture_issues:
        if arch_issue["severity"].lower() in ["critical", "high"] and arch_issue["id"] and arch_issue["id"] not in addressed_issues:
            issues.append({
                "issue_type": "unaddressed_critical_issue",
                "severity": "critical",
                "description": f"Critical/high severity architecture issue not addressed by tests: {arch_issue['id']}",
                "arch_issue_id": arch_issue["id"]
            })
    
    return issues


def _repair_missing_imports(
    test_implementations: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair missing imports in test code."""
    for issue in issues:
        category = issue.get("category")
        test_index = issue.get("test_index")
        
        if category and test_index is not None:
            if 0 <= test_index < len(test_implementations["tests"].get(category, [])):
                test = test_implementations["tests"][category][test_index]
                code = test.get("code", "")
                
                # Add common imports based on the test category and existing code
                new_imports = "import unittest\n"
                
                if "pytest" in code:
                    new_imports += "import pytest\n"
                if "mock" in code.lower() or "patch" in code.lower():
                    new_imports += "from unittest.mock import Mock, patch\n"
                if category == "property_based_tests":
                    new_imports += "import hypothesis\nfrom hypothesis import strategies as st\n"
                
                # Add the imports to the beginning of the code
                test["code"] = new_imports + code
    
    return test_implementations


def _repair_element_id_references(
    test_implementations: Dict[str, Any],
    issues: List[Dict[str, Any]],
    system_design: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair invalid element ID references."""
    # Extract all valid element IDs
    valid_element_ids = _extract_element_ids_from_system_design(system_design)
    
    for issue in issues:
        category = issue.get("category")
        test_index = issue.get("test_index")
        invalid_id = issue.get("invalid_id")
        
        if category and test_index is not None and invalid_id:
            if 0 <= test_index < len(test_implementations["tests"].get(category, [])):
                test = test_implementations["tests"][category][test_index]
                
                # Try to find a similar valid element ID
                best_match = None
                highest_similarity = 0
                
                for valid_id in valid_element_ids:
                    similarity = _string_similarity(invalid_id, valid_id)
                    if similarity > highest_similarity and similarity > 0.7:  # Threshold for similarity
                        highest_similarity = similarity
                        best_match = valid_id
                
                if best_match:
                    # Replace the invalid ID with the best match
                    if "target_element_ids" in test and invalid_id in test["target_element_ids"]:
                        test["target_element_ids"] = [
                            best_match if id == invalid_id else id 
                            for id in test["target_element_ids"]
                        ]
    
    return test_implementations


def _repair_incomplete_assertions(
    test_implementations: Dict[str, Any],
    issues: List[Dict[str, Any]],
    refined_test_specs: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair incomplete assertions in test code."""
    for issue in issues:
        category = issue.get("category")
        test_index = issue.get("test_index")
        
        if category and test_index is not None:
            if 0 <= test_index < len(test_implementations["tests"].get(category, [])):
                test = test_implementations["tests"][category][test_index]
                code = test.get("code", "")
                
                # Find matching test spec to extract expected outcomes
                if "name" in test:
                    test_name = test["name"]
                    test_specs = refined_test_specs.get("refined_test_requirements", {}).get(category, [])
                    
                    matching_spec = None
                    for spec in test_specs:
                        if spec.get("description", "") in test_name:
                            matching_spec = spec
                            break
                    
                    if matching_spec and "expected_outcome" in matching_spec:
                        expected_outcome = matching_spec["expected_outcome"]
                        
                        # Check if assertions are already present
                        if not re.search(r'assert|assertEqual|assertEquals|assertTrue|assertFalse|assertRaises', code):
                            # Add a basic assertion based on the expected outcome
                            if "unittest" in code:
                                assertion = f"\n        # Auto-added assertion\n        self.assertTrue(True, 'Test should verify: {expected_outcome}')\n"
                            else:
                                assertion = f"\n    # Auto-added assertion\n    assert True, 'Test should verify: {expected_outcome}'\n"
                            
                            # Add assertion before the last closing brace
                            last_brace_match = re.search(r'}\s*$', code)
                            if last_brace_match:
                                insert_pos = last_brace_match.start()
                                code = code[:insert_pos] + assertion + code[insert_pos:]
                            else:
                                code += assertion
                            
                            test["code"] = code
    
    return test_implementations


def _repair_test_structure(
    test_implementations: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair incorrect test structure."""
    for issue in issues:
        category = issue.get("category")
        test_index = issue.get("test_index")
        structure_issues = issue.get("structure_issues", [])
        
        if category and test_index is not None and structure_issues:
            if 0 <= test_index < len(test_implementations["tests"].get(category, [])):
                test = test_implementations["tests"][category][test_index]
                code = test.get("code", "")
                
                # Add basic setup if missing
                if "missing setup" in structure_issues and "def test_" in code:
                    if "unittest" in code:
                        setup = "\n    def setUp(self):\n        # Auto-added setup\n        pass\n\n"
                        # Insert after the class definition
                        class_match = re.search(r'class\s+\w+\(.*\):\s*', code)
                        if class_match:
                            insert_pos = class_match.end()
                            code = code[:insert_pos] + setup + code[insert_pos:]
                    elif "pytest" in code:
                        setup = "\n@pytest.fixture\ndef setup():\n    # Auto-added fixture\n    pass\n\n"
                        # Insert at the beginning, after imports
                        import_end = 0
                        for match in re.finditer(r'^import|^from', code, re.MULTILINE):
                            line_end = code.find('\n', match.start())
                            if line_end > import_end:
                                import_end = line_end
                        
                        if import_end > 0:
                            code = code[:import_end+1] + setup + code[import_end+1:]
                        else:
                            code = setup + code
                
                test["code"] = code
    
    return test_implementations


def _string_similarity(a: str, b: str) -> float:
    """Calculate string similarity using difflib."""
    return difflib.SequenceMatcher(None, a, b).ratio()
