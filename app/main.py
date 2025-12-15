"""Main Application Factory - Creates and configures the FastAPI application."""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from config.loader import ConfigurationLoader
from db.init_db import init_database, check_database_health
from api.routes import tasks, webui

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan management for FastAPI application.

    Handles startup and shutdown events including:
    - Database initialization
    - Configuration loading
    - Service registration

    Args:
        app: FastAPI application instance

    Yields:
        None (execution continues)
    """
    logger.info("Starting application lifespan")

    # Initialize configuration
    try:
        config_loader = ConfigurationLoader()
        global_config = config_loader.get_global_config()

        app.state.config_loader = config_loader
        app.state.global_config = global_config

        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Initialize database
    try:
        db_url = "sqlite:///tasks.db"
        if not check_database_health(db_url):
            logger.warning("Database health check failed, attempting initialization")
            init_database(db_url)
        else:
            logger.info("Database connection healthy")

        app.state.db_url = db_url
        logger.info(f"Using database: {db_url}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Register routes
    try:
        app.include_router(tasks.router)
        app.include_router(webui.router)
        logger.info("API routes registered successfully")
    except Exception as e:
        logger.error(f"Failed to register routes: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down application")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Dashcam Processor API",
        description="REST API for dashcam video processing pipeline",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )

    return app

# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )