import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_ai_client(mocker):
    """
    Мок для AIClient.
    Подменяет реальные вызовы к API (generate_response, get_embedding).
    """
    # Патчим глобальный объект ai_client там, где он импортируется в тестируемом коде
    # Но надежнее запатчить класс или сам синглтон, если он используется через импорт инстанса.
    # В коде мы используем `from src.core.ai.client import ai_client`. 
    # Поэтому патчить надо `src.core.services.memory.ai_client` (или где он используется).
    
    mock_client = AsyncMock()
    
    # Настройка generate_response
    mock_client.generate_response.return_value = "Test response"
    
    # Настройка get_embedding
    # Возвращаем список из 768 float
    mock_client.get_embedding.return_value = [0.1] * 768
    
    return mock_client

@pytest.fixture
def mock_db_session():
    """Мок для сессии БД."""
    session = AsyncMock()
    return session

@pytest.fixture
def memory_redis_mock():
    """Мок для Redis клиента."""
    redis = AsyncMock()
    return redis
