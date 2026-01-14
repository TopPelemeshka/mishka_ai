import asyncio
import aio_pika
import json
import httpx
import os
from loguru import logger

class ConfigManager:
    def __init__(self):
        self._configs = {}
        self.service_name = "mishka-brain"
        # Defaults
        self._configs["system_prompt"] = "Ты дружелюбный бот Мишка. Отвечай кратко и с юмором."
        self._configs["temperature"] = "0.7" # stored as string or whatever DB sends

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
            
            # Wait before retry (exponential backoff: 2s, 4s, 8s...)
            wait_time = 2 * (2 ** attempt)
            if attempt < 4:
                logger.info(f"Retrying config fetch in {wait_time}s...")
                await asyncio.sleep(wait_time)

        # 2. Start Listener Task
        asyncio.create_task(self._listen_updates())

    async def _listen_updates(self):
        try:
            # Construct URL manually as in consumer.py
            user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
            password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
            host = os.getenv("RABBITMQ_HOST", "rabbitmq")
            port = int(os.getenv("RABBITMQ_PORT", 5672))
            url = f"amqp://{user}:{password}@{host}:{port}/"

            connection = await aio_pika.connect_robust(url)
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
