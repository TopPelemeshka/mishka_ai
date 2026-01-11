import sys
from loguru import logger

def setup_logger():
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(sys.stderr, level="INFO")
    
    # Add file handler to shared log file
    logger.add(
        "logs/interactions.log",
        rotation="10 MB",
        level="INFO", # Initiative logs contain INFO mostly
        mode="a", # Append mode (Brain uses 'w'? Let's check)
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    )
    
    logger.info("Initiative logging initialized.")
