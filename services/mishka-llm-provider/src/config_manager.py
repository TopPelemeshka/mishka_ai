
import asyncio
import os
import aio_pika
import httpx
import json
from loguru import logger

class ConfigManager:
    def __init__(self):
        self._configs = {}
        self.service_name = "mishka-llm-provider"
        # Defaults
        self._configs["default_model"] = "gemini-2.0-flash"
        self._configs["request_timeout"] = "120.0"

    async def initialize(self):
        """Fetch initial configs and start listening."""
        await self._fetch_initial_configs()
        asyncio.create_task(self._listen_updates())

    def get(self, key: str, default=None):
        return self._configs.get(key, default)

    async def _fetch_initial_configs(self):
        admin_url = "http://mishka-admin-backend:8080"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{admin_url}/internal/configs/{self.service_name}", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("configs", []):
                        self._configs[item["key"]] = item["value"]
                    logger.info(f"Loaded dynamic configs: {self._configs}")
                else:
                    logger.warning(f"Failed to fetch configs: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Config fetch error: {e}")

    async def _listen_updates(self):
        rabbitmq_url = os.getenv("RABBITMQ_URL")
        if not rabbitmq_url:
            logger.error("RABBITMQ_URL not set, cannot listen for updates")
            return

        while True:
            try:
                connection = await aio_pika.connect_robust(rabbitmq_url)
                async with connection:
                    channel = await connection.channel()
                    exchange = await channel.declare_exchange("config_events", aio_pika.ExchangeType.FANOUT)
                    queue = await channel.declare_queue(exclusive=True)
                    await queue.bind(exchange)

                    logger.info("Listening for config updates...")
                    async with queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                try:
                                    payload = json.loads(message.body.decode())
                                    if payload.get("service") == self.service_name:
                                        key = payload.get("key")
                                        value = payload.get("value")
                                        self._configs[key] = value
                                        logger.info(f"Dynamic Config Update: {key}={value}")
                                except Exception as e:
                                    logger.error(f"Error processing update: {e}")
            except Exception as e:
                logger.error(f"RabbitMQ connection lost: {e}")
                await asyncio.sleep(5)

config_manager = ConfigManager()
