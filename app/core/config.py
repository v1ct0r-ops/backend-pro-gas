from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    pydantic-settings automatically reads from .env file in development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    DATABASE_URL: str

    # Application
    APP_ENV: str = "development"
    APP_DEBUG: bool = False

    # CORS - stored as a comma-separated string, parsed into a list
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parses the comma-separated CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Singleton instance used throughout the application
settings = Settings()
