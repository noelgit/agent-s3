
from agent_s3.tools.utils import (
    find_best_match,
    extract_assertions,
    extract_edge_cases,
    extract_expected_behaviors,
)


def test_find_best_match():
    candidates = {"alpha", "beta", "gamma"}
    assert find_best_match("alp", candidates) == "alpha"
    assert find_best_match("bet", candidates) == "beta"
    assert find_best_match("unknown", candidates) is None


def test_extract_assertions():
    code = """
    def test():
        assert foo == 1
        assertTrue(bar)
    """
    assertions = extract_assertions(code)
    assert "assertTrue(bar)" in assertions
    assert len(assertions) == 1


def test_extract_edge_cases():
    tests = [
        {"test_name": "handles edge case", "assertions": [], "code": ""},
        {"test_name": "normal", "assertions": ["assert fail"], "code": "# edge case"},
    ]
    cases = extract_edge_cases(tests)
    assert any("edge" in c for c in cases)


def test_extract_expected_behaviors():
    tests = [
        {
            "description": "should work",
            "given": "user logged in",
            "when": "action",
            "then": "result",
            "assertions": ["assert 1 == 1, \"ok\""],
            "code": "# comment",
        }
    ]
    behaviors = extract_expected_behaviors(tests)
    assert "should work" in behaviors
    assert "user logged in" in behaviors
    assert "result" in behaviors
    assert "ok" in behaviors
    assert "comment" in behaviors

