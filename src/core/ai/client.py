from typing import List, Optional

from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.config import settings


class AIClient:
    """Клиент для взаимодействия с Google Gemini."""

    def __init__(self):
        # Настройка транспорта и прокси, если необходимо.
        # LangChain/Google Generative AI обычно подхватывают HTTP_PROXY из переменных окружения.
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.8,
            convert_system_message_to_human=True, # Часто помогает с Google моделями
        )

    async def generate_response(self, messages: List[BaseMessage]) -> str:
        """
        Генерирует ответ на основе истории сообщений.
        
        Args:
            messages: Список сообщений LangChain (System, Human, AI).
            
        Returns:
            str: Текст ответа модели.
        """
        try:
            ai_msg = await self.llm.ainvoke(messages)
            content = ai_msg.content
            
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Сборка текста из частей (если мультимодальный ответ или сложная структура)
                parts = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        parts.append(part["text"])
                    elif isinstance(part, str):
                        parts.append(part)
                return "".join(parts)
            else:
                return str(content)
                
        except Exception as e:
            # Логирование ошибки лучше делать выше или тут
            return f"⚠️ Произошла ошибка при обращении к AI: {str(e)}"

    async def get_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """
        Генерирует эмбеддинг для текста с нормализацией (L2).
        Использует модель text-embedding-004 через LangChain (для поддержки прокси).
        """
        import numpy as np
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        
        try:
            # Используем LangChain враппер, так как он корректно работает с прокси через httpx
            # который подхватывает HTTP_PROXY из переменных окружения.
            embeddings_model = GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004",
                google_api_key=settings.GOOGLE_API_KEY,
                task_type=task_type.lower() if task_type else "retrieval_document",
            )
            
            # Получаем эмбеддинг
            # LangChain embed_query уже возвращает список флоатов
            embedding = await embeddings_model.aembed_query(text)
            
            # L2 Нормализация (на всякий случай, хотя text-embedding-004 может быть уже нормализован, но L2 не повредит)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = (np.array(embedding) / norm).tolist()
                
            return embedding
        except Exception as e:
            # Логируем ошибку
            import logging
            logging.getLogger(__name__).error(f"Embedding error: {e}")
            return []

# Глобальный экземпляр
ai_client = AIClient()
