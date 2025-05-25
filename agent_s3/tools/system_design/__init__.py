"""Submodules for system design validation utilities."""

from .structure import (
    validate_code_elements,
    validate_design_requirements_alignment,
    extract_requirement_ids,
    calculate_design_metrics,
    repair_structure,
    repair_code_elements,
    repair_requirements_alignment,
    is_element_related_to_requirement,
)
from .patterns import (
    validate_design_patterns,
    extract_patterns,
    infer_domain_type,
    check_pattern_domain_fit,
    repair_architectural_patterns,
    suggest_patterns_for_domain,
)
from .relationships import (
    validate_component_relationships,
    extract_component_dependencies,
    find_circular_dependencies,
    calculate_coupling_scores,
    check_proper_layering,
    repair_component_relationships,
)
from .constants import ErrorMessages, logger

__all__ = [
    "validate_code_elements",
    "validate_design_requirements_alignment",
    "extract_requirement_ids",
    "calculate_design_metrics",
    "repair_structure",
    "repair_code_elements",
    "repair_requirements_alignment",
    "is_element_related_to_requirement",
    "validate_design_patterns",
    "extract_patterns",
    "infer_domain_type",
    "check_pattern_domain_fit",
    "repair_architectural_patterns",
    "suggest_patterns_for_domain",
    "validate_component_relationships",
    "extract_component_dependencies",
    "find_circular_dependencies",
    "calculate_coupling_scores",
    "check_proper_layering",
    "repair_component_relationships",
    "ErrorMessages",
    "logger",
]
