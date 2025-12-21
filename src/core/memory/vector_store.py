from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.core.config import settings


class VectorDB:
    """Обертка над клиентом Qdrant для управления векторной памятью."""

    def __init__(self):
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None
        )
        self.collection_name = "mishka_memories"
        # Размер вектора для Google text-embedding-004
        self.vector_size = 768

    def ensure_collection(self):
        """Проверяет существование коллекции и создает её при необходимости."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Если коллекция не найдена, создаем новую
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                )
            )

# Глобальный экземпляр
vector_db = VectorDB()
