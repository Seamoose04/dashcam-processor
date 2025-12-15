"""Unit tests for ConfigurationLoader."""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from config.loader import ConfigurationLoader

@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "config.json"
        devices_dir = config_dir / "devices"

        # Create directories
        devices_dir.mkdir(exist_ok=True)

        # Create global config
        global_config = {
            "global": {
                "task_retry_delay_seconds": 300,
                "max_concurrent_tasks_per_device": 1
            },
            "storage_paths": {
                "indoor_nas": {
                    "base": "//nas-1/videos/"
                }
            }
        }
        with open(config_file, 'w') as f:
            json.dump(global_config, f)

        # Create device config
        device_config = {
            "capabilities": {
                "gpu": "NVIDIA Jetson",
                "memory_gb": 4
            }
        }
        device_file = devices_dir / "jetson-coral-1.json"
        with open(device_file, 'w') as f:
            json.dump(device_config, f)

        yield config_dir

class TestConfigurationLoader:
    """Test cases for ConfigurationLoader."""

    def test_init_with_default_path(self):
        """Test initialization with default path."""
        loader = ConfigurationLoader()
        assert str(loader.config_dir) == "/etc/dashcam-processor"

    def test_init_with_custom_path(self, temp_config_dir):
        """Test initialization with custom path."""
        loader = ConfigurationLoader(str(temp_config_dir))
        assert loader.config_dir == temp_config_dir

    def test_create_default_config(self, temp_config_dir):
        """Test creating default config when it doesn't exist."""
        # Remove the config file
        config_file = temp_config_dir / "config.json"
        config_file.unlink()

        loader = ConfigurationLoader(str(temp_config_dir))

        # Check that default config was created
        assert config_file.exists()
        config = json.loads(config_file.read_text())
        assert "global" in config
        assert "storage_paths" in config

    def test_get_global_config(self, temp_config_dir):
        """Test getting global configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))
        config = loader.get_global_config()

        assert "global" in config
        assert config["global"]["task_retry_delay_seconds"] == 300

    def test_get_device_config(self, temp_config_dir):
        """Test getting device-specific configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))
        device_config = loader.get_device_config("jetson-coral-1")

        assert "capabilities" in device_config
        assert device_config["capabilities"]["gpu"] == "NVIDIA Jetson"

    def test_get_device_config_not_found(self, temp_config_dir):
        """Test getting non-existent device configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))
        device_config = loader.get_device_config("unknown-device")

        assert device_config is None

    def test_update_global_config(self, temp_config_dir):
        """Test updating global configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))

        result = loader.update_global_config({
            "global": {
                "task_retry_delay_seconds": 600
            }
        })

        assert result is True

        # Verify the update
        config = loader.get_global_config()
        assert config["global"]["task_retry_delay_seconds"] == 600

    def test_update_device_config(self, temp_config_dir):
        """Test updating device-specific configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))

        result = loader.update_device_config("jetson-coral-1", {
            "capabilities": {
                "memory_gb": 8
            }
        })

        assert result is True

        # Verify the update
        config = loader.get_device_config("jetson-coral-1")
        assert config["capabilities"]["memory_gb"] == 8

    def test_validate_config_valid(self, temp_config_dir):
        """Test validating valid configuration."""
        loader = ConfigurationLoader(str(temp_config_dir))
        errors = loader.validate_config()

        assert len(errors) == 0

    def test_deep_merge_simple(self, temp_config_dir):
        """Test deep merge with simple dictionaries."""
        loader = ConfigurationLoader(str(temp_config_dir))

        target = {"a": 1, "b": 2}
        source = {"b": 3, "c": 4}

        # Call the protected method via update
        loader.update_global_config(target)
        result = loader.get_global_config()

        assert result["a"] == 1
        assert result["b"] == 2  # Original value preserved

    def test_deep_merge_nested(self, temp_config_dir):
        """Test deep merge with nested dictionaries."""
        loader = ConfigurationLoader(str(temp_config_dir))

        target = {"global": {"a": 1, "b": {"x": 10, "y": 20}}}
        source = {"global": {"b": {"y": 30, "z": 40}}}

        # Call the protected method via update
        loader.update_global_config(target)
        loader.update_global_config(source)

        config = loader.get_global_config()
        assert config["global"]["a"] == 1
        assert config["global"]["b"]["x"] == 10
        assert config["global"]["b"]["y"] == 20  # Original value preserved