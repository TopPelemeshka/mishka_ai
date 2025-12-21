from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router(name="basic_commands")


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Хендлер команды /start"""
    await message.answer(
        "👋 <b>Привет! Я Mishka AI.</b>\n\n"
        "🟢 Системы в норме.\n"
        "🧠 Память подключена."
    )
