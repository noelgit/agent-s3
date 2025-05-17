"""JSON Editor Bridge for Agent-S3.

This module provides a specialized interface for editing structured JSON data
in plan outputs, enabling more granular control and focused modifications.
It acts as an intermediary between the pre-planning and planning processes.
"""

import logging
import json
import re
import time
import threading
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from copy import deepcopy
from pathlib import Path

logger = logging.getLogger(__name__)

class JSONPath:
    """Helper class for JSON path operations."""
    
    @staticmethod
    def parse_path(path: str) -> List[Union[str, int]]:
        """Parse a JSON path string into its components.
        
        Args:
            path: The path string (e.g. "feature_groups[0].features[1].name")
            
        Returns:
            List of path components (strings for properties, integers for array indices)
        """
        components = []
        # Match either property names or array indices
        pattern = r'(\w+)|\[(\d+)\]'
        for match in re.finditer(pattern, path):
            prop_name, array_index = match.groups()
            if prop_name:
                components.append(prop_name)
            else:
                components.append(int(array_index))
        return components
    
    @staticmethod
    def get_value(data: Dict[str, Any], path: str) -> Any:
        """Get a value from a nested dictionary using a path.
        
        Args:
            data: The data structure to navigate
            path: The path string (e.g. "feature_groups[0].features[1].name")
            
        Returns:
            The value at the path or None if not found
            
        Raises:
            KeyError or IndexError if path is invalid
        """
        components = JSONPath.parse_path(path)
        current = data
        for component in components:
            if isinstance(component, str):
                current = current[component]
            else:  # Array index
                current = current[component]
        return current
    
    @staticmethod
    def set_value(data: Dict[str, Any], path: str, value: Any) -> Dict[str, Any]:
        """Set a value in a nested dictionary using a path.
        
        Args:
            data: The data structure to modify
            path: The path string (e.g. "feature_groups[0].features[1].name")
            value: The value to set
            
        Returns:
            The modified data structure
            
        Raises:
            KeyError or IndexError if path is invalid
        """
        components = JSONPath.parse_path(path)
        current = data
        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            if isinstance(component, str):
                if component not in current:
                    # If the next component is an index, create a list
                    if i + 1 < len(components) and isinstance(components[i + 1], int):
                        current[component] = []
                    else:
                        current[component] = {}
                current = current[component]
            else:  # Array index
                while len(current) <= component:
                    current.append({})
                current = current[component]
        
        # Set the value on the final component
        final = components[-1]
        if isinstance(final, str):
            current[final] = value
        else:  # Array index
            while len(current) <= final:
                current.append(None)
            current[final] = value
            
        return data


class JSONEditorBridge:
    """Bridge for editing JSON structures in preplanning and planning data."""
    
    def __init__(self, prompt_moderator=None, vscode_bridge=None):
        """Initialize the JSON editor bridge.
        
        Args:
            prompt_moderator: Optional prompt moderator for user interactions
            vscode_bridge: Optional VS Code bridge for UI integration
        """
        self.prompt_moderator = prompt_moderator
        self.vscode_bridge = vscode_bridge
        
    def get_json_schema(self, schema_type: str) -> Dict[str, Any]:
        """Get the appropriate JSON schema based on type.
        
        Args:
            schema_type: The type of schema to get ("pre_planning" or "planning")
            
        Returns:
            The JSON schema as a dictionary
        """
        # Base schemas path
        schemas_dir = Path(__file__).parent.parent / "schemas"
        
        if schema_type == "pre_planning":
            schema_path = schemas_dir / "pre_planning_schema.json"
        elif schema_type == "planning":
            schema_path = schemas_dir / "planning_schema.json"
        else:
            raise ValueError(f"Unknown schema type: {schema_type}")
        
        # Fall back to hardcoded schemas if files don't exist
        if not schema_path.exists():
            logger.warning(f"Schema file {schema_path} not found. Using default schema.")
            if schema_type == "pre_planning":
                return self._get_default_pre_planning_schema()
            else:
                return self._get_default_planning_schema()
        
        # Load schema from file
        try:
            with open(schema_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading schema from {schema_path}: {e}")
            # Fall back to hardcoded schemas
            if schema_type == "pre_planning":
                return self._get_default_pre_planning_schema()
            else:
                return self._get_default_planning_schema()
    
    def _get_default_pre_planning_schema(self) -> Dict[str, Any]:
        """Get the default pre-planning schema.
        
        Returns:
            Default pre-planning schema
        """
        return {
            "type": "object",
            "required": ["original_request", "feature_groups"],
            "properties": {
                "original_request": {"type": "string"},
                "feature_groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["group_name", "group_description", "features"],
                        "properties": {
                            "group_name": {"type": "string"},
                            "group_description": {"type": "string"},
                            "features": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "name", "description", "files_affected", 
                                        "test_requirements", "dependencies", 
                                        "risk_assessment", "system_design"
                                    ],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "files_affected": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        },
                                        "test_requirements": {
                                            "type": "object",
                                            "properties": {
                                                "unit_tests": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "description": {"type": "string"},
                                                            "target_element": {"type": "string"},
                                                            "target_element_id": {"type": "string"},
                                                            "inputs": {"type": "array", "items": {"type": "string"}},
                                                            "expected_outcome": {"type": "string"}
                                                        }
                                                    }
                                                },
                                                "integration_tests": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "description": {"type": "string"},
                                                            "components_involved": {"type": "array", "items": {"type": "string"}},
                                                            "scenario": {"type": "string"}
                                                        }
                                                    }
                                                },
                                                "property_based_tests": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "description": {"type": "string"},
                                                            "target_element": {"type": "string"},
                                                            "target_element_id": {"type": "string"},
                                                            "input_generators": {"type": "array", "items": {"type": "string"}}
                                                        }
                                                    }
                                                },
                                                "acceptance_tests": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "given": {"type": "string"},
                                                            "when": {"type": "string"},
                                                            "then": {"type": "string"}
                                                        }
                                                    }
                                                },
                                                "test_strategy": {
                                                    "type": "object",
                                                    "properties": {
                                                        "coverage_goal": {"type": "string"},
                                                        "ui_test_approach": {"type": "string"}
                                                    }
                                                }
                                            }
                                        },
                                        "dependencies": {
                                            "type": "object",
                                            "properties": {
                                                "internal": {"type": "array", "items": {"type": "string"}},
                                                "external": {"type": "array", "items": {"type": "string"}},
                                                "feature_dependencies": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "feature_name": {"type": "string"},
                                                            "dependency_type": {"type": "string"},
                                                            "reason": {"type": "string"}
                                                        }
                                                    }
                                                }
                                            }
                                        },
                                        "risk_assessment": {
                                            "type": "object",
                                            "properties": {
                                                "critical_files": {"type": "array", "items": {"type": "string"}},
                                                "potential_regressions": {"type": "array", "items": {"type": "string"}},
                                                "backward_compatibility_concerns": {"type": "array", "items": {"type": "string"}},
                                                "mitigation_strategies": {"type": "array", "items": {"type": "string"}},
                                                "required_test_characteristics": {
                                                    "type": "object",
                                                    "properties": {
                                                        "required_types": {"type": "array", "items": {"type": "string"}},
                                                        "required_keywords": {"type": "array", "items": {"type": "string"}},
                                                        "suggested_libraries": {"type": "array", "items": {"type": "string"}}
                                                    }
                                                }
                                            }
                                        },
                                        "system_design": {
                                            "type": "object",
                                            "properties": {
                                                "overview": {"type": "string"},
                                                "code_elements": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "element_type": {"type": "string"},
                                                            "name": {"type": "string"},
                                                            "element_id": {"type": "string"},
                                                            "signature": {"type": "string"},
                                                            "description": {"type": "string"},
                                                            "key_attributes_or_methods": {"type": "array", "items": {"type": "string"}},
                                                            "target_file": {"type": "string"}
                                                        }
                                                    }
                                                },
                                                "data_flow": {"type": "string"},
                                                "key_algorithms": {"type": "array", "items": {"type": "string"}}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _get_default_planning_schema(self) -> Dict[str, Any]:
        """Get the default planning schema.
        
        Returns:
            Default planning schema
        """
        return {
            "type": "object",
            "required": ["architecture_review", "tests", "implementation_plan", "discussion"],
            "properties": {
                "architecture_review": {
                    "type": "object",
                    "properties": {
                        "logical_gaps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "impact": {"type": "string"},
                                    "recommendation": {"type": "string"}
                                }
                            }
                        },
                        "optimization_suggestions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "description": {"type": "string"},
                                    "benefit": {"type": "string"},
                                    "implementation_approach": {"type": "string"}
                                }
                            }
                        },
                        "additional_considerations": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "tests": {
                    "type": "object",
                    "properties": {
                        "unit_tests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "test_name": {"type": "string"},
                                    "tested_functions": {"type": "array", "items": {"type": "string"}},
                                    "target_element_ids": {"type": "array", "items": {"type": "string"}},
                                    "description": {"type": "string"},
                                    "code": {"type": "string"},
                                    "setup_requirements": {"type": "string"}
                                }
                            }
                        },
                        "integration_tests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "test_name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "code": {"type": "string"},
                                    "setup_requirements": {"type": "string"}
                                }
                            }
                        },
                        "property_based_tests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "test_name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "code": {"type": "string"},
                                    "setup_requirements": {"type": "string"}
                                }
                            }
                        },
                        "acceptance_tests": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file": {"type": "string"},
                                    "test_name": {"type": "string"},
                                    "description": {"type": "string"},
                                    "code": {"type": "string"},
                                    "setup_requirements": {"type": "string"},
                                    "given": {"type": "string"},
                                    "when": {"type": "string"},
                                    "then": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "implementation_plan": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "function": {"type": "string"},
                                "description": {"type": "string"},
                                "element_id": {"type": "string"},
                                "steps": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "step_description": {"type": "string"},
                                            "pseudo_code": {"type": "string"},
                                            "relevant_data_structures": {"type": "array", "items": {"type": "string"}},
                                            "api_calls_made": {"type": "array", "items": {"type": "string"}},
                                            "error_handling_notes": {"type": "string"}
                                        }
                                    }
                                },
                                "edge_cases": {"type": "array", "items": {"type": "string"}}
                            }
                        }
                    }
                },
                "discussion": {"type": "string"}
            }
        }
    
    def flatten_json_structure(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Tuple[str, Any]]:
        """Flatten a nested JSON structure into key-value pairs with path information.
        
        Args:
            data: The JSON data to flatten
            prefix: Prefix for current recursion level
            
        Returns:
            Dictionary mapping flattened paths to tuples of (human description, value)
        """
        flat = {}
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                
                # Create human-readable description
                if key == "name" and isinstance(value, str):
                    # For name fields, just use the name as the description
                    description = value
                elif key == "description" and isinstance(value, str):
                    # For description fields, format a descriptive version
                    description = f"Description: {value[:50]}..." if len(value) > 50 else f"Description: {value}"
                else:
                    # Default description is just the field name
                    description = key.replace("_", " ").capitalize()
                
                if isinstance(value, (dict, list)):
                    # Recurse with new prefix
                    flat.update(self.flatten_json_structure(value, new_prefix))
                else:
                    # Leaf node
                    flat[new_prefix] = (description, value)
                    
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_prefix = f"{prefix}[{i}]"
                
                # Try to find a name or description for this list item
                if isinstance(item, dict):
                    # For dictionaries in lists, try to use name or description if available
                    name = item.get("name", "")
                    description = item.get("description", "")
                    if name:
                        item_desc = f"Item {i+1}: {name}"
                    elif description:
                        item_desc = f"Item {i+1}: {description[:30]}..." if len(description) > 30 else f"Item {i+1}: {description}"
                    else:
                        item_desc = f"Item {i+1}"
                else:
                    item_desc = f"Item {i+1}"
                
                if isinstance(item, (dict, list)):
                    # Recurse with new prefix
                    flat.update(self.flatten_json_structure(item, new_prefix))
                else:
                    # Leaf node
                    flat[new_prefix] = (item_desc, item)
        
        return flat
    
    def interactive_edit(self, data: Dict[str, Any], schema_type: str) -> Dict[str, Any]:
        """Interactively edit a JSON structure with validation.
        
        Args:
            data: The JSON data to edit
            schema_type: The schema type to use for validation
            
        Returns:
            The edited JSON data
        """
        if not self.prompt_moderator:
            logger.warning("No prompt moderator available. Cannot perform interactive edit.")
            return data
        
        # Make a copy to avoid modifying the original
        edited_data = deepcopy(data)
        
        # Get schema for validation
        schema = self.get_json_schema(schema_type)
        
        # Check if we have VS Code integration
        using_vscode = (
            self.vscode_bridge and 
            self.prompt_moderator.is_vscode_mode() and
            self.prompt_moderator.vscode_bridge.config.ui_components.get("json_editor", False)
        )
        
        if using_vscode:
            return self._vscode_interactive_edit(edited_data, schema, schema_type)
        else:
            return self._terminal_interactive_edit(edited_data, schema, schema_type)
    
    def _vscode_interactive_edit(self, data: Dict[str, Any], schema: Dict[str, Any], schema_type: str) -> Dict[str, Any]:
        """Perform interactive edit using VS Code UI.
        
        Args:
            data: The JSON data to edit
            schema: The JSON schema for validation
            schema_type: The schema type name
            
        Returns:
            The edited JSON data
        """
        # Create a message to VS Code with the JSON data and schema
        request_id = f"json_edit_{schema_type}_{int(time.time())}"
        
        # Get a flattened view for the tree view
        flat_data = self.flatten_json_structure(data)
        
        # Send the edit request
        wait_for_response = self.vscode_bridge.send_json_editor(
            data=data,
            schema=schema,
            title=f"Edit {schema_type.replace('_', ' ').title()} JSON",
            flat_data=flat_data,
            request_id=request_id
        )
        
        if wait_for_response:
            response = wait_for_response()
            if response and "modified_data" in response:
                return response["modified_data"]
        
        # If VS Code edit failed or was cancelled, fall back to terminal
        self.prompt_moderator.notify_user("VS Code JSON editor failed or cancelled. Falling back to terminal edit.", level="warning")
        return self._terminal_interactive_edit(data, schema, schema_type)
    
    def _terminal_interactive_edit(self, data: Dict[str, Any], schema: Dict[str, Any], schema_type: str) -> Dict[str, Any]:
        """Perform interactive edit using terminal UI.
        
        Args:
            data: The JSON data to edit
            schema: The JSON schema for validation
            schema_type: The schema type name
            
        Returns:
            The edited JSON data
        """
        editing = True
        edited_data = deepcopy(data)
        
        while editing:
            # Flatten the structure for display
            flat_data = self.flatten_json_structure(edited_data)
            
            # Display available fields
            print(f"\n=== JSON Editor ({schema_type}) ===")
            print("Available fields:")
            
            # Group fields by top-level sections
            sections = {}
            for path, (desc, value) in flat_data.items():
                top_section = path.split('.')[0] if '.' in path else path.split('[')[0]
                if top_section not in sections:
                    sections[top_section] = []
                sections[top_section].append((path, desc, value))
            
            # Display sections and fields
            for i, (section, fields) in enumerate(sections.items(), 1):
                print(f"\n{i}. {section.replace('_', ' ').title()}")
                for j, (path, desc, value) in enumerate(fields[:5], 1):  # Show first 5 fields
                    print(f"  {j}. {desc}: {str(value)[:50]}..." if len(str(value)) > 50 else f"  {j}. {desc}: {value}")
                if len(fields) > 5:
                    print(f"  ... and {len(fields) - 5} more fields")
            
            # Ask what to edit
            print("\nOptions:")
            print("1. Edit a specific field")
            print("2. Add a new item to an array")
            print("3. Remove an item from an array")
            print("4. Export to a file for editing")
            print("5. Import from a file")
            print("6. Save and exit")
            
            choice = input("\nEnter your choice (1-6): ").strip()
            
            if choice == "1":
                # Edit a specific field
                path = input("Enter the path to edit (e.g., 'feature_groups[0].features[0].name'): ").strip()
                try:
                    current_value = JSONPath.get_value(edited_data, path)
                    print(f"Current value: {current_value}")
                    new_value = input("Enter new value: ").strip()
                    
                    # Try to parse the new value as JSON if it's not a string
                    if not isinstance(current_value, str):
                        try:
                            new_value = json.loads(new_value)
                        except json.JSONDecodeError:
                            print("Warning: Could not parse as JSON. Treating as string.")
                    
                    edited_data = JSONPath.set_value(edited_data, path, new_value)
                    print(f"Updated {path} to: {new_value}")
                except (KeyError, IndexError) as e:
                    print(f"Error: Invalid path. {e}")
                    
            elif choice == "2":
                # Add a new item to an array
                path = input("Enter the path to the array (e.g., 'feature_groups[0].features'): ").strip()
                try:
                    current_value = JSONPath.get_value(edited_data, path)
                    if not isinstance(current_value, list):
                        print(f"Error: {path} is not an array.")
                        continue
                    
                    # Determine what type of item to add based on schema
                    if len(current_value) > 0:
                        # Use the first item as a template
                        new_item = deepcopy(current_value[0])
                        if isinstance(new_item, dict):
                            # For dictionaries, clear all values but keep structure
                            for key in new_item:
                                if isinstance(new_item[key], (dict, list)):
                                    # Keep structure for nested objects
                                    pass
                                else:
                                    new_item[key] = ""
                        else:
                            new_item = type(new_item)()  # Empty instance of same type
                    else:
                        # No template, create based on schema path
                        print("No existing items to use as template.")
                        new_item_type = input("Enter type for new item (dict/list/string/number/boolean): ").strip().lower()
                        if new_item_type == "dict":
                            new_item = {}
                        elif new_item_type == "list":
                            new_item = []
                        elif new_item_type == "string":
                            new_item = ""
                        elif new_item_type == "number":
                            new_item = 0
                        elif new_item_type == "boolean":
                            new_item = False
                        else:
                            print(f"Unknown type: {new_item_type}. Using empty string.")
                            new_item = ""
                    
                    # For dict items, allow filling in values
                    if isinstance(new_item, dict):
                        for key in new_item:
                            if not isinstance(new_item[key], (dict, list)):
                                new_value = input(f"Enter value for {key}: ").strip()
                                # Try to parse as JSON if not a string
                                if not isinstance(new_item[key], str):
                                    try:
                                        new_value = json.loads(new_value)
                                    except json.JSONDecodeError:
                                        print(f"Warning: Could not parse {new_value} as JSON. Treating as string.")
                                new_item[key] = new_value
                    
                    # Add the new item and update the data
                    current_value.append(new_item)
                    edited_data = JSONPath.set_value(edited_data, path, current_value)
                    print(f"Added new item to {path}.")
                    
                except (KeyError, IndexError) as e:
                    print(f"Error: Invalid path. {e}")
                    
            elif choice == "3":
                # Remove an item from an array
                path = input("Enter the path to the array (e.g., 'feature_groups[0].features'): ").strip()
                try:
                    current_value = JSONPath.get_value(edited_data, path)
                    if not isinstance(current_value, list):
                        print(f"Error: {path} is not an array.")
                        continue
                    
                    if not current_value:
                        print(f"Error: {path} is an empty array.")
                        continue
                    
                    print(f"Current items in {path}:")
                    for i, item in enumerate(current_value):
                        # For dictionaries, try to show a useful identifier
                        if isinstance(item, dict):
                            name = item.get("name", "")
                            desc = item.get("description", "")
                            if name:
                                display = f"{name}"
                            elif desc:
                                display = f"{desc[:50]}..." if len(desc) > 50 else desc
                            else:
                                display = str(item)[:50] + "..." if len(str(item)) > 50 else str(item)
                        else:
                            display = str(item)[:50] + "..." if len(str(item)) > 50 else str(item)
                        print(f"  {i}: {display}")
                    
                    index = int(input("Enter the index to remove: ").strip())
                    if 0 <= index < len(current_value):
                        removed = current_value.pop(index)
                        edited_data = JSONPath.set_value(edited_data, path, current_value)
                        print(f"Removed item at index {index}.")
                    else:
                        print(f"Error: Index {index} out of range.")
                        
                except (KeyError, IndexError) as e:
                    print(f"Error: Invalid path. {e}")
                except ValueError:
                    print("Error: Invalid index.")
                    
            elif choice == "4":
                # Export to a file for editing
                filename = input("Enter filename to export to: ").strip()
                try:
                    with open(filename, "w") as f:
                        json.dump(edited_data, f, indent=2)
                    print(f"Exported to {filename}.")
                    print("Edit the file and then use option 5 to import it back.")
                except Exception as e:
                    print(f"Error exporting to file: {e}")
                    
            elif choice == "5":
                # Import from a file
                filename = input("Enter filename to import from: ").strip()
                try:
                    with open(filename, "r") as f:
                        imported_data = json.load(f)
                    
                    # Validate imported data against schema
                    # Here we would use a JSON schema validator
                    # For now, just check if it has the required top-level keys
                    if schema_type == "pre_planning" and "feature_groups" not in imported_data:
                        print("Error: Imported data missing 'feature_groups' key.")
                        continue
                    elif schema_type == "planning" and not all(k in imported_data for k in ["architecture_review", "tests", "implementation_plan"]):
                        print("Error: Imported data missing required keys.")
                        continue
                    
                    edited_data = imported_data
                    print(f"Imported from {filename}.")
                    
                except json.JSONDecodeError:
                    print("Error: File does not contain valid JSON.")
                except FileNotFoundError:
                    print(f"Error: File {filename} not found.")
                except Exception as e:
                    print(f"Error importing from file: {e}")
                    
            elif choice == "6":
                # Save and exit
                editing = False
                print("Saving changes and exiting editor.")
            else:
                print("Invalid choice. Please enter a number between 1 and 6.")
        
        return edited_data

    def process_validation_errors(self, data: Dict[str, Any], errors: List[Dict[str, Any]], 
                                 schema_type: str) -> Tuple[Dict[str, Any], List[str]]:
        """Process validation errors interactively.
        
        Args:
            data: The JSON data with errors
            errors: List of validation error dictionaries
            schema_type: The schema type for context
            
        Returns:
            Tuple of (updated data, unresolved errors)
        """
        if not self.prompt_moderator:
            logger.warning("No prompt moderator available. Cannot process validation errors.")
            return data, [str(e) for e in errors]
        
        # Make a copy to avoid modifying the original
        edited_data = deepcopy(data)
        unresolved_errors = []
        
        self.prompt_moderator.notify_user(f"Found {len(errors)} validation errors in {schema_type}.", level="warning")
        
        # Group errors by path for easier processing
        grouped_errors = {}
        for error in errors:
            path = error.get("path", "")
            if path not in grouped_errors:
                grouped_errors[path] = []
            grouped_errors[path].append(error)
        
        # Process each group of errors
        for path, path_errors in grouped_errors.items():
            error_msgs = [e.get("message", "Unknown error") for e in path_errors]
            
            # Display the error to the user
            print(f"\n=== Error at {path} ===")
            for i, msg in enumerate(error_msgs, 1):
                print(f"{i}. {msg}")
            
            # Get current value
            try:
                current_value = JSONPath.get_value(edited_data, path) if path else edited_data
                print(f"\nCurrent value: {json.dumps(current_value, indent=2)}")
            except (KeyError, IndexError):
                print(f"\nPath {path} does not exist in the data.")
                current_value = None
            
            # Ask the user what to do
            options = ["Fix this error manually", "Skip this error", "Attempt automatic fix"]
            choice = self.prompt_moderator.present_choices(
                "How would you like to handle this error?", options
            )
            
            if choice == 0:  # Fix manually
                # Allow manual editing
                new_value = input("Enter new value (as JSON): ").strip()
                try:
                    parsed_value = json.loads(new_value)
                    if path:
                        edited_data = JSONPath.set_value(edited_data, path, parsed_value)
                    else:
                        # Updating root - merge to preserve structure
                        if isinstance(edited_data, dict) and isinstance(parsed_value, dict):
                            edited_data.update(parsed_value)
                        else:
                            edited_data = parsed_value
                    print("Value updated.")
                except json.JSONDecodeError:
                    print("Error: Invalid JSON. Skipping this error.")
                    unresolved_errors.extend(error_msgs)
                except (KeyError, IndexError) as e:
                    print(f"Error updating path: {e}. Skipping this error.")
                    unresolved_errors.extend(error_msgs)
                    
            elif choice == 1:  # Skip
                print("Skipping this error.")
                unresolved_errors.extend(error_msgs)
                
            elif choice == 2:  # Automatic fix
                print("Attempting automatic fix...")
                
                # Basic automatic fixes based on error type
                fixed = False
                for error in path_errors:
                    error_type = error.get("keyword", "")
                    
                    if error_type == "required":
                        # Missing required field
                        if isinstance(current_value, dict):
                            missing_prop = error.get("params", {}).get("missingProperty", "")
                            if missing_prop:
                                # Add placeholder based on property name
                                if "name" in missing_prop.lower():
                                    current_value[missing_prop] = f"Default {missing_prop}"
                                elif "description" in missing_prop.lower():
                                    current_value[missing_prop] = f"Default {missing_prop} placeholder"
                                elif missing_prop.endswith("s") and not missing_prop.endswith("ss"):
                                    # Likely an array
                                    current_value[missing_prop] = []
                                else:
                                    # Generic placeholder
                                    current_value[missing_prop] = ""
                                
                                try:
                                    if path:
                                        edited_data = JSONPath.set_value(edited_data, path, current_value)
                                    else:
                                        edited_data = current_value
                                    fixed = True
                                    print(f"Added placeholder for {missing_prop}.")
                                except (KeyError, IndexError) as e:
                                    print(f"Error updating path: {e}")
                        
                    elif error_type == "type":
                        # Type mismatch
                        expected_type = error.get("params", {}).get("type", "")
                        if expected_type == "string" and current_value is not None:
                            # Convert to string
                            try:
                                if path:
                                    edited_data = JSONPath.set_value(edited_data, path, str(current_value))
                                else:
                                    edited_data = str(current_value)
                                fixed = True
                                print(f"Converted value to string.")
                            except (KeyError, IndexError) as e:
                                print(f"Error updating path: {e}")
                                
                        elif expected_type == "array" and current_value is not None:
                            # Convert to array
                            try:
                                if isinstance(current_value, str):
                                    array_value = [current_value]
                                else:
                                    array_value = [current_value]
                                    
                                if path:
                                    edited_data = JSONPath.set_value(edited_data, path, array_value)
                                else:
                                    edited_data = array_value
                                fixed = True
                                print(f"Converted value to array.")
                            except (KeyError, IndexError) as e:
                                print(f"Error updating path: {e}")
                                
                        elif expected_type == "object" and current_value is not None:
                            # Convert to object
                            try:
                                if isinstance(current_value, str):
                                    obj_value = {"value": current_value}
                                else:
                                    obj_value = {"value": str(current_value)}
                                    
                                if path:
                                    edited_data = JSONPath.set_value(edited_data, path, obj_value)
                                else:
                                    edited_data = obj_value
                                fixed = True
                                print(f"Converted value to object.")
                            except (KeyError, IndexError) as e:
                                print(f"Error updating path: {e}")
                
                if not fixed:
                    print("Could not automatically fix all errors at this path.")
                    unresolved_errors.extend(error_msgs)
            
            else:
                print("Invalid choice. Skipping this error.")
                unresolved_errors.extend(error_msgs)
        
        return edited_data, unresolved_errors

    def explain_plan_section(self, data: Dict[str, Any], path: str) -> str:
        """Request an explanation for a specific section of the plan.
        
        Args:
            data: The JSON data containing the plan
            path: The path to the section to explain
            
        Returns:
            Explanation text from the LLM
        """
        if not self.prompt_moderator or not self.prompt_moderator.coordinator or not hasattr(self.prompt_moderator.coordinator, 'router_agent'):
            logger.warning("No router agent available. Cannot provide explanation.")
            return "Unable to provide explanation - router agent not available."
        
        try:
            # Get the section to explain
            section_data = JSONPath.get_value(data, path)
            section_json = json.dumps(section_data, indent=2)
            
            # Create the prompt for the LLM
            system_prompt = """You are a helpful assistant tasked with explaining technical planning details. 
Your explanations should be clear, concise, and focused on helping software engineers understand the rationale
behind design and implementation decisions."""
            
            user_prompt = f"""Please explain the following section from a software development plan:

```json
{section_json}
```

Path: {path}

Provide a clear explanation that covers:
1. What this component/section is meant to accomplish
2. Why it's designed this way
3. How it fits into the overall system design
4. Any critical considerations or rationale for specific design choices

Focus on explaining the "why" behind the decisions, not just describing what's in the JSON."""
            
            # Call the LLM
            router_agent = self.prompt_moderator.coordinator.router_agent
            response = router_agent.call_llm_by_role(
                role='explainer',
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                config={
                    "temperature": 0.3,  # Lower temperature for more factual response
                    "max_tokens": 1000   # Limit response length
                }
            )
            
            return response
            
        except (KeyError, IndexError) as e:
            logger.error(f"Error retrieving section at path {path}: {e}")
            return f"Error: Could not find section at path {path}."
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return f"Error generating explanation: {e}"


def send_json_editor(
    self,
    data: Dict[str, Any],
    schema: Dict[str, Any],
    title: str,
    flat_data: Optional[Dict[str, Tuple[str, Any]]] = None,
    request_id: Optional[str] = None
) -> Optional[Callable[[], Dict[str, Any]]]:
    """Send a JSON editor UI to VS Code extension.
    
    Args:
        data: The JSON data to edit
        schema: The JSON schema for validation
        title: The title for the editor window
        flat_data: Optional flattened view of the data for tree view
        request_id: Optional request ID
        
    Returns:
        Function to wait for and return the response, or None if bridge is not active
    """
    if not self.connection_active or not self.config.enabled:
        return None
        
    # Create a unique ID for this request
    request_id = request_id or f"json_edit_{int(time.time())}"
    
    # Create an event to wait on
    self.response_events[request_id] = threading.Event()
    
    # Flatten data if not provided
    if flat_data is None:
        # Basic flattening for compatibility
        flat_data = {}
        self._flatten_json(data, "", flat_data)
    
    # Create and queue message
    message = Message(
        type=MessageType.JSON_EDITOR,
        content={
            "title": title,
            "data": data,
            "schema": schema,
            "flat_data": flat_data,
            "request_id": request_id
        },
        schema_validation=False  # Skip validation for compatibility
    )
    
    self.message_queue.put(message)
    
    # Return a function to wait for the response
    def wait_for_response(timeout: float = 300) -> Optional[Dict[str, Any]]:
        if self.response_events[request_id].wait(timeout):
            response = self.response_data.pop(request_id, None)
            del self.response_events[request_id]
            return response
        else:
            if request_id in self.response_events:
                del self.response_events[request_id]
            if request_id in self.response_data:
                del self.response_data[request_id]
            logger.warning(f"Timeout waiting for response to JSON editor {request_id}")
            return None
            
    return wait_for_response

def _flatten_json(self, data: Any, prefix: str, result: Dict[str, Tuple[str, Any]]):
    """Helper method to flatten JSON for the tree view.
    
    Args:
        data: The data to flatten
        prefix: Current path prefix
        result: Dictionary to store results in
    """
    if isinstance(data, dict):
        for key, value in data.items():
            new_prefix = f"{prefix}.{key}" if prefix else key
            
            # Create a user-friendly description
            if key == "name" and isinstance(value, str):
                desc = value
            elif key == "description" and isinstance(value, str):
                desc = f"Description: {value[:30]}..." if len(value) > 30 else f"Description: {value}"
            else:
                desc = key.replace("_", " ").capitalize()
                
            if isinstance(value, (dict, list)):
                self._flatten_json(value, new_prefix, result)
            else:
                result[new_prefix] = (desc, value)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_prefix = f"{prefix}[{i}]"
            
            # Try to create a meaningful description for list items
            if isinstance(item, dict) and "name" in item:
                desc = f"Item {i+1}: {item['name']}"
            elif isinstance(item, dict) and "description" in item:
                desc = f"Item {i+1}: {item['description'][:30]}..." if len(item['description']) > 30 else f"Item {i+1}: {item['description']}"
            else:
                desc = f"Item {i+1}"
                
            if isinstance(item, (dict, list)):
                self._flatten_json(item, new_prefix, result)
            else:
                result[new_prefix] = (desc, item)


# Add the JSON editor method to VSCodeBridge
from .vscode_bridge import VSCodeBridge
from .message_protocol import Message, MessageType
VSCodeBridge.send_json_editor = send_json_editor
VSCodeBridge._flatten_json = _flatten_json
