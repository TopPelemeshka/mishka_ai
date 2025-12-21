from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Модель пользователя Telegram."""
    
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    
    # Режим личности бота для этого пользователя
    personality_mode: Mapped[str] = mapped_column(String, default="default", nullable=False)
    
    # Досье пользователя (накопленные факты)
    profile_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default={}, nullable=False)
    
    # Пользовательские настройки
    settings: Mapped[Dict[str, Any]] = mapped_column(JSONB, default={}, nullable=False)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
