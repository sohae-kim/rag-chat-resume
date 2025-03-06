from app.main import app
from mangum import Mangum

# Create handler for AWS Lambda / Vercel
handler = Mangum(app) 