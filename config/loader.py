"""Configuration Loader - Settings management system."""

import json
import os
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigurationLoader:
    """Central configuration manager for the dashcam processor system."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize ConfigurationLoader.

        Args:
            config_path: Path to configuration directory. If None, uses default.
        """
        self.config_dir = Path(config_path) if config_path else Path("/etc/dashcam-processor")
        self.global_config_file = self.config_dir / "config.json"
        self.device_configs_dir = self.config_dir / "devices"

        # Create directories if they don't exist
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure configuration directories exist."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.device_configs_dir.mkdir(exist_ok=True)

            # Create default config if it doesn't exist
            if not self.global_config_file.exists():
                self._create_default_config()
        except Exception as e:
            logger.error(f"Failed to create configuration directories: {e}")
            raise

    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        default_config = {
            "global": {
                "task_retry_delay_seconds": 300,
                "max_concurrent_tasks_per_device": 1,
                "storage_retention_days": {
                    "raw_videos": 90,
                    "preproc_data": 30,
                    "heavy_output": 7
                }
            },
            "devices": {},
            "storage_paths": {
                "indoor_nas": {
                    "base": "//nas-1/videos/",
                    "raw": "raw/",
                    "preproc": "preproc/",
                    "heavy_output": "heavy_output/"
                },
                "shed_nas": {
                    "archive_base": "//shed-nas/archive/"
                }
            }
        }

        try:
            with open(self.global_config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            logger.info("Created default configuration file")
        except Exception as e:
            logger.error(f"Failed to create default config: {e}")
            raise

    def get_global_config(self) -> Dict[str, Any]:
        """Get complete global configuration.

        Returns:
            Global configuration dictionary
        """
        try:
            with open(self.global_config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Global config file not found, creating default")
            self._create_default_config()
            return self.get_global_config()
        except Exception as e:
            logger.error(f"Failed to read global config: {e}")
            raise

    def get_device_config(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for specific device.

        Args:
            device_id: Device ID or hostname

        Returns:
            Device-specific configuration dictionary, or None if not found
        """
        config_file = self.device_configs_dir / f"{device_id}.json"

        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.debug(f"Device config not found for {device_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to read device config for {device_id}: {e}")
            raise

    def update_global_config(self, config_update: Dict[str, Any]) -> bool:
        """Update global configuration.

        Args:
            config_update: Partial configuration update

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Read current config
            current_config = self.get_global_config()

            # Deep merge updates
            self._deep_merge(current_config, config_update)

            # Write updated config
            with open(self.global_config_file, 'w') as f:
                json.dump(current_config, f, indent=2)

            logger.info("Updated global configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to update global config: {e}")
            return False

    def update_device_config(
        self,
        device_id: str,
        config_update: Dict[str, Any]
    ) -> bool:
        """Update device-specific configuration.

        Args:
            device_id: Device ID or hostname
            config_update: Partial configuration update

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Read current config (if exists)
            current_config = self.get_device_config(device_id) or {}

            # Deep merge updates
            self._deep_merge(current_config, config_update)

            # Write updated config
            config_file = self.device_configs_dir / f"{device_id}.json"
            with open(config_file, 'w') as f:
                json.dump(current_config, f, indent=2)

            logger.info(f"Updated configuration for device {device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update device config for {device_id}: {e}")
            return False

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source dictionary into target.

        Args:
            target: Dictionary to merge into
            source: Dictionary to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def validate_config(self) -> List[str]:
        """Validate all configurations and return errors.

        Returns:
            List of error messages (empty if no errors)
        """
        errors = []

        # Validate global config
        try:
            self.get_global_config()
        except Exception as e:
            errors.append(f"Global config validation failed: {str(e)}")

        # Validate device configs
        try:
            for config_file in self.device_configs_dir.glob("*.json"):
                with open(config_file, 'r') as f:
                    json.load(f)  # Just validate it's valid JSON
        except Exception as e:
            errors.append(f"Device config validation failed: {str(e)}")

        return errors

    def watch_for_changes(self, callback) -> None:
        """Subscribe to configuration changes.

        This is a simple implementation that checks for file modifications.
        In production, you might want to use proper file watching.

        Args:
            callback: Function to call when config changes
        """
        import time

        last_mod_time = self._get_last_modification_time()

        while True:
            time.sleep(5)
            current_mod_time = self._get_last_modification_time()

            if current_mod_time != last_mod_time:
                logger.info("Configuration changed, invoking callback")
                callback()
                last_mod_time = current_mod_time

    def _get_last_modification_time(self) -> float:
        """Get the last modification time of any config file."""
        files = [self.global_config_file]
        files.extend(self.device_configs_dir.glob("*.json"))

        return max(f.stat().st_mtime for f in files if f.exists())