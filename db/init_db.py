"""Database initialization script for creating tables and setting up the schema."""

import logging
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import OperationalError

from models.task import Base as TaskBase
from models.device import Base as DeviceBase

logger = logging.getLogger(__name__)

def init_database(db_url: str = "sqlite:///tasks.db") -> None:
    """Initialize the database by creating all tables.

    Args:
        db_url: Database connection URL
    """
    try:
        engine = create_engine(db_url)

        # Create all tables for both models
        TaskBase.metadata.create_all(engine)
        DeviceBase.metadata.create_all(engine)

        logger.info("Database initialization completed successfully")
        logger.info(f"Tables created: tasks, input_output, devices")

        return True
    except OperationalError as e:
        logger.error(f"Database operation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise

def check_database_health(db_url: str = "sqlite:///tasks.db") -> bool:
    """Check if the database is accessible and healthy.

    Args:
        db_url: Database connection URL

    Returns:
        True if database is healthy, False otherwise
    """
    try:
        engine = create_engine(db_url)
        with engine.connect():
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

def reset_database(db_url: str = "sqlite:///tasks.db") -> None:
    """Reset the database by dropping all tables and recreating them.

    WARNING: This will delete all data!

    Args:
        db_url: Database connection URL
    """
    try:
        engine = create_engine(db_url)
        metadata = MetaData()

        # Reflect existing tables
        metadata.reflect(bind=engine)

        # Drop all tables
        metadata.drop_all(engine)
        logger.info("All tables dropped")

        # Recreate tables
        init_database(db_url)
        logger.info("Database reset completed")
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        raise

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        print("WARNING: This will DELETE all data in the database!")
        confirm = input("Type 'YES' to confirm: ")
        if confirm == "YES":
            reset_database()
            print("Database reset complete")
        else:
            print("Reset cancelled")
    elif len(sys.argv) > 1 and sys.argv[1] == "check":
        healthy = check_database_health()
        print(f"Database health: {'OK' if healthy else 'FAILED'}")
    else:
        init_database()
        print("Database initialized successfully")