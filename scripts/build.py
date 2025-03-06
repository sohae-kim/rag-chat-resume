#!/usr/bin/env python3
"""
Build script for Vercel deployment.
Generates embeddings from content.json and saves them to embeddings.json.
"""

import os
import sys
import json
from pathlib import Path
import traceback

# Set up paths
project_root = Path(__file__).parent.parent
data_dir = project_root / "data"
content_path = data_dir / "content.json"
embeddings_path = data_dir / "embeddings.json"

print(f"Project root: {project_root}")
print(f"Data directory: {data_dir}")
print(f"Content path: {content_path}")
print(f"Embeddings path: {embeddings_path}")

# Ensure data directory exists
os.makedirs(data_dir, exist_ok=True)

try:
    # Check if content.json exists
    if not content_path.exists():
        print(f"Error: Content file not found at {content_path}")
        sys.exit(1)
    
    # Load content
    with open(content_path, "r") as f:
        content_data = json.load(f)
    
    print(f"Loaded {len(content_data)} content items")
    
    # Import OpenAI
    from openai import OpenAI
    
    # Check for API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set")
        sys.exit(1)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Generate embeddings
    embeddings_data = []
    for item in content_data:
        print(f"Generating embedding for: {item['id']}")
        
        # Generate embedding
        response = client.embeddings.create(
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
    
    print(f"Saved {len(embeddings_data)} embeddings to {embeddings_path}")
    print(f"File exists: {embeddings_path.exists()}")
    print(f"File size: {embeddings_path.stat().st_size} bytes")
    
    # Create a copy in the root directory as a backup
    root_embeddings_path = project_root / "embeddings.json"
    with open(root_embeddings_path, "w") as f:
        json.dump(embeddings_data, f)
    print(f"Created backup at {root_embeddings_path}")

except Exception as e:
    print(f"ERROR in build script: {str(e)}")
    traceback.print_exc()
    sys.exit(1)