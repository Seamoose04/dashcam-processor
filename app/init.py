"""System Initializer - Database setup, service registration, and configuration loading."""

from typing import Dict, Any
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.loader import ConfigurationLoader
from db.init_db import init_database, check_database_health
from services.task_manager import TaskManager
from services.device_registry import DeviceRegistry
from services.data_access import DataAccessLayer

logger = logging.getLogger(__name__)

class SystemInitializer:
    """Central system initializer for the dashcam processor pipeline."""

    def __init__(self, config_path: str = None):
        """Initialize SystemInitializer.

        Args:
            config_path: Path to configuration directory. If None, uses default.
        """
        self.config_path = config_path
        self.config_loader = ConfigurationLoader(config_path)
        self.global_config = None
        self.db_engine = None
        self.db_session_factory = None

    def initialize(self) -> Dict[str, Any]:
        """Initialize the entire system.

        Returns:
            Dictionary containing initialized services and configuration

        Raises:
            Exception: If initialization fails
        """
        logger.info("Starting system initialization")

        try:
            # Load configuration
            self._initialize_configuration()

            # Initialize database
            self._initialize_database()

            # Validate configuration
            self._validate_system()

            logger.info("System initialization completed successfully")
            return {
                "config_loader": self.config_loader,
                "global_config": self.global_config,
                "db_engine": self.db_engine,
                "task_manager": TaskManager(self._get_db_session()),
                "device_registry": DeviceRegistry(self._get_db_session()),
                "data_access_layer": DataAccessLayer(
                    config_loader=self.config_loader
                )
            }

        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            raise

    def _initialize_configuration(self) -> None:
        """Load and validate configuration."""
        try:
            self.global_config = self.config_loader.get_global_config()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def _initialize_database(self) -> None:
        """Initialize database connection and schema."""
        db_url = "sqlite:///tasks.db"

        try:
            # Check if database exists and is healthy
            if check_database_health(db_url):
                logger.info("Database connection healthy")
            else:
                logger.warning("Database health check failed, initializing...")
                init_database(db_url)

            # Create engine and session factory
            self.db_engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
            )
            self.db_session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.db_engine
            )

            logger.info(f"Database initialized: {db_url}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _validate_system(self) -> None:
        """Validate system configuration and dependencies."""
        errors = []

        # Validate global config
        try:
            self.config_loader.validate_config()
        except Exception as e:
            errors.append(f"Configuration validation failed: {str(e)}")

        # Check database connectivity
        if not check_database_health(str(self.db_engine.url)):
            errors.append("Database connection failed")

        if errors:
            error_msg = "\n".join(errors)
            logger.error(f"System validation failed:\n{error_msg}")
            raise RuntimeError(error_msg)

    def _get_db_session(self):
        """Get a new database session."""
        return self.db_session_factory()

    def create_device_configs(self) -> None:
        """Create default configuration files for all device types."""
        from docs.devices import get_device_specs

        try:
            devices = get_device_specs()
            config_dir = Path("/etc/dashcam-processor/devices")

            if not config_dir.exists():
                config_dir.mkdir(parents=True, exist_ok=True)

            for device_id, device_info in devices.items():
                # Create minimal default config
                device_config = {
                    "hostname": device_id,
                    "task_types": device_info.get("task_types", []),
                    "capabilities": device_info.get("capabilities", {}),
                    "processing": {}
                }

                config_file = config_dir / f"{device_id}.json"
                if not config_file.exists():
                    import json
                    with open(config_file, 'w') as f:
                        json.dump(device_config, f, indent=2)
                    logger.info(f"Created default config for {device_id}")

        except Exception as e:
            logger.error(f"Failed to create device configs: {e}")
            raise

def initialize_system() -> Dict[str, Any]:
    """Convenience function to initialize the system.

    Returns:
        Dictionary containing initialized services
    """
    initializer = SystemInitializer()
    return initializer.initialize()

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) > 1 and sys.argv[1] == "create-configs":
        initializer = SystemInitializer()
        initializer.create_device_configs()
        print("Device configurations created successfully")
    else:
        try:
            services = initialize_system()
            print("System initialized successfully")
            print(f"Configuration loaded: {len(services['global_config'])} sections")
        except Exception as e:
            print(f"Initialization failed: {e}")
            sys.exit(1)