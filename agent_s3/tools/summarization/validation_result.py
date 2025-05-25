"""
Data structure for validation results with metrics and identified issues.
"""
from typing import Dict
from typing import List

from dataclasses import dataclass
from dataclasses import field

@dataclass
class ValidationResult:
    is_valid: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
