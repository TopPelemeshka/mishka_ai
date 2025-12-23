import pytest
import json
from unittest.mock import MagicMock
from src.core.memory.short_term import ShortTermMemory

@pytest.mark.asyncio
async def test_add_message(memory_redis_mock):
    """Проверка добавления сообщения в Redis."""
    memory = ShortTermMemory(memory_redis_mock)
    user_id = 999
    
    await memory.add_message(user_id, "user", "Привет")
    
    assert memory_redis_mock.lpush.called
    assert memory_redis_mock.ltrim.called
    assert memory_redis_mock.expire.called

@pytest.mark.asyncio
async def test_get_history(memory_redis_mock):
    """Проверка получения истории."""
    memory = ShortTermMemory(memory_redis_mock)
    user_id = 999
    
    # Mock return
    msg1 = json.dumps({"role": "user", "content": "Hi"}) 
    
    # Ensure it returns list
    memory_redis_mock.lrange.return_value = [msg1]
    
    history = await memory.get_last_messages(user_id)
    
    assert len(history) == 1
    assert history[0]["content"] == "Hi"
