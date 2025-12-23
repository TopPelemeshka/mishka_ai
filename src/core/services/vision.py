import base64
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.core.config import settings


class VisionService:
    """Сервис для анализа изображений (Computer Vision via LLM)."""

    def __init__(self):
        # Используем ту же модель, что и основной клиент, или специальную
        # Gemini 1.5 Flash отлично подходит для Vision задачи
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview", # Используем конфиг пользователя
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.5, # Чуть строже для описаний
        )

    async def describe_image(self, image_bytes: bytes) -> str:
        """
        Получает байты изображения и возвращает текстовое описание.
        """
        # 1. Кодируем в base64
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        
        # 2. Формируем мультимодальное сообщение
        message = HumanMessage(
            content=[
                {
                    "type": "text", 
                    "text": (
                        "Проанализируй это изображение. "
                        "Опиши подробно, что происходит, кто присутствует (если есть люди), "
                        "детали обстановки и настроение. Если есть текст — прочитай его."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}
                }
            ]
        )

        try:
            # 3. Вызываем модель
            response = await self.llm.ainvoke([message])
            return response.content
            
        except Exception as e:
            return f"[Ошибка анализа изображения: {str(e)}]"

# Глобальный экземпляр
vision_service = VisionService()
