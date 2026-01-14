import datetime
import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.database import Base

class Personality(Base):
    __tablename__ = "personalities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True)
    base_prompt = Column(Text, nullable=False)
    is_active = Column(Boolean, default=False)
    
    logs = relationship("EvolutionLog", back_populates="personality")

class EvolutionLog(Base):
    __tablename__ = "evolution_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    personality_id = Column(UUID(as_uuid=True), ForeignKey("personalities.id"))
    traits = Column(Text, nullable=True) # JSON or just text list
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    personality = relationship("Personality", back_populates="logs")
