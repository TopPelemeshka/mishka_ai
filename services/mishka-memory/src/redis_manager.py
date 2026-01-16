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

    async def get_history(self, chat_id: int, limit: int = 50, hours: int = None):
        key = f"chat_history:{chat_id}"
        # Start with larger range if hours is requested
        read_limit = limit if not hours else 1000 
        
        messages = await self.redis.lrange(key, -read_limit, -1)
        parsed = [json.loads(m) for m in messages]
        
        if hours:
            import datetime
            now = datetime.datetime.utcnow()
            cutoff = now - datetime.timedelta(hours=hours)
            
            filtered = []
            for msg in parsed:
                ts_str = msg.get("created_at") or msg.get("timestamp")
                if ts_str:
                    try:
                        ts = datetime.datetime.fromisoformat(ts_str)
                        if ts > cutoff:
                            filtered.append(msg)
                    except:
                        filtered.append(msg) # Keep if no valid date
                else:
                    filtered.append(msg)
            parsed = filtered
            
        return parsed # Already limited by lrange mostly, filtered by date

    async def get_active_chats(self):
        """Returns list of chat_ids."""
        keys = await self.redis.keys("chat_history:*")
        return [int(k.split(":")[-1]) for k in keys]

redis_manager = RedisManager()
