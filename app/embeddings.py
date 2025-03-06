import json
import os
from openai import OpenAI
from dotenv import load_dotenv
import numpy as np

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text):
    """Get embedding for text using OpenAI's text-embedding-ada-002 model."""
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding

def create_embeddings():
    """Generate embeddings for all content chunks and save to JSON file."""
    # Use absolute path for content.json
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    content_path = os.path.join(data_dir, "content.json")
    embeddings_path = os.path.join(data_dir, "embeddings.json")
    
    # Ensure data directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    # Load content from JSON file
    try:
        with open(content_path, "r") as f:
            content = json.load(f)
    except FileNotFoundError:
        print(f"Content file not found at {content_path}. Creating a simple example...")
        # Create simple example content if file doesn't exist
        content = [
            {
                "id": "about",
                "content": "Sohae Kim is an ML Engineer with experience at Samsung Display and MIT.",
                "url": "#about"
            },
            {
                "id": "skills",
                "content": "Skills include Machine Learning, Deep Learning, NLP, TensorFlow, PyTorch, and Python.",
                "url": "#skills"
            },
            {
                "id": "education",
                "content": "Ph.D. from MIT, M.S. and B.S. from KAIST.",
                "url": "#education"
            }
        ]
        with open(content_path, "w") as f:
            json.dump(content, f)
    
    # Generate embeddings for each content chunk
    embedded_content = []
    for item in content:
        try:
            embedding = get_embedding(item["content"])
            embedded_content.append({
                "id": item["id"],
                "content": item["content"],
                "url": item["url"],
                "embedding": embedding
            })
            print(f"✓ Generated embedding for {item['id']}")
        except Exception as e:
            print(f"✗ Error generating embedding for {item['id']}: {e}")
    
    # Save embeddings to JSON file
    with open(embeddings_path, "w") as f:
        json.dump(embedded_content, f)
    
    print(f"✓ Saved {len(embedded_content)} embeddings to {embeddings_path}")

if __name__ == "__main__":
    create_embeddings()