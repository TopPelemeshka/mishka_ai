from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# Создание асинхронного движка
engine = create_async_engine(
    settings.database_url,
    echo=False, # Set to True for SQL logging
    pool_pre_ping=True,
)

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии базы данных.
    Используется в FastAPI handlers и TaskIQ.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
