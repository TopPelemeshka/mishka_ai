# mishka_ai/handlers/common.py
"""
Модуль с общими вспомогательными функциями для обработчиков.
"""
import logging
from telegram import User
from telegram.ext import ContextTypes

# Используется для аннотации типов, чтобы избежать циклических импортов
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mishka_ai.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

def _add_new_user_if_needed(user: User, current_users_data: dict, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Проверяет, существует ли пользователь в базе данных, и добавляет/обновляет его при необходимости.

    - Если пользователь новый, он добавляется в `current_users_data`.
    - Если пользователь уже существует, функция проверяет, не изменились ли его
      `full_name` или `username` в Telegram, и обновляет их.
    - После любого изменения данные сохраняются в `users.json` через `MemoryManager`.

    Args:
        user: Объект `telegram.User` нового или существующего пользователя.
        current_users_data: Словарь с данными всех известных пользователей.
        context: Контекст бота для доступа к `MemoryManager`.

    Returns:
        True, если пользователь был добавлен или его данные были обновлены, иначе False.
    """
    user_id_str = str(user.id)
    user_added_or_updated = False
    telegram_full_name = user.full_name
    telegram_username = user.username 

    # Если пользователя нет в базе, добавляем его
    if user_id_str not in current_users_data:
        # Используем username как первый никнейм, если он есть
        nicknames_default = [telegram_username] if telegram_username else []
        current_users_data[user_id_str] = {
            "name": telegram_full_name,
            "nicknames": nicknames_default,
            "known_info": "недавно присоединился к чату"
        }
        logger.info(f"Новый пользователь {telegram_full_name} (ID: {user_id_str}) добавлен в базу данных.")
        user_added_or_updated = True
    else:
        # Если пользователь уже есть, проверяем актуальность данных
        existing_user_data = current_users_data[user_id_str]
        updated_in_telegram = False
        
        # Обновляем имя, если оно изменилось
        if existing_user_data.get("name") != telegram_full_name:
            existing_user_data["name"] = telegram_full_name
            updated_in_telegram = True
        
        current_nicknames = existing_user_data.get("nicknames", [])
        # Для обратной совместимости, если в JSON никнейм - строка
        if isinstance(current_nicknames, str): 
            current_nicknames = [current_nicknames] if current_nicknames else []
        
        # Добавляем username в никнеймы, если его там еще нет
        if telegram_username and telegram_username not in current_nicknames:
            current_nicknames.append(telegram_username)
            # Используем set для удаления возможных дубликатов
            existing_user_data["nicknames"] = list(set(current_nicknames)) 
            updated_in_telegram = True
        
        if updated_in_telegram:
            user_added_or_updated = True
            logger.info(f"Данные пользователя {telegram_full_name} (ID: {user_id_str}) обновлены на основе данных из Telegram.")
    
    # Если были изменения, сохраняем обновленный словарь пользователей
    if user_added_or_updated:
        # Получаем MemoryManager из контекста бота
        memory_manager: 'MemoryManager' = context.bot_data.get("memory_manager")
        if memory_manager:
            try:
                # MemoryManager делегирует сохранение компоненту UserDataManager
                memory_manager.save_users_data(current_users_data) 
                logger.info(f"Данные пользователей сохранены после обновления информации о {user_id_str}.")
            except Exception as e:
                logger.error(f"Ошибка при сохранении данных пользователей для {user_id_str} через MemoryManager: {e}", exc_info=True)
        else:
            logger.error("MemoryManager не найден в context.bot_data. Не удалось сохранить users_data.")
            
    return user_added_or_updated