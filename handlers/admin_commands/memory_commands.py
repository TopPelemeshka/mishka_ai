# mishka_ai/handlers/admin_commands/memory_commands.py
import logging
import json 
import asyncio 
from datetime import datetime, timezone, timedelta 
from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
import numpy as np 

from mishka_ai.memory_manager import MemoryManager, DEFAULT_IMPORTANCE_SCORE 

logger = logging.getLogger(__name__)

FACTS_PER_PAGE = 5 

# --- Вспомогательные функции ---
def _get_facts_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    if current_page > 1:
        row.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"facts_page_{current_page - 1}"))
    
    row.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="facts_page_ignore"))

    if current_page < total_pages:
        row.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"facts_page_{current_page + 1}"))
    
    if row: buttons.append(row)
    return InlineKeyboardMarkup(buttons)

async def _format_facts_for_page(
    memory_manager: MemoryManager, 
    sorted_fact_items: list[dict], 
    page: int,
    users_data: dict
    ) -> str:
    
    start_index = (page - 1) * FACTS_PER_PAGE
    end_index = start_index + FACTS_PER_PAGE
    page_fact_items = sorted_fact_items[start_index:end_index]

    if not page_fact_items: return "\nНа этой странице данных нет."
    
    page_text_parts = []
    for fact_item in page_fact_items: 
        fact_id = fact_item['id']
        meta = fact_item.get('meta', {}) 
        
        fact_text_content = meta.get("text_original", f"N/A (text_original не найден для ID: {fact_id})")
        escaped_fact_text = escape_markdown(fact_text_content) 
        
        ts_added_str = meta.get("timestamp_added", "N/A")
        ts_last_accessed_str = meta.get("last_accessed_timestamp", "N/A")
        access_count = meta.get("access_count", 0)
        importance = meta.get("importance_score", 0.0)

        user_ids_json_str = meta.get("user_ids_json", "[]")
        user_ids_list = []
        try: user_ids_list = json.loads(user_ids_json_str)
        except json.JSONDecodeError: logger.warning(f"_format_facts_for_page: Некорректный JSON для user_ids в факте {fact_id}: {user_ids_json_str}")

        user_names_to_display = []
        if user_ids_list:
            for uid in user_ids_list:
                if uid in users_data:
                    user_names_to_display.append(users_data[uid].get('name', f'User_{uid}'))
                else:
                    user_names_to_display.append(f'{uid} (неизв.)')
        
        user_info_str = f" (Субъекты: {escape_markdown(', '.join(user_names_to_display))})" if user_names_to_display else ""
        
        entry = f"\n*ID Факта:* `{fact_id}`\n"
        entry += f"   *Текст:* _{escaped_fact_text}_{user_info_str}\n" 
        entry += f"   *Добавлен:* {escape_markdown(ts_added_str[:19])}\n" 
        entry += f"   *Доступ:* {escape_markdown(ts_last_accessed_str[:19])} (x{access_count}) *Важность:* {importance:.2f}\n"
        page_text_parts.append(entry)
        
    return "".join(page_text_parts)

def _calculate_cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    if vec1 is None or vec2 is None: 
        return 0.0
    if not isinstance(vec1, (list, np.ndarray)) or not isinstance(vec2, (list, np.ndarray)):
        logger.warning(f"Попытка рассчитать сходство для не-списков/массивов: {type(vec1)}, {type(vec2)}")
        return 0.0
    
    vec1_np = np.array(vec1, dtype=np.float32)
    vec2_np = np.array(vec2, dtype=np.float32)
    
    if vec1_np.size == 0 or vec2_np.size == 0: 
        return 0.0

    dot_product = np.dot(vec1_np, vec2_np)
    norm_vec1 = np.linalg.norm(vec1_np)
    norm_vec2 = np.linalg.norm(vec2_np)
    
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
        
    similarity = dot_product / (norm_vec1 * norm_vec2)
    return float(similarity)


# --- Команды ---
async def memory_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    memory_manager: MemoryManager = context.bot_data.get("memory_manager") 
    users_data: dict = context.bot_data.get("users_data_dict", {})
    
    short_term_memory_len = len(context.bot_data.get("short_term_memory").history) if context.bot_data.get("short_term_memory") else 0
    num_known_users = len(users_data)
    num_ltm_facts = memory_manager.count_ltm_facts() if memory_manager else "Ошибка"
    
    num_emotional_records = 0
    if memory_manager and memory_manager.emotional_memory_handler:
        num_emotional_records = len(memory_manager.emotional_memory_handler.emotional_memory)

    stats_message = "📊 *Отчет о состоянии системы памяти*\n\n"
    stats_message += f"   *Известные субъекты:* {num_known_users} ед.\n"
    stats_message += f"   *Факты в LTM:* {num_ltm_facts} записей\n"
    stats_message += f"   *Записей в STM (буфер):* {short_term_memory_len} сообщений\n"
    stats_message += f"   *Записи в Эмоц. Памяти:* {num_emotional_records} субъектов\n"
    
    await update.message.reply_text(stats_message, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Администратор {update.effective_user.full_name} запросил статистику памяти.")

async def list_facts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    memory_manager: MemoryManager = context.bot_data.get("memory_manager") 
    users_data: dict = context.bot_data.get("users_data_dict", {})
    if not memory_manager or not memory_manager.ltm_db or not memory_manager.ltm_db.collection:
        await update.message.reply_text("Долгосрочная память (LTM) не инициализирована.", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        all_facts_data = memory_manager.get_ltm_data(include=["metadatas"]) 
        
        if not all_facts_data or not all_facts_data.get("ids"):
            await update.message.reply_text("В долгосрочной памяти (LTM) отсутствуют данные.")
            return
            
        facts_for_sorting = []
        ids_list = all_facts_data.get("ids", []) 
        metadatas_list = all_facts_data.get("metadatas", [])

        for i in range(len(ids_list)):
            fact_id = ids_list[i]
            meta = metadatas_list[i] if i < len(metadatas_list) and metadatas_list[i] is not None else {}
            sort_key_timestamp = meta.get("last_accessed_timestamp", meta.get("timestamp_added", "1970-01-01T00:00:00Z"))
            facts_for_sorting.append({"id": fact_id, "sort_ts": sort_key_timestamp, "meta": meta})

        sorted_fact_items = sorted(facts_for_sorting, key=lambda x: x["sort_ts"], reverse=True)
        
        total_facts = len(sorted_fact_items)
        if total_facts == 0:
            await update.message.reply_text("В долгосрочной памяти (LTM) отсутствуют данные.")
            return

        total_pages = (total_facts + FACTS_PER_PAGE - 1) // FACTS_PER_PAGE
        current_page = 1

        context.user_data['sorted_ltm_fact_items'] = sorted_fact_items 
        context.user_data['ltm_facts_total_pages'] = total_pages
        
        page_content = await _format_facts_for_page(memory_manager, sorted_fact_items, current_page, users_data)
        
        header = f"📚 *Содержимое LTM (Стр. {current_page}/{total_pages}, Всего: {total_facts}, сорт. по доступу/дате):*"
        message_text = header + page_content
        reply_markup = _get_facts_pagination_keyboard(current_page, total_pages)
        
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"Админ {update.effective_user.full_name} запросил LTM (пагинация). Стр. {current_page}/{total_pages}")

    except Exception as e:
        logger.error(f"Ошибка в list_facts_command: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при получении списка фактов LTM.")

async def facts_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer() 
    if query.data == "facts_page_ignore": return

    try: requested_page = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        logger.error(f"Некорректный callback_data для пагинации фактов: {query.data}")
        await query.edit_message_text("Ошибка: неверный формат страницы.", parse_mode=constants.ParseMode.MARKDOWN); return

    user_id_str = str(query.from_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await query.edit_message_text("Эта функция доступна только администратору.", parse_mode=constants.ParseMode.MARKDOWN); return

    memory_manager: MemoryManager = context.bot_data.get("memory_manager")
    users_data: dict = context.bot_data.get("users_data_dict", {})
        
    sorted_fact_items = context.user_data.get('sorted_ltm_fact_items') 
    total_pages = context.user_data.get('ltm_facts_total_pages') 

    if sorted_fact_items is None or total_pages is None:
        await query.edit_message_text("Ошибка: Данные для пагинации устарели. Выполните /list_facts снова.", parse_mode=constants.ParseMode.MARKDOWN); return

    if not (1 <= requested_page <= total_pages):
        logger.warning(f"Запрошена некорректная страница LTM {requested_page} из {total_pages}.")
        await query.answer("Запрошена некорректная страница."); return
        
    current_page = requested_page
    try:
        page_content = await _format_facts_for_page(memory_manager, sorted_fact_items, current_page, users_data)
        total_facts = len(sorted_fact_items)
        header = f"📚 *Содержимое LTM (Стр. {current_page}/{total_pages}, Всего: {total_facts}, сорт. по доступу/дате):*"
        message_text = header + page_content
        reply_markup = _get_facts_pagination_keyboard(current_page, total_pages)
        
        if query.message and (query.message.text != message_text or query.message.reply_markup != reply_markup) :
            await query.edit_message_text(text=message_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
        else: logger.info(f"Текст и клавиатура для страницы {current_page} LTM не изменились.")
        logger.info(f"Админ {query.from_user.full_name} переключил страницу LTM на {current_page}/{total_pages}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении страницы списка LTM: {e}", exc_info=True)
        try: await query.edit_message_text("Произошла ошибка при обновлении страницы LTM.", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception: pass

async def find_facts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id: await update.message.reply_text("Эта команда доступна только администратору бота."); return
    if not context.args: await update.message.reply_text("Использование: `/find_facts <текстовый запрос>`", parse_mode=constants.ParseMode.MARKDOWN); return
    
    query_text = " ".join(context.args)
    memory_manager: MemoryManager = context.bot_data.get("memory_manager")
    if not memory_manager or not memory_manager.yandex_embedder or not memory_manager.ltm_db:
        await update.message.reply_text("Система памяти или эмбеддер не готовы для поиска.", parse_mode=constants.ParseMode.MARKDOWN); return
    
    max_relevant_distance = context.bot_data.get("LTM_MAX_RELEVANT_DISTANCE_CONFIG", 1.0)

    N_results = 5 
    found_fact_texts = await memory_manager.get_relevant_facts_from_ltm(
        query_text=query_text, 
        N=N_results,
        max_distance=max_relevant_distance
    )

    if not found_fact_texts:
        await update.message.reply_text(f"Семантический поиск не дал результатов по запросу: '{escape_markdown(query_text)}' (дистанция < {max_relevant_distance}).", parse_mode=constants.ParseMode.MARKDOWN); return

    response_text = f"🔎 *Результаты семантического поиска по запросу \"{escape_markdown(query_text)}\":*\n\n"
    for i, fact_text in enumerate(found_fact_texts):
        response_text += f"`{i+1}.` _{escape_markdown(fact_text)}_\n\n" 
    
    if len(response_text) > 4000: 
        await update.message.reply_text("Найдено много, показываю первые:\n" + response_text[:3900] + "\n...", parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(response_text, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Админ {update.effective_user.full_name} искал факты: '{query_text}'. Найдено: {len(found_fact_texts)}")

async def delete_fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота."); return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Использование: `/delete_fact <ID_факта>`", parse_mode=constants.ParseMode.MARKDOWN); return

    fact_id_to_delete = context.args[0]
    memory_manager: MemoryManager = context.bot_data.get("memory_manager") 

    if not memory_manager or not memory_manager.ltm_db:
        await update.message.reply_text("Долгосрочная память (LTM) не инициализирована.", parse_mode=constants.ParseMode.MARKDOWN); return
    
    try:
        # <--- ВОССТАНОВЛЕНО: Получение текста факта перед удалением ---
        fact_data = memory_manager.get_ltm_data(ids=[fact_id_to_delete], include=["metadatas"])
        fact_text_to_delete = "N/A"
        if fact_data and fact_data.get("ids") and fact_data.get("metadatas") and fact_data["metadatas"][0]:
            fact_text_to_delete = fact_data["metadatas"][0].get("text_original", "N/A")
        elif not (fact_data and fact_data.get("ids")):
            await update.message.reply_text(f"Факт с ID `{escape_markdown(fact_id_to_delete)}` не найден в LTM.", parse_mode=constants.ParseMode.MARKDOWN); return

        success = memory_manager.delete_ltm_facts_by_ids(ids=[fact_id_to_delete])
        
        if success:
            if 'sorted_ltm_fact_items' in context.user_data: del context.user_data['sorted_ltm_fact_items']
            if 'ltm_facts_total_pages' in context.user_data: del context.user_data['ltm_facts_total_pages']
            await update.message.reply_text(f"✅ *Факт удален.*\nID: `{escape_markdown(fact_id_to_delete)}`\nТекст: _{escape_markdown(fact_text_to_delete)}_\n\nКэш пагинации сброшен. Для просмотра используйте `/list_facts`.", parse_mode=constants.ParseMode.MARKDOWN)
            logger.info(f"Админ {update.effective_user.full_name} удалил факт ID: {fact_id_to_delete} из LTM.")
        else:
            await update.message.reply_text(f"❌ *Ошибка удаления.* Не удалось удалить факт ID `{escape_markdown(fact_id_to_delete)}`. Возможно, он уже был удален.", parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при удалении факта ID {fact_id_to_delete} из LTM: {e}", exc_info=True)
        await update.message.reply_text(f"Ошибка при удалении факта из LTM: {e}")

async def clear_ltm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота."); return

    keyboard = [[
        InlineKeyboardButton("🔴 ПОДТВЕРДИТЬ ОЧИСТКУ LTM", callback_data="confirm_clear_ltm_yes"),
        InlineKeyboardButton("🟢 Отмена", callback_data="confirm_clear_ltm_no")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "‼️ *КРИТИЧЕСКОЕ ДЕЙСТВИЕ* ‼️\nВы собираетесь инициировать протокол полной очистки Долгосрочной Памяти (LTM).\n\n*Это действие необратимо и приведет к потере всех сохраненных фактов.* Подтвердите операцию.",
        reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Админ {update.effective_user.full_name} инициировал очистку ВСЕХ фактов LTM.")

async def confirm_clear_ltm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    user_id_str = str(query.from_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await query.edit_message_text("Операция доступна только администратору.", parse_mode=constants.ParseMode.MARKDOWN); return

    choice = query.data
    memory_manager: MemoryManager = context.bot_data.get("memory_manager")

    if choice == "confirm_clear_ltm_yes":
        if not memory_manager or not memory_manager.ltm_db: 
            await query.edit_message_text("Ошибка: LTM компонент не инициализирован.", parse_mode=constants.ParseMode.MARKDOWN); return
        try:
            logger.warning(f"Админ {query.from_user.full_name} подтвердил очистку ВСЕХ фактов LTM.")
            success = memory_manager.clear_all_ltm_facts()
            if success:
                if 'sorted_ltm_fact_items' in context.user_data: del context.user_data['sorted_ltm_fact_items']
                if 'ltm_facts_total_pages' in context.user_data: del context.user_data['ltm_facts_total_pages']
                await query.edit_message_text("✅ *Протокол выполнен.* Долгосрочная Память (LTM) полностью очищена.", parse_mode=constants.ParseMode.MARKDOWN)
                logger.warning(f"LTM факты очищены админом {query.from_user.full_name}.")
            else:
                await query.edit_message_text("❌ Не удалось полностью очистить LTM факты. Проверьте логи.", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Ошибка при полной очистке LTM фактов: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка очистки LTM фактов: {escape_markdown(str(e))}", parse_mode=constants.ParseMode.MARKDOWN)
    elif choice == "confirm_clear_ltm_no":
        await query.edit_message_text("👌 *Операция отменена.* Очистка LTM не производилась.", parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"Админ {query.from_user.full_name} отменил очистку LTM фактов.")

async def clear_emotional_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    if not context.args:
        await update.message.reply_text(
            "Укажите ID, имя или ник субъекта, чью эмоциональную память (EM) нужно очистить.\n"
            "Пример: `/clear_emo_user 123456789`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    query_arg = " ".join(context.args).strip()
    users_data: dict = context.bot_data.get("users_data_dict", {})
    memory_manager: MemoryManager = context.bot_data.get("memory_manager")

    if not memory_manager or not memory_manager.emotional_memory_handler:
        await update.message.reply_text("Обработчик эмоциональной памяти не инициализирован.")
        return

    found_user_id_to_clear = None
    found_user_name_to_clear = "Неизвестный субъект"

    for u_id, info in users_data.items():
        name_lower = info.get('name', '').lower()
        nicknames = info.get('nicknames', [])
        if isinstance(nicknames, str): nicknames = [nicknames]
        nicknames_lower = [nick.lower() for nick in nicknames]

        if query_arg == u_id or query_arg.lower() == name_lower or query_arg.lower() in nicknames_lower:
            found_user_id_to_clear = u_id
            found_user_name_to_clear = info.get('name', f"User_{u_id}")
            break
    
    # <--- ВОССТАНОВЛЕНО: Поиск по ID в эмоциональной памяти, если не найден в users.json ---
    if not found_user_id_to_clear and query_arg.isdigit():
        emo_data_exists = memory_manager.get_emotional_notes(query_arg)
        if emo_data_exists:
             found_user_id_to_clear = query_arg
             found_user_name_to_clear = emo_data_exists.get("name", f"User_{query_arg}")
        
    if not found_user_id_to_clear:
        await update.message.reply_text(f"Субъект по запросу '{escape_markdown(query_arg)}' не найден.")
        return

    keyboard = [[
        InlineKeyboardButton(f"🗑️ Да, очистить для {escape_markdown(found_user_name_to_clear)}", callback_data=f"confirm_clear_emo_user_yes_{found_user_id_to_clear}"),
        InlineKeyboardButton("🟢 Нет, отмена", callback_data=f"confirm_clear_emo_user_no_{found_user_id_to_clear}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Подтвердите очистку всей эмоциональной памяти для субъекта *{escape_markdown(found_user_name_to_clear)}* (ID: `{found_user_id_to_clear}`).\n"
        f"Это действие необратимо.",
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    logger.info(f"Админ {update.effective_user.full_name} инициировал очистку EM для ID: {found_user_id_to_clear}.")

async def confirm_clear_emotional_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    requesting_admin_id_str = str(query.from_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or requesting_admin_id_str != admin_user_id:
        await query.edit_message_text("Операция доступна только администратору.")
        return

    callback_data_parts = query.data.split("_") 
    action = callback_data_parts[-2] 
    user_id_to_clear = callback_data_parts[-1]

    memory_manager: MemoryManager = context.bot_data.get("memory_manager")
    if not memory_manager or not memory_manager.emotional_memory_handler:
        await query.edit_message_text("Ошибка: Обработчик эмоциональной памяти не инициализирован.")
        return
    
    user_name_display = f"User_{user_id_to_clear}"
    user_data_entry = context.bot_data.get("users_data_dict", {}).get(user_id_to_clear)
    if user_data_entry and user_data_entry.get("name"):
        user_name_display = user_data_entry.get("name")
    else:
        emo_note = memory_manager.get_emotional_notes(user_id_to_clear)
        if emo_note and emo_note.get("name"):
            user_name_display = emo_note.get("name")

    if action == "yes":
        success = memory_manager.clear_user_emotional_data(user_id_to_clear)
        if success:
            await query.edit_message_text(f"✅ *Операция выполнена.* Эмоциональная память для *{escape_markdown(user_name_display)}* очищена.", parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(f"❌ *Ошибка.* Не удалось очистить EM для *{escape_markdown(user_name_display)}*.", parse_mode=constants.ParseMode.MARKDOWN)
    elif action == "no":
        await query.edit_message_text(f"👌 *Операция отменена.* EM для *{escape_markdown(user_name_display)}* не затронута.", parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await query.edit_message_text("Неизвестный выбор.")

async def clear_emotional_all_danger_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    keyboard = [[
        InlineKeyboardButton("🔴 ПОДТВЕРДИТЬ ОЧИСТКУ ВСЕЙ EM", callback_data="confirm_clear_emo_all_yes"),
        InlineKeyboardButton("🟢 Отмена", callback_data="confirm_clear_emo_all_no")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "‼️ *КРИТИЧЕСКОЕ ДЕЙСТВИЕ* ‼️\nВы уверены, что хотите *ПОЛНОСТЬЮ ОЧИСТИТЬ ВСЮ ЭМОЦИОНАЛЬНУЮ ПАМЯТЬ* (для всех субъектов)?\n"
        "*Это действие НЕОБРАТИМО!*",
        reply_markup=reply_markup,
        parse_mode=constants.ParseMode.MARKDOWN
    )
    logger.info(f"Админ {update.effective_user.full_name} инициировал очистку ВСЕЙ EM.")

async def confirm_clear_emotional_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    requesting_admin_id_str = str(query.from_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or requesting_admin_id_str != admin_user_id:
        await query.edit_message_text("Операция доступна только администратору.")
        return

    choice = query.data 
    memory_manager: MemoryManager = context.bot_data.get("memory_manager")

    if not memory_manager or not memory_manager.emotional_memory_handler:
        await query.edit_message_text("Ошибка: Обработчик эмоциональной памяти не инициализирован.")
        return

    if choice == "confirm_clear_emo_all_yes":
        try:
            logger.warning(f"Админ {query.from_user.full_name} подтвердил очистку ВСЕЙ EM.")
            success = memory_manager.clear_all_emotional_data()
            if success:
                await query.edit_message_text("✅ *Протокол выполнен.* Вся эмоциональная память (EM) полностью очищена.", parse_mode=constants.ParseMode.MARKDOWN)
            else:
                await query.edit_message_text("❌ Не удалось полностью очистить всю EM. Проверьте логи.", parse_mode=constants.ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Ошибка при полной очистке всей EM: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка очистки всей EM: {escape_markdown(str(e))}", parse_mode=constants.ParseMode.MARKDOWN)
    elif choice == "confirm_clear_emo_all_no":
        await query.edit_message_text("👌 *Операция отменена.* Очистка всей EM не производилась.", parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await query.edit_message_text("Неизвестный выбор.")

async def maintain_ltm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    memory_manager: MemoryManager = context.bot_data.get("memory_manager")
    if not memory_manager or not memory_manager.ltm_db or not memory_manager.yandex_embedder:
        await update.message.reply_text("LTM или эмбеддер не инициализированы. Обслуживание невозможно.")
        return

    await update.message.reply_text("⏳ *Запуск протокола обслуживания LTM...*\nАнализ и оптимизация базы данных. Отчет будет предоставлен по завершении.", 
                                    parse_mode=constants.ParseMode.MARKDOWN)
    
    try:
        args = context.args
        maintenance_config = {
            "similarity_threshold": float(args[0]) if args and len(args) > 0 else 0.95,
            "max_days_unaccessed": int(args[1]) if args and len(args) > 1 else 90,
            "min_access_for_retention": int(args[2]) if args and len(args) > 2 else 1,
            "importance_decay_factor": context.bot_data.get("LTM_IMPORTANCE_DECAY_FACTOR_CONFIG", 0.02),
            "min_importance_for_retention": context.bot_data.get("LTM_MIN_IMPORTANCE_FOR_RETENTION_CONFIG", 0.5),
            "days_for_decay_check": context.bot_data.get("LTM_DAYS_FOR_IMPORTANCE_DECAY_CONFIG", 14)
        }
        
        logger.info(f"Админ {update.effective_user.full_name} запустил обслуживание LTM с параметрами: {maintenance_config}")
        
        results = await memory_manager.perform_ltm_maintenance(maintenance_config)

        if results.get("error"):
            await update.message.reply_text(f"❌ Ошибка во время обслуживания LTM: {results['error']}")
            return
            
        if results.get("total_deleted", 0) > 0 or results.get("updated_importance", 0) > 0:
            if 'sorted_ltm_fact_items' in context.user_data: del context.user_data['sorted_ltm_fact_items']
            if 'ltm_facts_total_pages' in context.user_data: del context.user_data['ltm_facts_total_pages']

        deleted_duplicates = results.get("deleted_duplicates", 0)
        deleted_obsolete = results.get("deleted_obsolete", 0)
        total_deleted = results.get("total_deleted", 0)
        updated_importance = results.get("updated_importance", 0)

        if total_deleted == 0 and updated_importance == 0:
            await update.message.reply_text("✅ *Обслуживание LTM завершено.* Оптимизация не потребовалась, данные в актуальном состоянии.", parse_mode=constants.ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                f"✅ *Обслуживание LTM завершено.*\n\n"
                f"   *Оптимизация:*\n"
                f"   - Устранено дубликатов/схожих: {deleted_duplicates}\n"
                f"   - Удалено устаревших/неважных: {deleted_obsolete}\n"
                f"   - *Всего записей удалено:* {total_deleted}\n"
                f"   - *Пересчитана важность (decay):* {updated_importance} фактов.",
                parse_mode=constants.ParseMode.MARKDOWN
            )

    except Exception as e:
        logger.error(f"Критическая ошибка в хендлере maintain_ltm_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Критическая ошибка в хендлере /maintain_ltm: {escape_markdown(str(e))}", parse_mode=constants.ParseMode.MARKDOWN)