import asyncio
import aio_pika
import json
import httpx
import os
from loguru import logger
from src.config import settings

class ConfigManager:
    def __init__(self):
        self._configs = {}
        self.service_name = "mishka-memory"
        # Defaults
        self._configs["context_limit"] = 50

    async def initialize(self):
        # 1. Load from Admin Backend
        try:
            # We assume accessible as mishka-admin-backend:8080 or 8081 depending on internal port
            # Docker internal is 8080
            admin_url = "http://mishka-admin-backend:8080/internal/configs/" + self.service_name
            async with httpx.AsyncClient() as client:
                resp = await client.get(admin_url, timeout=5.0)
                if resp.status_code == 200:
                    remote = resp.json()
                    self._configs.update(remote)
                    logger.info(f"Loaded dynamic configs: {self._configs}")
                else:
                    logger.warning(f"Failed to fetch configs: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Config fetch error: {e}")

        # 2. Start Listener Task
        asyncio.create_task(self._listen_updates())

    async def _listen_updates(self):
        try:
            # Construct URL or use settings if available
            # redis_manager uses settings.REDIS_URL, so src.config exists
            # We need RabbitMQ URL. It might not be in settings?
            # Let's check src/config.py of mishka-memory.
            # Assuming standard env RABBITMQ_URL.
            # If not in settings, use os.getenv
            rmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")

            connection = await aio_pika.connect_robust(rmq_url)
            channel = await connection.channel()
            exchange = await channel.declare_exchange("config_events", aio_pika.ExchangeType.FANOUT)
            
            queue = await channel.declare_queue(exclusive=True)
            await queue.bind(exchange)
            
            logger.info("Listening for config updates...")
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        try:
                            data = json.loads(message.body.decode())
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

config_manager = ConfigManager()
