import asyncio
import sys
from loguru import logger
from src.consumer import consumer
from src.producer import producer
from src.logger_config import setup_logger

# Configure Loguru
logger.remove()
logger.add(sys.stderr, level="INFO")

async def main():
    setup_logger()
    logger.info("Starting Mishka Brain...")
    
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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
