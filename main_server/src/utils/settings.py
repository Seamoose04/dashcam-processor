from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dev.db"

    class Config:
        env_prefix = "MAIN_SERVER_"


settings = Settings()
