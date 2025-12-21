from typing import Any, Awaitable, Callable, Dict, Union

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from src.database.models.user import User
from src.database.session import AsyncSessionLocal


class UserSyncMiddleware(BaseMiddleware):
    """
    Middleware для синхронизации данных пользователя с базой данных (UPSERT).
    Добавляет объект пользователя (User ORM) в data['user'].
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: Union[Message, CallbackQuery],
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TelegramUser = data.get("event_from_user")

        if not tg_user:
            return await handler(event, data)

        async with AsyncSessionLocal() as session:
            # Upsert пользователя
            stmt = insert(User).values(
                id=tg_user.id,
                username=tg_user.username,
                full_name=tg_user.full_name,
            ).on_conflict_do_update(
                index_elements=[User.id],
                set_={
                    "username": tg_user.username,
                    "full_name": tg_user.full_name,
                    "updated_at": func.now(),
                }
            ).returning(User)

            result = await session.execute(stmt)
            user = result.scalar_one()
            
            await session.commit()
            
            # Добавляем ORM объект в data для хендлеров
            data["user"] = user

        return await handler(event, data)
