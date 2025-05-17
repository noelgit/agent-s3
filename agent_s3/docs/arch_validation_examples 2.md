# Architecture Review Validation Usage Examples

This document provides examples of how to use the enhanced architecture review validation system.

## Using Security Concern Validation

```python
from agent_s3.tools.phase_validator import validate_security_concerns

# Example architecture review with security concerns
architecture_review = {
    "security_concerns": [
        {
            "id": "SEC-1",
            "description": "User input in search function is passed directly to SQL query",
            "impact": "Could lead to SQL injection attacks and database compromise",
            "recommendation": "Implement parameterized queries with prepared statements",
            "target_element_ids": ["search_service_query_function", "database_executor"],
            "severity": "Critical"
        },
        {
            "id": "SEC-2",
            "description": "Session cookies missing secure and httpOnly flags",
            "impact": "Cookies could be accessed by client-side scripts or sent over unsecured connections",
            "recommendation": "Set secure and httpOnly flags for all session cookies",
            "target_element_ids": ["auth_service"],
            "severity": "High"
        }
    ]
}

# Validate security concerns
is_valid, error_message, validation_details = validate_security_concerns(architecture_review)

print(f"Valid: {is_valid}")
print(f"Message: {error_message}")
print(f"Total security concerns: {validation_details['total_security_concerns']}")
print(f"Properly documented: {validation_details['properly_documented_concerns']}")

if not is_valid:
    if validation_details.get("missing_critical_security_aspects"):
        print("Missing security aspects:", validation_details["missing_critical_security_aspects"])
    if validation_details.get("incomplete_security_concerns"):
        print("Incomplete security concerns:", validation_details["incomplete_security_concerns"])
    if validation_details.get("severity_issues"):
        print("Severity issues:", validation_details["severity_issues"])
```

## Validating Test Priority Alignment

```python
from agent_s3.test_spec_validator import validate_priority_alignment

# Example test specifications
test_specs = {
    "unit_tests": [
        {
            "description": "Test SQL injection prevention in search function",
            "target_element_id": "search_service_query_function",
            "architecture_issue_addressed": "SEC-1",
            "priority": "Medium"  # This is incorrect - should be Critical
        }
    ],
    "integration_tests": [
        {
            "description": "Test secure cookie configuration",
            "target_element_ids": ["auth_service"],
            "architecture_issue_addressed": "SEC-2",
            "priority": "High"  # This is correct
        }
    ]
}

# Example architecture review
architecture_review = {
    "security_concerns": [
        {
            "id": "SEC-1",
            "description": "SQL injection vulnerability",
            "severity": "Critical"
        },
        {
            "id": "SEC-2",
            "description": "Cookie security issue",
            "severity": "High"
        }
    ]
}

# Validate priority alignment
validation_issues = validate_priority_alignment(test_specs, architecture_review)

# Check for issues
if validation_issues:
    print(f"Found {len(validation_issues)} priority alignment issues:")
    for issue in validation_issues:
        print(f"- {issue['message']}")
        print(f"  Severity: {issue['severity']}")
        print(f"  Recommended: {', '.join(issue.get('allowed_priorities', []))}")
else:
    print("No priority alignment issues found")
```

## Complete Test Specification Validation

```python
from agent_s3.test_spec_validator import validate_and_repair_test_specifications

# Example system design
system_design = {
    "code_elements": [
        {"element_id": "search_service_query_function", "name": "SearchService.query"},
        {"element_id": "auth_service", "name": "AuthenticationService"},
        {"element_id": "database_executor", "name": "DatabaseQueryExecutor"}
    ]
}

# Validate and repair test specifications
repaired_specs, validation_issues, was_repaired = validate_and_repair_test_specifications(
    test_specs, system_design, architecture_review
)

# Check validation results
if validation_issues:
    print(f"Found {len(validation_issues)} validation issues:")
    for issue in validation_issues:
        print(f"- {issue['issue_type']}: {issue['message']}")
        print(f"  Severity: {issue['severity']}")
    
    if was_repaired:
        print("\nIssues were automatically repaired in the test specifications")
else:
    print("No validation issues found")

# Example of accessing a repaired test with corrected priority
if was_repaired:
    unit_test = repaired_specs.get("unit_tests", [])[0]
    print(f"\nRepaired test: {unit_test['description']}")
    print(f"Updated priority: {unit_test['priority']}")  # Should now be Critical
```

## Semantic Coherence Validation

```python
from agent_s3.planner_json_enforced import validate_planning_semantic_coherence

# Validate semantic coherence between planning phase outputs
validation_results = validate_planning_semantic_coherence(
    router_agent=router_agent,
    architecture_review=architecture_review,
    refined_test_specs=test_specs,
    test_implementations=test_implementations,
    implementation_plan=implementation_plan,
    task_description=task_description,
    system_design=system_design
)

# Check validation scores
results = validation_results.get("validation_results", {})
print(f"Coherence score: {results.get('coherence_score', 'N/A')}")
print(f"Technical consistency score: {results.get('technical_consistency_score', 'N/A')}")

# Check security validation
security_validation = results.get("security_validation", {})
print(f"Security validation score: {security_validation.get('score', 'N/A')}")
if security_validation.get("findings"):
    print("Security validation findings:")
    for finding in security_validation["findings"]:
        print(f"- {finding['description']} (Severity: {finding['severity']})")

# Check priority alignment
priority_alignment = results.get("priority_alignment", {})
print(f"Priority alignment score: {priority_alignment.get('score', 'N/A')}")
if priority_alignment.get("findings"):
    print("Priority alignment findings:")
    for finding in priority_alignment["findings"]:
        print(f"- {finding['description']} (Severity: {finding['severity']})")
```

## Integration with Test Specification Refinement

The validation system is automatically integrated into the test specification refinement process. When generating refined test specifications, the system will validate and repair issues:

```python
from agent_s3.planner_json_enforced import generate_refined_test_specifications

# Generate refined test specifications
refined_specs = generate_refined_test_specifications(
    router_agent=router_agent,
    feature_group=feature_group,
    architecture_review=architecture_review,
    task_description=task_description
)

# The refined_specs will automatically have priority issues and element ID issues repaired
print("Refined test specifications generated with automatic validation and repair")
```
