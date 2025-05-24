"""Tests for system design validation modules."""
from agent_s3.tools import system_design_validator as sdv
from agent_s3.tools.system_design import (
    is_valid_signature,
    find_circular_dependencies,
    extract_patterns,
)


def test_is_valid_signature():
    assert is_valid_signature("def foo(x):")
    assert not is_valid_signature("foo = lambda x: x")


def test_find_circular_dependencies():
    components = ["A", "B", "C"]
    deps = {("A", "B"): 1, ("B", "C"): 1, ("C", "A"): 1}
    cycles = find_circular_dependencies(components, deps)
    assert ["A", "B", "C", "A"] in cycles


def test_extract_patterns():
    design = {
        "overview": "This uses MVC and repository pattern",
        "code_elements": [],
    }
    patterns = extract_patterns(design)
    assert "Model-View-Controller" in patterns
    assert "Repository Pattern" in patterns


def test_validate_and_repair():
    design = {"overview": "test"}
    reqs = {"functional_requirements": []}
    validated, issues, needs_repair = sdv.validate_system_design(design, reqs)
    assert needs_repair
    repaired = sdv.repair_system_design(validated, issues, reqs)
    assert "code_elements" in repaired
