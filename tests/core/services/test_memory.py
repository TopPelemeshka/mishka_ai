import pytest
import json
from src.core.services.memory import MemoryService
from src.core.memory.models import MemoryFact, FactCategory

@pytest.mark.asyncio
async def test_extract_facts_success(mock_ai_client, mocker):
    """
    Тест успешного извлечения фактов.
    """
    # Подготовка данных
    user_text = "Меня зовут Миша, я люблю пиццу с ананасами."
    user_id = 123
    
    # Формируем ожидаемый JSON ответ от LLM
    expected_facts = [
        {
            "text": "Зовут Миша",
            "category": "bio",
            "importance": 10
        },
        {
            "text": "Любит пиццу с ананасами",
            "category": "preferences",
            "importance": 8
        }
    ]
    mock_ai_client.generate_response.return_value = json.dumps(expected_facts)
    
    # Патчим ai_client внутри модуля memory
    mocker.patch("src.core.services.memory.ai_client", mock_ai_client)
    
    # Создаем сервис (он stateless, можно использовать глобальный или создать новый)
    service = MemoryService()
    
    # Вызов метода
    facts = await service.extract_facts(user_text, user_id)
    
    # Проверки
    assert len(facts) == 2
    assert isinstance(facts[0], MemoryFact)
    assert facts[0].text == "Зовут Миша"
    assert facts[0].category == FactCategory.BIO
    assert facts[0].user_id == user_id
    
    assert facts[1].text == "Любит пиццу с ананасами"
    assert facts[1].category == FactCategory.PREFERENCES

@pytest.mark.asyncio
async def test_extract_facts_empty(mock_ai_client, mocker):
    """
    Тест поведения при пустом ответе или ошибке парсинга.
    """
    user_text = "Привет"
    user_id = 123
    
    # LLM вернул мусор или пустоту
    mock_ai_client.generate_response.return_value = "Не нашел фактов"
    
    mocker.patch("src.core.services.memory.ai_client", mock_ai_client)
    
    service = MemoryService()
    facts = await service.extract_facts(user_text, user_id)
    
    assert facts == []
