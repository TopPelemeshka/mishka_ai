import json
from redis import asyncio as aioredis
from src.config import settings

class RedisManager:
    def __init__(self):
        self.redis = None

    async def connect(self):
        self.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def add_message(self, chat_id: int, role: str, content: str, timestamp: str, user_name: str = None, created_at: str = None):
        key = f"chat_history:{chat_id}"
        message_data = {
            "role": role, 
            "content": content, 
            "timestamp": timestamp,
            "user_name": user_name,
            "created_at": created_at
        }
        message = json.dumps(message_data)
        
        async with self.redis.pipeline() as pipe:
            pipe.rpush(key, message)
            
            # Dynamic Limit
            from src.config_manager import config_manager
            try:
                limit = int(config_manager.get("context_limit", 50))
            except:
                limit = 50
                
            pipe.ltrim(key, -limit, -1) 
            await pipe.execute()

    async def get_history(self, chat_id: int):
        key = f"chat_history:{chat_id}"
        messages = await self.redis.lrange(key, 0, -1)
        return [json.loads(m) for m in messages]

redis_manager = RedisManager()
