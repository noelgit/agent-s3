"""
Adaptive Configuration Manager for Context Management System.

This module manages the adaptive configuration lifecycle, including initialization,
optimization, and application of configuration settings.
"""

import os
import logging
import json
import time
from typing import Dict, Any, Optional, List
import threading
import copy
from datetime import datetime

from agent_s3.tools.context_management.adaptive_config.project_profiler import ProjectProfiler
from agent_s3.tools.context_management.adaptive_config.config_templates import ConfigTemplateManager
from agent_s3.tools.context_management.adaptive_config.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class AdaptiveConfigManager:
    """
    Manages the adaptive configuration lifecycle for context management.

    This class integrates project profiling, configuration templates, and
    performance metrics to create and optimize configurations.
    """

    def __init__(
        self,
        repo_path: str,
        config_dir: Optional[str] = None,
        metrics_dir: Optional[str] = None
    ):
        """
        Initialize the adaptive configuration manager.

        Args:
            repo_path: Path to the repository
            config_dir: Optional directory for configuration storage
            metrics_dir: Optional directory for metrics storage
        """
        self.repo_path = repo_path
        self.config_dir = config_dir or os.path.join(repo_path, ".agent_s3", "config")
        self.metrics_dir = metrics_dir or os.path.join(repo_path, ".agent_s3", "metrics")

        # Create directories if they don't exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.metrics_dir, exist_ok=True)

        # Initialize components
        self.profiler = ProjectProfiler(repo_path)
        self.template_manager = ConfigTemplateManager()
        self.metrics_collector = MetricsCollector(self.metrics_dir)

        # Current active configuration
        self.active_config = {}
        self.config_lock = threading.RLock()
        self.config_version = 0

        # Configuration optimization
        self.last_optimization_time = 0
        self.optimization_interval = 3600  # Default: optimize once per hour
        self.optimization_in_progress = False

        # Initialize with a default config
        self._initialize_configuration()

    def _initialize_configuration(self) -> None:
        """Initialize configuration based on repository profile."""
        try:
            # Check if we have a saved configuration
            config_path = os.path.join(self.config_dir, "active_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded_config = json.load(f)

                logger.info("Loaded existing configuration")
                with self.config_lock:
                    self.active_config = loaded_config
                    self.config_version += 1
                return

            # No existing config, create a new one based on repository profile
            logger.info("No existing configuration found, analyzing repository")
            self._create_initial_configuration()

        except Exception as e:
            logger.error("Error initializing configuration: %s", e)
            logger.info("Falling back to default configuration")

            # Fall back to default configuration
            with self.config_lock:
                self.active_config = self.template_manager.get_default_config()
                self.config_version += 1

    def _create_initial_configuration(self) -> None:
        """Create initial configuration based on repository profile."""
        try:
            # Analyze repository
            repo_metrics = self.profiler.analyze_repository()

            # Generate configuration based on repository characteristics
            config = self.profiler.get_recommended_config()

            # Validate configuration
            is_valid, errors = self.template_manager.validate_config(config)
            if not is_valid:
                logger.warning(
                    "Generated configuration has validation errors: %s", errors
                )
                logger.info("Falling back to default configuration")
                config = self.template_manager.get_default_config()

            # Set as active configuration
            with self.config_lock:
                self.active_config = config
                self.config_version += 1

            # Save configuration
            self._save_configuration()

            logger.info(
                "Created initial configuration for %s project",
                repo_metrics.get("project_type"),
            )

        except Exception as e:
            logger.exception("Error creating initial configuration: %s", e)
            logger.info("Falling back to default configuration")

            # Fall back to default configuration
            with self.config_lock:
                self.active_config = self.template_manager.get_default_config()
                self.config_version += 1

    def get_current_config(self) -> Dict[str, Any]:
        """
        Get the current active configuration.

        Returns:
            Copy of the active configuration
        """
        with self.config_lock:
            return copy.deepcopy(self.active_config)

    def get_config_version(self) -> int:
        """
        Get the current configuration version number.

        Returns:
            Configuration version number
        """
        with self.config_lock:
            return self.config_version

    def update_configuration(self, new_config: Dict[str, Any], reason: str) -> bool:
        """
        Update the active configuration.

        Args:
            new_config: New configuration to apply
            reason: Reason for the update

        Returns:
            True if update was successful, False otherwise
        """
        # Validate new configuration
        is_valid, errors = self.template_manager.validate_config(new_config)
        if not is_valid:
            logger.error("Invalid configuration: %s", errors)
            return False

        # Apply update
        with self.config_lock:
            self.active_config = new_config
            self.config_version += 1

        # Save configuration
        self._save_configuration(reason)

        logger.info(
            "Updated configuration (v%s): %s", self.config_version, reason
        )

        return True

    def _save_configuration(self, reason: str = "initial") -> None:
        """
        Save current configuration to disk.

        Args:
            reason: Reason for the configuration update
        """
        try:
            # Save current active configuration
            config_path = os.path.join(self.config_dir, "active_config.json")
            with open(config_path, 'w') as f:
                json.dump(self.active_config, f, indent=2)

            # Save a versioned copy with metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned_config = {
                "config": copy.deepcopy(self.active_config),
                "metadata": {
                    "version": self.config_version,
                    "timestamp": timestamp,
                    "reason": reason
                }
            }

            versioned_path = os.path.join(
                self.config_dir,
                f"config_v{self.config_version}_{timestamp}.json"
            )

            with open(versioned_path, 'w') as f:
                json.dump(versioned_config, f, indent=2)

            # Clean up old versioned configs (keep last 10)
            self._cleanup_old_configs()

        except Exception as e:
            logger.exception("Error saving configuration: %s", e)

    def _cleanup_old_configs(self) -> None:
        """Clean up old versioned configurations."""
        try:
            # Get all versioned config files
            config_files = []
            for filename in os.listdir(self.config_dir):
                if filename.startswith("config_v") and filename.endswith(".json"):
                    file_path = os.path.join(self.config_dir, filename)
                    config_files.append((filename, os.path.getmtime(file_path), file_path))

            # Keep only the latest 10
            if len(config_files) > 10:
                # Sort by modification time (newest first)
                config_files.sort(key=lambda x: x[1], reverse=True)

                # Delete older files
                for _, _, file_path in config_files[10:]:
                    os.remove(file_path)

        except Exception as e:
            logger.exception(
                "Error cleaning up old configurations: %s", e
            )

    def check_optimization_needed(self) -> bool:
        """
        Check if configuration optimization is needed.

        Returns:
            True if optimization is needed, False otherwise
        """
        # Don't optimize if already in progress
        if self.optimization_in_progress:
            return False

        current_time = time.time()
        time_since_last = current_time - self.last_optimization_time

        # Get optimization interval from current config or use default
        interval = self.active_config.get("context_management", {}) \
                                    .get("optimization_interval", self.optimization_interval)

        return time_since_last >= interval

    def optimize_configuration(self) -> bool:
        """
        Optimize configuration based on performance metrics.

        Returns:
            True if optimization was performed, False otherwise
        """
        if self.optimization_in_progress:
            return False

        try:
            self.optimization_in_progress = True

            # Get current configuration
            current_config = self.get_current_config()

            # Get recommendations based on performance metrics
            recommendations = self.metrics_collector.recommend_config_improvements(current_config)

            if recommendations.get("status") == "no_data" or not recommendations.get("recommendations"):
                logger.info("No configuration improvements recommended at this time")
                return False

            # Apply recommended improvements
            new_config = copy.deepcopy(current_config)
            applied_changes = []

            for rec in recommendations.get("recommendations", []):
                if rec.get("confidence") not in ["high", "medium"]:
                    continue  # Only apply high and medium confidence recommendations

                param_path = rec.get("suggested_change", {}).get("parameter")
                new_value = rec.get("suggested_change", {}).get("suggested_value")

                if not param_path or new_value is None:
                    continue

                # Apply change to config
                self._update_config_param(new_config, param_path, new_value)
                applied_changes.append({
                    "parameter": param_path,
                    "old_value": rec.get("suggested_change", {}).get("current_value"),
                    "new_value": new_value,
                    "reason": rec.get("recommendation")
                })

            # If changes were applied, update configuration
            if applied_changes:
                reason = f"Automatic optimization with {len(applied_changes)} improvements"
                if self.update_configuration(new_config, reason):
                    logger.info(
                        "Applied %s configuration improvements",
                        len(applied_changes),
                    )
                    self.last_optimization_time = time.time()
                    return True

            return False

        except Exception as e:
            logger.exception("Error optimizing configuration: %s", e)
            return False

        finally:
            self.optimization_in_progress = False

    def _update_config_param(self, config: Dict[str, Any], param_path: str, value: Any) -> None:
        """
        Update a parameter in the configuration.

        Args:
            config: Configuration to update
            param_path: Parameter path (dot notation)
            value: New parameter value
        """
        parts = param_path.split('.')
        current = config

        # Navigate to the parent object
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Update the parameter
        current[parts[-1]] = value

    def log_context_performance(
        self,
        task_type: str,
        relevance_score: float
    ) -> None:
        """
        Log context performance for the current configuration.

        Args:
            task_type: Type of task
            relevance_score: Relevance score (0-1)
        """
        try:
            self.metrics_collector.log_context_relevance(
                task_type=task_type,
                relevance_score=relevance_score,
                config_used=self.get_current_config()
            )
        except Exception as e:
            logger.exception("Error logging context performance: %s", e)

    def log_token_usage(
        self,
        total_tokens: int,
        available_tokens: int,
        allocated_tokens: Dict[str, int]
    ) -> None:
        """
        Log token usage metrics.

        Args:
            total_tokens: Total tokens used
            available_tokens: Available token budget
            allocated_tokens: Dictionary mapping context sections to token counts
        """
        try:
            self.metrics_collector.log_token_usage(
                total_tokens=total_tokens,
                available_tokens=available_tokens,
                allocated_tokens=allocated_tokens
            )

            # Check if optimization is needed
            if self.check_optimization_needed():
                # Run optimization in a separate thread
                threading.Thread(target=self.optimize_configuration).start()

        except Exception as e:
            logger.exception("Error logging token usage: %s", e)

    def get_config_history(self) -> List[Dict[str, Any]]:
        """
        Get configuration history.

        Returns:
            List of historical configurations with metadata
        """
        history = []

        try:
            for filename in os.listdir(self.config_dir):
                if filename.startswith("config_v") and filename.endswith(".json"):
                    file_path = os.path.join(self.config_dir, filename)
                    with open(file_path, 'r') as f:
                        config_data = json.load(f)

                    if "metadata" in config_data:
                        history.append({
                            "version": config_data["metadata"].get("version"),
                            "timestamp": config_data["metadata"].get("timestamp"),
                            "reason": config_data["metadata"].get("reason"),
                            "file": filename
                        })

            # Sort by version (newest first)
            history.sort(key=lambda x: x.get("version", 0), reverse=True)

        except Exception as e:
            logger.exception("Error getting configuration history: %s", e)

        return history

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of performance metrics.

        Returns:
            Dictionary with performance metrics summary
        """
        try:
            summary = self.metrics_collector.get_metrics_summary()

            # Add config history
            history = self.get_config_history()
            if history:
                summary["config_history"] = {
                    "total_versions": len(history),
                    "latest_version": history[0].get("version") if history else 0,
                    "latest_update": history[0].get("timestamp") if history else None,
                    "latest_reason": history[0].get("reason") if history else None
                }

            return summary
        except Exception as e:
            logger.exception("Error getting performance summary: %s", e)
            return {"error": str(e)}

    def reset_to_version(self, version: int) -> bool:
        """
        Reset configuration to a specific version.

        Args:
            version: Configuration version to reset to

        Returns:
            True if reset was successful, False otherwise
        """
        try:
            # Find the configuration file for the specified version
            target_file = None
            for filename in os.listdir(self.config_dir):
                if filename.startswith(f"config_v{version}_") and filename.endswith(".json"):
                    target_file = os.path.join(self.config_dir, filename)
                    break

            if not target_file:
                logger.error("Configuration version %s not found", version)
                return False

            # Load the configuration
            with open(target_file, 'r') as f:
                config_data = json.load(f)

            if "config" not in config_data:
                logger.error(
                    "Invalid configuration data in %s", target_file
                )
                return False

            # Update configuration
            reason = f"Reset to version {version}"
            return self.update_configuration(config_data["config"], reason)

        except Exception as e:
            logger.exception(
                "Error resetting configuration to version %s: %s", version, e
            )
            return False

    def reset_to_default(self) -> bool:
        """
        Reset configuration to default profile-based configuration.

        Returns:
            True if reset was successful, False otherwise
        """
        try:
            # Generate new configuration based on repository characteristics
            # Analyze the repository and fetch a recommended configuration
            self.profiler.analyze_repository()
            config = self.profiler.get_recommended_config()

            # Update configuration
            reason = "Reset to default profile-based configuration"
            return self.update_configuration(config, reason)

        except Exception as e:
            logger.exception("Error resetting to default configuration: %s", e)
            return False
