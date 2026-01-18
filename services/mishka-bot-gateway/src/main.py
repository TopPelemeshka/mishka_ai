import asyncio
import sys
from loguru import logger
from src.bot import dp, bot, send_message_to_user
from src.rmq import rmq
from src.log_handler import setup_logger, start_log_handler, stop_log_handler

# Configure logging
setup_logger()

async def main():
    if not bot:
        logger.error("Bot token not configured. Exiting.")
        return

    # Start Logging
    await start_log_handler()

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
        await stop_log_handler()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
