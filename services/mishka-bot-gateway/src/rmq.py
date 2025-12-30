import os
import json
import logging
import aio_pika
import asyncio

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self):
        self.user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        url = f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"
        try:
            self.connection = await aio_pika.connect_robust(
                url, loop=asyncio.get_running_loop()
            )
            self.channel = await self.connection.channel()
            # Declare queues
            await self.channel.declare_queue("chat_events", durable=True)
            await self.channel.declare_queue("bot_outbox", durable=True)
            
            logger.info("Connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def publish(self, queue_name: str, message: dict):
        if not self.channel:
            raise RuntimeError("RabbitMQ not connected")
        
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=queue_name
        )
        logger.debug(f"Published to {queue_name}: {message}")

    async def consume(self, queue_name: str, callback):
        if not self.channel:
            raise RuntimeError("RabbitMQ not connected")

        queue = await self.channel.declare_queue(queue_name, durable=True)

        async def _wrapper(message: aio_pika.IncomingMessage):
            async with message.process():
                data = json.loads(message.body.decode())
                await callback(data)

        await queue.consume(_wrapper)
        logger.info(f"Started consuming from {queue_name}")

    async def close(self):
        if self.connection:
            await self.connection.close()

rmq = RabbitMQClient()
