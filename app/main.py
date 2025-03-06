from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from openai import OpenAI
import anthropic
import os
from dotenv import load_dotenv
import time
from typing import List, Dict, Any
from datetime import datetime, timedelta
from mangum import Mangum

from app.utils import sanitize_input, find_relevant_content, create_prompt, load_embeddings, detect_prompt_injection, check_content_safety
from app.logging import log_security_event, log_rate_limit, log_api_usage

# Load environment variables
load_dotenv()

# Initialize API clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
claude_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Create FastAPI app
app = FastAPI()

# Add trusted host middleware to prevent host header attacks
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "your-domain.com"]
)

# Add request size limiting middleware
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10000:  # 10KB limit
        return JSONResponse(
            status_code=413,
            content={"detail": "Request too large"}
        )
    return await call_next(request)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define API routes first (before mounting static files)
class QueryRequest(BaseModel):
    question: str

class ReferenceItem(BaseModel):
    title: str
    url: str

class QueryResponse(BaseModel):
    answer: str
    references: List[ReferenceItem]

# More robust rate limiting using a dictionary with IP tracking
class RateLimiter:
    def __init__(self):
        self.ip_data = {}
        self.short_limit = 5  # 5 requests per minute
        self.daily_limit = 20  # 20 requests per day
        self.cleanup_interval = 3600  # Clean old records every hour
        self.last_cleanup = datetime.now()
    
    def cleanup(self):
        """Remove old records to prevent memory leak"""
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            cutoff = now - timedelta(days=1)
            for ip in list(self.ip_data.keys()):
                if self.ip_data[ip]["first_request"] < cutoff:
                    del self.ip_data[ip]
            self.last_cleanup = now
    
    def check(self, ip: str) -> tuple[bool, str]:
        """Check if the request is allowed for this IP address"""
        now = datetime.now()
        self.cleanup()
        
        # Initialize data for new IP
        if ip not in self.ip_data:
            self.ip_data[ip] = {
                "requests": [],
                "first_request": now
            }
        
        # Clean up requests older than 1 minute
        minute_ago = now - timedelta(minutes=1)
        self.ip_data[ip]["requests"] = [
            req for req in self.ip_data[ip]["requests"] 
            if req > minute_ago
        ]
        
        # Count requests in the last day (including the current batch)
        daily_count = len(self.ip_data[ip]["requests"])
        
        # Check short-term limit (per minute)
        if len(self.ip_data[ip]["requests"]) >= self.short_limit:
            wait_seconds = 60 - (now - min(self.ip_data[ip]["requests"])).seconds
            return False, f"Rate limit exceeded. Try again in {wait_seconds} seconds."
        
        # Check daily limit
        if daily_count >= self.daily_limit:
            next_reset = self.ip_data[ip]["first_request"] + timedelta(days=1)
            hours_until_reset = max(1, (next_reset - now).seconds // 3600)
            return False, f"Daily limit reached. Try again in {hours_until_reset} hours."
        
        # Allow request and record it
        self.ip_data[ip]["requests"].append(now)
        return True, ""

# Initialize the rate limiter
rate_limiter = RateLimiter()

@app.post("/api/chat", response_model=QueryResponse)
async def chat(request: Request, query: QueryRequest):
    # Get client IP
    client_ip = request.client.host
    
    # Rate limiting
    allowed, message = rate_limiter.check(client_ip)
    if not allowed:
        log_rate_limit(client_ip, message)
        raise HTTPException(status_code=429, detail=message)
    
    # Sanitize input
    original_question = query.question
    sanitized_question = sanitize_input(original_question)
    
    if not sanitized_question:
        return {
            "answer": "Your question seems to be empty. Please provide a question about Sohae's career.",
            "references": []
        }
    
    # Security checks
    if detect_prompt_injection(sanitized_question):
        log_security_event(client_ip, "PROMPT_INJECTION", original_question)
        return {
            "answer": "I'm sorry, but I can only answer questions about Sohae's career and experience. Could you please ask a question related to her professional background?",
            "references": []
        }
    
    if not check_content_safety(sanitized_question):
        log_security_event(client_ip, "UNSAFE_CONTENT", original_question)
        return {
            "answer": "I'm sorry, but I can't process this request. Please ask a question related to Sohae's professional background.",
            "references": []
        }
    
    try:
        # Generate embedding for the question using OpenAI
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=sanitized_question
        )
        question_embedding = embedding_response.data[0].embedding
        
        # Find relevant content
        relevant_content = find_relevant_content(question_embedding)
        
        # Create context from relevant content
        context = "\n\n".join([item["content"] for item in relevant_content])
        
        # Create prompt
        prompt = create_prompt(sanitized_question, context)
        
        # Generate response using Anthropic Claude
        message = claude_client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=300,
            temperature=0,
            system=prompt,
            messages=[
                {"role": "user", "content": sanitized_question}
            ]
        )
        
        # Prepare references
        references = [
            {
                "title": item["id"],  # This is currently "about", "project1", etc.
                "url": f"https://sohae-kim.github.io/#{item['id']}"  # Link to specific sections
            } 
            for item in relevant_content
        ]
        
        # Log API usage after successful response
        tokens_estimate = len(message.content[0].text.split()) 
        log_api_usage(client_ip, sanitized_question, tokens_estimate)
        
        return {
            "answer": message.content[0].text,
            "references": references
        }
    
    except Exception as e:
        log_security_event(client_ip, "API_ERROR", str(e))
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Mount static files AFTER defining API routes
app.mount("/static", StaticFiles(directory="public/static"), name="static")

# Serve index.html as the root route
@app.get("/")
async def read_root():
    return FileResponse("public/index.html")

@app.get("/api/diagnostic")
async def diagnostic():
    """Diagnostic endpoint to check system status"""
    try:
        # Check if we can load embeddings
        try:
            embeddings = load_embeddings()
            embedding_count = len(embeddings)
        except Exception as e:
            return {"status": "error", "embeddings": str(e)}
        
        # Check API keys
        openai_api_key_set = bool(os.getenv("OPENAI_API_KEY"))
        anthropic_api_key_set = bool(os.getenv("ANTHROPIC_API_KEY"))
        
        # Check file paths
        current_dir = os.path.abspath(os.getcwd())
        data_dir = os.path.join(current_dir, "data")
        data_dir_exists = os.path.exists(data_dir)
        
        embeddings_file = os.path.join(data_dir, "embeddings.json")
        embeddings_file_exists = os.path.exists(embeddings_file)
        
        return {
            "status": "ok",
            "environment": {
                "current_directory": current_dir,
                "data_directory_exists": data_dir_exists,
                "embeddings_file_exists": embeddings_file_exists,
                "openai_api_key_set": openai_api_key_set,
                "anthropic_api_key_set": anthropic_api_key_set
            },
            "embeddings": {
                "count": embedding_count,
                "sample_ids": [item["id"] for item in embeddings[:3]] if embedding_count > 0 else []
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# Create a handler for AWS Lambda / Vercel
handler = Mangum(app)