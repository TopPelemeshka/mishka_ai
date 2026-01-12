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
if not ALLOWED_GROUP_ID:
    logger.critical("ALLOWED_GROUP_ID is missing in environment variables! Security violation.")
    raise ValueError("ALLOWED_GROUP_ID is REQUIRED. The bot will not start without a defined allowed group.")

try:
    ALLOWED_GROUP_ID = int(ALLOWED_GROUP_ID)
    logger.info(f"Bot restricted to chat_id: {ALLOWED_GROUP_ID}")
except ValueError:
    logger.critical(f"Invalid ALLOWED_GROUP_ID format: {ALLOWED_GROUP_ID}")
    raise ValueError("ALLOWED_GROUP_ID must be an integer.")


def is_chat_allowed(chat_id: int, user_id: int) -> bool:
    """
    Проверяет, разрешен ли чат для работы бота.
    """
    return chat_id == ALLOWED_GROUP_ID


@dp.message(CommandStart())
async def command_start_handler(message: Message):
    if not is_chat_allowed(message.chat.id, message.from_user.id):
        return
    await message.answer(f"Hello, {message.from_user.full_name}! I am Mishka AI.")


@dp.message()
async def message_handler(message: Message):
    logger.info(f"Received message from {message.from_user.id}")

    # Security check
    if not is_chat_allowed(message.chat.id, message.from_user.id):
        return

    # Create base event
    event = {
        "user_id": message.from_user.id,
        "chat_id": message.chat.id,
        "username": message.from_user.username,
        "date": message.date.isoformat(),
        "type": "text_message",
        "text": message.text or message.caption or ""
    }

    # Handle Photo
    if message.photo:
        # Get the largest photo
        photo = message.photo[-1]
        file_id = photo.file_id
        file_info = await bot.get_file(file_id)
        
        # Determine path in shared volume
        file_ext = file_info.file_path.split('.')[-1]
        local_filename = f"{file_info.file_unique_id}.{file_ext}"
        local_path = f"/media/{local_filename}"
        
        # Download file
        await bot.download_file(file_info.file_path, local_path)
        logger.info(f"Downloaded photo to {local_path}")
        
        event["type"] = "image_message"
        event["file_path"] = local_path
        event["mime_type"] = "image/jpeg" # Telegram photos are usually JPEGs

    # Handle Voice
    elif message.voice:
        voice = message.voice
        file_id = voice.file_id
        file_info = await bot.get_file(file_id)
        
        file_ext = file_info.file_path.split('.')[-1]
        local_filename = f"{file_info.file_unique_id}.{file_ext}"
        local_path = f"/media/{local_filename}"
        
        await bot.download_file(file_info.file_path, local_path)
        logger.info(f"Downloaded voice to {local_path}")
        
        event["type"] = "voice_message"
        event["file_path"] = local_path
        event["mime_type"] = voice.mime_type or "audio/ogg"

    # Skip if no text and no supported media
    elif not message.text:
         return
    
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
