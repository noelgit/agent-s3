"""Static Plan Checker to validate Pre-Planner JSON output.

This module provides fast, deterministic validation of Pre-Planner outputs
before they reach the Planner phase. It verifies structural correctness,
identifier uniqueness, path validity, token budget compliance, and other
constraints without requiring LLM calls.

Implementation uses comprehensive AST parsing for multi-language code analysis.
"""

import json
import re
import os
import glob
import logging
import keyword
import ast
import importlib.util
import xml.etree.ElementTree as ET
import datetime
from typing import Dict, Any, List, Tuple, Set, Optional, Union, Callable
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# Import AST tools for multi-language support
from agent_s3.ast_tools.python_units import extract_units
from .parsing.parser_registry import ParserRegistry
from .parsing.base_parser import LanguageParser

logger = logging.getLogger(__name__)

# Maximum token counts for different complexity levels
TOKEN_BUDGET_LIMITS = {
    0: 2000,  # trivial
    1: 5000,  # simple
    2: 10000, # moderate
    3: 20000  # complex
}

# Language-specific keywords
PYTHON_KEYWORDS = set(keyword.kwlist)
JS_KEYWORDS = {
    "break", "case", "catch", "class", "const", "continue", "debugger", 
    "default", "delete", "do", "else", "export", "extends", "false", 
    "finally", "for", "function", "if", "import", "in", "instanceof", 
    "new", "null", "return", "super", "switch", "this", "throw", "true", 
    "try", "typeof", "var", "void", "while", "with", "yield",
    # ES6+ keywords
    "let", "static", "await", "async"
}
PHP_KEYWORDS = {
    "__halt_compiler", "abstract", "and", "array", "as", "break", 
    "callable", "case", "catch", "class", "clone", "const", "continue", 
    "declare", "default", "die", "do", "echo", "else", "elseif", 
    "empty", "enddeclare", "endfor", "endforeach", "endif", "endswitch", 
    "endwhile", "eval", "exit", "extends", "final", "finally", "fn", 
    "for", "foreach", "function", "global", "goto", "if", "implements", 
    "include", "include_once", "instanceof", "insteadof", "interface", 
    "isset", "list", "namespace", "new", "or", "print", "private", 
    "protected", "public", "require", "require_once", "return", "static", 
    "switch", "throw", "trait", "try", "unset", "use", "var", "while", "xor", "yield"
}

# System-reserved environment variable names
RESERVED_ENV_VARS = {
    "PATH", "HOME", "USER", "SHELL", "LANG", "TERM", "EDITOR", 
    "PYTHONPATH", "JAVA_HOME", "LD_LIBRARY_PATH", "TEMP", "TMP",
    "NODE_ENV", "PORT", "HOST", "DATABASE_URL", "PWD", "PS1", 
    "DISPLAY", "HOSTNAME", "LOGNAME", "_", "OLDPWD", "MAIL", 
    "SSH_CONNECTION", "SSH_TTY", "TERM_PROGRAM", "SHELL_SESSION_ID",
    "HTTP_HOST", "DOCUMENT_ROOT", "SERVER_PROTOCOL", "REQUEST_METHOD",
    "SCRIPT_FILENAME", "QUERY_STRING", "PHP_SELF"
}


class PlanValidationError(Exception):
    """Exception raised when plan validation fails."""
    pass


@dataclass
class CodeElement:
    """Represents a code element with position information."""
    name: str
    element_type: str
    start_line: int = 0
    end_line: int = 0
    params: List[str] = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = []
    
    def __repr__(self) -> str:
        """String representation of the element."""
        return f"{self.element_type}:{self.name}:{self.start_line}-{self.end_line}"


@dataclass
class SemanticRelation:
    """Represents a semantic relationship between code elements."""
    source: str
    target: str
    relation_type: str
    
    def __repr__(self) -> str:
        """String representation of the relationship."""
        return f"{self.source} {self.relation_type} {self.target}"


class CodeAnalyzer:
    """AST-based code analyzer for extracting code elements across languages."""
    def __init__(self, parser_registry: ParserRegistry = None, file_tool=None):
        self.parser_registry = parser_registry or ParserRegistry()
        self.file_tool = file_tool

    def analyze_code(self, code_str: str, lang: str = None, file_path: str = None, tech_stack: dict = None) -> Dict[str, Any]:
        """
        Analyze code and extract elements and relationships using the pluggable parsing framework.
        Args:
            code_str: Code string to analyze
            lang: Language of code, defaults to auto-detect
            file_path: Optional file path for extension-based detection
            tech_stack: Optional tech stack info for framework extractors
        Returns:
            Dictionary with extracted code elements and relationships
        """
        # Auto-detect language if not provided
        if not lang and file_path:
            parser = self.parser_registry.get_parser(file_path=file_path)
            if parser:
                lang = parser.__class__.__name__.replace('Parser', '').lower()
        if not lang:
            lang = self._detect_language(code_str)
        parser = self.parser_registry.get_parser(file_path=file_path, language_name=lang)
        if parser:
            return parser.analyze(code_str, file_path or '', tech_stack)
        logger.error(f"No parser found for language '{lang}'. Skipping analysis.")
        return {
            "language": lang,
            "elements": [],
            "relations": [],
            "imports": set(),
            "functions": set(),
            "classes": set(),
            "variables": set(),
            "route_paths": set(),
            "env_vars": set(),
        }

    def _analyze_file(self, file_path: str, language: str = None):
        """
        Analyze a file using the new parser system only.
        """
        if not self.file_tool:
            logger.error("FileTool is not available. Cannot analyze file.")
            return None
        if not self.parser_registry:
            logger.error("ParserRegistry not available. Cannot analyze file.")
            return None
        try:
            content = self.file_tool.read_file(file_path)
            if content is None:
                logger.warning(f"Could not read content of file: {file_path}")
                return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            return None
        # Language detection
        if not language:
            if hasattr(self.file_tool, 'get_language_from_extension'):
                language = self.file_tool.get_language_from_extension(file_path)
            if not language:
                language = Path(file_path).suffix[1:].lower() if Path(file_path).suffix else 'unknown'
        parser = self.parser_registry.get_parser(language_name=language, file_path=file_path)
        if parser:
            try:
                logger.info(f"Analyzing {file_path} with {type(parser).__name__} for language '{language}'.")
                structure = parser.parse_code(content, file_path)
                return structure
            except Exception as e:
                logger.error(f"Error analyzing {file_path} with {type(parser).__name__}: {e}", exc_info=True)
                return None
        else:
            logger.error(f"No parser found for language '{language}' for file {file_path}.")
            return None

# Main validation functions
def validate_pre_plan(data: Dict[str, Any], repo_root: str = None, context_registry=None) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate Pre-Planner JSON output with fast, deterministic checks.
    
    This function performs comprehensive validation of the pre-planning JSON output,
    including schema validation, code syntax checking, identifier hygiene, path validity,
    token budget compliance, duplicate symbol detection, and content scanning for
    dangerous operations.
    
    Args:
        data: The Pre-Planner JSON data structure to validate
        repo_root: Optional repository root path for file glob validation
        context_registry: Optional context registry for accessing project context
        
    Returns:
        Tuple of (is_valid, validation_results dict with critical errors and warnings)
    """
    if repo_root is None:
        repo_root = os.getcwd()
    
    # Initialize structured validation results
    validation_results = {
        "critical": [],  # Critical errors that should block workflow
        "warnings": [],  # Warnings that can be addressed but don't block
        "suggestions": [],  # Optimization suggestions
        "sections": {
            "architecture": False,
            "implementation": False,
            "tests": False
        }
    }
    
    # Scan for dangerous content patterns
    dangerous_patterns = [
        "rm -rf", "deltree", "format", "DROP TABLE", "DROP DATABASE", 
        "DELETE FROM", "TRUNCATE TABLE", "sudo", "chmod 777", 
        "eval(", "exec(", "system(", "shell_exec", "os.system"
    ]
    
    # Check for dangerous content in descriptions, signatures, etc.
    for group_idx, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
            
        for feature_idx, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
                
            # Check feature description for dangerous content
            description = feature.get("description", "")
            for pattern in dangerous_patterns:
                if pattern.lower() in description.lower():
                    validation_results["critical"].append({
                        "message": f"Feature '{feature.get('name', f'at index {feature_idx}')}' contains potentially dangerous operation '{pattern}' in description",
                        "category": "security",
                        "suggestion": f"Remove or replace the dangerous operation '{pattern}'"
                    })
            
            # Check system_design elements
            if "system_design" in feature and isinstance(feature["system_design"], dict):
                # Mark architecture section as present
                validation_results["sections"]["architecture"] = True
                
                # Check code elements
                for el_idx, element in enumerate(feature["system_design"].get("code_elements", [])):
                    if not isinstance(element, dict):
                        continue
                        
                    # Check signature and description
                    for field in ["signature", "description"]:
                        content = element.get(field, "")
                        for pattern in dangerous_patterns:
                            if pattern.lower() in content.lower():
                                validation_results["critical"].append({
                                    "message": f"Code element '{element.get('name', f'at index {el_idx}')}' contains potentially dangerous operation '{pattern}' in {field}",
                                    "category": "security",
                                    "suggestion": f"Remove or replace the dangerous operation '{pattern}'"
                                })
            
            # Check test_requirements
            if "test_requirements" in feature and isinstance(feature["test_requirements"], dict):
                # Mark tests section as present
                validation_results["sections"]["tests"] = True
            
            # Check implementation steps if present
            if "implementation_steps" in feature and isinstance(feature["implementation_steps"], list):
                # Mark implementation section as present
                validation_results["sections"]["implementation"] = True
                
                for step_idx, step in enumerate(feature["implementation_steps"]):
                    if not isinstance(step, dict):
                        continue
                        
                    # Check step description and code
                    for field in ["description", "code"]:
                        content = step.get(field, "")
                        for pattern in dangerous_patterns:
                            if pattern.lower() in content.lower():
                                validation_results["critical"].append({
                                    "message": f"Implementation step {step_idx} contains potentially dangerous operation '{pattern}' in {field}",
                                    "category": "security",
                                    "suggestion": f"Remove or replace the dangerous operation '{pattern}'"
                                })
    
    # Run all validation checks with severity classification
    # Schema validation - critical if basic structure is invalid
    for error in validate_schema(data):
        if "missing required field" in error.lower() or "must be a" in error.lower():
            validation_results["critical"].append({
                "message": error,
                "category": "schema",
                "suggestion": None
            })
        else:
            validation_results["warnings"].append({
                "message": error,
                "category": "schema",
                "suggestion": None
            })
    
    # Code syntax validation - critical if code stubs have syntax errors
    for error in validate_code_syntax(data):
        validation_results["critical"].append({
            "message": error["message"],
            "category": "syntax",
            "suggestion": error.get("suggestion")
        })
    
    # Identifier hygiene validation - critical if reserved keywords used
    for error in validate_identifier_hygiene(data):
        if "reserved" in error.lower() or "duplicate" in error.lower():
            validation_results["critical"].append({
                "message": error,
                "category": "identifiers", 
                "suggestion": None
            })
        else:
            validation_results["warnings"].append({
                "message": error,
                "category": "identifiers",
                "suggestion": None
            })
    
    # Path validity - warnings only
    for error in validate_path_validity(data, repo_root):
        validation_results["warnings"].append({
            "message": error,
            "category": "paths",
            "suggestion": None
        })
    
    # Token budget - critical if significantly over budget
    for error in validate_token_budget(data):
        if "exceeds global budget" in error.lower():
            validation_results["critical"].append({
                "message": error,
                "category": "tokens",
                "suggestion": "Consider breaking down the task into smaller subtasks"
            })
        else:
            validation_results["warnings"].append({
                "message": error,
                "category": "tokens",
                "suggestion": None
            })
    
    # Duplicate symbols - critical error
    for error in validate_duplicate_symbols(data):
        validation_results["critical"].append({
            "message": error,
            "category": "duplicates",
            "suggestion": None
        })
    
    # Reserved prefixes - warnings
    for error in validate_reserved_prefixes(data):
        validation_results["warnings"].append({
            "message": error,
            "category": "env_vars",
            "suggestion": None
        })
    
    # Stub test coherence - warnings
    for error in validate_stub_test_coherence(data):
        validation_results["warnings"].append({
            "message": error,
            "category": "tests",
            "suggestion": None
        })
    
    # Complexity sanity - warnings
    for error in validate_complexity_sanity(data):
        validation_results["warnings"].append({
            "message": error,
            "category": "complexity",
            "suggestion": None
        })
    
    # Check for missing sections
    missing_sections = []
    for section, present in validation_results["sections"].items():
        if not present:
            missing_sections.append(section)
            validation_results["critical"].append({
                "message": f"Missing required section: {section.capitalize()}",
                "category": "completeness",
                "suggestion": f"Add the {section.capitalize()} section to ensure a complete plan"
            })
    
    # Calculate summary counts
    validation_results["summary"] = {
        "critical_count": len(validation_results["critical"]),
        "warning_count": len(validation_results["warnings"]),
        "suggestion_count": len(validation_results["suggestions"]),
        "missing_sections": missing_sections
    }
    
    # Plan is invalid if there are any critical errors
    is_valid = len(validation_results["critical"]) == 0
    
    # Add structured errors to context registry if available
    if context_registry and not is_valid:
        try:
            context_registry.add("validation_errors", validation_results)
        except Exception:
            # Don't fail validation if context registry update fails
            pass
    
    # Generate a more detailed error report
    if not is_valid:
        error_report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "validation_status": "failed",
            "critical_errors": validation_results["critical"],
            "warnings": validation_results["warnings"],
            "suggestions": validation_results["suggestions"],
            "sections_status": {
                section: "missing" if section in missing_sections else "present"
                for section in validation_results["sections"]
            }
        }
        
        # Save error report to file for debugging
        try:
            report_path = "validation_error_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(error_report, f, indent=2)
            logger.info(f"Validation error report saved to {report_path}")
        except Exception as e:
            logger.error(f"Failed to save validation error report: {e}")
    
    return is_valid, validation_results


def validate_schema(data: Dict[str, Any]) -> List[str]:
    """
    Validate basic schema structure and types.
    
    This function performs comprehensive validation of the pre-planning JSON schema,
    ensuring all required sections (Architecture, Implementation, Tests) are present
    and properly structured.
    """
    errors = []
    
    # Basic type checks
    if not isinstance(data, dict):
        errors.append("Pre-plan data must be a dictionary")
        return errors  # Can't continue if not a dict
    
    # Check required top-level keys
    if "original_request" not in data:
        errors.append("Missing required field 'original_request'")
    elif not isinstance(data["original_request"], str):
        errors.append("Field 'original_request' must be a string")
    
    if "feature_groups" not in data:
        errors.append("Missing required field 'feature_groups'")
        return errors  # Can't continue without feature_groups
    
    if not isinstance(data["feature_groups"], list):
        errors.append("Field 'feature_groups' must be a list")
        return errors  # Can't continue if not a list
    
    # Check each feature group
    for i, group in enumerate(data["feature_groups"]):
        group_prefix = f"Feature group {i}"
        
        if not isinstance(group, dict):
            errors.append(f"{group_prefix} must be a dictionary")
            continue
        
        # Check required feature group fields
        if "group_name" not in group:
            errors.append(f"{group_prefix} missing required field 'group_name'")
        elif not isinstance(group["group_name"], str):
            errors.append(f"{group_prefix} field 'group_name' must be a string")
        
        if "group_description" not in group:
            errors.append(f"{group_prefix} missing required field 'group_description'")
        elif not isinstance(group["group_description"], str):
            errors.append(f"{group_prefix} field 'group_description' must be a string")
        
        if "features" not in group:
            errors.append(f"{group_prefix} missing required field 'features'")
            continue
        
        if not isinstance(group["features"], list):
            errors.append(f"{group_prefix} field 'features' must be a list")
            continue
        
        # Check each feature
        for j, feature in enumerate(group["features"]):
            feature_prefix = f"Feature {j} in group {i}"
            
            if not isinstance(feature, dict):
                errors.append(f"{feature_prefix} must be a dictionary")
                continue
            
            # Check required feature fields
            for field in ["name", "description"]:
                if field not in feature:
                    errors.append(f"{feature_prefix} missing required field '{field}'")
                elif not isinstance(feature[field], str):
                    errors.append(f"{feature_prefix} field '{field}' must be a string")
            
            # Check files_affected
            if "files_affected" not in feature:
                errors.append(f"{feature_prefix} missing required field 'files_affected'")
            elif not isinstance(feature["files_affected"], list):
                errors.append(f"{feature_prefix} field 'files_affected' must be a list")
            else:
                for k, file_path in enumerate(feature["files_affected"]):
                    if not isinstance(file_path, str):
                        errors.append(f"{feature_prefix} files_affected[{k}] must be a string")
            
            # Check test_requirements
            if "test_requirements" not in feature:
                errors.append(f"{feature_prefix} missing required field 'test_requirements'")
            elif not isinstance(feature["test_requirements"], dict):
                errors.append(f"{feature_prefix} field 'test_requirements' must be a dictionary")
            else:
                test_reqs = feature["test_requirements"]
                # Define expected test types and their structure
                expected_test_types = {
                    "unit_tests": {"item_type": dict, "fields": {"description": str, "target_element": str}},
                    "integration_tests": {"item_type": dict, "fields": {"description": str}}, # Assuming description only
                    "property_based_tests": {"item_type": dict, "fields": {"description": str, "target_element": str}},
                    "acceptance_tests": {"item_type": dict, "fields": {"given": str, "when": str, "then": str}}
                }

                for test_type_key, structure_def in expected_test_types.items():
                    if test_type_key not in test_reqs:
                        errors.append(f"{feature_prefix} test_requirements missing '{test_type_key}'")
                    elif not isinstance(test_reqs[test_type_key], list):
                        errors.append(f"{feature_prefix} test_requirements field '{test_type_key}' must be a list")
                    else:
                        for k, test_case in enumerate(test_reqs[test_type_key]):
                            tc_prefix = f"{feature_prefix} test_requirements.{test_type_key}[{k}]"
                            if not isinstance(test_case, structure_def["item_type"]):
                                errors.append(f"{tc_prefix} must be a {structure_def['item_type'].__name__}")
                                continue
                            
                            if structure_def["item_type"] == dict:
                                for field, expected_field_type in structure_def["fields"].items():
                                    if field not in test_case:
                                        errors.append(f"{tc_prefix} missing required field '{field}'")
                                    elif not isinstance(test_case[field], expected_field_type):
                                        errors.append(f"{tc_prefix} field '{field}' must be a {expected_field_type.__name__}")
            
            # Check dependencies
            if "dependencies" not in feature:
                errors.append(f"{feature_prefix} missing required field 'dependencies'")
            elif not isinstance(feature["dependencies"], dict):
                errors.append(f"{feature_prefix} field 'dependencies' must be a dictionary")
            else:
                deps = feature["dependencies"]
                for dep_type in ["internal", "external", "feature_dependencies"]:
                    if dep_type not in deps:
                        errors.append(f"{feature_prefix} dependencies missing '{dep_type}'")
                    elif not isinstance(deps[dep_type], list):
                        errors.append(f"{feature_prefix} dependencies field '{dep_type}' must be a list")
            
            # Check risk_assessment
            if "risk_assessment" not in feature:
                errors.append(f"{feature_prefix} missing required field 'risk_assessment'")
            elif not isinstance(feature["risk_assessment"], dict):
                errors.append(f"{feature_prefix} field 'risk_assessment' must be a dictionary")
            
            # Check system_design (Architecture section)
            if "system_design" not in feature:
                errors.append(f"{feature_prefix} missing required field 'system_design' (Architecture section)")
            elif not isinstance(feature["system_design"], dict):
                errors.append(f"{feature_prefix} field 'system_design' must be a dictionary")
            else:
                system_design_data = feature["system_design"]
                # Check for required architecture components
                for arch_field in ["overview", "code_elements", "data_flow"]:
                    if arch_field not in system_design_data:
                        errors.append(f"{feature_prefix} system_design missing required field '{arch_field}'")
                
                if "code_elements" in system_design_data and not isinstance(system_design_data["code_elements"], list):
                    errors.append(f"{feature_prefix} system_design field 'code_elements' must be a list")
                elif "code_elements" in system_design_data and len(system_design_data["code_elements"]) == 0:
                    errors.append(f"{feature_prefix} system_design must have at least one code element")
                # Validate code elements in detail
                if "code_elements" in system_design_data and isinstance(system_design_data["code_elements"], list):
                    for ce_idx, code_el in enumerate(system_design_data["code_elements"]):
                        ce_prefix = f"{feature_prefix} system_design.code_elements[{ce_idx}]"
                        if not isinstance(code_el, dict):
                            errors.append(f"{ce_prefix} must be a dictionary")
                            continue
                        # Required fields in each code_element
                        required_str_fields = ["name", "element_type", "signature", "description", "target_file", "element_id"]
                        for field in required_str_fields:
                            if field not in code_el:
                                errors.append(f"{ce_prefix} missing required field '{field}'")
                            elif not isinstance(code_el[field], str):
                                errors.append(f"{ce_prefix} field '{field}' must be a string")
                            elif field == "element_id" and not code_el[field].strip():
                                errors.append(f"{ce_prefix} field 'element_id' cannot be empty")
                        
                        # Validate element_type values
                        valid_element_types = {"class", "function", "interface", "enum_type", "struct", "method", "module"}
                        if "element_type" in code_el and code_el["element_type"] not in valid_element_types:
                            errors.append(f"{ce_prefix} field 'element_type' must be one of: {', '.join(valid_element_types)}")
                        
                        # Optional fields and their types
                        optional_fields = {
                            "params": list, # list of strings
                            "start_line": int,
                            "end_line": int,
                            "key_attributes_or_methods": list
                        }
                        for field, expected_type in optional_fields.items():
                            if field in code_el and not isinstance(code_el[field], expected_type):
                                errors.append(f"{ce_prefix} field '{field}' must be a {expected_type.__name__}")
                            if field == "params" and isinstance(code_el.get(field), list):
                                for p_idx, param_val in enumerate(code_el[field]):
                                    if not isinstance(param_val, str):
                                        errors.append(f"{ce_prefix} field 'params[{p_idx}]' must be a string")
                            elif field == "key_attributes_or_methods" and isinstance(code_el.get(field), list):
                                for p_idx, attr_val in enumerate(code_el[field]):
                                    if not isinstance(attr_val, str):
                                        errors.append(f"{ce_prefix} field 'key_attributes_or_methods[{p_idx}]' must be a string")
    
    return errors


def validate_identifier_hygiene(data: Dict[str, Any]) -> List[str]:
    """
    Validate identifier hygiene (naming conventions, keywords) in system_design.code_elements.
    This version iterates through the structured code_elements.
    """
    errors = []
    
    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            # This case should ideally be caught by schema validation first
            logger.warning(f"Skipping feature group at index {group_idx} due to unexpected type: {type(group_data)}")
            continue
        group_name = group_data.get("group_name", f"Group {group_idx}")

        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                logger.warning(f"Skipping feature at index {feature_idx} in group '{group_name}' due to unexpected type: {type(feature_data)}")
                continue
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_location_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"

            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                errors.append(f"{feature_location_log_prefix}: 'system_design' is missing or not a dictionary.")
                logger.debug(f"{feature_location_log_prefix}: system_design is type {type(system_design)}, expected dict.")
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                errors.append(f"{feature_location_log_prefix}: 'system_design.code_elements' is missing or not a list.")
                logger.debug(f"{feature_location_log_prefix}: system_design.code_elements is type {type(code_elements)}, expected list.")
                continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    errors.append(f"{feature_location_log_prefix}: code_elements[{el_idx}] is not a dictionary.")
                    logger.debug(f"{feature_location_log_prefix}: code_elements[{el_idx}] is type {type(element)}, expected dict.")
                    continue

                identifier = element.get("name")
                if not isinstance(identifier, str) or not identifier.strip():
                    errors.append(f"{feature_location_log_prefix}: code_elements[{el_idx}] has missing, empty, or non-string 'name'.")
                    continue # Identifier is crucial for this validation
                
                target_file = element.get("target_file", "")
                if not isinstance(target_file, str): # Ensure target_file is a string for path operations
                    logger.warning(f"{feature_location_log_prefix}: code_elements[{el_idx}] has non-string 'target_file' (type: {type(target_file)}). Using empty string as fallback.")
                    target_file = ""
                    
                lang_keywords = PYTHON_KEYWORDS # Default
                current_lang_name = "Python"
                if isinstance(target_file, str) and target_file:
                    if target_file.endswith((".js", ".jsx", ".mjs")):
                        lang_keywords = JS_KEYWORDS
                        current_lang_name = "JavaScript"
                    elif target_file.endswith((".ts", ".tsx")):
                        lang_keywords = JS_KEYWORDS.union({"interface", "type", "enum", "public", "private", "protected", "readonly", "declare", "module", "namespace", "abstract", "implements", "override"}) # More TS keywords
                        current_lang_name = "TypeScript"
                    elif target_file.endswith(".php"):
                        lang_keywords = PHP_KEYWORDS
                        current_lang_name = "PHP"
                    elif target_file.endswith(".java"): # Basic Java keywords, can be expanded
                        lang_keywords = {"abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const", "continue", "default", "do", "double", "else", "enum", "extends", "final", "finally", "float", "for", "goto", "if", "implements", "import", "instanceof", "int", "interface", "long", "native", "new", "package", "private", "protected", "public", "return", "short", "static", "strictfp", "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try", "void", "volatile", "while"}
                        current_lang_name = "Java"

                id_simple_part = identifier.split('.')[-1] # Check the last part (e.g., method name in Class.method)

                if id_simple_part in lang_keywords:
                    errors.append(
                        f"{feature_location_log_prefix}: Identifier '{identifier}' (in code_elements[{el_idx}]) uses a reserved {current_lang_name} keyword '{id_simple_part}'."
                    )
                
                if id_simple_part and id_simple_part[0].isdigit():
                    errors.append(
                        f"{feature_location_log_prefix}: Identifier '{identifier}' (in code_elements[{el_idx}]) starts with a digit."
                    )
                
                if len(id_simple_part) > 70:
                     errors.append(
                        f"{feature_location_log_prefix}: Identifier part '{id_simple_part}' in '{identifier}' (code_elements[{el_idx}]) is too long (>{len(id_simple_part)} chars)."
                    )
                
                # Regex for typical class/function/method names (simple part)
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", id_simple_part):
                    # If the simple part fails, check if the full identifier is a valid qualified name (e.g., My.Class.method)
                    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$", identifier):
                         errors.append(
                            f"{feature_location_log_prefix}: Identifier '{identifier}' (in code_elements[{el_idx}]) contains invalid characters or structure."
                        )
    return errors


def validate_path_validity(data: Dict[str, Any], repo_root: str) -> List[str]:
    """Validate that specified file paths are syntactically valid, relative, and do not traverse upwards."""
    errors = []
    
    if not repo_root:
        logger.warning("Repository root not provided for path validity checks. Using current directory as fallback for some checks.")
        repo_root = os.getcwd()
    
    # abs_repo_root = os.path.abspath(repo_root) # Not directly used in current checks, but good to have if needed later

    paths_to_validate_with_context = [] # List of (path_string, context_string_for_error_message)

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            # Schema validation should ideally catch this.
            # errors.append(f"Feature group at index {group_idx} is not a dictionary.")
            continue
        group_name = group_data.get("group_name", f"Unnamed Group {group_idx}")

        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                # errors.append(f"Feature at index {feature_idx} in group '{group_name}' is not a dictionary.")
                continue
            current_feature_name = feature_data.get("name", f"Unnamed Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"
            
            # Validate files_affected
            files_affected = feature_data.get("files_affected", [])
            if isinstance(files_affected, list):
                for i, path_str in enumerate(files_affected):
                    if not isinstance(path_str, str) or not path_str.strip():
                        errors.append(f"{feature_log_prefix}: files_affected[{i}] ('{str(path_str)[:50]}...') is not a valid, non-empty string path.")
                        continue
                    paths_to_validate_with_context.append((path_str, f"{feature_log_prefix}, path from files_affected[{i}]"))
            elif files_affected is not None: # If key exists but is not a list
                 errors.append(f"{feature_log_prefix}: 'files_affected' is not a list, but type {type(files_affected).__name__}.")

            # Validate system_design.code_elements[*].target_file
            system_design = feature_data.get("system_design")
            if isinstance(system_design, dict):
                code_elements = system_design.get("code_elements", [])
                if isinstance(code_elements, list):
                    for el_idx, el_data in enumerate(code_elements):
                        if not isinstance(el_data, dict):
                            # errors.append(f"{feature_log_prefix}: system_design.code_elements[{el_idx}] is not a dictionary.")
                            continue
                        
                        target_file = el_data.get("target_file") # Might be None if key missing
                        element_name = el_data.get("name", f"element at index {el_idx}")

                        if target_file is not None: # Only process if target_file key exists and has a value
                            if isinstance(target_file, str) and target_file.strip():
                                paths_to_validate_with_context.append((target_file, f"{feature_log_prefix}, target_file for code_element '{element_name}'"))
                            elif not isinstance(target_file, str):
                                errors.append(f"{feature_log_prefix}: 'target_file' for code_element '{element_name}' is not a string (type: {type(target_file).__name__}). Value: '{str(target_file)[:50]}...'")
                            else: # Is a string, but empty or whitespace
                                errors.append(f"{feature_log_prefix}: 'target_file' for code_element '{element_name}' is an empty or whitespace-only string.")
                        # If target_file is None (key existed with value None, or key didn't exist and .get returned None), it's skipped.
                        # This assumes that a missing or None target_file is permissible by the schema for some elements.
                elif code_elements is not None: # If key exists but is not a list
                    errors.append(f"{feature_log_prefix}: system_design.code_elements is not a list, but type {type(code_elements).__name__}.")
            elif system_design is not None: # If it exists but isn't a dict (e.g. old string format or other error)
                 errors.append(f"{feature_log_prefix}: system_design is type {type(system_design).__name__}, expected a dictionary for structured data.")

    # Perform validation checks on all collected paths
    for path_str, context_str in paths_to_validate_with_context:
        if "*" in path_str or "?" in path_str:
            errors.append(f"{context_str}: Path '{path_str}' contains wildcard characters (* or ?), which are not allowed for specific file paths.")
            continue

        if ".." in path_str:
            errors.append(f"{context_str}: Path '{path_str}' traverses upwards ('..'), which is disallowed.")
            continue
        
        if os.path.isabs(path_str):
            errors.append(f"{context_str}: Path '{path_str}' is absolute, which is disallowed. All paths must be relative to the project root.")
            continue

        try:
            # os.path.normpath(path_str) # Good for cleaning, but check original for certain issues like backslashes
            if "\\" in path_str and os.sep != "\\":
                 errors.append(f"{context_str}: Path '{path_str}' contains backslashes ('\\') which might cause issues on non-Windows systems. Use forward slashes ('/') for portability.")
        except Exception as e:
            errors.append(f"{context_str}: Error performing basic path checks on '{path_str}': {e}")
            
    return errors


def validate_token_budget(data: Dict[str, Any]) -> List[str]:
    """Validate that token budget estimates are within limits."""
    errors = []
    
    # Track total token usage across all feature groups
    total_tokens = 0
    
    for i, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
        
        group_tokens = 0
        
        for j, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
            
            # Extract token estimate and complexity
            est_tokens = feature.get("est_tokens", 0)
            complexity = feature.get("complexity_enum", 0)
            
            # Validate tokens against complexity
            if complexity in TOKEN_BUDGET_LIMITS and est_tokens > TOKEN_BUDGET_LIMITS[complexity]:
                errors.append(f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} " +
                             f"exceeds token budget: {est_tokens} tokens for complexity level {complexity}")
            
            group_tokens += est_tokens
        
        total_tokens += group_tokens
    
    # Check against global token budget (if defined)
    global_budget = data.get("token_budget", 100000)
    if total_tokens > global_budget:
        errors.append(f"Total token estimate ({total_tokens}) exceeds global budget ({global_budget})")
    
    return errors


def validate_duplicate_symbols(data: Dict[str, Any]) -> List[str]:
    """Check for duplicate symbols within each feature's system_design.code_elements and optionally across features."""
    errors = []
    
    # Global tracking for symbols across all features (symbol_name, target_file) -> feature_location_log
    all_symbols_globally = {}

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            continue
        
        group_name = group_data.get("group_name", f"Group {group_idx}")
        
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                continue
            
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_location_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"
            
            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                # errors.append(f"{feature_location_log_prefix}: system_design is not a dictionary.")
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                # errors.append(f"{feature_location_log_prefix}: system_design.code_elements is not a list.")
                continue

            # Symbol tracking per feature: (symbol_name, target_file) -> list of element indices
            symbols_in_current_feature = defaultdict(list)
            
            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    continue
                
                symbol_name = element.get("name")
                # Use a default for target_file if not present or not a string, to make the symbol_key valid
                target_file = element.get("target_file")
                if not isinstance(target_file, str) or not target_file.strip():
                    target_file = "undefined_target_file"
                
                element_type = element.get("element_type", "unknown_type")


                if not isinstance(symbol_name, str) or not symbol_name:
                    # errors.append(f"{feature_location_log_prefix}, code_elements[{el_idx}] has missing or invalid 'name'.")
                    continue

                # Key for uniqueness within the feature: (symbol_name, target_file)
                # This assumes a symbol is unique by its name within a specific file.
                symbol_key_feature_scope = (symbol_name, target_file)
                symbols_in_current_feature[symbol_key_feature_scope].append(f"code_elements[{el_idx}] ({element_type})")

                # Key for global uniqueness check: (symbol_name, target_file)
                # This helps find if the same function/class in the same file is planned by multiple features.
                symbol_key_global_scope = (symbol_name, target_file)
                current_global_loc_info = f"{feature_location_log_prefix}, element code_elements[{el_idx}] ({element_type})"
                if symbol_key_global_scope in all_symbols_globally:
                    prev_global_loc_info = all_symbols_globally[symbol_key_global_scope]
                    # Avoid reporting the same element twice if it's part of the current feature's internal duplicates
                    is_internal_duplicate = len(symbols_in_current_feature[symbol_key_feature_scope]) > 1
                    if not is_internal_duplicate or (is_internal_duplicate and prev_global_loc_info != current_global_loc_info.split(", element ")[0]): # basic check to avoid self-reporting
                        errors.append(
                            f"Potentially conflicting definition for symbol '{symbol_name}' in file '{target_file}'. "
                            f"Current: {current_global_loc_info}. Previously planned by: {prev_global_loc_info}."
                        )
                else:
                    all_symbols_globally[symbol_key_global_scope] = current_global_loc_info
            
            # Report duplicates found within the current feature's code_elements
            for (s_name, s_file), locations in symbols_in_current_feature.items():
                if len(locations) > 1:
                    locations_str = ", ".join(locations)
                    errors.append(
                        f"{feature_location_log_prefix}: Duplicate symbol '{s_name}' in file '{s_file}' defined {len(locations)} times at: {locations_str} within this feature's system_design."
                    )
    return errors


def validate_reserved_prefixes(data: Dict[str, Any]) -> List[str]:
    """Check for environment variables starting with reserved prefixes, analyzing signatures and descriptions."""
    errors = []
    analyzer = CodeAnalyzer()
    env_vars_found_globally = set()

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict): continue
        group_name = group_data.get("group_name", f"Group {group_idx}")

        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict): continue
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"

            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict): continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list): continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict): continue

                signature_str = element.get("signature", "")
                description_str = element.get("description", "")
                element_name = element.get("name", f"element_{el_idx}")
                
                # Analyze signature for env var usage if it looks like a code block
                if isinstance(signature_str, str) and signature_str.strip():
                    # CodeAnalyzer expects a block of code. A signature might be too small.
                    # We'll try, but this might need refinement based on typical signature content.
                    # If signatures are guaranteed to be just one line, regex might be better here.
                    try:
                        # Determine language for the analyzer
                        target_file = element.get("target_file", "")
                        lang_for_analysis = "python" # default
                        if isinstance(target_file, str) and target_file:
                            if target_file.endswith((".js", ".jsx", ".mjs")): lang_for_analysis = "javascript"
                            elif target_file.endswith((".ts", ".tsx")): lang_for_analysis = "typescript"
                            elif target_file.endswith(".php"): lang_for_analysis = "php"
                            elif target_file.endswith(".java"): lang_for_analysis = "java"

                        # Wrap signature to make it more parsable as a block if it's simple
                        content_to_analyze = signature_str
                        if lang_for_analysis == "python" and signature_str.strip().endswith(":"):
                            content_to_analyze = signature_str + "\n  pass"
                        
                        analysis_result = analyzer.analyze_code(content_to_analyze, lang=lang_for_analysis)
                        if analysis_result.get("env_vars"):
                            logger.debug(f"{feature_log_prefix}, element '{element_name}': Found env_vars {analysis_result['env_vars']} in signature.")
                            env_vars_found_globally.update(analysis_result["env_vars"])
                    except Exception as e:
                        logger.debug(f"Could not analyze signature of element '{element_name}' for env vars: {e}")

                # Analyze description for env var usage (if descriptions can contain code)
                if isinstance(description_str, str) and "os.getenv" in description_str or "process.env" in description_str: # Quick check
                    try:
                        # Descriptions are less likely to have a clear language, default to python or try to detect
                        analysis_result = analyzer.analyze_code(description_str) # Auto-detect lang
                        if analysis_result.get("env_vars"):
                            logger.debug(f"{feature_log_prefix}, element '{element_name}': Found env_vars {analysis_result['env_vars']} in description.")
                            env_vars_found_globally.update(analysis_result["env_vars"])
                    except Exception as e:
                        logger.debug(f"Could not analyze description of element '{element_name}' for env vars: {e}")
    
    # Check collected environment variables
    for env_var in env_vars_found_globally:
        if env_var in RESERVED_ENV_VARS:
            errors.append(f"Environment variable '{env_var}' is a system-reserved name.")
        # Assuming typical env var naming (uppercase with underscores)
        if not re.match(r"^[A-Z0-9_]+$", env_var):
             errors.append(f"Environment variable '{env_var}' does not follow typical naming convention (UPPERCASE_WITH_UNDERSCORES).")
        # The original check for "__" might be too specific or covered by the general regex.
        # elif "__" in env_var: # This was an old check
        #     errors.append(f"Environment variable '{env_var}' should use single underscore separator")
            
    return errors


def validate_stub_test_coherence(data: Dict[str, Any]) -> List[str]:
    """
    Validate coherence between system_design.code_elements, implementation_plan, and test_requirements.
    Ensures:
    1. 'target_element' in tests (if used) refers to a 'name' in system_design.code_elements.
    2. 'tested_functions' in tests (if used, format: 'file_path::element_name') refer to elements
       defined or planned in the implementation_plan.
    3. Testable code_elements from system_design are targeted by at least one relevant test (via target_element).
    4. Implemented elements from implementation_plan are targeted by at least one relevant test (via tested_functions).
    """
    errors = []
    analyzer = CodeAnalyzer() # Instantiate CodeAnalyzer

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            logger.warning(f"Skipping feature group at index {group_idx} in stub/test coherence check due to unexpected type: {type(group_data)}")
            continue
        group_name = group_data.get("group_name", f"Group {group_idx}")

        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                logger.warning(f"Skipping feature at index {feature_idx} in group '{group_name}' (stub/test coherence) due to unexpected type: {type(feature_data)}")
                continue
            
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"
            
            system_design = feature_data.get("system_design")
            test_requirements = feature_data.get("test_requirements")
            implementation_plan = feature_data.get("implementation_plan")

            # Validate presence of system_design and test_requirements (core for any coherence)
            if not isinstance(system_design, dict):
                errors.append(f"{feature_log_prefix}: 'system_design' is missing or not a dictionary. Cannot validate stub/test coherence.")
                continue
            if not isinstance(test_requirements, dict):
                errors.append(f"{feature_log_prefix}: 'test_requirements' is missing or not a dictionary. Cannot validate stub/test coherence.")
                continue

            code_elements_from_design = system_design.get("code_elements")
            if not isinstance(code_elements_from_design, list):
                errors.append(f"{feature_log_prefix}: 'system_design.code_elements' is missing or not a list. Cannot validate stub/test coherence.")
                # Continue to next feature if core design elements are missing
                continue

            # 1. Collect defined element names from system_design
            defined_element_names_in_design = set()
            element_types_map_from_design = {}
            for el_idx, element in enumerate(code_elements_from_design):
                if isinstance(element, dict):
                    element_name = element.get("name")
                    element_type = element.get("element_type")
                    if isinstance(element_name, str) and element_name:
                        defined_element_names_in_design.add(element_name)
                        if isinstance(element_type, str) and element_type:
                             element_types_map_from_design[element_name] = element_type
                    else:
                        errors.append(f"{feature_log_prefix}: system_design.code_elements[{el_idx}] has an invalid or missing 'name'.")
                else:
                    errors.append(f"{feature_log_prefix}: system_design.code_elements[{el_idx}] is not a dictionary.")

            # 2. Collect implemented code signatures from implementation_plan
            implemented_code_signatures = set()  # Stores (file_path, element_name)
            if implementation_plan and isinstance(implementation_plan.get("steps"), list):
                for step_idx, step in enumerate(implementation_plan["steps"]):
                    if not isinstance(step, dict):
                        continue # Schema should catch this

                    step_file_path = step.get("file_path")
                    code_block = step.get("code_block")
                    target_element_name_in_step = step.get("target_element_name") # Explicit name in step

                    if step_file_path and target_element_name_in_step:
                        implemented_code_signatures.add((step_file_path, target_element_name_in_step))
                    elif step_file_path and code_block:
                        lang = None
                        if step_file_path.endswith(".py"): lang = "python"
                        elif step_file_path.endswith(".js"): lang = "javascript"
                        elif step_file_path.endswith(".ts"): lang = "typescript"
                        elif step_file_path.endswith(".php"): lang = "php"
                        elif step_file_path.endswith(".java"): lang = "java"
                        
                        try:
                            analysis_results = analyzer.analyze_code(code_block, lang=lang)
                            for el_data in analysis_results.get("elements", []):
                                # el_data is CodeElement(name, element_type, params, ...)
                                implemented_code_signatures.add((step_file_path, el_data.name))
                        except Exception as e:
                            errors.append(f"{feature_log_prefix}: Error analyzing code_block in implementation_plan.steps[{step_idx}] for '{step_file_path}': {str(e)[:100]}")
            
            # 3. Process tests: check target_element (design coherence) and tested_functions (implementation coherence)
            all_test_targets_from_design_link = set() # Names targeted via 'target_element'
            all_tested_signatures_from_impl_link = set() # (file, name) targeted via 'tested_functions'

            test_types_to_check = {
                "unit_tests": "unit_tests",
                "integration_tests": "integration_tests", # Assuming these might also have tested_functions
                "property_based_tests": "property_based_tests",
                "acceptance_tests": "acceptance_tests" # And these
            }

            for test_key_in_req, display_name in test_types_to_check.items():
                test_list = test_requirements.get(test_key_in_req)
                if not isinstance(test_list, list):
                    # Optional: log if a test type is expected but missing, or if it's not a list
                    # errors.append(f"{feature_log_prefix}: test_requirements.{test_key_in_req} is missing or not a list.")
                    continue
                
                for tc_idx, test_case in enumerate(test_list):
                    if not isinstance(test_case, dict):
                        errors.append(f"{feature_log_prefix}: {display_name}[{tc_idx}] is not a dictionary.")
                        continue
                    
                    # Check 'target_element' (link to system_design)
                    target_design_el = test_case.get("target_element")
                    if isinstance(target_design_el, str) and target_design_el:
                        all_test_targets_from_design_link.add(target_design_el)
                        if target_design_el not in defined_element_names_in_design:
                            available_symbols_preview = list(defined_element_names_in_design)[:5]
                            preview_str = ", ".join(available_symbols_preview)
                            if len(defined_element_names_in_design) > 5: preview_str += "..."
                            elif not defined_element_names_in_design: preview_str = "None defined in system_design"
                            errors.append(
                                f"{feature_log_prefix}: {display_name}[{tc_idx}].target_element '{target_design_el}' "
                                f"does not match any 'name' in system_design.code_elements. Available: {preview_str}."
                            )
                    elif "target_element" in test_case and not (isinstance(target_design_el, str) and target_design_el) : # Key exists but invalid
                         errors.append(f"{feature_log_prefix}: {display_name}[{tc_idx}] has an invalid 'target_element'.")

                    # Check 'tested_functions' (link to implementation_plan)
                    tested_functions_list = test_case.get("tested_functions")
                    if isinstance(tested_functions_list, list):
                        for tf_idx, tested_func_str in enumerate(tested_functions_list):
                            if not isinstance(tested_func_str, str) or "::" not in tested_func_str:
                                errors.append(f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions[{tf_idx}] ('{tested_func_str}') is invalid. Expected format 'file_path::element_name'.")
                                continue
                            
                            try:
                                tf_path, tf_name = tested_func_str.split("::", 1)
                                current_tested_sig = (tf_path, tf_name)
                                all_tested_signatures_from_impl_link.add(current_tested_sig)

                                if current_tested_sig not in implemented_code_signatures:
                                    # More detailed error if name matches but path doesn't, or vice-versa
                                    found_by_name_only = [p for p, s_name in implemented_code_signatures if s_name == tf_name]
                                    found_by_path_only = [s_name for p, s_name in implemented_code_signatures if p == tf_path]
                                    
                                    error_msg = f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions[{tf_idx}] ('{tested_func_str}') does not match any (file_path, element_name) pair derived from the implementation_plan. "
                                    if not implemented_code_signatures:
                                        error_msg += "No elements found in implementation_plan steps."
                                    else:
                                        if found_by_name_only and tf_path not in [p for p, _ in implemented_code_signatures if _ == tf_name]:
                                            error_msg += f"Element name '{tf_name}' exists in implementation_plan but under different file path(s): {list(set(found_by_name_only))[:3]}. "
                                        elif found_by_path_only and tf_name not in [s_name for p, s_name in implemented_code_signatures if p == tf_path]:
                                            error_msg += f"File path '{tf_path}' exists in implementation_plan but does not contain element '{tf_name}'. Elements in this file: {list(set(found_by_path_only))[:3]}. "
                                        else: # General mismatch
                                            preview_impl_sigs = list(implemented_code_signatures)[:3]
                                            error_msg += f"Available in implementation_plan: {preview_impl_sigs}"
                                            if len(implemented_code_signatures) > 3: error_msg += "..."
                                    errors.append(error_msg)
                            except ValueError:
                                errors.append(f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions[{tf_idx}] ('{tested_func_str}') is malformed. Expected 'file_path::element_name'.")
                    elif "tested_functions" in test_case: # Key exists but not a list
                         errors.append(f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions should be a list of strings.")

            # 4. Check for untested elements from system_design
            testable_element_types = {"function", "class", "struct", "method", "module"} # As per original
            actually_testable_elements_in_design = set()
            for name in defined_element_names_in_design:
                el_type = element_types_map_from_design.get(name, "unknown")
                if el_type in testable_element_types:
                    actually_testable_elements_in_design.add(name)
            
            untested_design_elements = actually_testable_elements_in_design - all_test_targets_from_design_link
            if untested_design_elements:
                for symbol_name in untested_design_elements:
                    el_type_str = element_types_map_from_design.get(symbol_name, 'N/A')
                    errors.append(
                        f"{feature_log_prefix}: Testable element '{symbol_name}' (type: {el_type_str}) "
                        f"from system_design.code_elements is not targeted by any 'target_element' in tests for this feature."
                    )

            # 5. Check for untested implemented elements from implementation_plan
            if implementation_plan: # Only if plan exists
                untested_implemented_elements = implemented_code_signatures - all_tested_signatures_from_impl_link
                if untested_implemented_elements:
                    for impl_path, impl_name in untested_implemented_elements:
                        # Try to find its type from system_design if it was also defined there
                        # This link is indirect and might not always be present or accurate
                        original_design_type = "N/A"
                        for el_design in code_elements_from_design:
                            if isinstance(el_design, dict) and el_design.get("name") == impl_name and el_design.get("target_file") == impl_path:
                                original_design_type = el_design.get("element_type", "N/A")
                                break
                        errors.append(
                            f"{feature_log_prefix}: Implemented element '{impl_path}::{impl_name}' (original design type: {original_design_type}) "
                            f"from implementation_plan is not targeted by any 'tested_functions' entry in tests for this feature."
                        )
    return errors


def validate_code_syntax(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Validate syntax of code signatures in system_design.code_elements.
    
    Args:
        data: Parsed JSON data from pre-planner

    Returns:
        List of error objects, each with 'feature_name', 'group_idx', 'feature_idx', 'element_idx', 'element_name', 'message'
    """
    errors = []
    # analyzer = CodeAnalyzer() # Not strictly needed if only parsing signatures with ast/tree-sitter directly

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict): continue
        
        group_name = group_data.get("group_name", f"Group {group_idx}")
        
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict): continue
            
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"
            
            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                # errors.append({...}) # Covered by schema validation
                continue
            
            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                # errors.append({...}) # Covered by schema validation
                continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    # errors.append({...}) # Covered by schema validation
                    continue

                signature_str = element.get("signature")
                element_type = element.get("element_type")
                element_name = element.get("name", f"unnamed_element_{el_idx}")
                target_file = element.get("target_file", "")

                if not isinstance(signature_str, str) or not signature_str.strip():
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": f"Missing or empty 'signature' for code_element."
                    })
                    continue

                # Determine language for parsing
                lang = "python" # Default
                if isinstance(target_file, str):
                    if target_file.endswith((".js", ".jsx", ".mjs")): lang = "javascript"
                    elif target_file.endswith((".ts", ".tsx")): lang = "typescript"
                    elif target_file.endswith(".php"): lang = "php"
                    elif target_file.endswith(".java"): lang = "java"
                
                parse_content = signature_str
                try:
                    if lang == "python":
                        # Attempt to make it a parsable snippet
                        if element_type == "function" and signature_str.strip().endswith(":"):
                            parse_content = f"{signature_str}\n  pass"
                        elif element_type == "class" and signature_str.strip().endswith("):"):
                             parse_content = f"{signature_str}\n  pass"
                        elif element_type == "class" and not signature_str.strip().endswith("):") and ":" not in signature_str : # e.g. "class MyClass"
                             parse_content = f"{signature_str}:\n  pass"

                        ast.parse(parse_content)

                    elif lang in ["javascript", "typescript"]:
                        # Attempt to make it a parsable snippet for tree-sitter
                        if element_type == "function":
                            # Handle arrow functions like `(a: type) => type:` or `name = (a:type): type =>`
                            if "=>" in signature_str:
                                if not signature_str.strip().endswith(";") and not signature_str.strip().endswith("}"):
                                     # Try to wrap in a const assignment if it looks like an arrow func expression
                                     if not re.match(r"^\s*(const|let|var)\s+\w+\s*=", signature_str):
                                         parse_content = f"const tempFunc = {signature_str};"
                                     elif not signature_str.strip().endswith(";"):
                                         parse_content = f"{signature_str};"

                            elif '(' in signature_str and ')' in signature_str and not signature_str.strip().endswith(";") and not signature_str.strip().endswith("}"):
                                parse_content = f"{signature_str} {{}}" # For `function name(args): type`
                        elif element_type == "class" and not signature_str.strip().endswith("}"):
                             parse_content = f"{signature_str} {{}}"
                        elif element_type == "interface" and not signature_str.strip().endswith("}"):
                             parse_content = f"{signature_str} {{}}"
                        
                        # Use the appropriate parser from agent_s3.ast_tools
                        if lang == "javascript":
                            parse_js(bytes(parse_content, "utf8"))
                        elif lang == "typescript":
                            # from agent_s3.ast_tools.parser import parse_ts # Ensure this is available
                            # For now, using parse_js as a fallback for basic TS syntax if parse_ts isn't set up
                            # This is a simplification; a real TS parser would be better.
                            try:
                                from agent_s3.ast_tools.ts_languages import get_ts_parser # Try to import specific TS parser
                                parser = get_ts_parser()
                                parser.parse(bytes(parse_content, "utf8"))
                            except ImportError:
                                logger.warning("TypeScript parser not fully available, using JavaScript parser for basic syntax check of TS.")
                                parse_js(bytes(parse_content, "utf8"))


                    elif lang == "php":
                        # PHP parsing is complex. A simple check:
                        if element_type == "function" and "function " not in signature_str:
                             errors.append({"message": f"PHP function signature for '{element_name}' should start with 'function '."}) # Example
                        # Full PHP syntax check usually requires `php -l` or a dedicated PHP parser lib
                        pass # Placeholder for more robust PHP check

                    elif lang == "java":
                        # Java parsing is also complex. Basic check:
                        if element_type == "class" and "class " not in signature_str:
                            errors.append({"message": f"Java class signature for '{element_name}' should start with 'class '."})
                        elif element_type == "interface" and "interface " not in signature_str:
                            errors.append({"message": f"Java interface signature for '{element_name}' should start with 'interface '."})
                        # Full Java syntax check requires a Java compiler/parser
                        pass # Placeholder

                except SyntaxError as e: # Python's ast.parse specific error
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": f"Python syntax error in signature '{signature_str[:50]}...': {e.msg} (line {e.lineno}, offset {e.offset}). Parsed as: '{parse_content[:50]}...'"
                    })
                except Exception as e: # Generic error for other parsers or issues
                    errors.append({
                        "feature_name": current_feature_name, "group_idx": group_idx, "feature_idx": feature_idx,
                        "element_idx": el_idx, "element_name": element_name,
                        "message": f"Syntax error or parsing issue in {lang} signature '{signature_str[:50]}...': {str(e)}. Parsed as: '{parse_content[:50]}...'"
                    })
    return errors
            


def validate_complexity_sanity(data: Dict[str, Any]) -> List[str]:
    """Check that complexity levels correlate with token estimates."""
    errors = []
    
    for i, group in enumerate(data.get("feature_groups", [])):
        if not isinstance(group, dict):
            continue
        
        for j, feature in enumerate(group.get("features", [])):
            if not isinstance(feature, dict):
                continue
            
            # Extract token estimate and complexity
            est_tokens = feature.get("est_tokens", 0)
            complexity = feature.get("complexity_enum", 0)
            
            # Check if complexity level exists
            if complexity not in TOKEN_BUDGET_LIMITS:
                errors.append(f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} " +
                             f"has invalid complexity level: {complexity}")
                continue
            
            # Sanity checks for complexity vs. token count
            if complexity == 0 and est_tokens > TOKEN_BUDGET_LIMITS[0]:  # trivial
                errors.append(f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} " +
                             f"marked as trivial but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[0]})")
            elif complexity == 1 and est_tokens > TOKEN_BUDGET_LIMITS[1]:  # simple
                errors.append(f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} " +
                             f"marked as simple but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[1]})")
            elif complexity == 2 and est_tokens > TOKEN_BUDGET_LIMITS[2]:  # moderate
                errors.append(f"Feature {feature.get('name', f'{j}')} in group {group.get('group_name', f'{i}')} " +
                             f"marked as moderate but has {est_tokens} tokens (expected < {TOKEN_BUDGET_LIMITS[2]})")
    
    return errors


def write_junit_report(errors: List[str], output_path: str = 'plan_validation.xml') -> bool:
    """
    Write validation errors as JUnit XML for CI integration.
    
    Args:
        errors: List of validation error messages
        output_path: Path to write the JUnit XML report
        
    Returns:
        True if report was written successfully
    """
    try:
        # Create the root element
        testsuites = ET.Element("testsuites")
        
        # Create a testsuite element
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", "Plan Validation")
        testsuite.set("tests", str(len(errors) if errors else 1))
        testsuite.set("errors", str(len(errors)))
        testsuite.set("failures", "0")
        testsuite.set("timestamp", datetime.datetime.now().isoformat())
        
        if errors:
            # Create a testcase for each error
            for error in errors:
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("name", error[:40] + "..." if len(error) > 40 else error)
                testcase.set("classname", "plan_validator")
                
                # Add error element
                error_elem = ET.SubElement(testcase, "error")
                error_elem.set("message", error)
                error_elem.text = error
        else:
            # Add a single successful test case
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("name", "Plan validation passed")
            testcase.set("classname", "plan_validator")
        
        # Create the XML tree and write to file
        tree = ET.ElementTree(testsuites)
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        
        return True
    except Exception as e:
        logger.error(f"Error writing JUnit report: {e}")
        return False


def create_github_annotations(errors: List[str]) -> List[Dict[str, Any]]:
    """
    Format validation errors as GitHub annotations.
    
    Args:
        errors: List of validation error messages
        
    Returns:
        List of annotation dictionaries
    """
    annotations = []
    
    for error in errors:
        annotation = {
            "message": error,
            "annotation_level": "failure",
            "title": "Plan Validation Error"
        }
        
        # Try to extract file path and line number if available
        file_match = re.search(r'in\s+file\s+[\'"]?([^\'"\s]+)[\'"]?', error)
        if file_match:
            annotation["path"] = file_match.group(1)
        
        # Try to extract specific path for duplicate route paths
        route_match = re.search(r'Route\s+[\'"]([^\'"]+)[\'"]', error)
        if route_match:
            annotation["path"] = "api_routes.md"  # Create a virtual file for route issues
            
        # Mark as warning for certain types of issues
        if any(x in error.lower() for x in ["warning", "suggest", "recommend", "consider"]):
            annotation["annotation_level"] = "warning"
        
        annotations.append(annotation)
    
    return annotations
