from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
import structlog

from src.core.config import settings

logger = structlog.get_logger()


class ChatAuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки доступа к боту.
    Разрешает взаимодействие только из чата с ID = ALLOWED_CHAT_ID.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        chat_id = None
        user = None

        # Определяем ID чата в зависимости от типа события
        if isinstance(event, Message):
            chat_id = event.chat.id
            user = event.from_user
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id
            user = event.from_user
            
        # Если ID определен и не совпадает с разрешенным
        if chat_id is not None and chat_id != settings.ALLOWED_CHAT_ID:
            user_info = f"{user.id} (@{user.username})" if user else "Unknown"
            logger.warning(
                "security.unauthorized_access",
                chat_id=chat_id,
                user=user_info,
                allowed_id=settings.ALLOWED_CHAT_ID
            )
            # Прерываем обработку
            return

        return await handler(event, data)
