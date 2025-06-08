# mishka_ai/handlers/conversation_logic.py
"""
Модуль, содержащий основную логику ведения диалога и управления памятью.

Здесь реализованы функции для:
- Генерации ответов бота с использованием контекста, фактов и эмоций.
- Запуска фоновых процессов анализа диалога для извлечения фактов.
- Запуска анализа и консолидации эмоциональной памяти.
"""
import logging
import json
import asyncio
from textwrap import dedent 
from mishka_ai.utils import get_user_details_string

# Используется для аннотации типов, чтобы избежать циклических импортов
from typing import TYPE_CHECKING
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from mishka_ai.gemini_client import GeminiClient
    from mishka_ai.short_term_memory import ShortTermMemory
    from mishka_ai.memory_manager import MemoryManager 

logger = logging.getLogger(__name__)

async def generate_mishka_response(
    user_message_text: str,
    user_id_str: str,
    current_users_data: dict,
    mishka_system_prompt_template_str: str,
    short_term_memory: 'ShortTermMemory',
    memory_manager: 'MemoryManager',
    gemini_client: 'GeminiClient', 
    involved_user_ids: set[str],
    context: ContextTypes.DEFAULT_TYPE
) -> str | None:
    """
    Генерирует ответ бота на сообщение пользователя.

    Эта функция собирает полный контекст для LLM, включая:
    1. Системный промпт с описанием личности бота и известных пользователей.
    2. Релевантные факты из долгосрочной памяти (LTM).
    3. Эмоциональный контекст об авторе сообщения.
    4. Историю последних сообщений из краткосрочной памяти (STM).

    Args:
        user_message_text: Текст сообщения от пользователя.
        user_id_str: ID пользователя, отправившего сообщение.
        current_users_data: Словарь с данными всех известных пользователей.
        mishka_system_prompt_template_str: Шаблон системного промпта.
        short_term_memory: Экземпляр STM.
        memory_manager: Экземпляр MemoryManager для доступа к LTM и эмо-памяти.
        gemini_client: Клиент для генерации ответа.
        involved_user_ids: Множество ID пользователей, задействованных в сообщении.
        context: Контекст бота для доступа к конфигурации.

    Returns:
        Сгенерированный текстовый ответ или None в случае ошибки.
    """
    user_details_str = get_user_details_string(current_users_data)
    max_relevant_distance = context.bot_data.get("LTM_MAX_RELEVANT_DISTANCE_CONFIG", 1.0)

    # 1. Получаем релевантные факты из LTM
    relevant_facts = await memory_manager.get_relevant_facts_from_ltm(
        query_text=user_message_text,
        user_ids=list(involved_user_ids),
        N=10,
        max_distance=max_relevant_distance
    )
    if relevant_facts:
        logger.info(f"conversation_logic: Получено релевантных фактов ({len(relevant_facts)}): " + ", ".join(relevant_facts))
    else:
        logger.info("conversation_logic: Релевантных фактов для текущего запроса не найдено.")

    # 2. Формируем базовый системный промпт
    mishka_system_prompt_base = ""
    if not mishka_system_prompt_template_str:
        logger.error("Шаблон системного промпта Мишки пуст!")
        mishka_system_prompt_base = "Ты Мишка, дружелюбный и немного саркастичный медведь."
    else:
        try:
            mishka_system_prompt_base = mishka_system_prompt_template_str.format(user_details=user_details_str)
        except KeyError as e:
            # Обработка ошибки, если в шаблоне промпта неверный плейсхолдер
            logger.error(f"Ошибка форматирования промпта: {e}. Промпт: '{mishka_system_prompt_template_str}', Детали: '{user_details_str}'")
            mishka_system_prompt_base = mishka_system_prompt_template_str 
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при форматировании промпта: {e}")
            mishka_system_prompt_base = "Ты Мишка, дружелюбный и немного саркастичный медведь."
    
    final_system_prompt = mishka_system_prompt_base
    # Добавляем факты из LTM в системный промпт, если они есть
    if relevant_facts:
        facts_str = "\n".join([f"- {fact}" for fact in relevant_facts])
        final_system_prompt += f"\n\n[ВАЖНАЯ ИНФОРМАЦИЯ ИЗ ПАМЯТИ ДЛЯ ТЕКУЩЕГО РАЗГОВОРА - используй ее при ответе]:\n{facts_str}"

    # 3. Получаем и добавляем эмоциональный контекст
    user_name_for_prompt = current_users_data.get(user_id_str, {}).get("name", f"Пользователь_{user_id_str}")
    emotional_data_for_user = memory_manager.get_emotional_notes(user_id_str)
    emotional_context_str_parts = []
    if emotional_data_for_user:
        logger.debug(f"Получены эмоциональные данные для user {user_name_for_prompt} (ID: {user_id_str}): {emotional_data_for_user}")
        
        notes = emotional_data_for_user.get('notes', [])
        if notes and isinstance(notes, list):
            notes_str = "; ".join(notes) 
            if notes_str:
                emotional_context_str_parts.append(f"Недавние/ключевые эмоциональные заметки о нем/ней: {notes_str}.")
        last_summary = emotional_data_for_user.get('last_interaction_summary', '')
        if last_summary:
            emotional_context_str_parts.append(f"Общее впечатление от предыдущего общения с ним/ней: {last_summary}.")
            
    if emotional_context_str_parts:
        emotional_context_str = " ".join(emotional_context_str_parts)
        final_system_prompt += (
            f"\n\n[ЭМОЦИОНАЛЬНЫЙ КОНТЕКСТ О {user_name_for_prompt} (ID: {user_id_str}) - "
            f"учти это в своем тоне и ответе]:\n{emotional_context_str}"
        )
        logger.info(f"Добавлен эмоциональный контекст для {user_name_for_prompt} в системный промпт.")
    else:
        logger.info(f"Эмоциональный контекст для {user_name_for_prompt} не найден или пуст.")
    
    logger.info(f"conversation_logic: Финальный системный промпт (начало): '{final_system_prompt[:450]}...'")

    # 4. Формируем историю для API-вызова
    history_for_gemini_call = [
        {"role": "user", "parts": [final_system_prompt]},
        {"role": "model", "parts": ["Понял задачу. Я Мишка, готов общаться, помнить о друзьях и фактах, а также учитывать эмоциональный фон и контекст отношений."]}
    ]
    # Добавляем историю из STM (кроме последнего сообщения пользователя, которое пойдет как основной промпт)
    processed_short_term_history = short_term_memory.get_formatted_history(exclude_last_n=1) 
    history_for_gemini_call.extend(processed_short_term_history)

    prompt_text_to_gemini = user_message_text
    current_user_name_from_data = current_users_data.get(user_id_str, {}).get("name")
    normalized_message = user_message_text.lower()

    # Особая логика для вопросов о себе, чтобы помочь модели понять контекст
    is_self_query = (
        "кто я" in normalized_message or
        "как меня зовут" in normalized_message or
        "ты знаешь меня" in normalized_message or
        "помнишь меня" in normalized_message
    )
    if current_user_name_from_data and is_self_query:
        prompt_text_to_gemini = f"[Мишка, учти, что это спрашивает {current_user_name_from_data} (ID: {user_id_str}) о себе.] {user_message_text}"
    
    # 5. Вызываем LLM для генерации ответа
    bot_response_text = await gemini_client.generate_response(
        prompt_text=prompt_text_to_gemini,
        history=history_for_gemini_call 
    )
    return bot_response_text


async def trigger_fact_extraction(
    short_term_memory: 'ShortTermMemory',
    memory_manager: 'MemoryManager', 
    gemini_analysis_client: 'GeminiClient',
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Запускает процесс извлечения фактов из недавнего фрагмента диалога.

    Анализируется определенное количество последних сообщений из STM.
    Извлеченные факты сохраняются в LTM.
    """
    conversation_chunk_size_for_fact_analysis = context.bot_data.get("CONVERSATION_CHUNK_SIZE_FOR_FACT_ANALYSIS_CONFIG", 6)
    all_users_data = context.bot_data.get("users_data_dict", {})

    logger.info("Попытка извлечения фактов из недавнего фрагмента переписки...")
    stm_list = list(short_term_memory.history)
    
    # Берем последние N сообщений для анализа
    num_messages_to_actually_analyze = min(len(stm_list), conversation_chunk_size_for_fact_analysis)
    history_to_analyze = stm_list[-num_messages_to_actually_analyze:]

    if history_to_analyze:
        logger.debug(f"Фрагмент переписки для анализа фактов ({len(history_to_analyze)} сообщ.): {json.dumps(history_to_analyze, ensure_ascii=False, indent=1)}")
        try:
            # Делегируем извлечение и сохранение MemoryManager'у
            extracted_new_facts = await memory_manager.process_chat_history_for_facts(
                chat_history_messages=history_to_analyze,
                gemini_analysis_client=gemini_analysis_client,
                all_users_data=all_users_data
            )
            if extracted_new_facts:
                logger.info(f"Успешно извлечено и сохранено {len(extracted_new_facts)} новых фактов из фрагмента переписки.")
            else:
                logger.info("Новых фактов из фрагмента переписки не извлечено.")
        except Exception as e:
            logger.error(f"Ошибка при выполнении trigger_fact_extraction: {e}", exc_info=True)
    else:
        logger.info("Нет сообщений в STM для анализа фактов.")


async def trigger_emotional_consolidation(
    user_id_str: str,
    user_name: str, 
    memory_manager: 'MemoryManager',
    gemini_analysis_client: 'GeminiClient',
    all_prompts_data: dict,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Запускает процесс консолидации (обобщения) эмоциональных заметок о пользователе.

    Когда "сырых" заметок накапливается много, эта функция "сжимает" их в несколько
    ключевых выводов и обновляет общее резюме об отношениях, предотвращая засорение памяти.
    """
    max_consolidated_emotional_notes = context.bot_data.get("MAX_CONSOLIDATED_EMOTIONAL_NOTES_CONFIG", 4)

    logger.info(f"Запуск консолидации эмоциональных заметок для пользователя {user_name} ({user_id_str}).")

    user_emotional_data = memory_manager.get_emotional_notes(user_id_str)
    if not user_emotional_data or not user_emotional_data.get("notes"):
        logger.info(f"Нет заметок для консолидации у пользователя {user_name} ({user_id_str}). Пропуск.")
        return

    current_notes_list = user_emotional_data.get("notes", [])
    if len(current_notes_list) < 2: 
        logger.info(f"У пользователя {user_name} ({user_id_str}) слишком мало заметок ({len(current_notes_list)}) для полноценной консолидации. Пропуск.")
        return

    # Подготовка данных для промпта
    current_overall_summary = user_emotional_data.get("last_interaction_summary", "Пока нет общего впечатления.")
    notes_to_consolidate_text = "\n".join([f"{i+1}. {note}" for i, note in enumerate(current_notes_list)]).strip()

    consolidation_prompt_template = all_prompts_data.get("emotional_consolidation_prompt")
    if not consolidation_prompt_template:
        logger.error("Шаблон 'emotional_consolidation_prompt' не найден. Консолидация невозможна.")
        return

    try:
        # Формирование и отправка запроса LLM
        final_prompt_for_consolidation = consolidation_prompt_template.format(
            user_name=user_name,
            user_id=user_id_str,
            current_overall_summary=current_overall_summary,
            notes_to_consolidate_text=notes_to_consolidate_text,
            max_consolidated_notes=max_consolidated_emotional_notes 
        )
    except KeyError as e:
        logger.error(f"Ошибка форматирования emotional_consolidation_prompt: ключ {e}. Проверьте плейсхолдеры в prompts.json.")
        return
    
    logger.info(f"Запрос к Gemini для консолидации эмоц. заметок user {user_name} ({user_id_str})...")
    
    response_str = await gemini_analysis_client.generate_response(prompt_text=final_prompt_for_consolidation)

    if not response_str:
        logger.warning(f"Gemini не вернул ответ для консолидации эмоц. заметок user {user_name} ({user_id_str}).")
        return
    
    logger.debug(f"Ответ Gemini (консолидация, сырой, user {user_name}): {response_str}")

    # Парсинг JSON-ответа от LLM
    try:
        clean_response_str = response_str.strip()
        if clean_response_str.startswith("```json"):
            clean_response_str = clean_response_str[len("```json"):]
        if clean_response_str.startswith("```"):
            clean_response_str = clean_response_str[len("```"):]
        if clean_response_str.endswith("```"):
            clean_response_str = clean_response_str[:-len("```")]
        clean_response_str = clean_response_str.strip()

        parsed_json_data = json.loads(clean_response_str) if clean_response_str else None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON (консолидация) user {user_name}: {e}. Ответ: {response_str[:500]}")
        return
    except Exception as e_parse:
        logger.error(f"Непредвиденная ошибка при парсинге JSON (консолидация) user {user_name}: {e_parse}. Ответ: {response_str[:500]}", exc_info=True)
        return

    if not isinstance(parsed_json_data, dict):
        logger.warning(f"Распарсенные данные для консолидации не являются словарем или пусты. User: {user_name}. Данные: {parsed_json_data}")
        return

    consolidated_notes = parsed_json_data.get("consolidated_notes")
    new_overall_summary = parsed_json_data.get("new_overall_summary")

    # Валидация структуры ответа
    if not isinstance(consolidated_notes, list) or not isinstance(new_overall_summary, str):
        logger.warning(f"Ответ Gemini для консолидации не содержит корректных 'consolidated_notes' (список) или 'new_overall_summary' (строка). User: {user_name}. Ответ: {parsed_json_data}")
        return
    
    logger.info(f"Результаты консолидации для user {user_name} ({user_id_str}): {len(consolidated_notes)} консолидированных заметок, новое резюме: '{new_overall_summary}'.")
    
    # Сохранение результатов консолидации
    success = memory_manager.overwrite_emotional_data_after_consolidation(
        user_id=user_id_str,
        consolidated_notes=consolidated_notes,
        new_overall_summary=new_overall_summary,
        user_name_if_missing=user_name 
    )

    if success:
        logger.info(f"Эмоциональная память для user {user_name} ({user_id_str}) успешно консолидирована и перезаписана.")
    else:
        logger.error(f"Не удалось перезаписать эмоциональную память для user {user_name} ({user_id_str}) после консолидации.")


async def trigger_emotional_analysis(
    user_id_str: str,
    user_name: str, 
    short_term_memory: 'ShortTermMemory',
    memory_manager: 'MemoryManager',
    gemini_analysis_client: 'GeminiClient',
    all_prompts_data: dict,
    context: ContextTypes.DEFAULT_TYPE 
):
    """
    Запускает анализ недавнего диалога для обновления эмоциональной памяти о пользователе.

    Эта функция срабатывает после накопления определенного количества сообщений от пользователя.
    Она анализирует фрагмент диалога, извлекает новую "сырую" эмоциональную заметку и,
    если порог достигнут, инициирует `trigger_emotional_consolidation`.
    """
    # Получаем пороги из конфигурации
    emotional_analysis_message_threshold = context.bot_data.get("EMOTIONAL_ANALYSIS_MESSAGE_THRESHOLD_CONFIG", 3)
    emotional_analysis_stm_window_size = context.bot_data.get("EMOTIONAL_ANALYSIS_STM_WINDOW_SIZE_CONFIG", 8)
    emotional_notes_consolidation_trigger_count = context.bot_data.get("EMOTIONAL_NOTES_CONSOLIDATION_TRIGGER_COUNT_CONFIG", 7)
    
    # Используем user_data для хранения счетчиков сообщений для каждого пользователя отдельно
    user_specific_analysis_trigger_counters = context.user_data.setdefault('emotional_analysis_msg_counters', {})
    current_msg_count_for_analysis = user_specific_analysis_trigger_counters.get(user_id_str, 0) + 1
    user_specific_analysis_trigger_counters[user_id_str] = current_msg_count_for_analysis

    logger.info(f"Счетчик сообщений для запуска эмоц. анализа user {user_name} ({user_id_str}): {current_msg_count_for_analysis}/{emotional_analysis_message_threshold}")

    # Если порог сообщений не достигнут, выходим
    if current_msg_count_for_analysis < emotional_analysis_message_threshold:
        logger.debug(f"Порог для запуска эмоц. анализа пользователя {user_name} ({user_id_str}) не достигнут.")
        return

    logger.info(f"Запуск эмоционального анализа для пользователя {user_name} ({user_id_str}). Счетчик сообщений для анализа сброшен.")
    user_specific_analysis_trigger_counters[user_id_str] = 0 # Сбрасываем счетчик

    # Подготовка данных для промпта
    user_emotional_data = memory_manager.get_emotional_notes(user_id_str)
    current_emotional_notes_str = "Пока нет эмоциональных заметок."
    if user_emotional_data and user_emotional_data.get('notes'):
        notes_list = user_emotional_data['notes']
        if isinstance(notes_list, list) and notes_list:
             display_notes = notes_list[-5:]
             current_emotional_notes_str = "Последние/ключевые заметки: " + "; ".join(display_notes)
    logger.debug(f"Текущие эмоциональные заметки для промпта обновления (user {user_name}): {current_emotional_notes_str}")

    stm_history_list = list(short_term_memory.history)
    interaction_history_messages = stm_history_list[-emotional_analysis_stm_window_size:]
    interaction_history_parts = [
        f"{msg.get('user_name', 'Мишка')}: {msg.get('parts', [''])[0]}" for msg in interaction_history_messages
    ]
    interaction_history_str = "\n".join(interaction_history_parts)
    
    if not interaction_history_str.strip():
        logger.warning(f"Сформированная история для эмоц. анализа пуста для user {user_name}. Анализ отменен.")
        return

    # Формирование и отправка запроса LLM
    emotional_update_prompt_template = all_prompts_data.get("emotional_update_prompt")
    if not emotional_update_prompt_template:
        logger.error("Шаблон 'emotional_update_prompt' не найден. Эмоц. анализ невозможен.")
        return

    try:
        final_prompt_for_gemini = emotional_update_prompt_template.format(
            user_name=user_name,
            user_id=user_id_str,
            current_emotional_notes=current_emotional_notes_str,
            interaction_history=interaction_history_str
        )
    except KeyError as e:
        logger.error(f"Ошибка форматирования emotional_update_prompt: ключ {e}.")
        return
    
    logger.info(f"Запрос к Gemini для эмоц. анализа user {user_name} ({user_id_str})...")
    
    response_str = await gemini_analysis_client.generate_response(prompt_text=final_prompt_for_gemini)
    if not response_str:
        logger.warning(f"Gemini не вернул ответ для эмоц. анализа user {user_name}.")
        return

    # Парсинг JSON-ответа
    try:
        clean_response_str = response_str.strip()
        if clean_response_str.startswith("```json"): clean_response_str = clean_response_str[len("```json"):]
        if clean_response_str.startswith("```"): clean_response_str = clean_response_str[len("```"):]
        if clean_response_str.endswith("```"): clean_response_str = clean_response_str[:-len("```")]
        clean_response_str = clean_response_str.strip()
        
        parsed_json_data = json.loads(clean_response_str) if clean_response_str else None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка декодирования JSON (эмоц. анализ) user {user_name}: {e}. Ответ: {response_str[:500]}")
        return
    except Exception as e_parse:
        logger.error(f"Непредвиденная ошибка при парсинге JSON (эмоц. анализ) user {user_name}: {e_parse}. Ответ: {response_str[:500]}", exc_info=True)
        return

    if not isinstance(parsed_json_data, dict):
        logger.warning(f"Распарсенные данные для эмоц. анализа не являются словарем или пусты. User: {user_name}. Данные: {parsed_json_data}")
        return

    new_emotional_note = parsed_json_data.get("new_emotional_note", "").strip()
    relationship_change_summary = parsed_json_data.get("relationship_change", "").strip()
    
    # Обновление эмоциональной памяти, если LLM вернул что-то значимое
    raw_notes_count_after_update = 0 
    if new_emotional_note or relationship_change_summary: 
        logger.info(f"Результаты эмоц. анализа для user {user_name}: Новая заметка: '{new_emotional_note}', Изменение отношений: '{relationship_change_summary}'.")
        raw_notes_count_after_update = memory_manager.update_emotional_notes(
            user_id=user_id_str,
            new_note_text=new_emotional_note if new_emotional_note else None, 
            interaction_summary=relationship_change_summary if relationship_change_summary else None,
            user_name=user_name 
        )
        logger.info(f"Эмоциональная память для user {user_name} обновлена. Текущее кол-во сырых заметок: {raw_notes_count_after_update}.")
    else:
        logger.info(f"Ни новой заметки, ни саммари не получено от Gemini для user {user_name}. Эмоц. память не обновлена.")
        current_emo_data = memory_manager.get_emotional_notes(user_id_str)
        if current_emo_data:
            raw_notes_count_after_update = current_emo_data.get("raw_notes_count", 0)

    # Проверяем, не пора ли запускать консолидацию
    if raw_notes_count_after_update >= emotional_notes_consolidation_trigger_count:
        logger.info(f"Достигнут порог сырых заметок ({raw_notes_count_after_update}/{emotional_notes_consolidation_trigger_count}) для пользователя {user_name} ({user_id_str}). Планирование консолидации.")
        
        asyncio.create_task(trigger_emotional_consolidation(
            user_id_str=user_id_str,
            user_name=user_name,
            memory_manager=memory_manager,
            gemini_analysis_client=gemini_analysis_client,
            all_prompts_data=all_prompts_data,
            context=context
        ))
    else:
        logger.info(f"Порог для консолидации эмоц. заметок для {user_name} не достигнут ({raw_notes_count_after_update}/{emotional_notes_consolidation_trigger_count}).")