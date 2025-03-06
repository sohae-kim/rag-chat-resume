from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import os
import sys
import json
from pathlib import Path

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a new FastAPI app just for the API routes
app = FastAPI()

# Import necessary functions from your app
from app.utils import sanitize_input, find_relevant_content, create_prompt
from openai import OpenAI
import anthropic

# Initialize API clients
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
claude_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Define models
class QueryRequest(BaseModel):
    question: str

class ReferenceItem(BaseModel):
    title: str
    url: str

class QueryResponse(BaseModel):
    answer: str
    references: List[ReferenceItem]

@app.post("/api/chat", response_model=QueryResponse)
async def chat(request: Request, query: QueryRequest):
    # Sanitize input
    sanitized_question = sanitize_input(query.question)
    
    if not sanitized_question:
        return {
            "answer": "Your question seems to be empty. Please provide a question about Sohae's career.",
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
                "title": item["id"],
                "url": f"https://sohae-kim.github.io/#{item['id']}"
            } 
            for item in relevant_content
        ]
        
        return {
            "answer": message.content[0].text,
            "references": references
        }
    
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"} 