import logging
import sys
from app.config import settings

def setup_logging():
    """
    Configure standard Python logging to output to stdout.
    """
    logger = logging.getLogger("feedbackpulse")
    logger.setLevel(logging.INFO)
    
    # Check if handler already exists to avoid duplicates
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        # Include timestamp, level, and message.
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Also configure uvicorn logging to use our format if needed, 
    # but uvicorn handles its own. We mainly care about app logs.
    return logger

logger = setup_logging()
