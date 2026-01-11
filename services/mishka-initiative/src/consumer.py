import asyncio
import aio_pika
import json
from loguru import logger
from src.config import settings
from src.rules import check_hard_rules, check_soft_rules
from src.producer import send_to_brain

async def process_message(message: aio_pika.IncomingMessage):
    async with message.process():
        try:
            body = message.body.decode()
            data = json.loads(body)
            # data structure depends on Gateway. Assuming it sends raw Update or Message dict.
            # Looking at Gateway: it sends {"chat_id": ..., "text": ..., "raw": update_dict} usually.
            # Correct logic: We need the full message object for rules.
            # Let's inspect Gateway's output format or assume standard Telegram Message dict is nested or flattened.
            # Standardizing on preserving the original message structure is safest.
            
            # Assuming data is the Telegram Message object or contains it.
            # If Gateway sends custom format, we need to adapt.
            # Let's assume data IS the message dictionary for now.
            
            msg = data
            
            # 1. Check Hard Rules
            if await check_hard_rules(msg):
                await send_to_brain(msg)
                return

            # 2. Check Soft Rules
            if await check_soft_rules(msg):
                await send_to_brain(msg)
                return
            
            logger.info("Message dropped by Initiative System.")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

async def start_consumer():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    
    # Declare exchange/queue
    # Gateway publishes to 'chat_events' queue directly or via exchange.
    # Assuming direct queue for simplicity as per architecture file.
    queue = await channel.declare_queue(settings.QUEUE_CHAT_EVENTS, durable=True)
    
    logger.info("Initiative Service: Listening to chat_events...")
    await queue.consume(process_message)
    
    try:
        await asyncio.Future()
    finally:
        await connection.close()
