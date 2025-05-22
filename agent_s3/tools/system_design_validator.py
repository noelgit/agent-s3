"""
System Design Validator Module

This module provides validation and repair functions for system designs.
It focuses on ensuring system designs are structurally correct, comprehensively address
requirements, and follow appropriate architectural patterns and component relationships.
"""

import json
import logging
import re
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class SystemDesignValidationError(Exception):
    """Exception raised when validation of system designs fails."""
    pass


def validate_system_design(
    system_design: Dict[str, Any],
    requirements: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """
    Validate system design against requirements.
    
    Args:
        system_design: The system design to validate
        requirements: The requirements data
        
    Returns:
        Tuple of (validated_design, validation_issues, needs_repair)
    """
    validation_issues = []
    needs_repair = False
    
    # Create a deep copy of system design for potential repairs
    validated_design = json.loads(json.dumps(system_design))
    
    # Validate overall structure
    if not isinstance(system_design, dict):
        validation_issues.append({
            "issue_type": "structure",
            "severity": "critical",
            "description": "System design must be a dictionary"
        })
        needs_repair = True
        return validated_design, validation_issues, needs_repair
    
    # Check for basic sections
    required_sections = ["overview", "code_elements", "data_flow"]
    for section in required_sections:
        if section not in system_design:
            validation_issues.append({
                "issue_type": "missing_section",
                "severity": "critical",
                "description": f"System design is missing required section: {section}",
                "section": section
            })
            needs_repair = True
            
    # Validate code elements
    code_elements_issues = _validate_code_elements(system_design)
    validation_issues.extend(code_elements_issues)
    if any(issue["severity"] in ["critical", "high"] for issue in code_elements_issues):
        needs_repair = True
    
    # Validate design against requirements
    requirements_issues = _validate_design_requirements_alignment(system_design, requirements)
    validation_issues.extend(requirements_issues)
    if any(issue["severity"] in ["critical", "high"] for issue in requirements_issues):
        needs_repair = True
    
    # Validate architectural patterns
    pattern_issues = _validate_design_patterns(system_design)
    validation_issues.extend(pattern_issues)
    if any(issue["severity"] in ["critical", "high"] for issue in pattern_issues):
        needs_repair = True
    
    # Validate component relationships
    relationship_issues = _validate_component_relationships(system_design)
    validation_issues.extend(relationship_issues)
    if any(issue["severity"] in ["critical", "high"] for issue in relationship_issues):
        needs_repair = True
    
    # Calculate design quality metrics
    metrics = _calculate_design_metrics(system_design, requirements)
    
    # Check if quality is below threshold
    if metrics["overall_score"] < 0.7:
        validation_issues.append({
            "issue_type": "low_design_quality",
            "severity": "high",
            "description": f"Overall design quality score ({metrics['overall_score']:.2f}) is below threshold (0.7)",
            "metrics": metrics
        })
        needs_repair = True
    
    return validated_design, validation_issues, needs_repair


def repair_system_design(
    system_design: Dict[str, Any],
    validation_issues: List[Dict[str, Any]],
    requirements: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Attempt to repair system design based on validation issues.
    
    Args:
        system_design: The system design to repair
        validation_issues: List of validation issues to address
        requirements: The requirements data
        
    Returns:
        Repaired system design
    """
    # Create a deep copy for repairs
    repaired_design = json.loads(json.dumps(system_design))
    
    # Ensure the basic structure exists
    if not isinstance(repaired_design, dict):
        repaired_design = {}
    
    # Group issues by type for targeted repairs
    issues_by_type = defaultdict(list)
    for issue in validation_issues:
        issues_by_type[issue.get("issue_type", "")].append(issue)
    
    # Fix structural issues first
    if "structure" in issues_by_type or any(t.startswith("missing_section") for t in issues_by_type):
        repaired_design = _repair_structure(repaired_design)
    
    # Fix code elements issues
    code_element_issue_types = [
        "missing_element_id", 
        "duplicate_element_id", 
        "invalid_element_signature",
        "missing_element_description"
    ]
    
    if any(t in issues_by_type for t in code_element_issue_types):
        repaired_design = _repair_code_elements(repaired_design, issues_by_type)
    
    # Fix requirements alignment issues
    if "missing_requirement_coverage" in issues_by_type:
        repaired_design = _repair_requirements_alignment(
            repaired_design,
            issues_by_type["missing_requirement_coverage"],
            requirements
        )
    
    # Fix component relationship issues
    relationship_issue_types = [
        "circular_dependency",
        "excessive_coupling",
        "missing_relationship"
    ]
    
    if any(t in issues_by_type for t in relationship_issue_types):
        relationship_issues = []
        for issue_type in relationship_issue_types:
            if issue_type in issues_by_type:
                relationship_issues.extend(issues_by_type[issue_type])
        
        repaired_design = _repair_component_relationships(repaired_design, relationship_issues)
    
    # Fix architectural pattern issues
    if "inconsistent_pattern" in issues_by_type:
        repaired_design = _repair_architectural_patterns(
            repaired_design,
            issues_by_type["inconsistent_pattern"]
        )
    
    return repaired_design


def _validate_code_elements(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate code elements in the system design."""
    issues = []
    
    if "code_elements" not in system_design:
        return issues  # Already handled by missing_section check
    
    code_elements = system_design.get("code_elements", [])
    if not isinstance(code_elements, list):
        issues.append({
            "issue_type": "invalid_code_elements_format",
            "severity": "critical",
            "description": f"code_elements must be a list, got {type(code_elements)}"
        })
        return issues
    
    # Check for required fields and uniqueness of element_ids
    element_ids = set()
    for idx, element in enumerate(code_elements):
        if not isinstance(element, dict):
            issues.append({
                "issue_type": "invalid_element_format",
                "severity": "critical",
                "description": f"Code element at index {idx} must be a dictionary",
                "index": idx
            })
            continue
        
        # Check required fields
        for field in ["element_id", "signature", "description"]:
            if field not in element:
                issues.append({
                    "issue_type": f"missing_element_{field}",
                    "severity": "high",
                    "description": f"Code element at index {idx} is missing required field: {field}",
                    "index": idx
                })
        
        # Check element_id uniqueness
        element_id = element.get("element_id")
        if element_id:
            if element_id in element_ids:
                issues.append({
                    "issue_type": "duplicate_element_id",
                    "severity": "critical",
                    "description": f"Duplicate element_id found: {element_id}",
                    "element_id": element_id
                })
            else:
                element_ids.add(element_id)
        
        # Check signature format
        signature = element.get("signature", "")
        if signature and not _is_valid_signature(signature):
            issues.append({
                "issue_type": "invalid_element_signature",
                "severity": "high",
                "description": f"Invalid signature format for element {element_id}: {signature}",
                "element_id": element_id,
                "signature": signature
            })
    
    return issues


def _is_valid_signature(signature: str) -> bool:
    """Check if a signature has a valid format."""
    # Function signature patterns
    function_patterns = [
        r'def\s+\w+\s*\([^)]*\)\s*(?:->.*)?:',  # Python function
        r'function\s+\w+\s*\([^)]*\)\s*{',       # JavaScript function
        r'async\s+function\s+\w+\s*\([^)]*\)',   # Async JS function
        r'const\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',  # Arrow function
        r'public\s+(?:static\s+)?(?:\w+\s+)+\w+\s*\([^)]*\)',  # Java/C# method
        r'class\s+\w+',                          # Class definition
        r'interface\s+\w+',                      # Interface definition
        r'\w+\([^)]*\)\s*{\s*',                  # C-style function
        r'@\w+(?:\([^)]*\))?\s*\n\s*def',        # Python decorated function
    ]
    
    for pattern in function_patterns:
        if re.search(pattern, signature):
            return True
            
    return False


def _validate_design_requirements_alignment(
    system_design: Dict[str, Any],
    requirements: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Check if system design satisfies all requirements."""
    issues = []
    
    # Extract requirements
    requirement_ids = _extract_requirement_ids(requirements)
    
    # Extract requirement coverage from the system design
    covered_requirements = set()
    
    # Check code elements for requirement coverage
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            # Check if there's an explicit requirements_addressed field
            if "requirements_addressed" in element:
                addressed = element.get("requirements_addressed", [])
                if isinstance(addressed, list):
                    covered_requirements.update(addressed)
            
            # Check descriptions for requirement mentions
            description = element.get("description", "")
            if description:
                for req_id in requirement_ids:
                    if req_id in description:
                        covered_requirements.add(req_id)
    
    # Check overview for requirement coverage
    overview = system_design.get("overview", "")
    if isinstance(overview, str):
        for req_id in requirement_ids:
            if req_id in overview:
                covered_requirements.add(req_id)
    
    # Identify requirements that aren't covered
    missing_requirements = requirement_ids - covered_requirements
    if missing_requirements:
        issues.append({
            "issue_type": "missing_requirement_coverage",
            "severity": "high",
            "description": f"System design does not address these requirements: {', '.join(missing_requirements)}",
            "missing_requirements": list(missing_requirements)
        })
    
    # Calculate coverage percentage
    if requirement_ids:
        coverage = len(covered_requirements) / len(requirement_ids)
        if coverage < 0.9:  # 90% coverage threshold
            issues.append({
                "issue_type": "low_requirements_coverage",
                "severity": "medium",
                "description": f"Requirements coverage is only {coverage:.1%}, below the 90% threshold",
                "coverage": coverage,
                "covered_count": len(covered_requirements),
                "total_count": len(requirement_ids)
            })
    
    return issues


def _extract_requirement_ids(requirements: Dict[str, Any]) -> Set[str]:
    """Extract requirement IDs from the requirements data."""
    requirement_ids = set()
    
    # This extraction logic will depend on the structure of your requirements
    # Here's a generic implementation that assumes requirements are in a list
    if "functional_requirements" in requirements:
        for req in requirements["functional_requirements"]:
            if isinstance(req, dict) and "id" in req:
                requirement_ids.add(req["id"])
    
    if "non_functional_requirements" in requirements:
        for req in requirements["non_functional_requirements"]:
            if isinstance(req, dict) and "id" in req:
                requirement_ids.add(req["id"])
    
    return requirement_ids


def _validate_design_patterns(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ensure appropriate architectural patterns are used."""
    issues = []
    
    # Extract patterns used in the design
    patterns = _extract_patterns(system_design)
    
    # Check for pattern consistency
    if len(patterns) > 3:  # Too many patterns might indicate inconsistency
        issues.append({
            "issue_type": "too_many_patterns",
            "severity": "medium",
            "description": f"Design uses too many architectural patterns ({len(patterns)}), which may lead to inconsistency",
            "patterns": list(patterns)
        })
    
    # Check if patterns are appropriate for the domain
    # This would require domain-specific knowledge, so here's a simplified check
    domain_type = _infer_domain_type(system_design)
    inappropriate_patterns = _check_pattern_domain_fit(patterns, domain_type)
    
    if inappropriate_patterns:
        issues.append({
            "issue_type": "inappropriate_patterns",
            "severity": "medium",
            "description": f"Some patterns may not be appropriate for {domain_type} domain: {', '.join(inappropriate_patterns)}",
            "domain_type": domain_type,
            "inappropriate_patterns": inappropriate_patterns
        })
    
    return issues


def _extract_patterns(system_design: Dict[str, Any]) -> Set[str]:
    """Extract architectural patterns from the system design."""
    patterns = set()
    
    # Common pattern keywords to look for
    pattern_keywords = {
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
        "hexagonal": "Hexagonal Architecture"
    }
    
    # Search for pattern mentions in overview
    overview = system_design.get("overview", "").lower()
    for keyword, pattern_name in pattern_keywords.items():
        if keyword in overview:
            patterns.add(pattern_name)
    
    # Check code elements for pattern indicators
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            description = element.get("description", "").lower()
            signature = element.get("signature", "").lower()
            
            for keyword, pattern_name in pattern_keywords.items():
                if keyword in description or keyword in signature:
                    patterns.add(pattern_name)
    
    # Check file structure for pattern indicators
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


def _infer_domain_type(system_design: Dict[str, Any]) -> str:
    """Infer the domain type from the system design."""
    # This is a simplified inference - real implementation would be more sophisticated
    overview = system_design.get("overview", "").lower()
    
    domain_indicators = {
        "web application": ["web", "browser", "http", "html", "css", "frontend"],
        "api service": ["api", "rest", "graphql", "endpoint", "microservice"],
        "data processing": ["data", "processing", "etl", "pipeline", "analytics"],
        "mobile application": ["mobile", "android", "ios", "app"],
        "desktop application": ["desktop", "gui", "electron"],
        "embedded system": ["embedded", "iot", "device", "hardware"],
        "ml system": ["machine learning", "ml", "model", "training", "inference"]
    }
    
    scores = defaultdict(int)
    
    for domain, indicators in domain_indicators.items():
        for indicator in indicators:
            if indicator in overview:
                scores[domain] += 1
        
        # Check code elements for domain indicators
        for element in system_design.get("code_elements", []):
            if not isinstance(element, dict):
                continue
                
            description = element.get("description", "").lower()
            signature = element.get("signature", "").lower()
            
            for indicator in indicators:
                if indicator in description or indicator in signature:
                    scores[domain] += 0.5
    
    if not scores:
        return "general"
        
    return max(scores, key=scores.get)


def _check_pattern_domain_fit(patterns: Set[str], domain_type: str) -> List[str]:
    """Check if the patterns are appropriate for the given domain type."""
    inappropriate_patterns = []
    
    # Simplified check - real implementation would have more nuanced rules
    domain_pattern_mismatches = {
        "web application": ["Command Pattern", "Adapter Pattern"],  # These are not necessarily bad, just examples
        "api service": ["Model-View-Controller", "Model-View-ViewModel"],
        "data processing": ["Model-View-Controller", "Model-View-ViewModel"],
        "mobile application": ["Microservice Architecture"],
        "embedded system": ["Microservice Architecture", "Serverless Architecture"],
    }
    
    if domain_type in domain_pattern_mismatches:
        for pattern in patterns:
            if pattern in domain_pattern_mismatches[domain_type]:
                inappropriate_patterns.append(pattern)
    
    return inappropriate_patterns


def _validate_component_relationships(system_design: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Verify relationships between components are appropriate."""
    issues = []
    
    # Extract component relationships
    components, dependencies = _extract_component_dependencies(system_design)
    
    # Check for circular dependencies
    circular_deps = _find_circular_dependencies(components, dependencies)
    for cycle in circular_deps:
        issues.append({
            "issue_type": "circular_dependency",
            "severity": "high",
            "description": f"Circular dependency detected: {' -> '.join(cycle)}",
            "components": cycle
        })
    
    # Check for excessive coupling
    coupling_scores = _calculate_coupling_scores(components, dependencies)
    for component, score in coupling_scores.items():
        if score > 0.7:  # Threshold for excessive coupling
            coupled_with = [other for other in components if other != component and 
                           (dependencies.get((component, other)) or dependencies.get((other, component)))]
            
            issues.append({
                "issue_type": "excessive_coupling",
                "severity": "medium",
                "description": f"Component {component} has excessive coupling (score: {score:.2f})",
                "component": component,
                "coupling_score": score,
                "coupled_with": coupled_with
            })
    
    # Check for proper layering (e.g., controllers shouldn't depend on data access)
    layering_issues = _check_proper_layering(components, dependencies)
    issues.extend(layering_issues)
    
    return issues


def _extract_component_dependencies(system_design: Dict[str, Any]) -> Tuple[List[str], Dict[Tuple[str, str], int]]:
    """Extract component dependencies from the system design."""
    components = []
    dependencies = {}  # (from_component, to_component) -> strength
    
    # Extract component names from code elements
    element_id_to_component = {}
    for element in system_design.get("code_elements", []):
        if not isinstance(element, dict) or "element_id" not in element:
            continue
            
        element_id = element["element_id"]
        
        # Infer component from file path or element type
        component = None
        if "target_file" in element:
            file_path = element["target_file"]
            parts = file_path.split("/")
            if len(parts) > 1:
                component = parts[-2]  # Use parent directory as component name
        
        if not component and "signature" in element:
            signature = element["signature"]
            if "class" in signature.lower():
                match = re.search(r'class\s+(\w+)', signature)
                if match:
                    component = match.group(1)
        
        if not component:
            component = element_id  # Use element_id as fallback
            
        if component not in components:
            components.append(component)
            
        element_id_to_component[element_id] = component
    
    # Extract dependencies from data_flow
    for flow in system_design.get("data_flow", []):
        if not isinstance(flow, dict):
            continue
            
        from_element = flow.get("from")
        to_element = flow.get("to")
        
        if from_element in element_id_to_component and to_element in element_id_to_component:
            from_component = element_id_to_component[from_element]
            to_component = element_id_to_component[to_element]
            
            if from_component != to_component:  # Ignore self-dependencies
                key = (from_component, to_component)
                dependencies[key] = dependencies.get(key, 0) + 1
    
    return components, dependencies


def _find_circular_dependencies(
    components: List[str], 
    dependencies: Dict[Tuple[str, str], int]
) -> List[List[str]]:
    """Find circular dependencies in the component graph."""
    # Build adjacency list
    graph = defaultdict(list)
    for (from_comp, to_comp), _ in dependencies.items():
        graph[from_comp].append(to_comp)
    
    # Find cycles using DFS
    cycles = []
    
    def find_cycles_dfs(node, path, visited):
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        
        if node in visited:
            return
            
        visited.add(node)
        path.append(node)
        
        for neighbor in graph.get(node, []):
            find_cycles_dfs(neighbor, path, visited)
            
        path.pop()
    
    for component in components:
        find_cycles_dfs(component, [], set())
    
    return cycles


def _calculate_coupling_scores(
    components: List[str], 
    dependencies: Dict[Tuple[str, str], int]
) -> Dict[str, float]:
    """Calculate coupling scores for each component."""
    scores = {}
    
    if not components:
        return scores
    
    max_possible_deps = len(components) - 1  # Maximum possible dependencies
    if max_possible_deps == 0:
        return {comp: 0 for comp in components}
    
    # Count outgoing and incoming dependencies
    outgoing = defaultdict(int)
    incoming = defaultdict(int)
    
    for (from_comp, to_comp), strength in dependencies.items():
        outgoing[from_comp] += 1
        incoming[to_comp] += 1
    
    # Calculate coupling score as (outgoing + incoming) / max_possible
    for component in components:
        total_deps = outgoing[component] + incoming[component]
        scores[component] = total_deps / (2 * max_possible_deps)  # Normalize to 0-1
    
    return scores


def _check_proper_layering(
    components: List[str], 
    dependencies: Dict[Tuple[str, str], int]
) -> List[Dict[str, Any]]:
    """Check for proper layering in the architecture."""
    issues = []
    
    # Define layering rules
    layer_rules = [
        # format: (higher_layer_pattern, lower_layer_pattern, allowed_direction)
        # allowed_direction: True means higher->lower is allowed, False means lower->higher is allowed
        (r'controller|api|rest|endpoint', r'service|business|domain', True),
        (r'service|business|domain', r'repository|dao|data', True),
        (r'repository|dao|data', r'controller|api|rest|endpoint', False),
    ]
    
    # Check each dependency against layering rules
    for (from_comp, to_comp), _ in dependencies.items():
        from_comp_lower = from_comp.lower()
        to_comp_lower = to_comp.lower()
        
        for higher_pattern, lower_pattern, higher_to_lower in layer_rules:
            is_from_higher = re.search(higher_pattern, from_comp_lower) is not None
            is_to_higher = re.search(higher_pattern, to_comp_lower) is not None
            is_from_lower = re.search(lower_pattern, from_comp_lower) is not None
            is_to_lower = re.search(lower_pattern, to_comp_lower) is not None
            
            if is_from_higher and is_to_lower:
                # Higher layer depends on lower layer - this is fine if higher_to_lower is True
                if not higher_to_lower:
                    issues.append({
                        "issue_type": "improper_layering",
                        "severity": "medium",
                        "description": f"Improper dependency: {from_comp} (higher layer) -> {to_comp} (lower layer)",
                        "from_component": from_comp,
                        "to_component": to_comp,
                        "violated_rule": f"{higher_pattern} should not depend on {lower_pattern}"
                    })
            elif is_from_lower and is_to_higher:
                # Lower layer depends on higher layer - this is fine if higher_to_lower is False
                if higher_to_lower:
                    issues.append({
                        "issue_type": "improper_layering",
                        "severity": "medium",
                        "description": f"Improper dependency: {from_comp} (lower layer) -> {to_comp} (higher layer)",
                        "from_component": from_comp,
                        "to_component": to_comp,
                        "violated_rule": f"{lower_pattern} should not depend on {higher_pattern}"
                    })
    
    return issues


def _calculate_design_metrics(
    system_design: Dict[str, Any],
    requirements: Dict[str, Any]
) -> Dict[str, float]:
    """
    Calculate quality metrics for the system design.
    
    Metrics include:
    - requirements_coverage_score: Percentage of requirements covered by design elements
    - design_cohesion_score: Measure of related functionality grouping
    - design_coupling_score: Measure of appropriate coupling between components
    - overall_score: Combined weighted score of all metrics
    
    Args:
        system_design: The system design to score
        requirements: The requirements data
        
    Returns:
        Dictionary of metric scores (0.0 to 1.0)
    """
    metrics = {}
    
    # Calculate requirements coverage
    requirement_ids = _extract_requirement_ids(requirements)
    covered_requirements = set()
    
    # Check code elements for requirement coverage
    for element in system_design.get("code_elements", []):
        if isinstance(element, dict):
            # Check explicit requirements addressed
            if "requirements_addressed" in element:
                addressed = element.get("requirements_addressed", [])
                if isinstance(addressed, list):
                    covered_requirements.update(addressed)
            
            # Check descriptions
            description = element.get("description", "")
            if description:
                for req_id in requirement_ids:
                    if req_id in description:
                        covered_requirements.add(req_id)
    
    # Calculate requirements coverage score
    if requirement_ids:
        metrics["requirements_coverage_score"] = len(covered_requirements) / len(requirement_ids)
    else:
        metrics["requirements_coverage_score"] = 1.0
    
    # Calculate design cohesion and coupling scores
    components, dependencies = _extract_component_dependencies(system_design)
    
    # Cohesion score - based on how well related functionality is grouped
    # Here we use a simplified approach - higher is better
    if components:
        # Calculate average number of dependencies within the same component
        internal_deps = 0
        total_deps = 0
        
        # Count internal vs. external dependencies
        for element in system_design.get("code_elements", []):
            if not isinstance(element, dict) or "element_id" not in element:
                continue
                
            element_id = element["element_id"]
            element_component = None
            
            # Find which component this element belongs to
            for comp_name in components:
                if comp_name in element_id or (
                    "target_file" in element and 
                    comp_name in element["target_file"]
                ):
                    element_component = comp_name
                    break
            
            if not element_component:
                continue
                
            # Check dependencies
            for flow in system_design.get("data_flow", []):
                if not isinstance(flow, dict):
                    continue
                    
                if flow.get("from") == element_id:
                    total_deps += 1
                    
                    # Check if target is in the same component
                    to_element = flow.get("to")
                    to_component = None
                    
                    for other_element in system_design.get("code_elements", []):
                        if isinstance(other_element, dict) and other_element.get("element_id") == to_element:
                            for comp_name in components:
                                if comp_name in to_element or (
                                    "target_file" in other_element and 
                                    comp_name in other_element["target_file"]
                                ):
                                    to_component = comp_name
                                    break
                            break
                    
                    if to_component == element_component:
                        internal_deps += 1
        
        cohesion_score = internal_deps / max(total_deps, 1)
        # Adjust score to favor higher cohesion
        metrics["design_cohesion_score"] = min(1.0, cohesion_score * 1.2)
    else:
        metrics["design_cohesion_score"] = 0.0
    
    # Coupling score - based on appropriate level of coupling
    coupling_scores = _calculate_coupling_scores(components, dependencies)
    if coupling_scores:
        # Ideal coupling is neither too high nor too low
        # We define ideal as around 0.3-0.4
        avg_coupling = sum(coupling_scores.values()) / len(coupling_scores)
        
        # Penalize deviation from ideal range
        ideal_min, ideal_max = 0.2, 0.4
        
        if avg_coupling < ideal_min:
            # Too little coupling might indicate disconnected components
            metrics["design_coupling_score"] = avg_coupling / ideal_min
        elif avg_coupling > ideal_max:
            # Too much coupling indicates poor separation of concerns
            excess = avg_coupling - ideal_max
            metrics["design_coupling_score"] = max(0, 1 - (excess / 0.6))
        else:
            # Within ideal range
            metrics["design_coupling_score"] = 1.0
    else:
        metrics["design_coupling_score"] = 0.0
    
    # Calculate overall design quality score
    weights = {
        "requirements_coverage_score": 0.5,
        "design_cohesion_score": 0.25,
        "design_coupling_score": 0.25
    }
    
    overall_score = sum(metrics[metric] * weight for metric, weight in weights.items())
    metrics["overall_score"] = overall_score
    
    return metrics


def _repair_structure(system_design: Dict[str, Any]) -> Dict[str, Any]:
    """Repair the basic structure of the system design."""
    repaired_design = system_design.copy() if isinstance(system_design, dict) else {}
    
    # Ensure required sections exist
    required_sections = ["overview", "code_elements", "data_flow"]
    for section in required_sections:
        if section not in repaired_design:
            if section == "overview":
                repaired_design[section] = "System design overview"
            elif section == "code_elements":
                repaired_design[section] = []
            elif section == "data_flow":
                repaired_design[section] = []
    
    return repaired_design


def _repair_code_elements(
    system_design: Dict[str, Any],
    issues_by_type: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Repair code elements in the system design."""
    repaired_design = json.loads(json.dumps(system_design))
    
    # Ensure code_elements is a list
    if "code_elements" not in repaired_design or not isinstance(repaired_design["code_elements"], list):
        repaired_design["code_elements"] = []
    
    # Fix issues with existing elements
    if repaired_design["code_elements"]:
        # Fix missing element IDs
        if "missing_element_id" in issues_by_type:
            for issue in issues_by_type["missing_element_id"]:
                idx = issue.get("index")
                if idx is not None and idx < len(repaired_design["code_elements"]):
                    element = repaired_design["code_elements"][idx]
                    if isinstance(element, dict) and "element_id" not in element:
                        # Generate a unique element ID
                        base_id = "element"
                        if "signature" in element:
                            sig = element["signature"]
                            match = re.search(r'\b(\w+)\s*\(', sig)
                            if match:
                                base_id = match.group(1)
                        
                        # Ensure uniqueness
                        existing_ids = {e["element_id"] for e in repaired_design["code_elements"] 
                                      if isinstance(e, dict) and "element_id" in e}
                        
                        element_id = base_id
                        counter = 1
                        while element_id in existing_ids:
                            element_id = f"{base_id}_{counter}"
                            counter += 1
                            
                        element["element_id"] = element_id
        
        # Fix invalid signatures
        if "invalid_element_signature" in issues_by_type:
            for issue in issues_by_type["invalid_element_signature"]:
                element_id = issue.get("element_id")
                if element_id:
                    for element in repaired_design["code_elements"]:
                        if isinstance(element, dict) and element.get("element_id") == element_id:
                            old_sig = element.get("signature", "")
                            
                            # Try to repair the signature
                            if "def" in old_sig and ":" not in old_sig:
                                element["signature"] = old_sig + ":"
                            elif "function" in old_sig and "{" not in old_sig:
                                element["signature"] = old_sig + " {"
                            elif "class" in old_sig and ":" not in old_sig:
                                element["signature"] = old_sig + ":"
    
    return repaired_design


def _repair_requirements_alignment(
    system_design: Dict[str, Any],
    issues: List[Dict[str, Any]],
    requirements: Dict[str, Any]
) -> Dict[str, Any]:
    """Repair requirements alignment issues in the system design."""
    repaired_design = json.loads(json.dumps(system_design))
    
    # Add missing requirement references
    for issue in issues:
        missing_reqs = issue.get("missing_requirements", [])
        
        if not missing_reqs:
            continue
            
        # Add missing requirements to the design
        for req_id in missing_reqs:
            # Find or create an appropriate code element for this requirement
            added = False
            
            # First try to find a related element to attach this requirement to
            for element in repaired_design.get("code_elements", []):
                if not isinstance(element, dict):
                    continue
                    
                # Check if this element might be related to the requirement
                if _is_element_related_to_requirement(element, req_id, requirements):
                    # Add to requirements_addressed if it exists, or create it
                    if "requirements_addressed" not in element:
                        element["requirements_addressed"] = []
                        
                    if req_id not in element["requirements_addressed"]:
                        element["requirements_addressed"].append(req_id)
                        
                    # Also mention in description
                    if "description" in element and req_id not in element["description"]:
                        element["description"] += f" Addresses requirement {req_id}."
                        
                    added = True
                    break
            
            # If no suitable element found, mention in overview
            if not added and "overview" in repaired_design:
                if req_id not in repaired_design["overview"]:
                    repaired_design["overview"] += f"\nThe design addresses requirement {req_id}."
    
    return repaired_design


def _is_element_related_to_requirement(
    element: Dict[str, Any],
    req_id: str,
    requirements: Dict[str, Any]
) -> bool:
    """Check if an element might be related to a given requirement."""
    # This is a simplified check - a real implementation would be more sophisticated
    # Get requirement details
    req_details = None
    
    if "functional_requirements" in requirements:
        for req in requirements["functional_requirements"]:
            if isinstance(req, dict) and req.get("id") == req_id:
                req_details = req
                break
                
    if not req_details and "non_functional_requirements" in requirements:
        for req in requirements["non_functional_requirements"]:
            if isinstance(req, dict) and req.get("id") == req_id:
                req_details = req
                break
    
    if not req_details:
        return False
    
    # Extract keywords from requirement
    req_desc = req_details.get("description", "").lower()
    req_keywords = set(re.findall(r'\b\w+\b', req_desc))
    
    # Extract keywords from element
    element_desc = element.get("description", "").lower()
    element_sig = element.get("signature", "").lower()
    element_text = f"{element_desc} {element_sig}"
    element_keywords = set(re.findall(r'\b\w+\b', element_text))
    
    # Calculate overlap
    overlap = len(req_keywords.intersection(element_keywords))
    
    # Check for significant keyword overlap
    return overlap >= 3 or (len(req_keywords) > 0 and overlap / len(req_keywords) > 0.2)


def _repair_component_relationships(
    system_design: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair component relationship issues in the system design."""
    repaired_design = json.loads(json.dumps(system_design))
    
    # Fix circular dependencies
    circular_issues = [issue for issue in issues if issue.get("issue_type") == "circular_dependency"]
    
    if circular_issues:
        # Extract components and current dependencies
        components, dependencies = _extract_component_dependencies(repaired_design)
        
        # For each cycle, break the weakest link
        for issue in circular_issues:
            cycle = issue.get("components", [])
            if len(cycle) < 2:
                continue
                
            # Find the weakest link in the cycle
            weakest_link = None
            min_strength = float('inf')
            
            for i in range(len(cycle)):
                from_comp = cycle[i]
                to_comp = cycle[(i + 1) % len(cycle)]
                
                strength = dependencies.get((from_comp, to_comp), 0)
                if strength < min_strength:
                    min_strength = strength
                    weakest_link = (from_comp, to_comp)
            
            if not weakest_link:
                continue
                
            # Break the cycle by removing data flows corresponding to the weakest link
            from_comp, to_comp = weakest_link
            
            # Update data_flow to remove the dependency
            if "data_flow" in repaired_design and isinstance(repaired_design["data_flow"], list):
                # First identify which element IDs correspond to these components
                element_to_component = {}
                for element in repaired_design.get("code_elements", []):
                    if not isinstance(element, dict) or "element_id" not in element:
                        continue
                        
                    element_id = element["element_id"]
                    component = None
                    
                    if "target_file" in element:
                        file_path = element["target_file"]
                        if from_comp in file_path:
                            component = from_comp
                        elif to_comp in file_path:
                            component = to_comp
                    
                    if not component and "signature" in element:
                        sig = element["signature"]
                        if from_comp in sig:
                            component = from_comp
                        elif to_comp in sig:
                            component = to_comp
                    
                    if component:
                        element_to_component[element_id] = component
                
                # Now remove flows between these components
                repaired_design["data_flow"] = [
                    flow for flow in repaired_design["data_flow"]
                    if not (isinstance(flow, dict) and
                           flow.get("from") in element_to_component and
                           flow.get("to") in element_to_component and
                           element_to_component[flow.get("from")] == from_comp and
                           element_to_component[flow.get("to")] == to_comp)
                ]
    
    # Fix excessive coupling
    coupling_issues = [issue for issue in issues if issue.get("issue_type") == "excessive_coupling"]
    
    if coupling_issues:
        # For each coupling issue, suggest a better organization
        for issue in issues:
            component = issue.get("component")
            if not component:
                continue
                
            # Add a note in the system design overview about reducing coupling
            if "overview" in repaired_design and isinstance(repaired_design["overview"], str):
                note = f"\nNote: Component '{component}' has high coupling and should be refactored" + \
                       " into smaller, more focused components."
                if note not in repaired_design["overview"]:
                    repaired_design["overview"] += note
    
    return repaired_design


def _repair_architectural_patterns(
    system_design: Dict[str, Any],
    issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Repair architectural pattern issues in the system design."""
    repaired_design = json.loads(json.dumps(system_design))
    
    # Add notes about architectural patterns
    if "overview" in repaired_design and isinstance(repaired_design["overview"], str):
        for issue in issues:
            if issue.get("issue_type") == "too_many_patterns":
                patterns = issue.get("patterns", [])
                if patterns:
                    # Suggest focusing on fewer patterns
                    dominant_patterns = patterns[:2]
                    note = ("\nArchitectural pattern recommendation: Focus on a smaller set of patterns" +
                            f" such as {' and '.join(dominant_patterns)} for more consistency.")
                    
                    if note not in repaired_design["overview"]:
                        repaired_design["overview"] += note
            
            elif issue.get("issue_type") == "inappropriate_patterns":
                domain = issue.get("domain_type", "")
                inappropriate = issue.get("inappropriate_patterns", [])
                
                if domain and inappropriate:
                    # Suggest more appropriate patterns
                    appropriate_patterns = _suggest_patterns_for_domain(domain)
                    
                    if appropriate_patterns:
                        note = (f"\nFor {domain} domain, consider using {', '.join(appropriate_patterns)}" +
                                f" patterns instead of {', '.join(inappropriate)}.")
                        
                        if note not in repaired_design["overview"]:
                            repaired_design["overview"] += note
    
    return repaired_design


def _suggest_patterns_for_domain(domain: str) -> List[str]:
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
