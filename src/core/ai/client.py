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

# Глобальный экземпляр
ai_client = AIClient()
