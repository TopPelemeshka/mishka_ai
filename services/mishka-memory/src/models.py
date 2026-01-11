from sqlalchemy import Column, BigInteger, String, DateTime, Integer
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True) # Telegram User ID
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatSettings(Base):
    __tablename__ = "chat_settings"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, unique=True, index=True)
    language = Column(String, default="ru")
    timezone = Column(String, default="UTC")
