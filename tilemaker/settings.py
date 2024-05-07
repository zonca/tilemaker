"""
Settings for the project.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    "SQLAlchemy-appropriate database URL."

    origins: list[str] | None = None
    add_cors: bool = False
    "Settings for managng CORS middleware; useful for development."

    static_directory: str | None = None
    "Static directory to serve the SPA from. If missing, no static is used."

    class Config:
        env_prefix = "TILEMAKER_"

settings = Settings()
