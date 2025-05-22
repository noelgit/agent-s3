"""
Data structure for validation results with metrics and identified issues.
"""
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ValidationResult:
    is_valid: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
