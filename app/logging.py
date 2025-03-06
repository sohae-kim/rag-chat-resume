import logging
import os
from datetime import datetime

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag_chat")

# Create a file handler if needed
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(logs_dir, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(logs_dir, "security.log"))
file_handler.setLevel(logging.WARNING)

# Set the format for logs
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def log_security_event(ip: str, event_type: str, details: str):
    """Log security-related events."""
    logger.warning(f"SECURITY EVENT - {event_type} - IP: {ip} - {details}")

def log_rate_limit(ip: str, reason: str):
    """Log rate limiting events."""
    logger.info(f"RATE LIMIT - IP: {ip} - {reason}")

def log_api_usage(ip: str, query: str, tokens_used: int):
    """Log API usage for auditing."""
    logger.info(f"API USAGE - IP: {ip} - Tokens: {tokens_used} - Query: {query[:30]}...") 