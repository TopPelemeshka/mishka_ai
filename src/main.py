import asyncio
import logging

from src.bot.handlers import basic, chat
from src.bot.loader import bot, dp
from src.core.memory.vector_store import vector_db


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🚀 Starting Mishka AI...")

    # 1. Инициализация инфраструктуры
    try:
        logger.info("Connecting to Vector DB...")
        vector_db.ensure_collection()
        logger.info("✅ Vector DB connected.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Vector DB: {e}")
        # Не падаем, если векторная БД недоступна (для отладки), или падаем?
        # По требованию "качество превыше всего" лучше упасть, если компонент критичен, но пока залогируем.
        raise e

    # 1.5. Регистрация Middleware
    from src.bot.middlewares.auth import ChatAuthMiddleware
    from src.bot.middlewares.user_sync import UserSyncMiddleware
    
    auth_middleware = ChatAuthMiddleware()
    user_sync_middleware = UserSyncMiddleware()
    
    # Сначала Auth (отсекаем лишних), потом Sync (пишем в БД)
    dp.message.outer_middleware(auth_middleware)
    dp.callback_query.outer_middleware(auth_middleware)
    
    dp.message.outer_middleware(user_sync_middleware)
    dp.callback_query.outer_middleware(user_sync_middleware)

    # 2. Регистрация роутеров
    dp.include_router(basic.router)
    dp.include_router(chat.router)

    # 3. Запуск бота
    logger.info("🤖 Bot started polling.")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
