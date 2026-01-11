import sys
from loguru import logger

def setup_logger():
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(sys.stderr, level="INFO")
    
    # Add file handler (truncate mode 'w' to clear on restart)
    logger.add(
        "logs/interactions.log",
        rotation="10 MB",
        level="DEBUG",
        mode="w", 
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    
    logger.info("Detailed file logging initialized.")
