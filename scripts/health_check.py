#!/usr/bin/env python3
"""System health check script for dashcam processor deployment."""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

def check_database_connection() -> dict:
    """Check if database is accessible.

    Returns:
        Dictionary with connection status and details
    """
    try:
        # Try to connect to the database (simplified check)
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.exc import OperationalError

        db_url = "sqlite:///dashcam_processor.db"  # Default for testing

        try:
            engine = create_engine(db_url)
            connection = engine.connect()
            connection.close()

            inspector = inspect(engine)
            tables = inspector.get_table_names()

            return {
                "status": "healthy",
                "message": "Database connection successful",
                "tables_found": len(tables),
                "required_tables": ["tasks", "devices", "input_output"]
            }
        except OperationalError as e:
            return {
                "status": "unhealthy",
                "message": f"Database connection failed: {str(e)}"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Database check error: {str(e)}"
        }

def check_config_files() -> dict:
    """Check configuration file existence and validity.

    Returns:
        Dictionary with config status
    """
    config_dirs = [
        Path.cwd() / "config",
        Path("/etc/dashcam-processor")
    ]

    for config_dir in config_dirs:
        if not config_dir.exists():
            continue

        global_config_file = config_dir / "config.json"
        devices_dir = config_dir / "devices"

        results = {
            "status": "healthy",
            "global_config_exists": False,
            "device_configs_found": 0,
            "messages": []
        }

        if global_config_file.exists():
            try:
                with open(global_config_file, 'r') as f:
                    json.load(f)
                results["global_config_exists"] = True
                results["status_detail"] = "Global config valid"
            except Exception as e:
                results["status"] = "unhealthy"
                results["messages"].append(f"Invalid global config: {str(e)}")

        if devices_dir.exists():
            device_configs = list(devices_dir.glob("*.json"))
            results["device_configs_found"] = len(device_configs)

            for config_file in device_configs:
                try:
                    with open(config_file, 'r') as f:
                        json.load(f)
                except Exception as e:
                    results["status"] = "unhealthy"
                    results["messages"].append(
                        f"Invalid device config {config_file.name}: {str(e)}"
                    )

        return results

    return {
        "status": "unhealthy",
        "message": "No configuration directory found"
    }

def check_device_registration() -> dict:
    """Check if devices are properly registered.

    Returns:
        Dictionary with device registration status
    """
    try:
        from services.device_registry import DeviceRegistry
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create in-memory engine for health check
        engine = create_engine('sqlite:///:memory:')
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        session = SessionLocal()

        registry = DeviceRegistry(session)

        # Check if we can list devices (even if empty)
        try:
            devices = registry.list_all_devices()
            return {
                "status": "healthy",
                "devices_registered": len(devices),
                "message": f"Device registry check passed ({len(devices)} devices)"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Device registry error: {str(e)}"
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Device registration check failed: {str(e)}"
        }

def check_task_system() -> dict:
    """Check if task system is functional.

    Returns:
        Dictionary with task system status
    """
    try:
        from services.task_manager import TaskManager
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        # Create in-memory engine for health check
        engine = create_engine('sqlite:///:memory:')
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        session = SessionLocal()

        manager = TaskManager(session)

        # Check if we can create a test task
        try:
            from src.models.task import Base
            Base.metadata.create_all(bind=engine)

            test_task = manager.create_task(
                task_type="HEALTH_CHECK",
                video_id="health_test"
            )

            return {
                "status": "healthy",
                "message": "Task system functional",
                "test_task_created": True,
                "task_id": getattr(test_task, 'task_id', None)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Task creation failed: {str(e)}"
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Task system check error: {str(e)}"
        }

def check_system_dependencies() -> dict:
    """Check if required Python packages are installed.

    Returns:
        Dictionary with dependency status
    """
    missing_packages = []

    # Check key dependencies
    dependencies = {
        "sqlalchemy": "SQLAlchemy ORM",
        "pytest": "Testing framework (optional)"
    }

    for module, description in dependencies.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(description)

    if missing_packages:
        return {
            "status": "unhealthy",
            "message": f"Missing packages: {', '.join(missing_packages)}"
        }
    else:
        return {
            "status": "healthy",
            "message": "All required dependencies installed"
        }

def print_health_report(checks: dict) -> None:
    """Print a formatted health check report.

    Args:
        checks: Dictionary of health check results
    """
    print("\n" + "="*70)
    print("DASHCAM PROCESSOR SYSTEM HEALTH CHECK")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("="*70)

    overall_status = "HEALTHY ✓"
    status_count = {"healthy": 0, "unhealthy": 0}

    for check_name, result in checks.items():
        status = result.get("status", "unknown")
        status_count[status] += 1

        if status == "healthy":
            print(f"\n✓ {check_name.upper().replace('_', ' ')}")
            print(f"  Status: {status}")
            if "message" in result:
                print(f"  Message: {result['message']}")
            for key, value in result.items():
                if key not in ["status", "message"]:
                    print(f"  • {key}: {value}")
        else:
            print(f"\n✗ {check_name.upper().replace('_', ' ')}")
            print(f"  Status: {status}")
            if "message" in result:
                print(f"  Error: {result['message']}")

    # Determine overall status
    if status_count["unhealthy"] > 0:
        overall_status = "UNHEALTHY ✗"

    print("\n" + "-"*70)
    print(f"SUMMARY: {overall_status}")
    print(f"Checks passed: {status_count['healthy']}/{len(checks)}")
    print("-"*70)

def main():
    """Main entry point for health check."""
    checks = {
        "system_dependencies": check_system_dependencies(),
        "database_connection": check_database_connection(),
        "config_files": check_config_files(),
        "device_registration": check_device_registration(),
        "task_system": check_task_system()
    }

    print_health_report(checks)

    # Exit with appropriate code
    unhealthy_checks = [c for c in checks.values() if c.get("status") == "unhealthy"]
    sys.exit(1 if unhealthy_checks else 0)

if __name__ == "__main__":
    main()
