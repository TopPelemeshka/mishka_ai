from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

import asyncio
from loguru import logger

async def init_db(retries=5, delay=2):
    from src.models import Base
    
    for i in range(retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            if i == retries - 1:
                logger.error(f"Failed to initialize database after {retries} attempts: {e}")
                raise
            logger.warning(f"Database connection failed, retrying in {delay}s... ({i+1}/{retries})")
            await asyncio.sleep(delay)
            delay *= 2 # Exponential backoff
