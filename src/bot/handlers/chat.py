import asyncio
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
    
    # ... logic continues ...
    # Выделяем логику генерации в отдельную функцию или оставляем тут повтор?
    # Пока оставим тут, чтобы не менять структуру слишком сильно, но для фото будет похоже.
    
    # 2. Показываем статус "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    await _process_and_respond(message, user_id, user)


@router.message(F.photo)
async def photo_handler(message: types.Message, user: User):
    """Обработка фотографий."""
    user_id = message.from_user.id
    
    # 1. Уведомляем о загрузке
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_PHOTO)
    
    # 2. Скачиваем фото (берем самый большой размер)
    photo = message.photo[-1]
    file_io = await message.bot.download(photo)
    image_bytes = file_io.getvalue()
    
    # 3. Получаем описание от VisionService
    # Мы могли бы отправить 'typing' пока ждем описание
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    from src.core.services.vision import vision_service
    description = await vision_service.describe_image(image_bytes)
    
    # 4. Формируем сообщение для контекста
    context_message = f"[Пользователь отправил фото]\nОписание изображения: {description}"
    
    # 5. Сохраняем в память как сообщение от пользователя (но с пометкой что это описание фото)
    await short_term_memory.add_message(user_id, "user", context_message)
    
    # 6. Генерируем реакцию бота
    await _process_and_respond(message, user_id, user)


async def _process_and_respond(message: types.Message, user_id: int, user: User):
    """Общая логика генерации ответа на основе истории."""
    # Запускаем фоновый процесс извлечения фактов (чтобы не задерживать ответ)
    # Используем asyncio.create_task
    # В идеале это делать через TaskIQ, но простого asyncio пока хватит для MVP
    from src.core.services.memory import memory_service
    
    async def process_facts_task():
        # Извлекаем факты из последнего сообщения пользователя (которое мы получили)
        # Оно уже есть в short_term_memory, но проще взять текст из message.text (если это текст)
        # Если это фото - там свое описание. 
        # Сделаем анализ только если это текстовое сообщение или описание фото.
        
        content_to_analyze = message.text or message.caption or ""
        # Если это было фото, у нас есть контекст в short_term_memory, но сюда передан message original.
        # Для фото хендлер сам добавил описание в память. 
        # Чтобы не усложнять, пока анализируем только прямой текст сообщения.
        # Если пусто - пропускаем.
        if not content_to_analyze:
            return

        try:
            facts = await memory_service.extract_facts(content_to_analyze, user_id, message.message_id)
            if facts:
                await memory_service.save_facts(facts)
                # Можно логировать
                # print(f"Saved {len(facts)} facts for user {user_id}")
        except Exception as e:
            print(f"Background memory task error: {e}")

    asyncio.create_task(process_facts_task())
  
    # --- RAG: Поиск фактов (Вариант Б: Query Generation) ---
    found_facts = ""
    
    # Получаем историю для контекста генерации запроса
    # Нам нужны последние пара сообщений, чтобы понять контекст (например "А кто это?" после "Я люблю Бэтмена")
    history = await short_term_memory.get_langchain_history(user_id)
    
    # Берем последние 2 сообщения из истории (или все что есть)
    last_context_msgs = history[-2:] if len(history) >= 2 else history
    # Превращаем в строку для промпта
    context_str = "\n".join([f"{m.type}: {m.content}" for m in last_context_msgs])
    
    # Текущее сообщение
    current_msg = message.text or (message.caption if message.caption else "[PHOTO]")
    
    # Промпт для генерации поискового запроса
    # Исправляем на правильный тип сообщений
    from langchain_core.messages import HumanMessage
    rag_query_messages = [
        SystemMessage(content=(
            "You are a helpful assistant improving a search query for a personal fact database.\n"
            "Analyze the User message and Context.\n"
            "Reformulate the user's intent into a semantic search query to find relevant facts about the user (e.g. 'user's favorite food', 'events in 2024').\n"
            "If the message is just greetings, chit-chat, or doesn't require remembering anything, return 'SKIP'.\n"
            "Output ONLY the query or 'SKIP'."
        )),
        HumanMessage(content=f"User message: {current_msg}\nContext: {context_str}")
    ]

    try:
        # Генерируем запрос (быстро, temperature можно пониже)
        # В идеале иметь отдельный метод в AIClient с низкой температурой, но и так сойдет.
        search_query = await ai_client.generate_response(rag_query_messages)
        search_query = search_query.strip()
        
        if search_query != "SKIP":
            # Ищем факты
            found_facts = await memory_service.search_relevant_facts(search_query, user_id=user_id)
            if found_facts:
                pass 
                # print(f"RAG: Found facts for query '{search_query}':\n{found_facts}")
    except Exception as e:
        print(f"RAG Error: {e}")

    # --- Конец RAG ---

    # Получаем персонализированный системный промпт с фактами
    system_prompt_text = personality_manager.get_system_prompt(user, facts=found_facts)
    system_prompt = SystemMessage(content=system_prompt_text)
    
    full_context = [system_prompt] + history

    # Генерируем ответ
    response_text = await ai_client.generate_response(full_context)

    # Сохраняем ответ бота
    await short_term_memory.add_message(user_id, "ai", response_text)

    # Отправляем ответ
    try:
        await message.answer(response_text)
    except Exception:
        await message.answer(response_text, parse_mode=None)
