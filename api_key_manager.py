# mishka_ai/api_key_manager.py
import logging
import threading
from typing import List, Optional

# Настройка логгера для этого модуля
logger = logging.getLogger(__name__)

class ApiKeyManager:
    """
    Управляет списком API-ключей Gemini, обеспечивая их ротацию и отслеживание использования.

    Этот класс является потокобезопасным благодаря использованию threading.Lock.
    Он позволяет автоматически переключаться на следующий ключ, когда у текущего
    достигается лимит использования, что помогает обходить суточные ограничения API.
    """

    def __init__(self, api_keys: List[str], usage_limit: int):
        """
        Инициализирует менеджер API-ключей.

        Args:
            api_keys: Список API-ключей Gemini.
            usage_limit: Максимальное количество использований одного ключа перед ротацией.
        
        Raises:
            ValueError: Если список api_keys пуст.
        """
        if not api_keys:
            raise ValueError("Список API ключей не может быть пустым.")
        
        self.api_keys = api_keys
        self.usage_limit = usage_limit
        # Словарь для хранения счетчиков использования каждого ключа
        self.usage_counts = {key: 0 for key in api_keys}
        self.current_key_index = 0
        # Блокировка для обеспечения потокобезопасности при доступе к общим ресурсам
        self.lock = threading.Lock()
        logger.info(f"ApiKeyManager инициализирован с {len(api_keys)} ключами. Лимит использования: {usage_limit}.")

    def _rotate_key(self) -> None:
        """
        Выполняет ротацию ключа, переключаясь на следующий доступный в списке.

        Метод ищет следующий ключ, у которого счетчик использования еще не достиг лимита.
        Если все ключи исчерпаны, оставляет текущий индекс, что приведет к ошибке
        лимита при следующем запросе к API.
        """
        initial_index = self.current_key_index
        while True:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            
            new_key = self.api_keys[self.current_key_index]
            if self.usage_counts[new_key] < self.usage_limit:
                logger.warning(f"Лимит для ключа #{initial_index} достигнут. Переключение на ключ #{self.current_key_index}.")
                return

            # Этот блок выполняется, если пройден полный круг по всем ключам,
            # и ни один из них не является доступным.
            if self.current_key_index == initial_index:
                logger.error("Все API ключи Gemini исчерпали свой лимит! Ротация невозможна.")
                # Оставляем текущий ключ. При его использовании API вернет ошибку о превышении лимита.
                return

    def get_key(self) -> Optional[str]:
        """
        Возвращает текущий активный API-ключ и инкрементирует его счетчик использования.

        Перед возвратом ключа проверяется, не достигнут ли лимит. Если да,
        происходит ротация. Если все ключи исчерпаны, возвращается текущий
        "перегруженный" ключ, что позволит API сообщить об ошибке.

        Returns:
            Текущий активный API-ключ в виде строки или None, если ключи отсутствуют.
        """
        with self.lock:
            if not self.api_keys:
                return None
            
            current_key = self.api_keys[self.current_key_index]
            
            # Проверяем лимит и при необходимости ротируем ключ *перед* его использованием.
            if self.usage_counts[current_key] >= self.usage_limit:
                self._rotate_key()
                current_key = self.api_keys[self.current_key_index]
            
            # Если после попытки ротации все ключи по-прежнему исчерпаны,
            # возвращаем текущий ключ, чтобы API вернуло ошибку 429 (Resource Exhausted).
            if self.usage_counts[current_key] >= self.usage_limit:
                 logger.critical("Нет доступных API ключей Gemini, все лимиты исчерпаны.")
                 return current_key

            # Увеличиваем счетчик и возвращаем ключ
            self.usage_counts[current_key] += 1
            logger.info(f"Используется API ключ #{self.current_key_index}. Использовано: {self.usage_counts[current_key]}/{self.usage_limit}.")
            return current_key

    def reset_daily_counts(self) -> None:
        """
        Сбрасывает суточные счетчики использования для всех ключей.

        Этот метод предназначен для вызова по расписанию (например, раз в день).
        """
        with self.lock:
            self.usage_counts = {key: 0 for key in self.api_keys}
            self.current_key_index = 0
            logger.warning("Счетчики использования всех API ключей Gemini сброшены.")

    def get_stats(self) -> dict:
        """
        Возвращает статистику использования API-ключей.

        Returns:
            Словарь со статистикой: общее количество ключей, индекс текущего ключа,
            лимит использования и текущие счетчики для каждого ключа.
        """
        with self.lock:
            return {
                "total_keys": len(self.api_keys),
                "current_key_index": self.current_key_index,
                "usage_limit": self.usage_limit,
                "usage_counts": self.usage_counts.copy()
            }