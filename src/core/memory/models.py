from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FactCategory(str, Enum):
    BIO = "bio"
    PREFERENCES = "preferences"
    EVENTS = "events"
    OPINIONS = "opinions"
    RELATIONSHIPS = "relationships"


class MemoryFact(BaseModel):
    """Модель факта, извлеченного из диалога."""
    text: str
    category: FactCategory
    importance: int = Field(..., ge=1, le=10)
    user_id: int
    created_at: datetime = Field(default_factory=datetime.now)
    original_message_id: Optional[int] = None

    class Config:
        use_enum_values = True
