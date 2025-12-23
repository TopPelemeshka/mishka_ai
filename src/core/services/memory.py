import asyncio
import json
import uuid
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from qdrant_client.models import PointStruct

from src.core.ai.client import ai_client
from src.core.memory.models import MemoryFact
from src.core.memory.vector_store import vector_db


class MemoryService:
    """Сервис долгосрочной памяти (Facts Extraction & RAG)."""

    async def extract_facts(self, text: str, user_id: int, message_id: int = None) -> List[MemoryFact]:
        """
        Извлекает факты из текста сообщения с помощью Gemini.
        """
        prompt = (
            "Проанализируй сообщение пользователя. Выдели важные факты о нем, его предпочтениях, "
            "событиях в жизни или отношениях. Игнорируй приветствия, короткие ответы ('да', 'нет') и флуд. "
            "Для каждого факта укажи категорию (bio, preferences, events, opinions, relationships) "
            "и важность (1-10). "
            "Верни ответ ТОЛЬКО в формате JSON списка объектов: "
            "[{'text': '...', 'category': '...', 'importance': 1}]"
        )
        
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content=text)
        ]

        try:
            response_json = await ai_client.generate_response(messages)
            # Очистка от markdown ```json ... ```
            clean_json = response_json.replace("```json", "").replace("```", "").strip()
            
            facts_data = json.loads(clean_json)
            if not isinstance(facts_data, list):
                facts_data = [facts_data]

            facts = []
            for item in facts_data:
                # Валидация и создание моделей
                try:
                    fact = MemoryFact(
                        text=item["text"],
                        category=item["category"],
                        importance=item["importance"],
                        user_id=user_id,
                        original_message_id=message_id
                    )
                    facts.append(fact)
                except Exception as e:
                    print(f"Validation error for fact {item}: {e}")
                    continue
            
            return facts

        except Exception as e:
            # Если не удалось распарсить или ошибка модели - просто возвращаем пустой список
            # print(f"Fact extraction error: {e}") 
            return []

    async def save_facts(self, facts: List[MemoryFact]):
        """
        Векторизует и сохраняет факты в Qdrant.
        """
        if not facts:
            return

        points = []
        for fact in facts:
            # Генерация эмбеддинга (Task: Document)
            embedding = await ai_client.get_embedding(fact.text, task_type="RETRIEVAL_DOCUMENT")
            
            if not embedding:
                continue

            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "text": fact.text,
                    "category": fact.category,
                    "importance": fact.importance,
                    "user_id": fact.user_id,
                    "created_at": fact.created_at.isoformat(),
                    "original_message_id": fact.original_message_id
                }
            ))

        if points:
            # Асинхронная вставка (через run_in_executor или родной async метод qdrant client если есть)
            # QdrantClient (sync) используется в VectorDB.
            # Лучше бы VectorDB имел async метод, но у QdrantClient есть AsyncQdrantClient.
            # В vector_store.py мы использовали sync client? Надо проверить.
            # Если sync, то надо оборачивать.
            
            # Проверка показала, что мы используем QdrantClient (синхронный) в vector_store.py.
            # Для простоты пока сделаем синхронный вызов в треде или допустим блокировку (плохо).
            # Правильнее обернуть.
            await asyncio.to_thread(
                vector_db.client.upsert,
                collection_name=vector_db.collection_name,
                points=points
            )

    async def search_relevant_facts(self, query: str, user_id: int = None, limit: int = 5, score_threshold: float = 0.65) -> str:
        """
        Ищет факты по запросу и возвращает отформатированную строку.
        """
        # Эмбеддинг запроса (Task: Query)
        embedding = await ai_client.get_embedding(query, task_type="RETRIEVAL_QUERY")
        if not embedding:
            return ""

        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        query_filter = None
        if user_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                    )
                ]
            )

        # Используем query_points (новый API), так как search удален в текущей версии
        search_result = await asyncio.to_thread(
            vector_db.client.query_points,
            collection_name=vector_db.collection_name,
            query=embedding,
            query_filter=query_filter,
            limit=limit,
            score_threshold=score_threshold
        )
        
        # query_points возвращает QueryResponse, у которого points - это список ScoredPoint
        # Либо просто список ScoredPoint (зависит от версии, но в новых это объект)
        # Проверим атрибуты. В v1.10+ это QueryResponse с полем points.
        # А если это просто список...
        # В output dir мы видели query_points.
        
        points = search_result.points if hasattr(search_result, 'points') else search_result

        if not points:
            return ""

        formatted_facts = []
        for hit in points:
            payload = hit.payload
            # Формат: [Факт (Importance: X): Текст]
            fact_str = f"- {payload['text']} (Важность: {payload['importance']})"
            formatted_facts.append(fact_str)
            
        return "\n".join(formatted_facts)

# Глобальный экземпляр
memory_service = MemoryService()
