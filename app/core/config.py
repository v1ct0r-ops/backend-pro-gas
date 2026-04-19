from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from sqlalchemy import create_engine


class Settings(BaseSettings):
    """
    Variables de entorno cargadas desde el archivo .env.
    pydantic-settings lo lee automáticamente en desarrollo.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Base de datos
    DATABASE_URL: str

    # Aplicación
    APP_ENV: str = "development"
    APP_DEBUG: bool = False

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # CORS — string separado por comas, se parsea a lista en cors_origins_list
    CORS_ORIGINS: str = "http://localhost:5173"

    # Email (SMTP) — opcional: si no se configura, el envío se omite silenciosamente
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SUPER_ADMIN_EMAIL: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        """Convierte el string de CORS_ORIGINS en una lista."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Instancia única, se importa desde el resto de la app
settings = Settings()


engine = create_engine(settings.DATABASE_URL)