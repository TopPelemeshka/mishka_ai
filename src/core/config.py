from typing import Optional

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Конфигурация приложения.
    Читает переменные из .env файла или переменных окружения.
    """
    
    # Telegram Bot
    BOT_TOKEN: SecretStr

    # Google Gemini
    GOOGLE_API_KEY: SecretStr

    # Database (PostgreSQL)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Qdrant
    QDRANT_HOST: str
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: Optional[SecretStr] = None

    # Proxy
    HTTP_PROXY: Optional[str] = None
    
    # Security
    ALLOWED_CHAT_ID: int

    @property
    def database_url(self) -> str:
        """
        Сборка DSN для SQLAlchemy (AsyncPG).
        Формат: postgresql+asyncpg://user:pass@host:port/db
        """
        return str(PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        ))

    @property
    def redis_url(self) -> RedisDsn:
        """
        Сборка URL для Redis.
        Формат: redis://host:port/db
        """
        return RedisDsn.build(
            scheme="redis",
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            path=f"{self.REDIS_DB}",
        )
    
    @property
    def qdrant_url(self) -> str:
        """URL для Qdrant"""
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Игнорировать лишние переменные в .env
    )


# Глобальный экземпляр настроек
settings = Settings()
