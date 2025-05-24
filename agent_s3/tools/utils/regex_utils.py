"""Utility helpers for common regex extraction routines."""

import re
from typing import Dict, List


def extract_assertions(test_code: str) -> List[str]:
    """Extract assertion statements from test code."""
    pattern = r"assert\w*\s*\(.*?\)"
    return [match.strip() for match in re.findall(pattern, test_code)]


def extract_edge_cases(test_requirements: List[Dict[str, str]]) -> List[str]:
    """Extract potential edge cases mentioned in test requirements."""
    cases: List[str] = []
    for req in test_requirements:
        name = req.get("test_name", "").lower()
        if any(term in name for term in ["edge", "boundary", "invalid", "null", "empty", "error"]):
            cases.append(name)
        for assertion in req.get("assertions", []):
            text = assertion.lower()
            if any(term in text for term in ["edge", "boundary", "invalid", "null", "empty", "error"]):
                cases.append(assertion)
        for line in req.get("code", "").split("\n"):
            line_lower = line.lower()
            if any(term in line_lower for term in ["edge case", "boundary", "invalid input", "null value", "empty"]):
                start = max(0, line_lower.find("edge"))
                cases.append(line[start:].strip())
    return list(set(cases))


def extract_expected_behaviors(tests: List[Dict[str, str]]) -> List[str]:
    """Collect behavior descriptions from tests."""
    behaviors: List[str] = []
    for test in tests:
        description = test.get("description")
        if description:
            behaviors.append(description)
        for field in ("given", "when", "then"):
            value = test.get(field)
            if value:
                behaviors.append(value)
        for assertion in test.get("assertions", []):
            match = re.search(r',[^,]*[\'\"]([^\'\"]*)[\'\"]', assertion)
            if match:
                behaviors.append(match.group(1).strip())
        for line in test.get("code", "").split("\n"):
            comment_match = re.match(r"\s*#\s*(.+)$", line)
            if comment_match:
                behaviors.append(comment_match.group(1))
            else:
                str_match = re.search(r"[\'\"](?:[\'\"][\'\"]\s*)?([^\'\"]*)(?:[\'\"][\'\"])?\s*[\'\"]", line)
                if str_match:
                    behaviors.append(str_match.group(1).strip())
    return behaviors
