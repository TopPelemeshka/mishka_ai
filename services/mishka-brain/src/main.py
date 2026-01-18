import asyncio
import sys
from loguru import logger
from src.consumer import consumer
from src.producer import producer
from src.log_handler import setup_logger, start_log_handler, stop_log_handler

# Configure Loguru (Run setup immediately)
setup_logger()

async def main():
    logger.info("Starting Mishka Brain...")
    await start_log_handler()
    
    from src.config_manager import config_manager
    await config_manager.initialize()

    # Connect Producer and Consumer
    await producer.connect()
    await consumer.connect()
    
    # Start Consumer
    await consumer.start()
    
    # Keep running
    try:
        # Wait forever
        await asyncio.Future()
    finally:
        logger.info("Shutting down...")
        await consumer.close()
        await producer.close()
        await stop_log_handler()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
