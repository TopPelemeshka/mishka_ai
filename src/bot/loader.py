from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import from_url

from src.core.config import settings

# Настройка Redis Storage для FSM
redis_conn = from_url(str(settings.redis_url))
storage = RedisStorage(redis=redis_conn)

# Настройка сессии (Proxy)
session: AiohttpSession | None = None
if settings.HTTP_PROXY:
    session = AiohttpSession(proxy=settings.HTTP_PROXY)

# Инициализация бота
bot = Bot(
    token=settings.BOT_TOKEN.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session
)

# Инициализация диспетчера
# Инъекция зависимости vector_db и db_session (если нужно будет глобально) можно сделать через middleware
# Но пока просто базовый диспетчер
dp = Dispatcher(storage=storage)
