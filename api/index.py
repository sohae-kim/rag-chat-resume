from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import os
import sys
import json
import shutil
from pathlib import Path
import tempfile

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a new FastAPI app just for the API routes
app = FastAPI()

# Import necessary functions from your app
from app.utils import sanitize_input, find_relevant_content, create_prompt, load_embeddings, cosine_similarity
from openai import OpenAI
import anthropic

# Initialize API clients
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
claude_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Create a writable temp directory for the embeddings
TEMP_DIR = tempfile.gettempdir()
TEMP_EMBEDDINGS_PATH = os.path.join(TEMP_DIR, "embeddings.json")

# Try to copy the embeddings file to the temp directory on startup
try:
    # Check various possible locations
    possible_paths = [
        "/var/task/data/embeddings.json",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "embeddings.json"),
        os.path.join(os.getcwd(), "data", "embeddings.json")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found embeddings at {path}, copying to {TEMP_EMBEDDINGS_PATH}")
            shutil.copy(path, TEMP_EMBEDDINGS_PATH)
            break
    else:
        print("Warning: Could not find embeddings file to copy")
except Exception as e:
    print(f"Error copying embeddings file: {str(e)}")

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

@app.get("/api/debug")
async def debug():
    """Debug endpoint to check file paths and environment"""
    import os
    import sys
    import tempfile
    
    # Check various paths
    cwd = os.getcwd()
    temp_dir = tempfile.gettempdir()
    
    # Check for data directory
    data_dir = os.path.join(cwd, "data")
    data_exists = os.path.exists(data_dir)
    
    # Check for embeddings file in various locations
    embeddings_paths = [
        os.path.join(temp_dir, "embeddings.json"),
        os.path.join(cwd, "data", "embeddings.json"),
        "/var/task/data/embeddings.json"
    ]
    
    embeddings_status = {}
    for path in embeddings_paths:
        embeddings_status[path] = {
            "exists": os.path.exists(path),
            "size": os.path.getsize(path) if os.path.exists(path) else 0
        }
    
    # List files in key directories
    files_in_cwd = os.listdir(cwd) if os.path.exists(cwd) else []
    files_in_data = os.listdir(data_dir) if data_exists else []
    files_in_temp = os.listdir(temp_dir) if os.path.exists(temp_dir) else []
    
    return {
        "cwd": cwd,
        "temp_dir": temp_dir,
        "data_dir_exists": data_exists,
        "embeddings_status": embeddings_status,
        "files_in_cwd": files_in_cwd,
        "files_in_data": files_in_data,
        "files_in_temp": files_in_temp,
        "python_path": sys.path,
        "env_vars": {k: "***" if "key" in k.lower() else v for k, v in os.environ.items()}
    }

@app.get("/api/embeddings-check")
async def embeddings_check():
    """Check the quality of embeddings and similarity calculations"""
    try:
        # Load embeddings
        embeddings = load_embeddings()
        
        # Basic stats
        embedding_count = len(embeddings)
        embedding_dimensions = len(embeddings[0]["embedding"]) if embedding_count > 0 else 0
        
        # Check for zero embeddings
        zero_embeddings = []
        for item in embeddings:
            embedding = item["embedding"]
            if all(v == 0 for v in embedding) or sum(abs(v) for v in embedding) < 0.001:
                zero_embeddings.append(item["id"])
        
        # Test similarity between a few items
        similarity_tests = []
        if embedding_count >= 2:
            for i in range(min(3, embedding_count)):
                for j in range(i+1, min(4, embedding_count)):
                    item1 = embeddings[i]
                    item2 = embeddings[j]
                    sim = cosine_similarity(item1["embedding"], item2["embedding"])
                    similarity_tests.append({
                        "item1": item1["id"],
                        "item2": item2["id"],
                        "similarity": sim
                    })
        
        # Test query
        test_query = "Tell me about Sohae's experience at Samsung"
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Generate embedding for test query
        embedding_response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=test_query
        )
        query_embedding = embedding_response.data[0].embedding
        
        # Find most similar content
        relevant = find_relevant_content(query_embedding, top_k=3)
        
        return {
            "embedding_count": embedding_count,
            "embedding_dimensions": embedding_dimensions,
            "zero_embeddings": zero_embeddings,
            "similarity_tests": similarity_tests,
            "test_query": test_query,
            "relevant_content": [{"id": item["id"], "similarity": item["similarity"]} for item in relevant]
        }
    except Exception as e:
        return {"error": str(e)} 