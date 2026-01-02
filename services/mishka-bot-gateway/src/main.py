import asyncio
import logging
import sys
from src.bot import dp, bot, send_message_to_user
from src.rmq import rmq

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

async def main():
    if not bot:
        logger.error("Bot token not configured. Exiting.")
        return

    # Connect to RabbitMQ
    logger.info("Connecting to RabbitMQ...")
    await rmq.connect()
    
    # Start consuming bot_outbox
    await rmq.consume("bot_outbox", send_message_to_user)
    
    # Start polling
    bot_info = await bot.get_me()
    logger.info(f"Starting polling for bot: @{bot_info.username}")
    try:
        await dp.start_polling(bot)
    finally:
        await rmq.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
