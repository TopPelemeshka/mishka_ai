# mishka_ai/handlers/user_commands/general_commands.py
import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from mishka_ai.handlers.common import _add_new_user_if_needed

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение при команде /start."""
    user = update.effective_user
    current_users_data: dict = context.bot_data.get("users_data_dict", {})
    
    # Обновленный, более "технический" старт
    await update.message.reply_html(
        rf"Приветствую, {user.mention_html()}. Я — ИИ-ассистент «Мишка». Мои нейронные цепи активированы. Готов к взаимодействию и анализу данных в этом чате. Для вызова справки отправьте команду /help_ai",
    )
    logger.info(f"Пользователь {user.full_name} (ID: {user.id}) выполнил протокол /start.")
    
    target_chat_id = context.bot_data.get("target_chat_id")
    if target_chat_id is None or update.effective_chat.id == target_chat_id:
        if _add_new_user_if_needed(user, current_users_data, context):
            logger.info(f"Данные пользователя {user.full_name} (ID: {user.id}) интегрированы в базу данных после /start.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение."""
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")
    is_admin = admin_user_id and user_id_str == admin_user_id
    
    target_chat_id = context.bot_data.get("target_chat_id")
    is_bot_active = context.bot_data.get("is_bot_active", True)

    # --- НОВЫЙ СЕРЬЕЗНЫЙ ТЕКСТ ДЛЯ HELP ---
    help_text = "🤖 *ИИ-ассистент «Мишка»*\n"
    help_text += "_Система с гибридной архитектурой памяти и контекстуальным анализом на базе LLM._\n\n"
    
    help_text += "*Архитектура памяти:*\n"
    help_text += "Я использую трехуровневую систему памяти для поддержания глубокого и релевантного диалога:\n"
    help_text += "1.  *Краткосрочная память (STM):* Оперативный буфер последних сообщений для мгновенного контекста.\n"
    help_text += "2.  *Долгосрочная память (LTM):* Векторная база данных (ChromaDB) для хранения и семантического поиска ключевых фактов из диалогов.\n"
    help_text += "3.  *Эмоциональная память (EM):* Система для анализа и консолидации эмоционального фона общения с каждым участником.\n\n"

    help_text += "*Основное взаимодействие:*\n"
    help_text += "Для активации моего ответа, начните сообщение с моего имени ('миш', 'миша', 'мишу', 'мишка', 'мишку', 'мишке', 'мишаня', 'мишань', 'мишуня', 'мишунь', 'мишенька', 'мишутка', 'миха', 'михаил', 'потапыч', 'медведь', 'медведюшка', 'топтыгин', 'косолапый') или ответьте на мое сообщение. Я анализирую контекст, релевантные факты из LTM и эмоциональный фон для генерации ответа.\n\n"
    
    help_text += "*Общие команды:*\n"
    help_text += "`/chatid` - Получить идентификатор текущего чата.\n"
    
    if is_admin:
        bot_status_emoji = "🟢" if is_bot_active else "🔴"
        bot_status_text = "АКТИВЕН" if is_bot_active else "ПРИОСТАНОВЛЕН (PAUSED)"
        help_text += f"\n👑 *Протоколы Администратора:*\n"
        help_text += f"   *Текущий статус системы:* {bot_status_emoji} *{bot_status_text}*\n"
        help_text += "   `/toggle_bot_active` - Переключить основной цикл обработки сообщений.\n\n"
        
        help_text += "*Управление базой данных пользователей:*\n"
        help_text += "  `/list_users` - Вывести список всех известных субъектов.\n"
        help_text += "  `/show_user_info` `[ID|имя|ник]` - Показать данные по конкретному субъекту.\n\n"
        
        help_text += "*Управление Долгосрочной Памятью (LTM):*\n"
        help_text += "  `/memory_stats` - Статистика всех уровней памяти.\n"
        help_text += "  `/list_facts` - Постраничный вывод всех фактов из LTM.\n"
        help_text += "  `/find_facts` `[запрос]` - Семантический поиск фактов в LTM.\n"
        help_text += "  `/delete_fact` `[ID]` - Удалить факт по его уникальному ID.\n"
        help_text += "  `/maintain_ltm` - Запустить ручное обслуживание LTM (дедупликация и удаление устаревших данных).\n"
        help_text += "  `/clear_ltm_admin_danger_zone` - *[DANGER]* Полная очистка LTM.\n\n"
        
        help_text += "*Управление Эмоциональной Памятью (EM):*\n"
        help_text += "  `/clear_emo_user` `[ID|имя|ник]` - Очистить EM для субъекта.\n"
        help_text += "  `/clear_emo_all_danger` - *[DANGER]* Полная очистка всей EM.\n"

    help_text += "\n_v1.0. Mishka AI Core_"

    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Пользователь {update.effective_user.full_name} запросил системную документацию (/help).")


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет ID текущего чата."""
    chat_id = update.effective_chat.id
    message_text = f"Идентификатор данного чата (Chat ID): `{chat_id}`"
    user_full_name = update.effective_user.full_name
    await update.message.reply_text(message_text, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Пользователь {user_full_name} (ID: {update.effective_user.id}) запросил Chat ID: {chat_id}")