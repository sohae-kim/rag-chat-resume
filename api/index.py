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
import numpy as np

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create a new FastAPI app
app = FastAPI()

# Import necessary functions
from app.utils import sanitize_input, create_prompt
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

# Global cache for embeddings
_embeddings_cache = None

def load_embeddings():
    """Load embeddings with robust error handling"""
    global _embeddings_cache
    
    if _embeddings_cache is not None:
        return _embeddings_cache
    
    # Try to load from various locations
    possible_paths = [
        os.path.join(tempfile.gettempdir(), "embeddings.json"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "embeddings.json"),
        os.path.join(os.getcwd(), "data", "embeddings.json"),
        "/var/task/data/embeddings.json"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                print(f"Loading embeddings from: {path}")
                with open(path, "r") as f:
                    _embeddings_cache = json.load(f)
                    
                # Validate embeddings
                if _embeddings_cache and len(_embeddings_cache) > 0:
                    # Check if first item has an embedding
                    if "embedding" in _embeddings_cache[0] and len(_embeddings_cache[0]["embedding"]) > 100:
                        return _embeddings_cache
                    else:
                        print(f"Invalid embeddings in {path}")
                else:
                    print(f"Empty embeddings in {path}")
            except Exception as e:
                print(f"Error loading embeddings from {path}: {str(e)}")
    
    # If we get here, we need to load content and generate embeddings
    print("Generating embeddings from content...")
    return generate_embeddings_from_content()

def load_content():
    """Load content from content.json"""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "content.json"),
        os.path.join(os.getcwd(), "data", "content.json"),
        "/var/task/data/content.json"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Loading content from: {path}")
            with open(path, "r") as f:
                return json.load(f)
    
    # Fallback content
    print("WARNING: Using fallback content")
    return [
        {
            "id": "about",
            "content": "Sohae Kim is a Staff Engineer with experience in machine learning and data science.",
            "url": "https://sohae-kim.github.io/#about"
        },
        {
            "id": "experience",
            "content": "Sohae has experience as a Staff Engineer at Samsung Display.",
            "url": "https://sohae-kim.github.io/#experience"
        },
        {
            "id": "education",
            "content": "Sohae has a PhD from MIT in Mechanical Engineering.",
            "url": "https://sohae-kim.github.io/#education"
        }
    ]

def generate_embeddings_from_content():
    """Generate embeddings from content as a fallback"""
    global _embeddings_cache
    
    content_data = load_content()
    embeddings_data = []
    
    # Only process the first 3 items to save on API costs in emergency situations
    for item in content_data[:3]:
        print(f"Generating embedding for: {item['id']}")
        try:
            response = openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=item["content"]
            )
            embeddings_data.append({
                "id": item["id"],
                "content": item["content"],
                "url": item.get("url", f"https://sohae-kim.github.io/#{item['id']}"),
                "embedding": response.data[0].embedding
            })
        except Exception as e:
            print(f"Error generating embedding for {item['id']}: {str(e)}")
    
    # Cache the results
    _embeddings_cache = embeddings_data
    
    # Try to save to temp directory for future requests
    try:
        temp_path = os.path.join(tempfile.gettempdir(), "embeddings.json")
        with open(temp_path, "w") as f:
            json.dump(embeddings_data, f)
        print(f"Saved embeddings to {temp_path}")
    except Exception as e:
        print(f"Error saving embeddings to temp: {str(e)}")
    
    return embeddings_data

def cosine_similarity(vec_a, vec_b):
    """Calculate cosine similarity between two vectors."""
    vec_a = np.array(vec_a)
    vec_b = np.array(vec_b)
    
    dot_product = np.dot(vec_a, vec_b)
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0
    
    return dot_product / (norm_a * norm_b)

def find_relevant_content(query_embedding, top_k=3):
    """Find the most relevant content based on embedding similarity."""
    embeddings = load_embeddings()
    
    # Calculate similarity with all content
    similarities = []
    for item in embeddings:
        similarity = cosine_similarity(query_embedding, item["embedding"])
        similarities.append({
            "id": item["id"],
            "content": item["content"],
            "url": item.get("url", f"https://sohae-kim.github.io/#{item['id']}"),
            "similarity": similarity
        })
    
    # Sort by similarity and take top k
    sorted_similarities = sorted(similarities, key=lambda x: x["similarity"], reverse=True)
    print(f"Top similarities: {[(item['id'], item['similarity']) for item in sorted_similarities[:top_k]]}")
    return sorted_similarities[:top_k]

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
        # Generate embedding for the question
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
        
        # Generate response using Claude
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
                "title": item["id"].replace("_", " ").title(),
                "url": item.get("url", f"https://sohae-kim.github.io/#{item['id']}")
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

def ensure_embeddings_exist():
    """Check if embeddings exist, and generate them if they don't"""
    # Check if embeddings already exist
    data_dir = os.path.join(os.getcwd(), "data")
    embeddings_path = os.path.join(data_dir, "embeddings.json")
    
    if os.path.exists(embeddings_path):
        print(f"Embeddings already exist at {embeddings_path}")
        return
    
    print("Embeddings not found, generating them...")
    
    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    # Load content
    content_path = os.path.join(data_dir, "content.json")
    if not os.path.exists(content_path):
        print(f"Content file not found at {content_path}")
        return
    
    with open(content_path, "r") as f:
        content_data = json.load(f)
    
    # Generate embeddings
    embeddings_data = []
    for item in content_data:
        print(f"Generating embedding for: {item['id']}")
        
        # Generate embedding
        response = openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=item["content"]
        )
        
        # Add to data
        embeddings_data.append({
            "id": item["id"],
            "url": item.get("url", f"https://sohae-kim.github.io/#{item['id']}"),
            "content": item["content"],
            "embedding": response.data[0].embedding
        })
    
    # Save embeddings
    with open(embeddings_path, "w") as f:
        json.dump(embeddings_data, f)
    
    print(f"Generated and saved {len(embeddings_data)} embeddings")

# Add this to your startup code
try:
    ensure_embeddings_exist()
except Exception as e:
    print(f"Error ensuring embeddings exist: {str(e)}")