from aiogram import F, Router, types
from aiogram.enums import ChatAction
from langchain_core.messages import SystemMessage

from src.core.ai.client import ai_client
from src.core.memory.short_term import short_term_memory

from src.core.services.personality import personality_manager
from src.database.models.user import User

router = Router(name="chat_interaction")


@router.message(F.text)
async def chat_handler(message: types.Message, user: User):
    """Основные сообщения, отправляем в AI."""
    user_id = message.from_user.id
    text = message.text

    # 1. Сохраняем сообщение пользователя
    await short_term_memory.add_message(user_id, "user", text)

    # 2. Показываем статус "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # 3. Формируем контекст
    history = await short_term_memory.get_langchain_history(user_id)
    
    # Получаем персонализированный системный промпт
    system_prompt_text = personality_manager.get_system_prompt(user)
    system_prompt = SystemMessage(content=system_prompt_text)
    
    full_context = [system_prompt] + history

    # 4. Генерируем ответ
    response_text = await ai_client.generate_response(full_context)

    # 5. Сохраняем ответ бота
    await short_term_memory.add_message(user_id, "ai", response_text)

    # 6. Отправляем ответ (с поддержкой Markdown, если модель выдаст его)
    # Используем try/except на случай если разметка битая
    try:
        await message.answer(response_text)
    except Exception:
        # Фоллбек без разметки
        await message.answer(response_text, parse_mode=None)
