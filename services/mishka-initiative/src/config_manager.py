import asyncio
import aio_pika
import json
import httpx
from loguru import logger
from src.config import settings

class ConfigManager:
    def __init__(self):
        self._configs = {}
        self.service_name = "mishka-initiative"
        # Defaults
        self._configs["threshold"] = settings.INITIATIVE_THRESHOLD
        self._configs["aliases"] = "мишка,миш,bear,потапыч" # Default csv string

    async def initialize(self):
        # 1. Load from Admin Backend
        # 1. Load from Admin Backend (with retries)
        admin_url = "http://mishka-admin-backend:8080/internal/configs/" + self.service_name
        
        for attempt in range(5):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(admin_url, timeout=5.0)
                    if resp.status_code == 200:
                        remote = resp.json()
                        self._configs.update(remote)
                        logger.info(f"Loaded dynamic configs: {self._configs}")
                        break
                    else:
                        logger.warning(f"Failed to fetch configs (Attempt {attempt+1}/5): {resp.status_code}")
            except Exception as e:
                logger.warning(f"Config fetch error (Attempt {attempt+1}/5): {e}")

            # Wait before retry
            wait_time = 2 * (2 ** attempt)
            if attempt < 4:
                logger.info(f"Retrying config fetch in {wait_time}s...")
                await asyncio.sleep(wait_time)

        # 2. Start Listener Task
        asyncio.create_task(self._listen_updates())

    async def _listen_updates(self):
        try:
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            channel = await connection.channel()
            exchange = await channel.declare_exchange("config_events", aio_pika.ExchangeType.FANOUT)
            
            # Exclusive queue for this instance
            queue = await channel.declare_queue(exclusive=True)
            await queue.bind(exchange)
            
            logger.info("Listening for config updates...")
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            data = json.loads(message.body.decode())
                            # Check if targeted for us OR global (if we support global keys)
                            # For now, data has "service" field.
                            if data.get("service") == self.service_name:
                                key = data["key"]
                                value = data["value"]
                                self._configs[key] = value
                                logger.info(f"Dynamic Config Update: {key}={value}")
                        except Exception as e:
                            logger.error(f"Config update error: {e}")
        except Exception as e:
             logger.error(f"Config listener failed: {e}")

    def get(self, key: str, default=None):
        return self._configs.get(key, default)

    def get_list(self, key: str, default=None) -> list:
        val = self.get(key, default)
        if isinstance(val, str):
            return [x.strip() for x in val.split(",") if x.strip()]
        return val if isinstance(val, list) else []

config_manager = ConfigManager()
