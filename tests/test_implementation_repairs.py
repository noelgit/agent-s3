from agent_s3.tools.implementation_repairs import repair_architecture_issue_coverage


def test_architecture_issues_addressed_unique():
    plan = {
        "file1.py": [
            {"element_id": "E1", "architecture_issues_addressed": []},
            {"element_id": "E2", "architecture_issues_addressed": []},
        ],
        "file2.py": [
            {"element_id": "E1", "architecture_issues_addressed": []},
        ],
    }
    issues = [
        {"issue_type": "unaddressed_critical_issue", "arch_issue_id": "A1"}
    ]
    architecture_review = {
        "logical_gaps": [
            {
                "id": "A1",
                "description": "",
                "severity": "critical",
                "target_element_ids": ["E1", "E2"],
            }
        ]
    }

    repaired = repair_architecture_issue_coverage(plan, issues, architecture_review)

    occurrences = sum(
        "A1" in func.get("architecture_issues_addressed", [])
        for funcs in repaired.values()
        for func in funcs
    )
    assert occurrences == 1

    for funcs in repaired.values():
        for func in funcs:
            ai_list = func.get("architecture_issues_addressed", [])
            assert len(ai_list) == len(set(ai_list))


def test_non_list_target_element_ids_handled():
    plan = {
        "file.py": [
            {"element_id": "E1", "architecture_issues_addressed": []},
        ]
    }
    issues = [{"issue_type": "unaddressed_critical_issue", "arch_issue_id": "A1"}]
    architecture_review = {
        "logical_gaps": [
            {
                "id": "A1",
                "description": "",
                "severity": "critical",
                "target_element_ids": "E1",
            }
        ]
    }

    repaired = repair_architecture_issue_coverage(plan, issues, architecture_review)

    assert repaired["file.py"][0]["architecture_issues_addressed"] == ["A1"]

