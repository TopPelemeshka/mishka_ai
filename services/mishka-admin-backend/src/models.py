from sqlalchemy import Column, Integer, String, Boolean, Text
from src.database import Base

class DynamicConfig(Base):
    __tablename__ = "dynamic_configs"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True) # e.g. "mishka-initiative"
    key = Column(String, index=True)     # e.g. "threshold"
    value = Column(String)               # Values are strings, parsed by service
    description = Column(String, nullable=True)
    type = Column(String, default="string") # string, int, float, bool, json
    
    # Composite unique constraint could be useful, but for MVP simple index is enough with logic checks.
