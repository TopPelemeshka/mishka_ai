import uuid
from typing import Any, Dict, List

from sqlalchemy import String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin


class MemoryLog(Base, TimestampMixin):
    """Модель для хранения логов размышлений агента (Chain of Thought)."""
    
    __tablename__ = "memory_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    process_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # Список шагов: [{thought: ..., action: ..., observation: ...}, ...]
    steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, default=[], nullable=False)

    def __repr__(self) -> str:
        return f"<MemoryLog(id={self.id}, process={self.process_name})>"
