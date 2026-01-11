import requests
import os
from dotenv import load_dotenv

load_dotenv()

PROXY_URL = "http://localhost:8000/v1/embeddings"
API_KEY = os.getenv("GEMINI_API_KEY")

def test_embedding():
    print(f"Testing Embedding on {PROXY_URL}...")
    
    payload = {
        "content": "Мишка любит мед",
        "task_type": "retrieval_document"
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }
    
    try:
        resp = requests.post(PROXY_URL, json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            embedding = data.get("embedding")
            print(f"Success! Embedding length: {len(embedding)}")
            print(f"First 5 dims: {embedding[:5]}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_embedding()
