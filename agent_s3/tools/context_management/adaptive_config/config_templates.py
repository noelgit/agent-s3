"""
Configuration Templates for Adaptive Configuration.

This module provides predefined configuration templates for different project types
and sizes, as well as validation for configuration parameters.
"""

import json
import logging
from typing import Dict, Any, List, Tuple
import jsonschema

logger = logging.getLogger(__name__)

# Configuration schema for validation
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["context_management"],
    "properties": {
        "context_management": {
            "type": "object",
            "properties": {
                "optimization_interval": {"type": "number", "minimum": 5, "maximum": 300},
                "embedding": {
                    "type": "object",
                    "properties": {
                        "chunk_size": {"type": "integer", "minimum": 100, "maximum": 3000},
                        "chunk_overlap": {"type": "integer", "minimum": 0, "maximum": 1000}
                    }
                },
                "search": {
                    "type": "object",
                    "properties": {
                        "bm25": {
                            "type": "object",
                            "properties": {
                                "k1": {"type": "number", "minimum": 0.1, "maximum": 5.0},
                                "b": {"type": "number", "minimum": 0.1, "maximum": 1.0}
                            }
                        }
                    }
                },
                "summarization": {
                    "type": "object",
                    "properties": {
                        "threshold": {"type": "integer", "minimum": 500, "maximum": 5000},
                        "compression_ratio": {"type": "number", "minimum": 0.1, "maximum": 0.9}
                    }
                },
                "importance_scoring": {
                    "type": "object",
                    "properties": {
                        "code_weight": {"type": "number", "minimum": 0.1, "maximum": 2.0},
                        "comment_weight": {"type": "number", "minimum": 0.1, "maximum": 2.0},
                        "metadata_weight": {"type": "number", "minimum": 0.1, "maximum": 2.0},
                        "framework_weight": {"type": "number", "minimum": 0.1, "maximum": 2.0}
                    }
                }
            }
        }
    }
}

# Base configuration templates
BASE_CONFIG_TEMPLATES = {
    "default": {
        "context_management": {
            "optimization_interval": 60,
            "embedding": {
                "chunk_size": 1000,
                "chunk_overlap": 200,
            },
            "search": {
                "bm25": {
                    "k1": 1.2,
                    "b": 0.75
                },
            },
            "summarization": {
                "threshold": 2000,
                "compression_ratio": 0.5
            },
            "importance_scoring": {
                "code_weight": 1.0,
                "comment_weight": 0.8,
                "metadata_weight": 0.7,
                "framework_weight": 0.9
            }
        }
    },

    # Small project template
    "small": {
        "context_management": {
            "optimization_interval": 30,
            "embedding": {
                "chunk_size": 800,
                "chunk_overlap": 150,
            },
            "search": {
                "bm25": {
                    "k1": 1.1,
                    "b": 0.7
                },
            },
            "summarization": {
                "threshold": 1500,
                "compression_ratio": 0.6
            },
            "importance_scoring": {
                "code_weight": 1.1,
                "comment_weight": 0.9,
                "metadata_weight": 0.8,
                "framework_weight": 0.8
            }
        }
    },

    # Large project template
    "large": {
        "context_management": {
            "optimization_interval": 90,
            "embedding": {
                "chunk_size": 1200,
                "chunk_overlap": 250,
            },
            "search": {
                "bm25": {
                    "k1": 1.3,
                    "b": 0.8
                },
            },
            "summarization": {
                "threshold": 2500,
                "compression_ratio": 0.4
            },
            "importance_scoring": {
                "code_weight": 1.0,
                "comment_weight": 0.7,
                "metadata_weight": 0.7,
                "framework_weight": 1.0
            }
        }
    },

    # Project type specific templates
    "web_frontend": {
        "context_management": {
            "optimization_interval": 45,
            "embedding": {
                "chunk_size": 800,
                "chunk_overlap": 250,
            },
            "importance_scoring": {
                "code_weight": 1.1,
                "framework_weight": 1.2,
                "metadata_weight": 0.8
            }
        }
    },

    "web_backend": {
        "context_management": {
            "embedding": {
                "chunk_size": 1200,
                "chunk_overlap": 200,
            },
            "search": {
                "bm25": {
                    "k1": 1.5,
                    "b": 0.75
                }
            },
            "importance_scoring": {
                "code_weight": 1.2,
                "metadata_weight": 0.6
            }
        }
    },

    "data_science": {
        "context_management": {
            "embedding": {
                "chunk_size": 1500,
                "chunk_overlap": 300,
            },
            "importance_scoring": {
                "comment_weight": 1.0,
                "metadata_weight": 0.9
            }
        }
    },

    "cli_tool": {
        "context_management": {
            "embedding": {
                "chunk_size": 900,
                "chunk_overlap": 180,
            },
            "importance_scoring": {
                "code_weight": 1.3,
                "metadata_weight": 0.6
            }
        }
    },

    "library": {
        "context_management": {
            "embedding": {
                "chunk_size": 1100,
                "chunk_overlap": 220,
            },
            "importance_scoring": {
                "code_weight": 1.1,
                "comment_weight": 1.0,
                "metadata_weight": 0.7
            }
        }
    },

    # Language specific templates
    "python": {
        "context_management": {
            "embedding": {
                "chunk_size": 900,  # Python tends to be more concise
            },
            "importance_scoring": {
                "code_weight": 1.0,
                "comment_weight": 0.9
            }
        }
    },

    "javascript": {
        "context_management": {
            "embedding": {
                "chunk_size": 950,
            },
            "search": {
                "bm25": {
                    "k1": 1.3
                }
            }
        }
    },

    "typescript": {
        "context_management": {
            "embedding": {
                "chunk_size": 950,
            },
            "search": {
                "bm25": {
                    "k1": 1.3
                }
            },
            "importance_scoring": {
                "code_weight": 1.1,
                "comment_weight": 0.85
            }
        }
    },

    "java": {
        "context_management": {
            "embedding": {
                "chunk_size": 1200,  # Java tends to be more verbose
            },
            "search": {
                "bm25": {
                    "b": 0.8  # More length normalization for Java
                }
            }
        }
    },

    "csharp": {
        "context_management": {
            "embedding": {
                "chunk_size": 1200,  # C# tends to be more verbose
            },
            "search": {
                "bm25": {
                    "b": 0.8
                }
            }
        }
    }
}


class ConfigTemplateManager:
    """
    Manages configuration templates and provides validation for configuration parameters.
    """

    def __init__(self):
        """Initialize the configuration template manager."""
        self.templates = BASE_CONFIG_TEMPLATES
        self.schema = CONFIG_SCHEMA

    def get_default_config(self) -> Dict[str, Any]:
        """
        Get the default configuration template.

        Returns:
            Default configuration template
        """
        return self.templates["default"].copy()

    def get_template(self, template_name: str) -> Dict[str, Any]:
        """
        Get a configuration template by name.

        Args:
            template_name: Name of the template

        Returns:
            Configuration template dictionary

        Raises:
            ValueError: If template name is not found
        """
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")

        return self.templates[template_name].copy()

    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a configuration against the schema.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            jsonschema.validate(instance=config, schema=self.schema)
            return True, []
        except jsonschema.exceptions.ValidationError as e:
            # Extract error messages
            path = " -> ".join([str(p) for p in e.path])
            message = f"Validation error at {path}: {e.message}"
            return False, [message]

    def merge_templates(self, templates: List[str]) -> Dict[str, Any]:
        """
        Merge multiple templates into a single configuration.

        Templates are applied in order, with later templates overriding earlier ones.
        Always starts with the default template.

        Args:
            templates: List of template names to merge

        Returns:
            Merged configuration dictionary

        Raises:
            ValueError: If any template name is not found
        """
        result = self.get_default_config()

        for template_name in templates:
            if template_name not in self.templates:
                raise ValueError(f"Template {template_name} not found")

            template = self.templates[template_name]
            self._deep_merge(result, template)

        return result

    def create_config_for_project(
        self,
        project_size: str,
        project_type: str,
        primary_language: str
    ) -> Dict[str, Any]:
        """
        Create a configuration optimized for a specific project profile.

        Args:
            project_size: Size category (small, medium, large)
            project_type: Type of project (web_frontend, web_backend, etc.)
            primary_language: Primary programming language

        Returns:
            Optimized configuration dictionary
        """
        templates = ["default"]

        # Add size template if valid
        if project_size in ["small", "large"]:
            templates.append(project_size)

        # Add project type template if valid
        if project_type in self.templates:
            templates.append(project_type)

        # Add language template if valid
        if primary_language in self.templates:
            templates.append(primary_language)

        # Merge templates
        config = self.merge_templates(templates)

        # Validate merged config
        is_valid, errors = self.validate_config(config)
        if not is_valid:
            logger.warning(
                "%s",
                "Generated configuration has validation errors: %s",
                errors,
            )
            # Fall back to default if invalid
            return self.get_default_config()

        return config

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge source dictionary into target.

        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from

        Returns:
            Merged dictionary (same reference as target)
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                self._deep_merge(target[key], value)
            else:
                # Override or add value
                target[key] = value

        return target

    def register_template(self, name: str, template: Dict[str, Any]) -> None:
        """
        Register a new configuration template.

        Args:
            name: Template name
            template: Template configuration dictionary

        Raises:
            ValueError: If template is invalid
        """
        # Validate template
        is_valid, errors = self.validate_config(template)
        if not is_valid:
            raise ValueError(f"Invalid template: {errors}")

        # Register template
        self.templates[name] = template

    def load_templates_from_file(self, file_path: str) -> int:
        """
        Load templates from a JSON file.

        Args:
            file_path: Path to JSON file with templates

        Returns:
            Number of templates loaded

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON or templates
        """
        try:
            with open(file_path, 'r') as f:
                templates = json.load(f)

            if not isinstance(templates, dict):
                raise ValueError("Templates file must contain a JSON object")

            count = 0
            for name, template in templates.items():
                self.register_template(name, template)
                count += 1

            return count
        except FileNotFoundError:
            raise FileNotFoundError(f"Templates file not found: {file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in templates file: {file_path}")

    def save_templates_to_file(self, file_path: str) -> None:
        """
        Save all templates to a JSON file.

        Args:
            file_path: Path to save templates

        Raises:
            IOError: If file cannot be written
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.templates, f, indent=2)
        except IOError as e:
            raise IOError(f"Failed to save templates to {file_path}: {e}")

    def create_new_template(
        self,
        name: str,
        base_template: str,
        overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new template based on an existing one with overrides.

        Args:
            name: Name for the new template
            base_template: Name of the template to base on
            overrides: Dictionary of values to override

        Returns:
            The new template

        Raises:
            ValueError: If base template doesn't exist or result is invalid
        """
        if base_template not in self.templates:
            raise ValueError(f"Base template {base_template} not found")

        # Start with base template
        new_template = self.get_template(base_template)

        # Apply overrides
        self._deep_merge(new_template, overrides)

        # Validate new template
        is_valid, errors = self.validate_config(new_template)
        if not is_valid:
            raise ValueError(f"Invalid template after overrides: {errors}")

        # Register new template
        self.templates[name] = new_template

        return new_template
