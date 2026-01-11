from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None

class UserCreate(UserBase):
    id: int # Telegram ID

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class HistoryMessage(BaseModel):
    role: str # "user", "assistant", or "tool"
    content: str
    timestamp: Optional[str] = None
    user_name: Optional[str] = None # Display name of the sender
    created_at: Optional[str] = None # ISO format time specific for the message context

class ContextResponse(BaseModel):
    user: Optional[UserResponse] = None
    history: List[HistoryMessage] = []
