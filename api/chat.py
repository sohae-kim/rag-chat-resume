import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the app
from app.main import app

# Create handler for AWS Lambda / Vercel
from mangum import Mangum
handler = Mangum(app)

# This is important - Vercel needs this specific export
def lambda_handler(event, context):
    return handler(event, context) 