import aio_pika
import json
from loguru import logger
from src.config import settings

async def send_to_brain(payload: dict):
    """Sends the validated task to the Brain service."""
    try:
        connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            
            # Ensure queue exists
            await channel.declare_queue(settings.QUEUE_BRAIN_TASKS, durable=True)
            
            message = aio_pika.Message(
                body=json.dumps(payload).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await channel.default_exchange.publish(
                message,
                routing_key=settings.QUEUE_BRAIN_TASKS
            )
            logger.info(f"Task sent to Brain: {payload.get('chat_id')}")
            
    except Exception as e:
        logger.error(f"Failed to publish to brain_tasks: {e}")
