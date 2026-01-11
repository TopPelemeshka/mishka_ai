import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Security
    ADMIN_PASSWORD: str = "change_me_please" # Default for dev if missing
    JWT_SECRET: str = "unsafe_secret_for_dev"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = "missing_token"
    DEV_MODE: bool = False # Bypass signature check for local testing
    
    # Access Control
    SUPERADMIN_ID: int = 0
    VIEWER_IDS: str = "" # e.g. "111222,333444"

    # Database
    POSTGRES_USER: str = "mishka"
    POSTGRES_PASSWORD: str = "secret"
    POSTGRES_DB: str = "mishka_db"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def viewer_ids_list(self) -> List[int]:
        if not self.VIEWER_IDS: return []
        try:
            return [int(x.strip()) for x in self.VIEWER_IDS.split(",") if x.strip()]
        except ValueError:
            return []

    class Config:
        env_file = ".env"
        extra = "ignore" 

settings = Settings()
