import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
import uuid
from typing import List, Dict

import qdrant_client

import importlib.metadata

QDRANT_HOST = os.getenv("QDRANT_HOST", "mishka_qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "mishka_facts"
VECTOR_SIZE = 768

class QdrantManager:
    def __init__(self):
        print(f"Connecting to {QDRANT_HOST}:{QDRANT_PORT}")
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._ensure_collection()

    def _ensure_collection(self):
        """Creates collection if not exists."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == COLLECTION_NAME for c in collections)
            
            if not exists:
                print(f"Creating collection: {COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
        except Exception as e:
            print(f"Qdrant Init Error: {e}")

    def add_fact(self, text: str, vector: List[float], metadata: Dict = None):
        """Adds a fact embedding to Qdrant."""
        if metadata is None:
            metadata = {}
        
        # Store original text in payload
        metadata["text"] = text
        
        point_id = str(uuid.uuid4())
        
        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=metadata
                )
            ]
        )
        return point_id

    def search_facts(self, vector: List[float], limit: int = 5) -> List[Dict]:
        """Searches for similar facts."""
        results = self.client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
            score_threshold=0.6 # Only relevant facts
        ).points
        
        return [
            {
                "score": hit.score,
                "text": hit.payload.get("text"),
                "metadata": hit.payload,
                "id": hit.id
            }
            for hit in results
        ]

    def get_all_facts(self, limit: int = 1000) -> List[Dict]:
        """Iterates over facts (Scroll)."""
        # Scroll API
        results, _ = self.client.scroll(
            collection_name=COLLECTION_NAME,
            limit=limit,
            with_payload=True,
            with_vectors=True # Needed for clustering
        )
        return [
            {
                "id": p.id,
                "vector": p.vector,
                "metadata": p.payload,
                "text": p.payload.get("text")
            }
            for p in results
        ]

    def delete_fact(self, fact_id: str):
        """Deletes a fact by ID."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=[fact_id]
            )
        )

# Global instance
try:
    qdrant_manager = QdrantManager()
except Exception as e:
    print(f"Failed to init QdrantManager: {e}")
    qdrant_manager = None
