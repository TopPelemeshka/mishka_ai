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

# Security: Allowed Group ID
ALLOWED_GROUP_ID = os.getenv("ALLOWED_GROUP_ID")
if ALLOWED_GROUP_ID:
    try:
        ALLOWED_GROUP_ID = int(ALLOWED_GROUP_ID)
        logger.info(f"Bot restricted to chat_id: {ALLOWED_GROUP_ID}")
    except ValueError:
        logger.error(f"Invalid ALLOWED_GROUP_ID format: {ALLOWED_GROUP_ID}")
        ALLOWED_GROUP_ID = None
else:
    logger.warning("ALLOWED_GROUP_ID not set - bot will not respond to any messages!")


def is_chat_allowed(chat_id: int, user_id: int) -> bool:
    """
    Проверяет, разрешен ли чат для работы бота.
    """
    if not ALLOWED_GROUP_ID:
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id} (User: {user_id}) - ALLOWED_GROUP_ID not configured")
        return False
    
    if chat_id != ALLOWED_GROUP_ID:
        logger.warning(f"Unauthorized access attempt from chat_id: {chat_id} (User: {user_id})")
        return False
    
    return True


@dp.message(CommandStart())
async def command_start_handler(message: Message):
    if not is_chat_allowed(message.chat.id, message.from_user.id):
        return
    await message.answer(f"Hello, {message.from_user.full_name}! I am Mishka AI.")


@dp.message()
async def message_handler(message: Message):
    logger.info(f"Received message from {message.from_user.id}: {message.text}")

    # Security check
    if not is_chat_allowed(message.chat.id, message.from_user.id):
        return

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
