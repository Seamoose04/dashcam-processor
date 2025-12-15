#!/usr/bin/env python3
"""Configuration validation script for dashcam processor deployment."""
import sys
import json
from pathlib import Path
from typing import List, Dict, Any

def validate_global_config(config: Dict[str, Any]) -> List[str]:
    """Validate global configuration structure and values.

    Args:
        config: Global configuration dictionary

    Returns:
        List of error messages
    """
    errors = []

    # Check required top-level sections
    required_sections = ["global", "storage_paths"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")

    # Validate global section
    if "global" in config:
        global_section = config["global"]

        # Check task_retry_delay_seconds is a positive integer
        if "task_retry_delay_seconds" in global_section:
            retry_delay = global_section["task_retry_delay_seconds"]
            if not isinstance(retry_delay, int) or retry_delay <= 0:
                errors.append("task_retry_delay_seconds must be a positive integer")

        # Check max_concurrent_tasks_per_device is a positive integer
        if "max_concurrent_tasks_per_device" in global_section:
            max_tasks = global_section["max_concurrent_tasks_per_device"]
            if not isinstance(max_tasks, int) or max_tasks <= 0:
                errors.append("max_concurrent_tasks_per_device must be a positive integer")

    # Validate storage_paths
    if "storage_paths" in config:
        storage_paths = config["storage_paths"]

        for device_type, paths in storage_paths.items():
            if not isinstance(paths, dict):
                errors.append(f"storage_paths.{device_type} must be an object")
            else:
                # Check that paths are non-empty strings
                for key, path in paths.items():
                    if not isinstance(path, str) or not path.strip():
                        errors.append(f"storage_paths.{device_type}.{key} must be a non-empty string")

    return errors

def validate_device_config(device_id: str, config: Dict[str, Any]) -> List[str]:
    """Validate device-specific configuration.

    Args:
        device_id: Device identifier
        config: Device configuration dictionary

    Returns:
        List of error messages
    """
    errors = []

    # Check capabilities section exists and is an object
    if "capabilities" not in config:
        errors.append(f"{device_id}: Missing 'capabilities' section")
    else:
        capabilities = config["capabilities"]
        if not isinstance(capabilities, dict):
            errors.append(f"{device_id}: 'capabilities' must be an object")

        # Validate capability values
        for key, value in capabilities.items():
            if isinstance(value, dict):
                # Nested capabilities (e.g., gpu, cpu)
                for nested_key, nested_value in value.items():
                    if not isinstance(nested_value, (int, float, str, bool)):
                        errors.append(f"{device_id}: capabilities.{key}.{nested_key} has invalid type")
            elif not isinstance(value, (int, float, str, bool)):
                errors.append(f"{device_id}: capabilities.{key} has invalid type")

    return errors

def validate_config_files(config_dir: Path) -> Dict[str, Any]:
    """Validate all configuration files in the config directory.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Dictionary with validation results
    """
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "global_config_valid": False,
        "device_configs_checked": 0,
        "device_configs_valid": 0
    }

    # Check if config directory exists
    if not config_dir.exists():
        results["valid"] = False
        results["errors"].append(f"Configuration directory not found: {config_dir}")
        return results

    global_config_file = config_dir / "config.json"
    devices_dir = config_dir / "devices"

    # Validate global config
    if global_config_file.exists():
        try:
            with open(global_config_file, 'r') as f:
                global_config = json.load(f)

            errors = validate_global_config(global_config)
            if errors:
                results["valid"] = False
                results["errors"].extend(errors)
                results["global_config_valid"] = False
            else:
                results["global_config_valid"] = True

        except json.JSONDecodeError as e:
            results["valid"] = False
            results["errors"].append(f"Invalid JSON in global config: {str(e)}")
    else:
        results["warnings"].append("Global config file not found")

    # Validate device configs
    if devices_dir.exists():
        device_config_files = list(devices_dir.glob("*.json"))
        results["device_configs_checked"] = len(device_config_files)

        for config_file in device_config_files:
            try:
                with open(config_file, 'r') as f:
                    device_config = json.load(f)

                device_id = config_file.stem
                errors = validate_device_config(device_id, device_config)

                if errors:
                    results["valid"] = False
                    results["errors"].extend(errors)
                else:
                    results["device_configs_valid"] += 1

            except json.JSONDecodeError as e:
                results["valid"] = False
                results["errors"].append(
                    f"Invalid JSON in device config {config_file.name}: {str(e)}"
                )

    return results

def print_validation_report(results: Dict[str, Any]) -> None:
    """Print a formatted validation report.

    Args:
        results: Validation results dictionary
    """
    print("\n" + "="*60)
    print("DASHCAM PROCESSOR CONFIGURATION VALIDATION REPORT")
    print("="*60)

    print(f"\nStatus: {'PASS ✓' if results['valid'] else 'FAIL ✗'}")

    if results["global_config_valid"]:
        print("\n✓ Global configuration is valid")
    else:
        print("\n✗ Global configuration has issues")

    print(f"\nDevice configurations checked: {results['device_configs_checked']}")
    print(f"Device configurations valid: {results['device_configs_valid']}")

    if results["errors"]:
        print("\n" + "-"*60)
        print("ERRORS:")
        print("-"*60)
        for error in results["errors"]:
            print(f"  • {error}")

    if results["warnings"]:
        print("\n" + "-"*60)
        print("WARNINGS:")
        print("-"*60)
        for warning in results["warnings"]:
            print(f"  • {warning}")

    print("\n" + "="*60)

def main():
    """Main entry point for configuration validation."""
    # Use current directory or /etc/dashcam-processor if specified
    config_paths = [
        Path.cwd() / "config",
        Path("/etc/dashcam-processor")
    ]

    config_dir = None
    for path in config_paths:
        if path.exists():
            config_dir = path
            break

    if not config_dir:
        print("Error: No configuration directory found", file=sys.stderr)
        print(f"Checked: {', '.join(str(p) for p in config_paths)}", file=sys.stderr)
        sys.exit(1)

    results = validate_config_files(config_dir)
    print_validation_report(results)

    if not results["valid"]:
        sys.exit(1)
    else:
        print("\nConfiguration validation completed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()