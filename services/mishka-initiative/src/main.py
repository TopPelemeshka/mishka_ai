import asyncio
from loguru import logger
from src.consumer import start_consumer
from src.logger_config import setup_logger
from src.config_manager import config_manager

async def init_app():
    await config_manager.initialize()
    await start_consumer()

if __name__ == "__main__":
    setup_logger()
    logger.info("Starting Mishka Initiative Service 🧠✨")
    
    try:
        # Run init in loop
        asyncio.run(init_app())
    except KeyboardInterrupt:
        logger.info("Stopping...")
