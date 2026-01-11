import asyncio
from loguru import logger
from src.consumer import start_consumer
from src.logger_config import setup_logger

if __name__ == "__main__":
    setup_logger()
    logger.info("Starting Mishka Initiative Service 🧠✨")
    
    try:
        asyncio.run(start_consumer())
    except KeyboardInterrupt:
        logger.info("Stopping...")
