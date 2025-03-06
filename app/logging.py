import os
import json
from datetime import datetime
import logging

# Check if running in Vercel (serverless environment)
is_vercel = os.environ.get('VERCEL', '0') == '1'

if is_vercel:
    # Configure logging to use stdout in Vercel
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('rag-chat')
else:
    # For local development, use file logging
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure file handler
    file_handler = logging.FileHandler(os.path.join(logs_dir, "app.log"))
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Configure logger
    logger = logging.getLogger('rag-chat')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)

def log_security_event(ip, event_type, details):
    """Log security events"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "type": event_type,
        "details": details
    }
    logger.warning(f"SECURITY EVENT: {json.dumps(event)}")

def log_rate_limit(ip, message):
    """Log rate limiting events"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "message": message
    }
    logger.info(f"RATE LIMIT: {json.dumps(event)}")

def log_api_usage(ip, query, tokens):
    """Log API usage"""
    event = {
        "timestamp": datetime.now().isoformat(),
        "ip": ip,
        "query": query,
        "tokens": tokens
    }
    logger.info(f"API USAGE: {json.dumps(event)}") 