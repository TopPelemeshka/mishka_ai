import os
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from src.rmq import rmq

logger = logging.getLogger(__name__)

# Initialize Bot and Dispatcher
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN is not set!")
    
bot = Bot(token=TOKEN) if TOKEN else None
dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    await message.answer(f"Hello, {message.from_user.full_name}! I am Mishka AI.")

@dp.message()
async def message_handler(message: Message):
    logger.info(f"Received message from {message.from_user.id}: {message.text}")

    if not message.text:
        return

    # Create event for Mishka Brain
    event = {
        "user_id": message.from_user.id,
        "chat_id": message.chat.id,
        "username": message.from_user.username,
        "text": message.text,
        "date": message.date.isoformat(),
        "type": "text_message"
    }
    
    # Publish to RabbitMQ
    try:
        logger.info(f"Sending to RabbitMQ: {event}")
        await rmq.publish("chat_events", event)
    except Exception as e:
        logger.error(f"Failed to publish message: {e}")
        await message.answer("Error processing message.")


async def send_message_to_user(data: dict):
    """
    Callback for processing messages from bot_outbox queue.
    """
    logger.info(f"Received response from Brain: {data}")
    chat_id = data.get("chat_id")
    text = data.get("text")
    
    if chat_id and text:
        try:
            if bot:
                await bot.send_message(chat_id=chat_id, text=text)
                logger.info(f"Sent message to {chat_id}: {text}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
