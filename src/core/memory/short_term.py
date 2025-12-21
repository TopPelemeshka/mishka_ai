import json
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.bot.loader import redis_conn


class ShortTermMemory:
    """Краткосрочная память пользователя на базе Redis List."""

    def __init__(self, ttl: int = 86400): # 24 часа TTL
        self.redis = redis_conn
        self.ttl = ttl

    def _get_key(self, user_id: int) -> str:
        return f"chat:{user_id}"

    async def add_message(self, user_id: int, role: str, content: str):
        """
        Сохраняет сообщение в историю.
        role: 'user' или 'ai'
        """
        key = self._get_key(user_id)
        message_data = json.dumps({"role": role, "content": content})
        
        # Добавляем в начало списка (слева)
        await self.redis.lpush(key, message_data)
        
        # Обрезаем до последних 50 сообщений, чтобы не раздувать
        await self.redis.ltrim(key, 0, 49)
        
        # Обновляем TTL
        await self.redis.expire(key, self.ttl)

    async def get_last_messages(self, user_id: int, limit: int = 20) -> List[dict]:
        """Возвращает сырые сообщения (dict) в хронологическом порядке."""
        key = self._get_key(user_id)
        # Получаем с конца (старые) или начала? LPUSH кладет в начало 0.
        # Значит 0 - самое новое.
        # lrange(0, limit-1) вернет от нового к старому.
        # Нам нужно для истории от старого к новому.
        raw_messages = await self.redis.lrange(key, 0, limit - 1)
        
        messages = []
        for raw in raw_messages:
            messages.append(json.loads(raw))
            
        # Разворачиваем, чтобы было [старое, ..., новое]
        return messages[::-1]

    async def get_langchain_history(self, user_id: int, limit: int = 20) -> List[BaseMessage]:
        """Возвращает историю в формате LangChain."""
        raw_history = await self.get_last_messages(user_id, limit)
        history: List[BaseMessage] = []
        
        for msg in raw_history:
            if msg["role"] == "user":
                history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                history.append(AIMessage(content=msg["content"]))
                
        return history

# Глобальный экземпляр
short_term_memory = ShortTermMemory()
