"""Feature flag management for controlled deployments.

This module provides functionality for:
1. Managing feature flags to enable staged deployments
2. Controlling access to features in different environments
3. Supporting dynamic enabling/disabling of features
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
import threading

logger = logging.getLogger(__name__)

class FeatureFlagManager:
    """Manages feature flags for controlled feature deployments."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the feature flag manager.

        Args:
            config_path: Path to feature flag configuration JSON file
        """
        self.config_path = config_path or os.path.join(os.getcwd(), "feature_flags.json")
        self._features = {}
        self._lock = threading.RLock()  # For thread safety
        self._last_modified = 0
        self._watch_interval = 30  # Seconds between file checks
        self._file_watcher = None
        self._stop_watching = threading.Event()

        # Load initial configuration
        self.load_configuration()

    def load_configuration(self) -> bool:
        """Load feature flag configuration from file.

        Returns:
            True if configuration was loaded successfully, False otherwise
        """
        with self._lock:
            try:
                config_file = Path(self.config_path)

                # Create default config if it doesn't exist
                if not config_file.exists():
                    logger.info("%s", Feature flag configuration not found at {self.config_path}. Creating default.)
                    self._features = {
                        "features": {},
                        "environments": ["development", "staging", "production"],
                        "current_environment": "development"
                    }
                    self._save_configuration()
                    return True

                # Load existing configuration
                self._last_modified = os.path.getmtime(self.config_path)
                with open(self.config_path, 'r') as f:
                    self._features = json.load(f)

                logger.debug("%s", Loaded {len(self._features.get('features', {}))} feature flags)
                return True
            except Exception as e:
                logger.error("%s", Error loading feature flag configuration: {e})

                # Initialize with empty defaults
                if not self._features:
                    self._features = {
                        "features": {},
                        "environments": ["development", "staging", "production"],
                        "current_environment": "development"
                    }
                return False

    def _save_configuration(self) -> bool:
        """Save current feature flag configuration to file.

        Returns:
            True if saved successfully, False otherwise
        """
        with self._lock:
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(self._features, f, indent=2)
                self._last_modified = os.path.getmtime(self.config_path)
                logger.debug("%s", Saved feature flag configuration with {len(self._features.get('features', {}))} flags)
                return True
            except Exception as e:
                logger.error("%s", Error saving feature flag configuration: {e})
                return False

    def start_watching(self) -> bool:
        """Start watching the configuration file for changes.

        Returns:
            True if watcher started successfully, False otherwise
        """
        if self._file_watcher and self._file_watcher.is_alive():
            logger.warning("File watcher is already running")
            return True

        self._stop_watching.clear()
        self._file_watcher = threading.Thread(target=self._watch_config_file)
        self._file_watcher.daemon = True
        self._file_watcher.start()
        logger.debug("Started feature flag configuration file watcher")
        return True

    def stop_watching(self) -> None:
        """Stop watching the configuration file."""
        if self._file_watcher and self._file_watcher.is_alive():
            self._stop_watching.set()
            self._file_watcher.join(timeout=5)
            logger.debug("Stopped feature flag configuration file watcher")

    def _watch_config_file(self) -> None:
        """Watch the configuration file for changes and reload when modified."""
        while not self._stop_watching.is_set():
            try:
                if os.path.exists(self.config_path):
                    current_mtime = os.path.getmtime(self.config_path)
                    if current_mtime > self._last_modified:
                        logger.info("Feature flag configuration file modified, reloading")
                        self.load_configuration()
            except Exception as e:
                logger.error("%s", Error checking feature flag configuration file: {e})

            self._stop_watching.wait(self._watch_interval)

    def is_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled in the current environment.

        Args:
            feature_name: Name of the feature to check

        Returns:
            True if the feature is enabled, False otherwise
        """
        with self._lock:
            features = self._features.get("features", {})
            current_env = self._features.get("current_environment", "development")

            if feature_name not in features:
                # Feature not defined, default to disabled
                return False

            feature_config = features.get(feature_name, {})

            # Check if explicitly enabled/disabled
            if isinstance(feature_config, bool):
                return feature_config

            # Check environment-specific settings
            enabled_in = feature_config.get("enabled_in", [])

            # Always check exact match first
            if current_env in enabled_in:
                return True

            # If development is enabled and we're in a non-specified environment, default to enabled
            # This makes local development easier
            if "development" in enabled_in and current_env not in self._features.get("environments", []):
                return True

            return False

    def set_feature(self, feature_name: str, enabled: Union[bool, List[str]],
                   description: Optional[str] = None,
                   deployment_stage: Optional[str] = None) -> bool:
        """Set a feature's configuration.

        Args:
            feature_name: Name of the feature
            enabled: Boolean or list of environments where the feature is enabled
            description: Optional description of the feature
            deployment_stage: Optional deployment stage (e.g., 'alpha', 'beta', 'ga')

        Returns:
            True if the feature was set successfully, False otherwise
        """
        with self._lock:
            # Get current features or initialize empty dict
            features = self._features.setdefault("features", {})

            # Create or update feature configuration
            if isinstance(enabled, bool):
                # Simple boolean flag
                features[feature_name] = enabled
            else:
                # Environment-specific configuration
                features[feature_name] = {
                    "enabled_in": enabled,
                    "description": description or "",
                    "deployment_stage": deployment_stage or "alpha"
                }

            return self._save_configuration()

    def remove_feature(self, feature_name: str) -> bool:
        """Remove a feature flag.

        Args:
            feature_name: Name of the feature to remove

        Returns:
            True if the feature was removed successfully, False otherwise
        """
        with self._lock:
            features = self._features.get("features", {})

            if feature_name in features:
                del features[feature_name]
                return self._save_configuration()
            return False

    def set_environment(self, environment: str) -> bool:
        """Set the current environment.

        Args:
            environment: Name of the environment

        Returns:
            True if the environment was set successfully, False otherwise
        """
        with self._lock:
            env_list = self._features.setdefault("environments", ["development", "staging", "production"])

            # Add environment if it doesn't exist
            if environment not in env_list:
                env_list.append(environment)

            self._features["current_environment"] = environment
            return self._save_configuration()

    def get_features(self) -> Dict[str, Any]:
        """Get all feature flags and their configurations.

        Returns:
            Dictionary of all feature flags and their configurations
        """
        with self._lock:
            return dict(self._features.get("features", {}))

    def get_enabled_features(self) -> Set[str]:
        """Get the set of enabled feature names in the current environment.

        Returns:
            Set of feature names that are enabled
        """
        with self._lock:
            features = self._features.get("features", {})
            current_env = self._features.get("current_environment", "development")

            enabled = set()
            for name, config in features.items():
                # Handle boolean flags
                if isinstance(config, bool):
                    if config:
                        enabled.add(name)
                    continue

                # Handle environment-specific config
                enabled_in = config.get("enabled_in", [])
                if current_env in enabled_in:
                    enabled.add(name)
                elif "development" in enabled_in and current_env not in self._features.get("environments", []):
                    enabled.add(name)

            return enabled

    def get_current_environment(self) -> str:
        """Get the current environment name.

        Returns:
            Current environment name
        """
        with self._lock:
            return self._features.get("current_environment", "development")
