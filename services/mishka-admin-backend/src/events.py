import aio_pika
import json
import logging
from src.config import settings

logger = logging.getLogger(__name__)

class EventProducer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            self.channel = await self.connection.channel()
            
            # Declare Fanout Exchange
            self.exchange = await self.channel.declare_exchange(
                "config_events", 
                aio_pika.ExchangeType.FANOUT
            )
            logger.info("Connected to RabbitMQ for Config Events")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")

    async def publish_update(self, service: str, key: str, value: str):
        if not self.exchange:
            await self.connect()
            if not self.exchange:
                logger.error("Cannot publish: Exchange not ready")
                return

        message_body = json.dumps({
            "service": service,
            "key": key,
            "value": value
        })
        
        await self.exchange.publish(
            aio_pika.Message(body=message_body.encode()),
            routing_key="" # Fanout ignores routing key
        )
        logger.info(f"Published config update: {service}.{key}={value}")

    async def close(self):
        if self.connection:
            await self.connection.close()

producer = EventProducer()
