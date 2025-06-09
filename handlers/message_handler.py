# mishka_ai/handlers/message_handler.py
"""
Модуль для обработки всех входящих текстовых сообщений, не являющихся командами.
"""
import logging
import re
import json 
import asyncio 
import time
from telegram import Update, constants 
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown 

# Импорт внутренних модулей
from mishka_ai.handlers.common import _add_new_user_if_needed
from mishka_ai.handlers.conversation_logic import (
    generate_mishka_response, 
    trigger_fact_extraction,
    trigger_emotional_analysis 
)
from mishka_ai.gemini_client import GeminiClient 
from mishka_ai.short_term_memory import ShortTermMemory
from mishka_ai.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

# Список слов-триггеров, на которые бот будет реагировать
MISHKA_TRIGGERS = [
    "миш", "миша", "мишу", "мишка", "мишку", "мишке", "мишаня", "мишань", 
    "мишуня", "мишунь", "мишенька", "мишутка", "миха", "михаил", 
    "потапыч", "медведь", "медведюшка", "топтыгин", "косолапый",
]
# Регулярное выражение для определения прямого обращения к боту в начале сообщения
MISHKA_MENTION_PATTERN_STR = r"^(?:(" + "|".join(re.escape(trigger) for trigger in MISHKA_TRIGGERS) + r")\b)"
MISHKA_MENTION_REGEX = re.compile(MISHKA_MENTION_PATTERN_STR, re.IGNORECASE)


async def _parse_tool_call(response_text: str) -> dict | None:
    """Пытается распарсить JSON для вызова инструмента из ответа LLM.
    Обрабатывает как 'голый' JSON, так и обернутый в ```json ... ```."""
    
    clean_text = response_text.strip()
    
    # Сначала ищем JSON, обернутый в блок кода
    match = re.search(r"```json\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
    if match:
        json_str = match.group(1)
    # Если не нашли, и текст похож на 'голый' JSON, используем его
    elif clean_text.startswith('{') and clean_text.endswith('}'):
        json_str = clean_text
    else:
        return None

    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and "tool_name" in data:
            logger.info(f"Обнаружен вызов инструмента: {data}")
            return data
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Ошибка парсинга JSON для вызова инструмента: {e}. Строка для парсинга: {json_str[:200]}")
    
    return None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Основной обработчик текстовых сообщений.

    Эта функция выполняет роль диспетчера:
    - Проверяет, должен ли бот реагировать на сообщение (целевой чат, активность бота).
    - Добавляет/обновляет информацию о пользователе.
    - Добавляет сообщение в краткосрочную память (STM).
    - Определяет, является ли сообщение прямым обращением или ответом боту.
    - Если да, запускает генерацию ответа и фоновые задачи анализа.
    - Если нет, просто сохраняет сообщение в STM для контекста.
    """
    logger.info(f"handle_message: Получено сообщение (ID обновления: {update.update_id}) от пользователя {update.effective_user.full_name if update.effective_user else 'Unknown User'} в чате {update.effective_chat.id}.")

    if not update.message or not update.message.text:
        logger.warning(f"handle_message: Сообщение отсутствует или не содержит текст. ID обновления: {update.update_id}")
        return
    
    # --- Проверка 1: Целевой чат ---
    target_chat_id = context.bot_data.get("target_chat_id")
    current_chat_id = update.effective_chat.id
    
    if target_chat_id is not None and current_chat_id != target_chat_id:
        is_admin_sender = str(update.effective_user.id) == context.bot_data.get("admin_user_id")
        if not (is_admin_sender and update.message.text.startswith("/")):
            logger.info(f"Сообщение из чата {current_chat_id} проигнорировано (целевой чат: {target_chat_id}).")
            return
        else:
            logger.info(f"Администратор {update.effective_user.full_name} отправил команду из чата {current_chat_id} (целевой: {target_chat_id}). Обработка разрешена.")


    # --- Проверка 2: Активность бота ---
    is_bot_active = context.bot_data.get("is_bot_active", True)
    if not is_bot_active:
        is_admin_sender = str(update.effective_user.id) == context.bot_data.get("admin_user_id")
        if not (is_admin_sender and update.message.text.startswith("/")):
            logger.info(f"Бот неактивен. Сообщение от {update.effective_user.full_name} проигнорировано.")
            return
        else:
            logger.info(f"Бот неактивен, но администратор {update.effective_user.full_name} отправил команду. Обработка разрешена.")

    # --- Получение зависимостей из контекста бота ---
    gemini_chat_client: GeminiClient = context.bot_data.get("gemini_chat_client")
    gemini_analysis_client: GeminiClient = context.bot_data.get("gemini_analysis_client")
    short_term_memory: ShortTermMemory = context.bot_data.get("short_term_memory")
    current_users_data: dict = context.bot_data.get("users_data_dict", {})
    mishka_system_prompt_template_str: str = context.bot_data.get("mishka_system_prompt_template", "")
    memory_manager: MemoryManager = context.bot_data.get("memory_manager")
    all_prompts_data: dict = context.bot_data.get("all_prompts", {}) 
    
    user_messages_threshold_for_fact_extraction_config = context.bot_data.get("USER_MESSAGES_THRESHOLD_FOR_FACT_EXTRACTION_CONFIG", 3)
    user_message_count_for_fact_extraction_trigger: int = context.bot_data.get("user_message_count_for_fact_extraction_trigger", 0)

    # --- Проверка 3: Наличие всех компонентов ---
    if not all([gemini_chat_client, gemini_analysis_client, short_term_memory, memory_manager, 
                current_users_data is not None, 
                mishka_system_prompt_template_str,
                all_prompts_data 
                ]): 
        missing_components = [name for name, val in {
            "GeminiChatClient": gemini_chat_client, "GeminiAnalysisClient": gemini_analysis_client,
            "ShortTermMemory": short_term_memory, "MemoryManager": memory_manager,
            "users_data_dict": current_users_data, "mishka_system_prompt_template": mishka_system_prompt_template_str,
            "all_prompts_data": all_prompts_data
        }.items() if val is None or val == ""]
        logger.error(f"Отсутствуют ключевые компоненты/данные в context.bot_data: {', '.join(missing_components)}! ID обновления: {update.update_id}")
        if is_bot_active and (target_chat_id is None or current_chat_id == target_chat_id):
             await update.message.reply_text("У меня серьезные внутренние неполадки. Пожалуйста, сообщите моему создателю.")
        return

    # --- Начало обработки сообщения ---
    user_message_text = update.message.text
    user = update.effective_user
    user_id_str = str(user.id)
    is_from_bot = user.is_bot

    if is_from_bot and user.id == context.bot.id:
        logger.info("Сообщение от самого себя проигнорировано.")
        return

    if not is_from_bot:
        if _add_new_user_if_needed(user, current_users_data, context): 
            logger.info(f"Данные пользователя {user.full_name} (ID: {user_id_str}) были добавлены/обновлены и сохранены. ID обновления: {update.update_id}")

    user_name_for_log = current_users_data.get(user_id_str, {}).get("name", user.full_name)
    
    should_process_stm_and_triggers = is_bot_active and (target_chat_id is None or current_chat_id == target_chat_id)
    
    if should_process_stm_and_triggers:
        short_term_memory.add_message(
            role="user", 
            text=user_message_text, 
            user_name=user_name_for_log, 
            user_id=user_id_str,
            is_bot=is_from_bot
        )
        
        if not is_from_bot:
            user_message_count_for_fact_extraction_trigger += 1
            context.bot_data["user_message_count_for_fact_extraction_trigger"] = user_message_count_for_fact_extraction_trigger
            logger.info(f"Счетчик сообщений пользователя для извлечения фактов: {user_message_count_for_fact_extraction_trigger}. Пользователь: {user_name_for_log}")

    # --- Логика реакции бота ---
    direct_mention_match_obj = MISHKA_MENTION_REGEX.match(user_message_text.lstrip())
    is_direct_mention_match = bool(direct_mention_match_obj)
    is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    if not is_from_bot and (is_direct_mention_match or is_reply_to_bot) and should_process_stm_and_triggers:
        
        # ✅✅✅ НАЧАЛО НОВОГО БЛОКА ✅✅✅
        last_response_time = context.bot_data.get("last_response_timestamp", 0.0)
        cooldown = context.bot_data.get("response_cooldown_seconds", 3.0)
        current_time = time.time()

        if current_time - last_response_time < cooldown:
            logger.warning(f"Отработал антифлуд. Прошло {current_time - last_response_time:.2f} сек. из {cooldown}. Сообщение от {user_name_for_log} проигнорировано.")
            return # Прерываем выполнение
        
        context.bot_data["last_response_timestamp"] = current_time # Обновляем время ответа
        # ✅✅✅ КОНЕЦ НОВОГО БЛОКА ✅✅✅
        
        mention_type = "прямое упоминание" if is_direct_mention_match else "ответ боту"
        
        logger.info(f"Обнаружено {mention_type} Мишки от {user_name_for_log}. Текст: '{user_message_text}'.")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        involved_user_ids = {user_id_str}

        bot_response_raw = await generate_mishka_response(
            user_message_text=user_message_text,
            author_user_id=user_id_str, # Передаем ID текущего автора
            author_user_name=user_name_for_log, # Передаем имя текущего автора
            current_users_data=current_users_data,
            mishka_system_prompt_template_str=mishka_system_prompt_template_str,
            short_term_memory=short_term_memory,
            memory_manager=memory_manager,
            gemini_client=gemini_chat_client,
            involved_user_ids=involved_user_ids,
            context=context
        )

        if not bot_response_raw:
            logger.warning("generate_mishka_response вернул пустой ответ.")
            return

        tool_call_data = await _parse_tool_call(bot_response_raw)

        if tool_call_data:
            tool_name = tool_call_data.get("tool_name")
            arguments = tool_call_data.get("arguments", {})
            
            await update.message.reply_text("Секундочку, сейчас сделаю...")

            command_to_send = "" # <--- Инициализируем переменную

            if tool_name == "call_meme_bot":
                query = arguments.get("query", "")
                command_to_send = f"/meme {query}".strip()
                await context.bot.send_message(chat_id=current_chat_id, text=command_to_send)
                logger.info(f"Выполнена команда другого бота: {command_to_send}")

            elif tool_name == "request_rating":
                command_to_send = "/rating"
                await context.bot.send_message(chat_id=current_chat_id, text=command_to_send)
                logger.info(f"Выполнена команда другого бота: {command_to_send}")
                
            else:
                await update.message.reply_text("Хм, я попытался сделать что-то, чего не умею. Странно.")
                logger.warning(f"LLM сгенерировал неизвестный инструмент: {tool_name}")

            # --- НОВЫЙ БЛОК: Добавляем вызванную команду в память бота ---
            if command_to_send:
                short_term_memory.add_message(
                    role="model", 
                    text=f"[Вызвал команду: {command_to_send}]", 
                    user_name="Мишка"
                )
            # --- КОНЕЦ НОВОГО БЛОКА ---

        else:
            bot_response_text_escaped = escape_markdown(bot_response_raw)
            logger.info(f"Ответ Gemini (сырой): '{bot_response_raw[:100]}...'")

            try:
                await update.message.reply_text(bot_response_text_escaped, parse_mode=constants.ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Ошибка при отправке экранированного Markdown ответа: {e}. Отправка как обычный текст.")
                await update.message.reply_text(bot_response_raw)

            short_term_memory.add_message(role="model", text=bot_response_raw, user_name="Мишка")
            
            if user_message_count_for_fact_extraction_trigger >= user_messages_threshold_for_fact_extraction_config:
                logger.info(f"Достигнут порог ({user_message_count_for_fact_extraction_trigger}/{user_messages_threshold_for_fact_extraction_config}) для извлечения фактов.")
                asyncio.create_task(trigger_fact_extraction( 
                    short_term_memory,
                    memory_manager,
                    gemini_analysis_client,
                    context 
                ))
                context.bot_data["user_message_count_for_fact_extraction_trigger"] = 0
            else:
                logger.info(f"Порог для извлечения фактов не достигнут ({user_message_count_for_fact_extraction_trigger}/{user_messages_threshold_for_fact_extraction_config}).")

            actual_user_name_for_analysis = current_users_data.get(user_id_str, {}).get("name", user.full_name)
            logger.info(f"Планирование задачи для эмоционального анализа пользователя {actual_user_name_for_analysis} (ID: {user_id_str})")
            asyncio.create_task(trigger_emotional_analysis(
                user_id_str=user_id_str,
                user_name=actual_user_name_for_analysis,
                short_term_memory=short_term_memory,
                memory_manager=memory_manager,
                gemini_analysis_client=gemini_analysis_client,
                all_prompts_data=all_prompts_data, 
                context=context 
            ))
            
    elif is_from_bot and should_process_stm_and_triggers:
        logger.info(f"Сообщение от бота {user.full_name} сохранено в STM. Текст: '{user_message_text[:100]}...'")

    elif not should_process_stm_and_triggers and (is_direct_mention_match or is_reply_to_bot):
        if not is_bot_active:
             await update.message.reply_text("🐻 Zzz... (Я сейчас на паузе. Спроси позже или попроси администратора меня включить.)", parse_mode=constants.ParseMode.MARKDOWN)
             logger.info(f"Попытка обращения к неактивному боту от {user_name_for_log}.")

    else:
        logger.info(f"Сообщение от {user_name_for_log} проигнорировано (не обращение, бот неактивен или не в целевом чате).")