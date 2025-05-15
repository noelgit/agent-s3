"""Signature & ID Normalizer for Pre-Planning output.

This module provides utilities to validate and normalize element_ids, target_files,
and signatures in pre-planning data. It ensures consistent formatting and uniqueness
of identifiers, normalizes file paths according to project conventions, and fixes
common syntax issues in code signatures.
"""

import os
import re
import ast
import logging
from typing import Dict, Any, List, Set, Tuple, Optional
from pathlib import Path

# Import plan validator for path validation and code validation
from agent_s3.tools.plan_validator import validate_code_syntax

logger = logging.getLogger(__name__)

class SignatureNormalizer:
    """
    Normalizes and validates element IDs, target files, and signatures
    in pre-planning data to ensure consistency and correctness.
    """

    def __init__(self, cwd: str, context_registry=None):
        """
        Initialize the normalizer.
        
        Args:
            cwd: Current working directory for resolving relative paths
            context_registry: Optional context registry for additional validation
        """
        self.cwd = Path(cwd)
        self.context_registry = context_registry
        self.seen_element_ids: Set[str] = set()
        
    def normalize_pre_plan(self, pre_plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize element_ids, target_files, and signatures in a pre-plan.
        
        Args:
            pre_plan_data: Pre-planning data structure
            
        Returns:
            Normalized pre-planning data
        """
        if not isinstance(pre_plan_data, dict) or "feature_groups" not in pre_plan_data:
            logger.warning("Invalid pre_plan_data format. Missing 'feature_groups' key.")
            return pre_plan_data
            
        # Reset seen IDs for a fresh normalization
        self.seen_element_ids = set()
        
        # Process each feature group
        for group_idx, group in enumerate(pre_plan_data.get("feature_groups", [])):
            if not isinstance(group, dict):
                continue
                
            group_name = group.get("group_name", f"Group {group_idx}")
            
            # Process each feature
            for feature_idx, feature in enumerate(group.get("features", [])):
                if not isinstance(feature, dict):
                    continue
                    
                feature_name = feature.get("name", f"Feature {feature_idx}")
                feature_log_prefix = f"Feature '{feature_name}' in group '{group_name}'"
                
                # Process system_design.code_elements
                system_design = feature.get("system_design", {})
                if isinstance(system_design, dict) and "code_elements" in system_design:
                    code_elements = system_design.get("code_elements", [])
                    
                    if isinstance(code_elements, list):
                        normalized_elements = []
                        
                        for element_idx, element in enumerate(code_elements):
                            if not isinstance(element, dict):
                                continue
                                
                            # Apply normalizations
                            normalized_element = self._normalize_element(
                                element, 
                                feature_name, 
                                group_name, 
                                element_idx
                            )
                            normalized_elements.append(normalized_element)
                            
                        # Update with normalized elements
                        system_design["code_elements"] = normalized_elements
                
                # Also process test requirements to ensure target_element_id consistency
                self._normalize_test_requirements(feature)
            
        return pre_plan_data
    
    def _normalize_element(self, element: Dict[str, Any], feature_name: str, 
                          group_name: str, element_idx: int) -> Dict[str, Any]:
        """
        Normalize a single code element.
        
        Args:
            element: The code element to normalize
            feature_name: Name of the feature containing this element
            group_name: Name of the group containing this feature
            element_idx: Index of the element in its feature
            
        Returns:
            Normalized code element
        """
        # Make a copy to avoid modifying the original
        normalized = dict(element)
        
        # 1. Normalize element_id
        normalized["element_id"] = self._normalize_element_id(
            element.get("element_id", ""),
            element.get("name", ""),
            element.get("element_type", ""),
            feature_name,
            group_name
        )
        
        # 2. Normalize target_file
        normalized["target_file"] = self._normalize_target_file(
            element.get("target_file", ""),
            element.get("name", ""),
            element.get("element_type", "")
        )
        
        # 3. Normalize signature
        normalized["signature"] = self._normalize_signature(
            element.get("signature", ""),
            element.get("name", ""),
            element.get("element_type", ""),
            normalized["target_file"]
        )
        
        return normalized
        
    def _normalize_element_id(self, element_id: str, name: str, element_type: str,
                             feature_name: str, group_name: str) -> str:
        """
        Normalize element ID to ensure uniqueness and consistent formatting.
        
        Args:
            element_id: Original element ID
            name: Element name
            element_type: Element type (class, function, etc.)
            feature_name: Parent feature name
            group_name: Parent group name
            
        Returns:
            Normalized unique element ID
        """
        if not element_id:
            # Generate a new ID if missing
            sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '_', name).lower()
            sanitized_feature = re.sub(r'[^a-zA-Z0-9_]', '_', feature_name).lower()
            element_id = f"{sanitized_feature}_{sanitized_name}_{element_type}"
        
        # Clean up the ID format (lowercase, alphanumeric with underscores)
        normalized_id = re.sub(r'[^a-zA-Z0-9_]', '_', element_id).lower()
        
        # Ensure uniqueness by adding a suffix if needed
        base_id = normalized_id
        counter = 1
        
        while normalized_id in self.seen_element_ids:
            normalized_id = f"{base_id}_{counter}"
            counter += 1
        
        # Record this ID as seen
        self.seen_element_ids.add(normalized_id)
        
        return normalized_id
    
    def _normalize_target_file(self, target_file: str, name: str, element_type: str) -> str:
        """
        Normalize target file path.
        
        Args:
            target_file: Original target file path
            name: Element name
            element_type: Element type (class, function, etc.)
            
        Returns:
            Normalized file path
        """
        if not target_file:
            # No target file provided, generate a reasonable default
            module_name = name.lower()
            if element_type == "class":
                # For classes, convert CamelCase to snake_case
                module_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
            
            # Default to a Python file in a module named after the element
            target_file = f"src/{module_name}.py"
        
        # Get the extension to determine language conventions
        _, ext = os.path.splitext(target_file)
        
        # Normalize according to language conventions
        if ext in ['.py']:
            # Python - use snake_case file names
            norm_basename = os.path.basename(target_file)
            # Convert camelCase or PascalCase to snake_case if needed
            if any(c.isupper() for c in norm_basename):
                basename_no_ext = os.path.splitext(norm_basename)[0]
                snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', basename_no_ext).lower()
                norm_basename = f"{snake_case}{ext}"
                target_file = os.path.join(os.path.dirname(target_file), norm_basename)
                
        elif ext in ['.js', '.ts', '.tsx', '.jsx']:
            # JavaScript/TypeScript - use camelCase or PascalCase for React components
            norm_basename = os.path.basename(target_file)
            basename_no_ext = os.path.splitext(norm_basename)[0]
            
            if element_type == "class" and ext in ['.tsx', '.jsx']:
                # React components should use PascalCase
                pascal_case = basename_no_ext[0].upper() + basename_no_ext[1:]
                norm_basename = f"{pascal_case}{ext}"
            elif '_' in basename_no_ext:
                # Convert snake_case to camelCase
                camel_case = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), basename_no_ext)
                norm_basename = f"{camel_case}{ext}"
                
            target_file = os.path.join(os.path.dirname(target_file), norm_basename)
        
        # Normalize path separators
        target_file = os.path.normpath(target_file)
        
        # Make sure it's a relative path
        if os.path.isabs(target_file):
            try:
                target_file = os.path.relpath(target_file, self.cwd)
            except ValueError:
                # If there's an issue with relpath, keep the original
                pass
                
        return target_file
    
    def _normalize_signature(self, signature: str, name: str, element_type: str, target_file: str) -> str:
        """
        Normalize code signature for syntactic correctness.
        
        Args:
            signature: Original code signature
            name: Element name
            element_type: Element type (class, function, etc.)
            target_file: Target file path (for language determination)
            
        Returns:
            Normalized signature
        """
        if not signature:
            # Generate a basic signature if missing
            return self._generate_basic_signature(name, element_type, target_file)
        
        # Determine the language based on the file extension
        _, ext = os.path.splitext(target_file)
        language = self._get_language_from_extension(ext)
        
        # Apply language-specific normalizations
        if language == "python":
            return self._normalize_python_signature(signature, name, element_type)
        elif language in ["javascript", "typescript"]:
            return self._normalize_js_ts_signature(signature, name, element_type, language)
        else:
            # For unsupported languages, return as is
            return signature
    
    def _normalize_python_signature(self, signature: str, name: str, element_type: str) -> str:
        """Normalize Python signatures."""
        # Ensure the signature ends with a colon
        if not signature.rstrip().endswith(':'):
            signature = signature.rstrip() + ':'
        
        # For class definitions, ensure proper inheritance syntax
        if element_type == "class" and "(" not in signature:
            # Add empty parentheses for classes that don't inherit
            signature = signature.replace(f"class {name}:", f"class {name}():")
        
        # Attempt to parse with ast to verify syntactic correctness
        try:
            # Add a dummy body to make it valid Python syntax
            test_code = f"{signature}\n    pass"
            ast.parse(test_code)
        except SyntaxError as e:
            # Log the error but keep the signature
            logger.warning(f"Syntax error in Python signature: {signature} - {str(e)}")
        
        return signature
    
    def _normalize_js_ts_signature(self, signature: str, name: str, element_type: str, language: str) -> str:
        """Normalize JavaScript/TypeScript signatures."""
        # Ensure semicolon termination for appropriate declarations
        if element_type != "class" and not signature.rstrip().endswith('{') and not signature.rstrip().endswith(';'):
            signature = signature.rstrip() + ';'
        
        # Make sure class definitions have an opening brace
        if element_type == "class" and not signature.rstrip().endswith('{'):
            signature = signature.rstrip() + ' {'
        
        # For interfaces in TypeScript, ensure they have an opening brace
        if language == "typescript" and element_type == "interface" and not signature.rstrip().endswith('{'):
            signature = signature.rstrip() + ' {'
        
        return signature
    
    def _generate_basic_signature(self, name: str, element_type: str, target_file: str) -> str:
        """Generate a basic signature when one is missing."""
        _, ext = os.path.splitext(target_file)
        language = self._get_language_from_extension(ext)
        
        if language == "python":
            if element_type == "function":
                return f"def {name}():"
            elif element_type == "class":
                return f"class {name}:"
            elif element_type == "method":
                return f"def {name}(self):"
            else:
                return f"def {name}():"
        
        elif language in ["javascript", "typescript"]:
            if element_type == "function":
                return f"function {name}() {'{'}";
            elif element_type == "class":
                return f"class {name} {'{'}";
            elif element_type == "interface" and language == "typescript":
                return f"interface {name} {'{'}";
            else:
                return f"function {name}() {'{'}";
        
        # Default fallback
        return f"{element_type} {name}"
    
    def _get_language_from_extension(self, ext: str) -> str:
        """Determine the programming language from a file extension."""
        if ext in ['.py']:
            return "python"
        elif ext in ['.js', '.jsx', '.mjs']:
            return "javascript"
        elif ext in ['.ts', '.tsx']:
            return "typescript"
        elif ext in ['.php']:
            return "php"
        elif ext in ['.java']:
            return "java"
        else:
            return "unknown"
    
    def _normalize_test_requirements(self, feature: Dict[str, Any]) -> None:
        """
        Normalize test_requirements to ensure target_element_id consistency.
        
        Args:
            feature: Feature object containing test_requirements
        """
        test_requirements = feature.get("test_requirements", {})
        if not isinstance(test_requirements, dict):
            return
            
        # Map element names to their normalized IDs to update test target_element_id fields
        element_name_to_id = {}
        
        # Build the map from system_design.code_elements
        system_design = feature.get("system_design", {})
        if isinstance(system_design, dict) and "code_elements" in system_design:
            for element in system_design.get("code_elements", []):
                if isinstance(element, dict) and "name" in element and "element_id" in element:
                    element_name_to_id[element["name"]] = element["element_id"]
        
        # Test categories that have target_element references
        test_categories = ["unit_tests", "integration_tests", "property_based_tests"]
        
        for category in test_categories:
            tests = test_requirements.get(category, [])
            if not isinstance(tests, list):
                continue
                
            for test in tests:
                if not isinstance(test, dict):
                    continue
                    
                # If test has target_element field, update the target_element_id
                if "target_element" in test and isinstance(test["target_element"], str):
                    target_name = test["target_element"]
                    if target_name in element_name_to_id:
                        test["target_element_id"] = element_name_to_id[target_name]
                    # If no direct match, could try more complex matching but for now skip

def normalize_pre_plan(pre_plan_data: Dict[str, Any], cwd: str, context_registry=None) -> Dict[str, Any]:
    """
    Convenience function to normalize a pre-plan.
    
    Args:
        pre_plan_data: Pre-planning data to normalize
        cwd: Current working directory
        context_registry: Optional context registry for additional validation
        
    Returns:
        Normalized pre-plan data
    """
    normalizer = SignatureNormalizer(cwd, context_registry)
    return normalizer.normalize_pre_plan(pre_plan_data)