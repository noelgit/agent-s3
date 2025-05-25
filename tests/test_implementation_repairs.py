import pytest

from agent_s3.tools.implementation_repairs import repair_architecture_issue_coverage


def test_repair_architecture_issue_coverage_ignores_non_list():
    plan = {"file.py": {"element_id": "e1"}}
    issues = [
        {"issue_type": "unaddressed_critical_issue", "arch_issue_id": "A1"}
    ]
    architecture_review = {
        "logical_gaps": [
            {"id": "A1", "target_element_ids": ["e1"], "description": ""}
        ]
    }

    repaired = repair_architecture_issue_coverage(plan, issues, architecture_review)
    assert repaired == plan


def test_repair_architecture_issue_coverage_handles_missing_function():
    plan = {}
    issues = [
        {"issue_type": "unaddressed_critical_issue", "arch_issue_id": "A2"}
    ]
    architecture_review = {
        "logical_gaps": [
            {"id": "A2", "target_element_ids": ["missing"], "description": ""}
        ]
    }

    repaired = repair_architecture_issue_coverage(plan, issues, architecture_review)
    assert repaired == {}
