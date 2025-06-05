"""
Configuration Updates for Enhanced Context Management

This module provides configuration examples and utilities for the enhanced
context management system, including unified context management, monitoring,
and orchestrator integration.
"""

import json
import os
from typing import Dict, Any, Optional, List


class ContextManagementConfig:
    """Configuration management for enhanced context management features."""
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """
        Get the default configuration for enhanced context management.
        
        Returns:
            Dictionary with default configuration settings
        """
        return {
            "context_management": {
                "unified_manager": {
                    "enabled": True,
                    "prefer_new_system": True,
                    "enable_deduplication": True,
                    "max_token_limit": 100000,
                    "cache_enabled": True,
                    "cache_size_limit": 1000
                },
                "monitoring": {
                    "enabled": True,
                    "log_level": "INFO",
                    "max_events": 10000,
                    "metrics_window": 300,
                    "enable_file_logging": True,
                    "log_directory": None,  # Will use .agent_s3/logs if None
                    "performance_thresholds": {
                        "max_response_time": 30.0,
                        "max_error_rate": 0.1,
                        "min_cache_hit_rate": 0.5
                    }
                },
                "orchestrator_integration": {
                    "enabled": True,
                    "optimization_interval": 60.0,
                    "max_cache_size": 1000,
                    "context_staleness_threshold": 300.0
                },
                "coordinator_integration": {
                    "enabled": True,
                    "adaptive_config": {
                        "enabled": True,
                        "config_dir": None  # Will use .agent_s3/config if None
                    }
                },
                "llm_integration": {
                    "use_unified_manager": True,
                    "enable_monitoring": True,
                    "context_optimization": True
                }
            }
        }
    
    @staticmethod
    def get_production_config() -> Dict[str, Any]:
        """
        Get production-optimized configuration for enhanced context management.
        
        Returns:
            Dictionary with production configuration settings
        """
        config = ContextManagementConfig.get_default_config()
        
        # Production optimizations
        production_overrides = {
            "context_management": {
                "unified_manager": {
                    "max_token_limit": 150000,
                    "cache_size_limit": 2000
                },
                "monitoring": {
                    "log_level": "WARNING",
                    "max_events": 50000,
                    "metrics_window": 600,  # 10 minutes
                    "performance_thresholds": {
                        "max_response_time": 15.0,  # Stricter in production
                        "max_error_rate": 0.05,     # 5% max error rate
                        "min_cache_hit_rate": 0.7   # 70% min cache hit rate
                    }
                },
                "orchestrator_integration": {
                    "optimization_interval": 30.0,  # More frequent optimization
                    "max_cache_size": 2000,
                    "context_staleness_threshold": 180.0  # 3 minutes
                }
            }
        }
        
        # Deep merge the overrides
        return ContextManagementConfig._deep_merge(config, production_overrides)
    
    @staticmethod
    def get_development_config() -> Dict[str, Any]:
        """
        Get development-optimized configuration for enhanced context management.
        
        Returns:
            Dictionary with development configuration settings
        """
        config = ContextManagementConfig.get_default_config()
        
        # Development optimizations
        development_overrides = {
            "context_management": {
                "monitoring": {
                    "log_level": "DEBUG",
                    "max_events": 5000,
                    "enable_file_logging": True,
                    "performance_thresholds": {
                        "max_response_time": 60.0,  # More lenient in development
                        "max_error_rate": 0.2,      # 20% max error rate
                        "min_cache_hit_rate": 0.3   # 30% min cache hit rate
                    }
                },
                "orchestrator_integration": {
                    "optimization_interval": 120.0,  # Less frequent optimization
                    "max_cache_size": 500
                }
            }
        }
        
        return ContextManagementConfig._deep_merge(config, development_overrides)
    
    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ContextManagementConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def load_config_file(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dictionary with configuration settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is not valid JSON
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def save_config_file(config: Dict[str, Any], config_path: str) -> None:
        """
        Save configuration to a JSON file.
        
        Args:
            config: Configuration dictionary to save
            config_path: Path where to save the configuration file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    @staticmethod
    def merge_with_defaults(user_config: Dict[str, Any], 
                          environment: str = "default") -> Dict[str, Any]:
        """
        Merge user configuration with defaults based on environment.
        
        Args:
            user_config: User-provided configuration
            environment: Environment type ("default", "production", "development")
            
        Returns:
            Merged configuration
        """
        if environment == "production":
            base_config = ContextManagementConfig.get_production_config()
        elif environment == "development":
            base_config = ContextManagementConfig.get_development_config()
        else:
            base_config = ContextManagementConfig.get_default_config()
        
        return ContextManagementConfig._deep_merge(base_config, user_config)
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate configuration for required fields and correct types.
        
        Args:
            config: Configuration to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check if context_management section exists
        if "context_management" not in config:
            errors.append("Missing 'context_management' section")
            return False, errors
        
        cm_config = config["context_management"]
        
        # Validate unified_manager section
        if "unified_manager" in cm_config:
            um_config = cm_config["unified_manager"]
            if not isinstance(um_config.get("enabled"), bool):
                errors.append("unified_manager.enabled must be a boolean")
            if not isinstance(um_config.get("prefer_new_system"), bool):
                errors.append("unified_manager.prefer_new_system must be a boolean")
            if "max_token_limit" in um_config and not isinstance(um_config["max_token_limit"], int):
                errors.append("unified_manager.max_token_limit must be an integer")
        
        # Validate monitoring section
        if "monitoring" in cm_config:
            mon_config = cm_config["monitoring"]
            if not isinstance(mon_config.get("enabled"), bool):
                errors.append("monitoring.enabled must be a boolean")
            if "log_level" in mon_config and mon_config["log_level"] not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                errors.append("monitoring.log_level must be one of: DEBUG, INFO, WARNING, ERROR")
            if "max_events" in mon_config and not isinstance(mon_config["max_events"], int):
                errors.append("monitoring.max_events must be an integer")
        
        # Validate orchestrator_integration section
        if "orchestrator_integration" in cm_config:
            oi_config = cm_config["orchestrator_integration"]
            if not isinstance(oi_config.get("enabled"), bool):
                errors.append("orchestrator_integration.enabled must be a boolean")
            if "optimization_interval" in oi_config and not isinstance(oi_config["optimization_interval"], (int, float)):
                errors.append("orchestrator_integration.optimization_interval must be a number")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_config_template() -> str:
        """
        Get a configuration template as a formatted JSON string.
        
        Returns:
            JSON string with configuration template
        """
        template = ContextManagementConfig.get_default_config()
        return json.dumps(template, indent=2)


def setup_enhanced_context_management(coordinator: Any, 
                                     config: Optional[Dict[str, Any]] = None,
                                     environment: str = "default") -> bool:
    """
    Setup enhanced context management for a coordinator instance.
    
    Args:
        coordinator: Coordinator instance to enhance
        config: Optional configuration dictionary
        environment: Environment type for default settings
        
    Returns:
        True if setup was successful, False otherwise
    """
    try:
        # Get configuration
        if config is None:
            if environment == "production":
                config = ContextManagementConfig.get_production_config()
            elif environment == "development":
                config = ContextManagementConfig.get_development_config()
            else:
                config = ContextManagementConfig.get_default_config()
        
        # Validate configuration
        is_valid, errors = ContextManagementConfig.validate_config(config)
        if not is_valid:
            print(f"Configuration validation failed: {', '.join(errors)}")
            return False
        
        # Apply configuration to coordinator
        if hasattr(coordinator, 'config'):
            # Merge with existing config
            merged_config = ContextManagementConfig._deep_merge(
                coordinator.config.config if hasattr(coordinator.config, 'config') else {},
                config
            )
            coordinator.config.config = merged_config
        else:
            # Create new config attribute
            coordinator.config = type('Config', (), {'config': config})()
        
        # Initialize enhanced context management components  
        from .context_monitoring import get_context_monitor
        from .coordinator_integration import CoordinatorContextIntegration
        
        # Setup consolidated context manager (unified_context_manager removed)
        if config["context_management"]["unified_manager"]["enabled"]:
            # Use the consolidated context manager directly
            if hasattr(coordinator, 'context_manager'):
                coordinator.unified_context_manager = coordinator.context_manager
        
        # Setup monitoring
        if config["context_management"]["monitoring"]["enabled"]:
            monitor = get_context_monitor()
            coordinator.context_monitor = monitor
        
        # Setup coordinator integration
        if config["context_management"]["coordinator_integration"]["enabled"]:
            integration = CoordinatorContextIntegration(coordinator)
            coordinator.context_integration = integration
        
        print("Enhanced context management setup completed successfully")
        return True
        
    except Exception as e:
        print(f"Failed to setup enhanced context management: {e}")
        return False


# Example configuration files

EXAMPLE_CONFIG_JSON = """
{
  "context_management": {
    "unified_manager": {
      "enabled": true,
      "prefer_new_system": true,
      "enable_deduplication": true,
      "max_token_limit": 100000,
      "cache_enabled": true,
      "cache_size_limit": 1000
    },
    "monitoring": {
      "enabled": true,
      "log_level": "INFO",
      "max_events": 10000,
      "metrics_window": 300,
      "enable_file_logging": true,
      "performance_thresholds": {
        "max_response_time": 30.0,
        "max_error_rate": 0.1,
        "min_cache_hit_rate": 0.5
      }
    },
    "orchestrator_integration": {
      "enabled": true,
      "optimization_interval": 60.0,
      "max_cache_size": 1000,
      "context_staleness_threshold": 300.0
    },
    "coordinator_integration": {
      "enabled": true,
      "adaptive_config": {
        "enabled": true
      }
    },
    "llm_integration": {
      "use_unified_manager": true,
      "enable_monitoring": true,
      "context_optimization": true
    }
  }
}
"""

if __name__ == "__main__":
    # Example usage
    print("Enhanced Context Management Configuration")
    print("=" * 50)
    
    # Print default config
    default_config = ContextManagementConfig.get_default_config()
    print("\nDefault Configuration:")
    print(json.dumps(default_config, indent=2))
    
    # Print production config
    prod_config = ContextManagementConfig.get_production_config()
    print("\nProduction Configuration:")
    print(json.dumps(prod_config, indent=2))
    
    # Validate example config
    is_valid, errors = ContextManagementConfig.validate_config(default_config)
    print(f"\nConfiguration Validation: {'PASSED' if is_valid else 'FAILED'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
