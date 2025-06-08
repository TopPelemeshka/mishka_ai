# mishka_ai/short_term_memory.py
from collections import deque
import logging

logger = logging.getLogger(__name__)

class ShortTermMemory:
    def __init__(self, max_length: int = 10):
        self.history = deque(maxlen=max_length)
        self.max_length = max_length
        logger.info(f"Краткосрочная память инициализирована с размером {max_length}")

    def add_message(self, role: str, text: str, user_name: str = None, user_id: str = None, is_bot: bool = False):
        """
        Добавляет сообщение в историю.
        Args:
            role: Роль ("user" или "model").
            text: Текст сообщения.
            user_name: Имя пользователя (для логов или форматирования).
            user_id: ID пользователя (для сообщений 'user').
            is_bot: Флаг, указывающий, что сообщение от бота.
        """
        if not role or not text:
            logger.warning("Попытка добавить пустое сообщение в краткосрочную память.")
            return
        
        message_entry = {"role": role, "parts": [text]}
        
        # Если сообщение от другого бота, помечаем его как "user", но с особым именем
        if role == "user" and is_bot:
             message_entry["user_name"] = f"Бот {user_name}"
        elif user_name:
            message_entry["user_name"] = user_name

        if role == "user" and user_id:
            message_entry["user_id"] = user_id

        self.history.append(message_entry)
        log_user_info = f" ({user_name or 'N/A'}{f', ID: {user_id}' if user_id else ''}{', is_bot' if is_bot else ''})" if role == "user" else ""
        logger.debug(f"Добавлено в short_term_memory (role: {role}{log_user_info}): {text[:50]}...")

    def get_formatted_history(self, exclude_last_n: int = 0) -> list:
        if exclude_last_n < 0: exclude_last_n = 0
        history_list = list(self.history)
        if exclude_last_n > 0 and len(history_list) >= exclude_last_n:
            return history_list[:-exclude_last_n]
        elif exclude_last_n > 0 and len(history_list) < exclude_last_n: 
            return []
        return history_list

    def clear(self):
        self.history.clear()
        logger.info("Краткосрочная память очищена.")