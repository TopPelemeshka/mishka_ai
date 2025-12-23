import pytest
import numpy as np
from unittest.mock import AsyncMock, patch

from src.core.ai.client import AIClient

@pytest.mark.asyncio
async def test_generate_response_string(mocker):
    """Тест генерации простого строкового ответа."""
    # Мокаем ChatGoogleGenerativeAI -> instance -> ainvoke
    mock_llm_instance = AsyncMock()
    mock_llm_instance.ainvoke.return_value.content = "Hello world"
    
    # Патчим класс, чтобы __init__ возвращал наш мок
    with patch("src.core.ai.client.ChatGoogleGenerativeAI", return_value=mock_llm_instance):
        client = AIClient()
        response = await client.generate_response("Hi")
        assert response == "Hello world"

@pytest.mark.asyncio
async def test_generate_response_list(mocker):
    """Тест генерации ответа, когда модель возвращает список частей."""
    mock_llm_instance = AsyncMock()
    # Имитируем content = list
    mock_llm_instance.ainvoke.return_value.content = [{"text": "Part 1"}, "Part 2"]
    
    with patch("src.core.ai.client.ChatGoogleGenerativeAI", return_value=mock_llm_instance):
        client = AIClient()
        response = await client.generate_response("Hi")
        assert response == "Part 1Part 2"

@pytest.mark.asyncio
async def test_get_embedding(mocker):
    """Тест получения эмбеддинга."""
    # Патчим глобально langchain класс, так как он импортируется локально внутри функции
    mock_embeddings_instance = AsyncMock()
    # LangChain aembed_query
    mock_embeddings_instance.aembed_query.return_value = [3.0, 4.0]
    
    with patch("langchain_google_genai.GoogleGenerativeAIEmbeddings", return_value=mock_embeddings_instance):
        client = AIClient()
        vector = await client.get_embedding("text")
        
        assert len(vector) == 2
        # Проверка нормализации [3, 4] -> length 5 -> [0.6, 0.8]
        norm = np.linalg.norm(vector)
        assert np.isclose(norm, 1.0)
        assert np.allclose(vector, [0.6, 0.8])

def build_async_mock(return_value):
    async def _mock(*args, **kwargs):
        return return_value
    return _mock
