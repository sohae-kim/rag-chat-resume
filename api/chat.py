import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Now import the app
from app.main import app
from mangum import Mangum

# Create handler for AWS Lambda / Vercel
handler = Mangum(app) 