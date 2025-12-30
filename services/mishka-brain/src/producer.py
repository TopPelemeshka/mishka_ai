import os
import json
import aio_pika
from loguru import logger

class RabbitMQProducer:
    def __init__(self):
        self.user = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
        self.password = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        self.host = os.getenv("RABBITMQ_HOST", "rabbitmq")
        self.port = int(os.getenv("RABBITMQ_PORT", 5672))
        
        self.connection = None
        self.channel = None

    async def connect(self):
        url = f"amqp://{self.user}:{self.password}@{self.host}:{self.port}/"
        try:
            self.connection = await aio_pika.connect_robust(url)
            self.channel = await self.connection.channel()
            # Declare queue to ensure it exists
            await self.channel.declare_queue("bot_outbox", durable=True)
            logger.info("Connected to RabbitMQ Producer")
        except Exception as e:
            logger.error(f"Producer connection failed: {e}")
            raise

    async def send_response(self, chat_id: int, text: str):
        if not self.channel:
             raise RuntimeError("Producer not connected")
             
        message = {
            "chat_id": chat_id,
            "text": text
        }
        
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key="bot_outbox"
        )
        logger.info(f"Sent response to bot_outbox for chat {chat_id}")

    async def close(self):
        if self.connection:
            await self.connection.close()

producer = RabbitMQProducer()
