from pydantic import BaseModel
from typing import Optional, List
import datetime
from uuid import UUID

class PersonalityBase(BaseModel):
    name: str
    base_prompt: str

class PersonalityCreate(PersonalityBase):
    pass

class PersonalityResponse(PersonalityBase):
    id: UUID
    is_active: bool
    
    class Config:
        from_attributes = True

class EvolutionLogResponse(BaseModel):
    id: UUID
    traits: Optional[str]
    reason: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class CurrentPromptResponse(BaseModel):
    text: str
    traits: Optional[str]

class EvolveRequest(BaseModel):
    reason: str = "Manual Evolution Trigger"

class RollbackRequest(BaseModel):
    target_log_id: UUID
