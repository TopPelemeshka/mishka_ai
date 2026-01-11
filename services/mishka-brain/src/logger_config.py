import sys
from loguru import logger

def setup_logger():
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.configure(
        handlers=[
            {
                "sink": "logs/interactions.log", 
                "rotation": "10 MB", 
                "compression": "zip", 
                "level": "INFO", 
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
                "mode": "a" # Append mode
            },
            # Add stdout for docker logs visibility if needed
            {"sink": sys.stderr, "level": "INFO"} 
        ]
    )
    
    logger.info("Detailed file logging initialized.")
