"""Architectural pattern validation utilities."""
from __future__ import annotations

from collections import defaultdict
import json
from typing import Any, Dict, List, Set

from .constants import ErrorMessages
from ...config import get_config


def validate_design_patterns(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ensure appropriate architectural patterns are used.

    Uses ``config.max_design_patterns`` to enforce a limit on the number of
    architectural patterns allowed in ``system_design``.
    """
    issues: List[Dict[str, Any]] = []
    patterns = extract_patterns(system_design)
    max_allowed = get_config().max_design_patterns
    if len(patterns) > max_allowed:
        issues.append(
            {
                "issue_type": "too_many_patterns",
                "severity": "medium",
                "description": ErrorMessages.TOO_MANY_PATTERNS.format(count=len(patterns)),
                "patterns": list(patterns),
            }
        )
    domain_type = infer_domain_type(system_design)
    inappropriate = check_pattern_domain_fit(patterns, domain_type)
    if inappropriate:
        issues.append(
            {
                "issue_type": "inappropriate_patterns",
                "severity": "medium",
                "description": ErrorMessages.INAPPROPRIATE_PATTERNS.format(
                    domain=domain_type, patterns=", ".join(inappropriate)
                ),
                "domain_type": domain_type,
                "inappropriate_patterns": inappropriate,
            }
        )
    return issues


def extract_patterns(system_design: Dict[str, Any]) -> Set[str]:
    """Extract architectural patterns from the system design."""
    patterns: Set[str] = set()
    keywords = {
        "mvc": "Model-View-Controller",
        "mvvm": "Model-View-ViewModel",
        "repository": "Repository Pattern",
        "factory": "Factory Pattern",
        "singleton": "Singleton Pattern",
        "observer": "Observer Pattern",
        "strategy": "Strategy Pattern",
        "adapter": "Adapter Pattern",
        "facade": "Facade Pattern",
        "decorator": "Decorator Pattern",
        "command": "Command Pattern",
        "mediator": "Mediator Pattern",
        "microservice": "Microservice Architecture",
        "layered": "Layered Architecture",
        "event-driven": "Event-Driven Architecture",
        "serverless": "Serverless Architecture",
        "cqrs": "Command Query Responsibility Segregation",
        "ddd": "Domain-Driven Design",
        "clean architecture": "Clean Architecture",
        "hexagonal": "Hexagonal Architecture",
    }
    overview = system_design.get("overview", "").lower()
    for keyword, name in keywords.items():
        if keyword in overview:
            patterns.add(name)
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            description = element.get("description", "").lower()
            signature = element.get("signature", "").lower()
            for keyword, name in keywords.items():
                if keyword in description or keyword in signature:
                    patterns.add(name)
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict) and "target_file" in element:
            file_path = element.get("target_file", "").lower()
            if "/controllers/" in file_path:
                patterns.add("Model-View-Controller")
            elif "/repositories/" in file_path:
                patterns.add("Repository Pattern")
            elif "/factories/" in file_path:
                patterns.add("Factory Pattern")
            elif "/services/" in file_path or "/providers/" in file_path:
                patterns.add("Service Pattern")
            elif "/adapters/" in file_path:
                patterns.add("Adapter Pattern")
            elif "/decorators/" in file_path:
                patterns.add("Decorator Pattern")
            elif "/commands/" in file_path:
                patterns.add("Command Pattern")
            elif "/observers/" in file_path:
                patterns.add("Observer Pattern")
    return patterns


def infer_domain_type(system_design: Dict[str, Any]) -> str:
    """Infer the domain type from the system design."""
    overview = system_design.get("overview", "").lower()
    domain_indicators = {
        "web application": ["web", "browser", "http", "html", "css", "frontend"],
        "api service": ["api", "rest", "graphql", "endpoint", "microservice"],
        "data processing": ["data", "processing", "etl", "pipeline", "analytics"],
        "mobile application": ["mobile", "android", "ios", "app"],
        "desktop application": ["desktop", "gui", "electron"],
        "embedded system": ["embedded", "iot", "device", "hardware"],
        "ml system": ["machine learning", "ml", "model", "training", "inference"],
    }
    scores = defaultdict(int)
    for domain, indicators in domain_indicators.items():
        for indicator in indicators:
            if indicator in overview:
                scores[domain] += 1
        for element in system_design.get("code_elements", []):
            if not isinstance(element, dict):
                continue
            description = element.get("description", "").lower()
            signature = element.get("signature", "").lower()
            if indicator in description or indicator in signature:
                scores[domain] += 0.5
    if not scores:
        return "general"
    return max(scores, key=scores.get)


def check_pattern_domain_fit(patterns: Set[str], domain_type: str) -> List[str]:
    """Check if the patterns are appropriate for the given domain type."""
    mismatches = {
        "web application": ["Command Pattern", "Adapter Pattern"],
        "api service": ["Model-View-Controller", "Model-View-ViewModel"],
        "data processing": ["Model-View-Controller", "Model-View-ViewModel"],
        "mobile application": ["Microservice Architecture"],
        "embedded system": ["Microservice Architecture", "Serverless Architecture"],
    }
    inappropriate: List[str] = []
    if domain_type in mismatches:
        for pattern in patterns:
            if pattern in mismatches[domain_type]:
                inappropriate.append(pattern)
    return inappropriate


# Repair helpers

def repair_architectural_patterns(
    system_design: Dict[str, Any], issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair architectural pattern issues in the system design."""
    repaired = json.loads(json.dumps(system_design))
    if "overview" in repaired and isinstance(repaired["overview"], str):
        for issue in issues:
            if issue.get("issue_type") == "too_many_patterns":
                patterns = issue.get("patterns", [])
                if patterns:
                    dominant = patterns[:2]
                    note = (
                        "\nArchitectural pattern recommendation: Focus on a smaller set of patterns "
                        f"such as {' and '.join(dominant)} for more consistency."
                    )
                    if note not in repaired["overview"]:
                        repaired["overview"] += note
            elif issue.get("issue_type") == "inappropriate_patterns":
                domain = issue.get("domain_type", "")
                inappropriate = issue.get("inappropriate_patterns", [])
                if domain and inappropriate:
                    suggestions = suggest_patterns_for_domain(domain)
                    if suggestions:
                        note = (
                            f"\nFor {domain} domain, consider using {', '.join(suggestions)} patterns instead of {', '.join(inappropriate)}."
                        )
                        if note not in repaired["overview"]:
                            repaired["overview"] += note
    return repaired


def suggest_patterns_for_domain(domain: str) -> List[str]:
    """Suggest appropriate patterns for a given domain."""
    domain_pattern_suggestions = {
        "web application": ["Model-View-Controller", "Component-Based Architecture", "Repository Pattern"],
        "api service": ["Layered Architecture", "Repository Pattern", "Dependency Injection"],
        "data processing": ["Pipeline Pattern", "Repository Pattern", "Command Pattern"],
        "mobile application": ["MVVM", "Repository Pattern", "Observer Pattern"],
        "desktop application": ["MVC", "MVVM", "Observer Pattern"],
        "embedded system": ["State Pattern", "Observer Pattern", "Command Pattern"],
        "ml system": ["Pipeline Pattern", "Strategy Pattern", "Factory Pattern"],
    }
    return domain_pattern_suggestions.get(domain, ["Layered Architecture", "Repository Pattern"])
