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
    TELEGRAM_BOT_TOKEN: str # Using same env name as Gateway for consistency
    DEV_MODE: bool = False # Bypass signature check for local testing
    
    # Access Control
    SUPERADMIN_ID: int = 0
    VIEWER_IDS: str = "" # e.g. "111222,333444"

    @property
    def viewer_ids_list(self) -> List[int]:
        if not self.VIEWER_IDS: return []
        try:
            return [int(x.strip()) for x in self.VIEWER_IDS.split(",") if x.strip()]
        except ValueError:
            return []

    @property
    def viewer_ids_list(self) -> List[int]:
        if not self.VIEWER_IDS: return []
        return [int(x.strip()) for x in self.VIEWER_IDS.split(",") if x.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore" 

settings = Settings()
