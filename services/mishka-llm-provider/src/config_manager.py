
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
        
        for attempt in range(5):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{admin_url}/internal/configs/{self.service_name}", timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Handling different return format here (wrapper "configs" vs direct dict)
                        # Previous implementation: data.get("configs", []) which implies list of k/v
                        # But wait, other services assume dict?
                        # Let's check main.py of admin backend:
                        # return {c.key: c.value for c in configs} -> It returns a DICT.
                        
                        # Wait, LLM Provider code was:
                        # data = resp.json()
                        # for item in data.get("configs", []): ...
                        
                        # So LLM Provider EXPECTS a different format than what backend sends?
                        # Backend sends: {"key": "value"}
                        # LLM Provider expects: {"configs": [{"key": "k", "value": "v"}]} ?
                        
                        # Let's check Admin Backend logic again.
                        # @app.get("/internal/configs/{service_name}") -> return {c.key: c.value for c in configs}
                        # So it returns {"request_timeout": "120.0"} etc.
                        
                        # So LLM Provider code was WRONG or OLD.
                        # Since it updates self._configs, let's fix it to match backend.
                        
                        # Oh wait, verify_configs.py logic?
                        # No, let's just use .update(resp.json()) like others if format is dict.
                        
                        self._configs.update(data)
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
