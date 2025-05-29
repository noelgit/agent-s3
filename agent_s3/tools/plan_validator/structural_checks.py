from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from typing import Any, Dict, List

from .ast_utils import CodeAnalyzer
from .config import JS_KEYWORDS, PHP_KEYWORDS, PYTHON_KEYWORDS, RESERVED_ENV_VARS

logger = logging.getLogger(__name__)


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

                            if structure_def["item_type"] is dict:
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
            logger.warning("Skipping feature group at index %d due to unexpected type: %s", group_idx, type(group_data))
            continue
        group_name = group_data.get("group_name", f"Group {group_idx}")
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                logger.warning("Skipping feature at index %d in group '%s' due to unexpected type: %s", feature_idx, group_name, type(feature_data))
                continue
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_location_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"

            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                errors.append(f"{feature_location_log_prefix}: 'system_design' is missing or not a dictionary.")
                logger.debug("%s: system_design is type %s, expected dict.", feature_location_log_prefix, type(system_design))
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                errors.append(f"{feature_location_log_prefix}: 'system_design.code_elements' is missing or not a list.")
                logger.debug("%s: system_design.code_elements is type %s, expected list.", feature_location_log_prefix, type(code_elements))
                continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    errors.append(f"{feature_location_log_prefix}: code_elements[{el_idx}] is not a dictionary.")
                    logger.debug("%s: code_elements[%d] is type %s, expected dict.", feature_location_log_prefix, el_idx, type(element))
                    continue

                identifier = element.get("name")
                if not isinstance(identifier, str) or not identifier.strip():
                    errors.append(f"{feature_location_log_prefix}: code_elements[{el_idx}] has missing, empty, or non-string 'name'.")
                    continue # Identifier is crucial for this validation

                target_file = element.get("target_file", "")
                if not isinstance(target_file, str): # Ensure target_file is a string for path operations
                    logger.warning("%s: code_elements[%d] has non-string 'target_file' (type: %s). Using empty string as fallback.", feature_location_log_prefix, el_idx, type(target_file))
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
        if not isinstance(group_data, dict):
            continue
        group_name = group_data.get("group_name", f"Group {group_idx}")
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                continue
            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"

            system_design = feature_data.get("system_design")
            if not isinstance(system_design, dict):
                continue

            code_elements = system_design.get("code_elements")
            if not isinstance(code_elements, list):
                continue

            for el_idx, element in enumerate(code_elements):
                if not isinstance(element, dict):
                    continue

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
                            if target_file.endswith((".js", ".jsx", ".mjs")):
                                lang_for_analysis = "javascript"
                            elif target_file.endswith((".ts", ".tsx")):
                                lang_for_analysis = "typescript"
                            elif target_file.endswith(".php"):
                                lang_for_analysis = "php"
                            elif target_file.endswith(".java"):
                                lang_for_analysis = "java"

                        # Wrap signature to make it more parsable as a block if it's simple
                        content_to_analyze = signature_str
                        if lang_for_analysis == "python" and signature_str.strip().endswith(":"):
                            content_to_analyze = signature_str + "\n  pass"

                        analysis_result = analyzer.analyze_code(content_to_analyze, lang=lang_for_analysis)
                        if analysis_result.get("env_vars"):
                            logger.debug("%s, element '%s': Found env_vars %s in signature.", feature_log_prefix, element_name, analysis_result['env_vars'])
                            env_vars_found_globally.update(analysis_result["env_vars"])
                    except Exception as e:
                        logger.debug("Could not analyze signature of element '%s' for env vars: %s", element_name, e)

                # Analyze description for env var usage (if descriptions can contain code)
                if isinstance(description_str, str) and "os.getenv" in description_str or "process.env" in description_str: # Quick check
                    try:
                        # Descriptions are less likely to have a clear language, default to python or try to detect
                        analysis_result = analyzer.analyze_code(description_str) # Auto-detect lang
                        if analysis_result.get("env_vars"):
                            logger.debug("%s, element '%s': Found env_vars %s in description.", feature_log_prefix, element_name, analysis_result['env_vars'])
                            env_vars_found_globally.update(analysis_result["env_vars"])
                    except Exception as e:
                        logger.debug("Could not analyze description of element '%s' for env vars: %s", element_name, e)

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



def validate_stub_test_coherence(data: Dict[str, Any], *, error_limit: int | None = None) -> List[str]:
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

    def _record_error(message: str) -> bool:
        """Record an error and return True if the limit is exceeded."""
        errors.append(message)
        return error_limit is not None and len(errors) >= error_limit
    analyzer = CodeAnalyzer() # Instantiate CodeAnalyzer

    for group_idx, group_data in enumerate(data.get("feature_groups", [])):
        if not isinstance(group_data, dict):
            logger.warning("Skipping feature group at index %d in stub/test coherence check due to unexpected type: %s", group_idx, type(group_data))
            continue
        group_name = group_data.get("group_name", f"Group {group_idx}")
        for feature_idx, feature_data in enumerate(group_data.get("features", [])):
            if not isinstance(feature_data, dict):
                logger.warning(
                    f"Skipping feature at index {feature_idx} in group '{group_name}' (stub/test coherence) due to unexpected type: {type(feature_data)}"
                )
                continue

            current_feature_name = feature_data.get("name", f"Feature {feature_idx}")
            feature_log_prefix = f"Feature '{current_feature_name}' in group '{group_name}'"

            system_design = feature_data.get("system_design")
            test_requirements = feature_data.get("test_requirements")
            implementation_plan = feature_data.get("implementation_plan")

            # Validate presence of system_design and test_requirements (core for any coherence)
            if not isinstance(system_design, dict):
                if _record_error(
                    f"{feature_log_prefix}: 'system_design' is missing or not a dictionary. Cannot validate stub/test coherence."
                ):
                    return errors
                continue
            if not isinstance(test_requirements, dict):
                if _record_error(
                    f"{feature_log_prefix}: 'test_requirements' is missing or not a dictionary. Cannot validate stub/test coherence."
                ):
                    return errors
                continue

            code_elements_from_design = system_design.get("code_elements")
            if not isinstance(code_elements_from_design, list):
                if _record_error(
                    f"{feature_log_prefix}: 'system_design.code_elements' is missing or not a list. Cannot validate stub/test coherence."
                ):
                    return errors
                # Continue to next feature if core design elements are missing
                continue

            # 1. Collect defined element names from system_design
            defined_element_names_in_design = set()
            element_types_map_from_design = {}
            design_signature_type_map = {}
            for el_idx, element in enumerate(code_elements_from_design):
                if isinstance(element, dict):
                    element_name = element.get("name")
                    element_type = element.get("element_type")
                    target_file = element.get("target_file")
                    if isinstance(element_name, str) and element_name:
                        defined_element_names_in_design.add(element_name)
                        if isinstance(element_type, str) and element_type:
                             element_types_map_from_design[element_name] = element_type
                        if isinstance(target_file, str) and target_file:
                            design_signature_type_map[(target_file, element_name)] = element_type
                    else:
                        if _record_error(
                            f"{feature_log_prefix}: system_design.code_elements[{el_idx}] has an invalid or missing 'name'."
                        ):
                            return errors
                else:
                    if _record_error(
                        f"{feature_log_prefix}: system_design.code_elements[{el_idx}] is not a dictionary."
                    ):
                        return errors

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
                        if step_file_path.endswith(".py"):
                            lang = "python"
                        elif step_file_path.endswith(".js"):
                            lang = "javascript"
                        elif step_file_path.endswith(".ts"):
                            lang = "typescript"
                        elif step_file_path.endswith(".php"):
                            lang = "php"
                        elif step_file_path.endswith(".java"):
                            lang = "java"

                        try:
                            analysis_results = analyzer.analyze_code(code_block, lang=lang)
                            for el_data in analysis_results.get("elements", []):
                                # el_data is CodeElement(name, element_type, params, ...)
                                implemented_code_signatures.add((step_file_path, el_data.name))
                        except Exception as e:
                            if _record_error(
                                f"{feature_log_prefix}: Error analyzing code_block in implementation_plan.steps[{step_idx}] for '{step_file_path}': {str(e)[:100]}"
                            ):
                                return errors

            # 3. Process tests: check target_element (design coherence) and tested_functions (implementation coherence)
            all_test_targets_from_design_link = set() # Names targeted via 'target_element'
            all_tested_signatures_from_impl_link = set() # (file, name) targeted via 'tested_functions'

            test_types_to_check = {
                "unit_tests": "unit_tests",
                "property_based_tests": "property_based_tests",
                "acceptance_tests": "acceptance_tests"
            }

            for test_key_in_req, display_name in test_types_to_check.items():
                test_list = test_requirements.get(test_key_in_req)
                if not isinstance(test_list, list):
                    # Optional: log if a test type is expected but missing, or if it's not a list
                    # errors.append(f"{feature_log_prefix}: test_requirements.{test_key_in_req} is missing or not a list.")
                    continue

                for tc_idx, test_case in enumerate(test_list):
                    if not isinstance(test_case, dict):
                        if _record_error(
                            f"{feature_log_prefix}: {display_name}[{tc_idx}] is not a dictionary."
                        ):
                            return errors
                        continue

                    # Check 'target_element' (link to system_design)
                    target_design_el = test_case.get("target_element")
                    if isinstance(target_design_el, str) and target_design_el:
                        all_test_targets_from_design_link.add(target_design_el)
                        if target_design_el not in defined_element_names_in_design:
                            available_symbols_preview = list(defined_element_names_in_design)[:5]
                            preview_str = ", ".join(available_symbols_preview)
                            if len(defined_element_names_in_design) > 5:
                                preview_str += "..."
                            elif not defined_element_names_in_design:
                                preview_str = "None defined in system_design"
                            if _record_error(
                                f"{feature_log_prefix}: {display_name}[{tc_idx}].target_element '{target_design_el}' "
                                f"does not match any 'name' in system_design.code_elements. Available: {preview_str}."
                            ):
                                return errors
                    elif "target_element" in test_case and not (isinstance(target_design_el, str) and target_design_el) : # Key exists but invalid
                         if _record_error(
                             f"{feature_log_prefix}: {display_name}[{tc_idx}] has an invalid 'target_element'."
                         ):
                             return errors

                    # Check 'tested_functions' (link to implementation_plan)
                    tested_functions_list = test_case.get("tested_functions")
                    if isinstance(tested_functions_list, list):
                        for tf_idx, tested_func_str in enumerate(tested_functions_list):
                            if not isinstance(tested_func_str, str) or "::" not in tested_func_str:
                                if _record_error(
                                    f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions[{tf_idx}] ('{tested_func_str}') is invalid. Expected format 'file_path::element_name'."
                                ):
                                    return errors
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
                                            if len(implemented_code_signatures) > 3:
                                                error_msg += "..."
                                    if _record_error(error_msg):
                                        return errors
                            except ValueError:
                                if _record_error(
                                    f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions[{tf_idx}] ('{tested_func_str}') is malformed. Expected 'file_path::element_name'."
                                ):
                                    return errors
                    elif "tested_functions" in test_case: # Key exists but not a list
                         if _record_error(
                             f"{feature_log_prefix}: {display_name}[{tc_idx}].tested_functions should be a list of strings."
                         ):
                             return errors

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
                    if _record_error(
                        f"{feature_log_prefix}: Testable element '{symbol_name}' (type: {el_type_str}) "
                        f"from system_design.code_elements is not targeted by any 'target_element' in tests for this feature."
                    ):
                        return errors

            # 5. Check for untested implemented elements from implementation_plan
            if implementation_plan: # Only if plan exists
                untested_implemented_elements = implemented_code_signatures - all_tested_signatures_from_impl_link
                if untested_implemented_elements:
                    for impl_path, impl_name in untested_implemented_elements:
                        original_design_type = design_signature_type_map.get((impl_path, impl_name), "N/A")
                        if _record_error(
                            f"{feature_log_prefix}: Implemented element '{impl_path}::{impl_name}' (original design type: {original_design_type}) "
                            f"from implementation_plan is not targeted by any 'tested_functions' entry in tests for this feature."
                        ):
                            return errors
    return errors



