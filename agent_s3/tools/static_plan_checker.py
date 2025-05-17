"""Static Plan Checker for validating plan modifications.

This module provides validation functionality for plans after user modifications,
ensuring consistency and correctness before applying changes.
"""

import logging
import re
import json
from typing import Dict, Any, List, Tuple, Optional, Set
from difflib import SequenceMatcher

from agent_s3.tools.plan_validator import validate_pre_plan
from agent_s3.tools.phase_validator import validate_user_modifications

logger = logging.getLogger(__name__)

class StaticPlanChecker:
    """Validates plans after modifications to ensure consistency and correctness."""
    
    def __init__(self, context_registry=None):
        """Initialize the static plan checker.
        
        Args:
            context_registry: Optional context registry for accessing project context
        """
        self.context_registry = context_registry
    
    def validate_plan(self, plan: Dict[str, Any], original_plan: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        """Validate a plan after modifications.
        
        This method runs all validation rules on the updated plan and specifically
        verifies consistency between components if the plan was modified.
        
        Args:
            plan: The plan to validate
            original_plan: Optional original plan for comparison
            
        Returns:
            Tuple of (is_valid, validation_results)
        """
        # Run basic validation using plan_validator
        is_valid, validation_results = validate_pre_plan(plan, context_registry=self.context_registry)
        
        # If we have an original plan, perform additional consistency checks
        if original_plan:
            consistency_results = self._validate_consistency(plan, original_plan)
            
            # Merge consistency results with basic validation results
            for key in consistency_results:
                if key in validation_results:
                    validation_results[key].extend(consistency_results[key])
                else:
                    validation_results[key] = consistency_results[key]
            
            # Update is_valid flag if consistency validation failed
            if consistency_results.get("critical", []):
                is_valid = False
        
        return is_valid, validation_results
    
    def _validate_consistency(self, plan: Dict[str, Any], original_plan: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Validate consistency between modified plan and original plan.
        
        This method checks for orphaned references, inconsistent naming,
        and other issues that might arise from modifications.
        
        Args:
            plan: The modified plan
            original_plan: The original plan before modifications
            
        Returns:
            Dictionary with validation results
        """
        results = {
            "critical": [],
            "warnings": [],
            "suggestions": []
        }
        
        # Track all element IDs and names in both plans
        original_ids = self._extract_element_ids(original_plan)
        modified_ids = self._extract_element_ids(plan)
        
        # Check for renamed elements that might create orphaned references
        renamed_elements = self._find_renamed_elements(original_plan, plan)
        
        # Check for orphaned references in the modified plan
        orphaned_refs = self._find_orphaned_references(plan, modified_ids, renamed_elements)
        
        if orphaned_refs:
            for ref in orphaned_refs:
                results["critical"].append({
                    "message": f"Orphaned reference to '{ref['reference']}' in {ref['location']}",
                    "category": "consistency",
                    "suggestion": f"Update reference to match a valid element ID or name"
                })
        
        # Check for inconsistent naming patterns
        naming_issues = self._check_naming_consistency(plan)
        
        if naming_issues:
            for issue in naming_issues:
                results["warnings"].append({
                    "message": issue["message"],
                    "category": "naming",
                    "suggestion": issue["suggestion"]
                })
        
        # Check for duplicate element IDs
        duplicate_ids = self._find_duplicate_ids(plan)
        
        if duplicate_ids:
            for dup in duplicate_ids:
                results["critical"].append({
                    "message": f"Duplicate element ID '{dup['id']}' found in {dup['locations']}",
                    "category": "consistency",
                    "suggestion": "Ensure each element has a unique ID"
                })
        
        return results
    
    def _extract_element_ids(self, plan: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all element IDs and names from a plan.
        
        Args:
            plan: The plan to extract IDs from
            
        Returns:
            Dictionary mapping element IDs to their locations
        """
        element_ids = {}
        
        # Process feature groups
        for group_idx, group in enumerate(plan.get("feature_groups", [])):
            if not isinstance(group, dict):
                continue
            
            group_name = group.get("group_name", f"Group {group_idx}")
            
            # Process features
            for feature_idx, feature in enumerate(group.get("features", [])):
                if not isinstance(feature, dict):
                    continue
                
                feature_name = feature.get("name", f"Feature {feature_idx}")
                feature_location = f"feature '{feature_name}' in group '{group_name}'"
                
                # Process system_design.code_elements
                system_design = feature.get("system_design", {})
                if isinstance(system_design, dict):
                    for el_idx, element in enumerate(system_design.get("code_elements", [])):
                        if not isinstance(element, dict):
                            continue
                        
                        element_id = element.get("element_id")
                        element_name = element.get("name")
                        
                        if element_id:
                            if element_id not in element_ids:
                                element_ids[element_id] = []
                            
                            element_ids[element_id].append({
                                "location": f"{feature_location}, code_elements[{el_idx}]",
                                "name": element_name,
                                "type": "element_id"
                            })
                        
                        if element_name:
                            if element_name not in element_ids:
                                element_ids[element_name] = []
                            
                            element_ids[element_name].append({
                                "location": f"{feature_location}, code_elements[{el_idx}]",
                                "id": element_id,
                                "type": "name"
                            })
        
        return element_ids
    
    def _find_renamed_elements(self, original_plan: Dict[str, Any], modified_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find elements that have been renamed between original and modified plans.
        
        Args:
            original_plan: The original plan
            modified_plan: The modified plan
            
        Returns:
            List of renamed elements with old and new names
        """
        renamed_elements = []
        
        # Extract element IDs and names from both plans
        original_ids = self._extract_element_ids(original_plan)
        modified_ids = self._extract_element_ids(modified_plan)
        
        # Find elements with the same ID but different names
        for element_id in original_ids:
            if element_id in modified_ids and original_ids[element_id][0].get("type") == "element_id":
                original_name = original_ids[element_id][0].get("name")
                modified_name = modified_ids[element_id][0].get("name")
                
                if original_name != modified_name:
                    renamed_elements.append({
                        "id": element_id,
                        "old_name": original_name,
                        "new_name": modified_name,
                        "location": modified_ids[element_id][0].get("location")
                    })
        
        return renamed_elements
    
    def _find_orphaned_references(self, plan: Dict[str, Any], element_ids: Dict[str, List[Dict[str, Any]]], renamed_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find orphaned references in a plan.
        
        Args:
            plan: The plan to check
            element_ids: Dictionary of element IDs and names
            renamed_elements: List of renamed elements
            
        Returns:
            List of orphaned references
        """
        orphaned_refs = []
        
        # Process feature groups
        for group_idx, group in enumerate(plan.get("feature_groups", [])):
            if not isinstance(group, dict):
                continue
            
            group_name = group.get("group_name", f"Group {group_idx}")
            
            # Process features
            for feature_idx, feature in enumerate(group.get("features", [])):
                if not isinstance(feature, dict):
                    continue
                
                feature_name = feature.get("name", f"Feature {feature_idx}")
                feature_location = f"feature '{feature_name}' in group '{group_name}'"
                
                # Check test_requirements for references to code elements
                test_requirements = feature.get("test_requirements", {})
                if isinstance(test_requirements, dict):
                    # Check unit tests
                    for test_idx, test in enumerate(test_requirements.get("unit_tests", [])):
                        if not isinstance(test, dict):
                            continue
                        
                        target_element = test.get("target_element")
                        if target_element and target_element not in element_ids:
                            # Check if this is a renamed element
                            renamed = False
                            for renamed_el in renamed_elements:
                                if renamed_el.get("old_name") == target_element:
                                    renamed = True
                                    break
                            
                            if not renamed:
                                orphaned_refs.append({
                                    "reference": target_element,
                                    "location": f"{feature_location}, test_requirements.unit_tests[{test_idx}]",
                                    "type": "target_element"
                                })
                    
                    # Check other test types similarly...
                
                # Check dependencies for references
                dependencies = feature.get("dependencies", {})
                if isinstance(dependencies, dict):
                    # Check feature_dependencies
                    for dep_idx, dep in enumerate(dependencies.get("feature_dependencies", [])):
                        if isinstance(dep, str) and dep not in [f.get("name") for f in plan.get("feature_groups", []) for f in f.get("features", []) if isinstance(f, dict)]:
                            orphaned_refs.append({
                                "reference": dep,
                                "location": f"{feature_location}, dependencies.feature_dependencies[{dep_idx}]",
                                "type": "feature_dependency"
                            })
        
        return orphaned_refs
    
    def _find_duplicate_ids(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find duplicate element IDs in a plan.
        
        Args:
            plan: The plan to check
            
        Returns:
            List of duplicate IDs with their locations
        """
        duplicate_ids = []
        id_locations = {}
        
        # Process feature groups
        for group_idx, group in enumerate(plan.get("feature_groups", [])):
            if not isinstance(group, dict):
                continue
            
            group_name = group.get("group_name", f"Group {group_idx}")
            
            # Process features
            for feature_idx, feature in enumerate(group.get("features", [])):
                if not isinstance(feature, dict):
                    continue
                
                feature_name = feature.get("name", f"Feature {feature_idx}")
                feature_location = f"feature '{feature_name}' in group '{group_name}'"
                
                # Process system_design.code_elements
                system_design = feature.get("system_design", {})
                if isinstance(system_design, dict):
                    for el_idx, element in enumerate(system_design.get("code_elements", [])):
                        if not isinstance(element, dict):
                            continue
                        
                        element_id = element.get("element_id")
                        
                        if element_id:
                            location = f"{feature_location}, code_elements[{el_idx}]"
                            
                            if element_id in id_locations:
                                id_locations[element_id].append(location)
                            else:
                                id_locations[element_id] = [location]
        
        # Find IDs with multiple locations
        for element_id, locations in id_locations.items():
            if len(locations) > 1:
                duplicate_ids.append({
                    "id": element_id,
                    "locations": locations
                })
        
        return duplicate_ids
    
    def _check_naming_consistency(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for inconsistent naming patterns in a plan.
        
        Args:
            plan: The plan to check
            
        Returns:
            List of naming issues
        """
        naming_issues = []
        
        # Track naming patterns for different element types
        naming_patterns = {
            "class": {},
            "function": {},
            "method": {},
            "interface": {},
            "enum_type": {},
            "struct": {},
            "module": {}
        }
        
        # Process feature groups
        for group_idx, group in enumerate(plan.get("feature_groups", [])):
            if not isinstance(group, dict):
                continue
            
            # Process features
            for feature_idx, feature in enumerate(group.get("features", [])):
                if not isinstance(feature, dict):
                    continue
                
                # Process system_design.code_elements
                system_design = feature.get("system_design", {})
                if isinstance(system_design, dict):
                    for element in system_design.get("code_elements", []):
                        if not isinstance(element, dict):
                            continue
                        
                        element_type = element.get("element_type")
                        element_name = element.get("name")
                        
                        if element_type and element_name and element_type in naming_patterns:
                            # Determine naming pattern (camelCase, snake_case, PascalCase)
                            if re.match(r'^[a-z][a-zA-Z0-9]*$', element_name):
                                pattern = "camelCase"
                            elif re.match(r'^[a-z][a-z0-9_]*$', element_name):
                                pattern = "snake_case"
                            elif re.match(r'^[A-Z][a-zA-Z0-9]*$', element_name):
                                pattern = "PascalCase"
                            else:
                                pattern = "other"
                            
                            if pattern != "other":
                                if element_type in naming_patterns:
                                    if pattern in naming_patterns[element_type]:
                                        naming_patterns[element_type][pattern] += 1
                                    else:
                                        naming_patterns[element_type][pattern] = 1
        
        # Check for inconsistent naming patterns
        for element_type, patterns in naming_patterns.items():
            if len(patterns) > 1:
                # Find the dominant pattern
                dominant_pattern = max(patterns.items(), key=lambda x: x[1])[0]
                
                # Report inconsistent patterns
                for pattern, count in patterns.items():
                    if pattern != dominant_pattern:
                        naming_issues.append({
                            "message": f"Inconsistent naming pattern for {element_type}s: {count} using {pattern}, majority using {dominant_pattern}",
                            "suggestion": f"Consider using {dominant_pattern} consistently for all {element_type}s"
                        })
        
        return naming_issues
