# mishka_ai/handlers/message_handler.py
"""
Модуль для обработки всех входящих текстовых сообщений, не являющихся командами.
"""
import logging
import re
import json 
import asyncio 
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
        # Игнорируем сообщения из других чатов, но разрешаем админу использовать команды
        is_admin_sender = str(update.effective_user.id) == context.bot_data.get("admin_user_id")
        if not (is_admin_sender and update.message.text.startswith("/")):
            logger.info(f"Сообщение из чата {current_chat_id} проигнорировано (целевой чат: {target_chat_id}).")
            return
        else:
            logger.info(f"Администратор {update.effective_user.full_name} отправил команду из чата {current_chat_id} (целевой: {target_chat_id}). Обработка разрешена.")


    # --- Проверка 2: Активность бота ---
    is_bot_active = context.bot_data.get("is_bot_active", True)
    if not is_bot_active:
        # Если бот на паузе, игнорируем все, кроме команд от администратора
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
        # Собираем информацию о недостающих компонентах для лога
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
    
    # Добавляем или обновляем пользователя в базе, если необходимо
    if _add_new_user_if_needed(user, current_users_data, context): 
        logger.info(f"Данные пользователя {user.full_name} (ID: {user_id_str}) были добавлены/обновлены и сохранены. ID обновления: {update.update_id}")

    user_name_for_log = current_users_data.get(user_id_str, {}).get("name", user.full_name)
    
    # Определяем, нужно ли обрабатывать сообщение для STM и триггеров.
    # Это происходит, только если бот активен и в нужном чате.
    should_process_stm_and_triggers = is_bot_active and (target_chat_id is None or current_chat_id == target_chat_id)
    
    if should_process_stm_and_triggers:
        # Добавляем сообщение в краткосрочную память
        short_term_memory.add_message(
            role="user", 
            text=user_message_text, 
            user_name=user_name_for_log, 
            user_id=user_id_str
        )
        
        # Инкрементируем счетчик сообщений, который используется для отложенного запуска извлечения фактов
        user_message_count_for_fact_extraction_trigger += 1
        context.bot_data["user_message_count_for_fact_extraction_trigger"] = user_message_count_for_fact_extraction_trigger
        logger.info(f"Счетчик сообщений пользователя для извлечения фактов: {user_message_count_for_fact_extraction_trigger}. Пользователь: {user_name_for_log}")

    # --- Логика реакции бота ---
    processed_text_for_mention_check = user_message_text.lstrip()
    direct_mention_match_obj = MISHKA_MENTION_REGEX.match(processed_text_for_mention_check)
    is_direct_mention_match = bool(direct_mention_match_obj)
    is_reply_to_bot = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id

    # Бот отвечает, только если к нему обратились напрямую или ответили на его сообщение,
    # и при этом он активен и находится в правильном чате.
    if (is_direct_mention_match or is_reply_to_bot) and should_process_stm_and_triggers:
        mention_type = "прямое упоминание" if is_direct_mention_match else "ответ боту"
        matched_alias = direct_mention_match_obj.group(1) if is_direct_mention_match and direct_mention_match_obj.group(1) else "N/A"

        logger.info(f"Обнаружено {mention_type} Мишки от {user_name_for_log}. Текст: '{user_message_text}'. Обращение: '{matched_alias}'")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Собираем ID всех пользователей, вовлеченных в сообщение (автор и тот, кому отвечают)
        involved_user_ids = {user_id_str}
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            involved_user_ids.add(str(update.message.reply_to_message.from_user.id))

        # Генерируем ответ
        bot_response_text_raw = await generate_mishka_response(
            user_message_text=user_message_text, 
            user_id_str=user_id_str,
            current_users_data=current_users_data,
            mishka_system_prompt_template_str=mishka_system_prompt_template_str,
            short_term_memory=short_term_memory,
            memory_manager=memory_manager,
            gemini_client=gemini_chat_client,
            involved_user_ids=involved_user_ids,
            context=context
        )

        if bot_response_text_raw:
            # Системный промпт просит Gemini не использовать Markdown, но на всякий случай экранируем
            bot_response_text_escaped = escape_markdown(bot_response_text_raw)
            logger.info(f"Ответ Gemini (сырой): '{bot_response_text_raw[:100]}...'")

            try:
                # Отправляем ответ. Изначально была отправка с Markdown, но сейчас, согласно промпту,
                # используется обычный текст или экранированный Markdown для безопасности.
                await update.message.reply_text(bot_response_text_escaped, parse_mode=constants.ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Ошибка при отправке экранированного Markdown ответа: {e}. Отправка как обычный текст.")
                await update.message.reply_text(bot_response_text_raw)

            # Добавляем ответ бота в STM для поддержания контекста
            short_term_memory.add_message(role="model", text=bot_response_text_raw, user_name="Мишка")
            
            # --- Запуск фоновых задач после ответа ---
            
            # 1. Проверяем, не пора ли извлечь факты
            if user_message_count_for_fact_extraction_trigger >= user_messages_threshold_for_fact_extraction_config:
                logger.info(f"Достигнут порог ({user_message_count_for_fact_extraction_trigger}/{user_messages_threshold_for_fact_extraction_config}) для извлечения фактов.")
                asyncio.create_task(trigger_fact_extraction( 
                    short_term_memory,
                    memory_manager,
                    gemini_analysis_client,
                    context 
                ))
                context.bot_data["user_message_count_for_fact_extraction_trigger"] = 0 # Сбрасываем счетчик
            else:
                logger.info(f"Порог для извлечения фактов не достигнут ({user_message_count_for_fact_extraction_trigger}/{user_messages_threshold_for_fact_extraction_config}).")

            # 2. Запускаем эмоциональный анализ для текущего пользователя
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
            
    elif should_process_stm_and_triggers: # Если это обычное сообщение в целевом чате и бот активен
        logger.info(f"Сообщение от {user_name_for_log} не является прямым обращением. Только сохранено в STM для контекста.")
        # STM уже пополнено выше. Текущая логика позволяет боту "слушать" весь чат.
        # Задачи анализа (извлечение фактов и эмоций) запускаются только после прямого взаимодействия,
        # но анализируют они всю накопленную историю, включая "пассивные" сообщения.
        # Это позволяет боту быть в курсе событий в чате, даже когда он не участвует в диалоге.
        
    elif not should_process_stm_and_triggers and (is_direct_mention_match or is_reply_to_bot):
        # Бот не активен или не в том чате, но было прямое обращение.
        # Отвечаем коротким сообщением о статусе.
        if not is_bot_active:
             await update.message.reply_text("🐻 Zzz... (Я сейчас на паузе. Спроси позже или попроси администратора меня включить.)", parse_mode=constants.ParseMode.MARKDOWN)
             logger.info(f"Попытка обращения к неактивному боту от {user_name_for_log}.")

    else: # Сообщение полностью игнорируется
        logger.info(f"Сообщение от {user_name_for_log} проигнорировано (не обращение, бот неактивен или не в целевом чате).")