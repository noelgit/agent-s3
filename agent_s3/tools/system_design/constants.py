"""Shared constants for system design validation."""
from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger("agent_s3.system_design")


class ErrorMessages:
    """Centralized error message templates."""

    SYSTEM_NOT_DICT = "System design must be a dictionary"
    MISSING_SECTION = "System design is missing required section: {section}"
    INVALID_CODE_ELEMENTS_FORMAT = "code_elements must be a list, got {type}"
    INVALID_ELEMENT_FORMAT = "Code element at index {index} must be a dictionary"
    MISSING_ELEMENT_FIELD = (
        "Code element at index {index} is missing required field: {field}"
    )
    DUPLICATE_ELEMENT_ID = "Duplicate element_id found: {element_id}"
    INVALID_SIGNATURE = (
        "Invalid signature format for element {element_id}: {signature}"
    )
    MISSING_REQUIREMENT_COVERAGE = (
        "System design does not address these requirements: {requirements}"
    )
    LOW_REQUIREMENTS_COVERAGE = (
        "Requirements coverage is only {coverage:.1%}, below the 90% threshold"
    )
    TOO_MANY_PATTERNS = (
        "Design uses too many architectural patterns ({count}), which may lead to inconsistency"
    )
    INAPPROPRIATE_PATTERNS = (
        "Some patterns may not be appropriate for {domain} domain: {patterns}"
    )
    CIRCULAR_DEPENDENCY = "Circular dependency detected: {cycle}"
    EXCESSIVE_COUPLING = "Component {component} has excessive coupling (score: {score:.2f})"
    IMPROPER_LAYERING_HIGHER = (
        "Improper dependency: {from_component} (higher layer) -> {to_component} (lower layer)"
    )
    IMPROPER_LAYERING_LOWER = (
        "Improper dependency: {from_component} (lower layer) -> {to_component} (higher layer)"
    )
    LOW_DESIGN_SCORE = (
        "Overall design quality score ({score:.2f}) is below threshold (0.7)"
    )
