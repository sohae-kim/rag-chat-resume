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

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

print(f"Current directory: {os.getcwd()}")
print(f"Project root: {project_root}")

# Ensure data directory exists
data_dir = project_root / "data"
os.makedirs(data_dir, exist_ok=True)
print(f"Data directory: {data_dir} (exists: {data_dir.exists()})")

# List files in data directory
print(f"Files in data directory: {list(data_dir.glob('*'))}")

try:
    # Import project utilities
    from app.utils import sanitize_input
    
    def generate_embeddings():
        print("Starting embeddings generation...")
        
        # Check for API key
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize OpenAI client
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # Load content
        content_path = data_dir / "content.json"
        print(f"Content path: {content_path} (exists: {content_path.exists()})")
        
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
        embeddings_path = data_dir / "embeddings.json"
        with open(embeddings_path, "w") as f:
            json.dump(embeddings_data, f)
        
        print(f"Embeddings saved to {embeddings_path}")
        print(f"Generated {len(embeddings_data)} embeddings")
        print(f"Embeddings file exists: {embeddings_path.exists()}")
        print(f"Embeddings file size: {embeddings_path.stat().st_size} bytes")

    if __name__ == "__main__":
        generate_embeddings()
        
except Exception as e:
    print(f"ERROR in build script: {str(e)}")
    traceback.print_exc()
    sys.exit(1)