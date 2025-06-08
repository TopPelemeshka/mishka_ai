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
    
    await update.message.reply_html(
        rf"Привет, {user.mention_html()}! Я Мишка, твой новый друг-медведь в этой группе. Готов к общению!",
    )
    logger.info(f"Пользователь {user.full_name} (ID: {user.id}) запустил команду /start.")
    
    # Добавление пользователя, если его нет
    if target_chat_id is None or update.effective_chat.id == target_chat_id: # Добавляем только в целевом чате или если нет ограничений
        if _add_new_user_if_needed(user, current_users_data, context): 
            logger.info(f"Данные пользователя {user.full_name} (ID: {user.id}) сохранены после /start.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет справочное сообщение."""
    user_id_str = str(update.effective_user.id) 
    admin_user_id = context.bot_data.get("admin_user_id")
    is_admin = admin_user_id and user_id_str == admin_user_id 
    
    target_chat_id = context.bot_data.get("target_chat_id")
    is_bot_active = context.bot_data.get("is_bot_active", True)

    help_text = "🐻 *Привет, я Мишка!* Вот что я умею:\n\n"
    
    if target_chat_id and update.effective_chat.id != target_chat_id and not is_admin:
        help_text += f"Я работаю только в специально настроенном чате. Этот чат (`{update.effective_chat.id}`) не является моим основным рабочим местом.\n\n"
        help_text += "Для получения полной справки, пожалуйста, используйте команду /help в целевом чате."
        await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)
        return
    elif target_chat_id:
         help_text += f"ℹ️ Я настроен для работы преимущественно в чате с ID: `{target_chat_id}`.\n"


    help_text += "Чтобы пообщаться со мной, просто напиши сообщение, начиная с моего имени (Мишка, Миш, Мишаня и т.д.) или ответь на одно из моих сообщений.\n\n" 
    help_text += "Я стараюсь запоминать интересные факты из наших разговоров и использовать их, чтобы быть лучшим собеседником.\n\n"
    help_text += "/chatid - Показать ID текущего чата.\n" 
    
    if is_admin:
        bot_status_emoji = "🟢" if is_bot_active else "🔴"
        bot_status_text = "Активен" if is_bot_active else "Приостановлен (на паузе)"
        help_text += f"\n👑 *Команды для Администратора:*\n"
        help_text += f"   Текущий статус бота: {bot_status_emoji} *{bot_status_text}*\n"
        help_text += "   /toggle\\_bot\\_active - Переключить активность бота (пауза/возобновление).\n"
        help_text += "*Управление Данными Пользователей:*\n"
        help_text += "  /list\\_users - Список известных пользователей.\n"
        help_text += "  /show\\_user\\_info `[ID | имя | ник]` - Инфо о пользователе.\n"
        help_text += "*Управление Долгосрочной Памятью (Факты LTM):*\n"
        help_text += "  /memory\\_stats - Статистика памяти (включая LTM и Эмоц. память).\n"
        help_text += "  /list\\_facts - Список фактов из LTM (ID факта виден здесь).\n"
        help_text += "  /find\\_facts `[ключ. слова]` - Поиск фактов в LTM.\n"
        help_text += "  /delete\\_fact `[ID факта]` - Удалить факт из LTM.\n"
        help_text += "  /maintain\\_ltm `[sim_thresh] [days_old] [min_acc]` - Обслуживание LTM (удаление дублей/старых). Аргументы опциональны.\n"
        help_text += "     `sim_thresh`: порог схожести (0.0-1.0, умолч. 0.9)\n"
        help_text += "     `days_old`: макс. дней без доступа (умолч. 90)\n"
        help_text += "     `min_acc`: мин. обращений для сохр. (умолч. 1)\n"
        help_text += "  /clear\\_ltm\\_admin\\_danger\\_zone - *ОПАСНО!* Очистить ВСЕ факты LTM.\n"
        help_text += "*Управление Эмоциональной Памятью:*\n"
        help_text += "  /clear\\_emo\\_user `[ID | имя | ник]` - Очистить эмоц. память для пользователя.\n"
        help_text += "  /clear\\_emo\\_all\\_danger - *ОПАСНО!* Очистить ВСЮ эмоц. память.\n"
        help_text += "   _(Для команд с ID/именем/ником пользователя, указывайте их как аргумент команды.)_\n"

    help_text += "\nЕсли что-то пойдет не так, или у тебя есть идеи, как меня улучшить, сообщи моему создателю!"

    try:
        await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Ошибка при отправке /help сообщения (Markdown): {e}", exc_info=True)
        simplified_help_text = ("Привет, я Мишка! Обращайся ко мне по имени. Команды: /chatid.\n"
                                "Админ-команды: /toggle_bot_active, /memory_stats, /list_users, /show_user_info, "
                                "/list_facts, /find_facts, /delete_fact, /maintain_ltm, /clear_ltm_admin_danger_zone, "
                                "/clear_emo_user, /clear_emo_all_danger.")
        await update.message.reply_text(simplified_help_text)
    logger.info(f"Пользователь {update.effective_user.full_name} запросил /help.")


async def chat_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет ID текущего чата."""
    chat_id = update.effective_chat.id
    message_text = f"ID этого чата: `{chat_id}`"
    user_full_name = update.effective_user.full_name
    try:
        await update.message.reply_text(message_text, parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"Пользователь {user_full_name} (ID: {update.effective_user.id}) запросил ID чата: {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке ID чата для {user_full_name}: {e}", exc_info=True)
        await update.message.reply_text(f"ID этого чата: {chat_id}") 