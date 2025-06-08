# mishka_ai/handlers/admin_commands/user_data_commands.py
"""
Модуль с обработчиками административных команд для управления данными пользователей.

Содержит команды для просмотра списка пользователей и информации о конкретном пользователе.
"""
import logging
import asyncio
from telegram import Update, constants
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /list_users.

    Показывает администратору список всех известных боту пользователей
    с их ID, именами, никнеймами и известной информацией.
    Если список слишком длинный, он разбивается на несколько сообщений.
    """
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")

    # Проверка прав администратора
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    users_data: dict = context.bot_data.get("users_data_dict", {})
    if not users_data:
        await update.message.reply_text("Я пока не знаю ни одного пользователя.")
        return

    user_entries_texts = []
    for u_id, info in users_data.items():
        # Экранируем спецсимволы для Markdown
        name = escape_markdown(info.get('name', 'Имя не указано'))
        nicknames_list = info.get('nicknames', [])
        if isinstance(nicknames_list, str): nicknames_list = [nicknames_list] # Для обратной совместимости
        escaped_nicknames = [escape_markdown(n) for n in nicknames_list]
        known_info = escape_markdown(info.get('known_info', 'Нет информации'))

        nick_str_display = f" (Прозвища: {', '.join(escaped_nicknames)})" if escaped_nicknames else ""
        entry = f"👤 *{name}*{nick_str_display}\n   ID: `{u_id}`\n   О нем известно: _{known_info}_"
        user_entries_texts.append(entry)
    
    header = "👥 *Список известных мне пользователей:*\n\n"
    messages_to_send = []
    current_message_part = header

    # Логика разбивки на несколько сообщений, если список слишком длинный
    for entry_text in user_entries_texts:
        if len(current_message_part) + len(entry_text) + 2 > 4096: # Лимит Telegram на длину сообщения
            messages_to_send.append(current_message_part)
            current_message_part = "👥 *Список пользователей (продолжение):*\n\n" + entry_text + "\n\n"
        else:
            current_message_part += entry_text + "\n\n"
            
    if current_message_part.strip() != header.strip():
        messages_to_send.append(current_message_part)
    elif not user_entries_texts: 
         messages_to_send.append(header + "В базе данных нет пользователей для отображения.")

    # Отправка сообщений с небольшой задержкой
    for i, part_msg in enumerate(messages_to_send):
        try:
            await update.message.reply_text(part_msg, parse_mode=constants.ParseMode.MARKDOWN)
            if i < len(messages_to_send) - 1: await asyncio.sleep(0.3) 
        except Exception as e:
            logger.error(f"Ошибка при отправке части списка пользователей (Markdown): {e}")
            await update.message.reply_text(f"Произошла ошибка при отображении части списка: {e}")
            break 
    logger.info(f"Администратор {update.effective_user.full_name} запросил список пользователей.")


async def show_user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /show_user_info.

    Показывает администратору подробную информацию о конкретном пользователе,
    найденном по ID, имени или никнейму.
    """
    requesting_user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")

    # Проверка прав администратора
    if not admin_user_id or requesting_user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return
        
    if not context.args:
        await update.message.reply_text("Использование: `/show_user_info <ID | имя | ник>`", parse_mode=constants.ParseMode.MARKDOWN)
        return
    
    query = " ".join(context.args).strip().lower()
    users_data: dict = context.bot_data.get("users_data_dict", {})
    found_user_id = None
    found_user_info = None

    # Поиск пользователя в базе данных
    for u_id, info in users_data.items():
        name_lower = info.get('name', '').lower()
        nicknames = info.get('nicknames', [])
        if isinstance(nicknames, str): nicknames = [nicknames]
        nicknames_lower = [nick.lower() for nick in nicknames]

        if query == u_id.lower() or query == name_lower or query in nicknames_lower:
            found_user_id = u_id
            found_user_info = info
            break
            
    if not found_user_info:
        await update.message.reply_text(f"Пользователь по запросу '{escape_markdown(query)}' не найден.", parse_mode=constants.ParseMode.MARKDOWN)
        return

    # Форматирование и отправка информации о найденном пользователе
    name = escape_markdown(found_user_info.get('name', 'Имя не указано'))
    nicknames_list = found_user_info.get('nicknames', [])
    if isinstance(nicknames_list, str): nicknames_list = [nicknames_list]
    escaped_nicknames = [escape_markdown(n) for n in nicknames_list]
    known_info = escape_markdown(found_user_info.get('known_info', 'Нет информации'))
    
    nick_str_display = f"Прозвища: {', '.join(escaped_nicknames)}" if escaped_nicknames else ""

    response_text = f"ℹ️ *Информация о пользователе:*\n"
    response_text += f"   Имя: *{name}*\n"
    response_text += f"   ID: `{found_user_id}`\n"
    if nick_str_display: 
        response_text += f"   {nick_str_display}\n"
    response_text += f"   Известно: _{known_info}_" 
    
    await update.message.reply_text(response_text, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info(f"Администратор {update.effective_user.full_name} запросил информацию о пользователе: {query} (Найден: {name if found_user_info else 'Нет'}).")