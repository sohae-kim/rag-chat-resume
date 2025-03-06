#!/usr/bin/env python3
"""
Build script for Vercel deployment.
Generates embeddings from content.json and saves them to embeddings.json.
"""

import os
import sys
import json
from pathlib import Path
from openai import OpenAI

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import project utilities
from app.utils import sanitize_input

def generate_embeddings():
    print("Starting embeddings generation...")
    
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Load content
    content_path = project_root / "data" / "content.json"
    if not content_path.exists():
        raise FileNotFoundError(f"Content file not found: {content_path}")
    
    with open(content_path, "r") as f:
        content_data = json.load(f)
    
    print(f"Loaded {len(content_data)} content items")
    
    # Generate embeddings for each content item
    embeddings_data = []
    
    for item in content_data:
        # Sanitize content
        sanitized_content = sanitize_input(item["content"])
        
        # Generate embedding
        print(f"Generating embedding for: {item['id']}")
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=sanitized_content
        )
        
        # Add embedding to data
        embeddings_data.append({
            "id": item["id"],
            "url": item.get("url", f"https://sohae-kim.github.io/#{item['id']}"),
            "content": item["content"],
            "embedding": response.data[0].embedding
        })
    
    # Save embeddings
    embeddings_path = project_root / "data" / "embeddings.json"
    with open(embeddings_path, "w") as f:
        json.dump(embeddings_data, f)
    
    print(f"Embeddings saved to {embeddings_path}")
    print(f"Generated {len(embeddings_data)} embeddings")

if __name__ == "__main__":
    generate_embeddings()