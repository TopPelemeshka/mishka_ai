# mishka_ai/handlers/admin_commands/general_admin_commands.py
"""
Модуль с обработчиками общих административных команд.

Эти команды управляют глобальным состоянием и поведением бота.
"""
import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)

async def toggle_bot_active_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /toggle_bot_active.

    Переключает состояние активности бота (вкл/выкл). В выключенном состоянии
    бот не реагирует на обычные сообщения, но продолжает принимать команды
    от администратора.

    Доступно только администратору бота.
    """
    user_id_str = str(update.effective_user.id)
    admin_user_id = context.bot_data.get("admin_user_id")

    # Проверка, является ли отправитель команды администратором
    if not admin_user_id or user_id_str != admin_user_id:
        await update.message.reply_text("Эта команда доступна только администратору бота.")
        return

    # Получаем текущий статус из bot_data и инвертируем его
    current_status = context.bot_data.get("is_bot_active", True)
    new_status = not current_status
    context.bot_data["is_bot_active"] = new_status

    # Обновленный текст
    status_text = "🟢 *АКТИВЕН*" if new_status else "🔴 *ПРИОСТАНОВЛЕН (PAUSED)*"
    await update.message.reply_text(
        f"Статус системы изменен. Текущий статус: {status_text}\n"
        f"В режиме паузы основной цикл обработки сообщений деактивирован. Доступны только протоколы администратора.",
        parse_mode=constants.ParseMode.MARKDOWN
    )
    logger.info(f"Администратор {update.effective_user.full_name} изменил статус системы на: {'активен' if new_status else 'приостановлен'}")