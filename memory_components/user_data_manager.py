# mishka_ai/memory_components/user_data_manager.py
"""
Модуль для управления данными пользователей.

Содержит класс `UserDataManager`, который отвечает за сохранение
информации о пользователях в JSON-файл.
"""
import logging
import json
from pathlib import Path
from mishka_ai.config_loader import USERS_FILE, DATA_DIR

logger = logging.getLogger(__name__)

class UserDataManager:
    """
    Отвечает за сохранение данных пользователей в `users.json`.

    Этот класс инкапсулирует логику записи в файл, обеспечивая
    разделение ответственности: другие части приложения передают ему
    данные, а он заботится об их сохранении на диск.
    """
    def __init__(self, users_file_path: Path = USERS_FILE):
        """
        Инициализирует менеджер данных пользователей.

        Args:
            users_file_path: Путь к файлу `users.json`.
        """
        self.users_file_path = users_file_path
        # Убеждаемся, что директория для данных существует
        if not self.users_file_path.parent.exists():
            self.users_file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для данных: {self.users_file_path.parent}")

    def _save_json_data(self, file_path: Path, data: dict | list):
        """
        Вспомогательная функция для сохранения данных в JSON-файл.

        Args:
            file_path: Путь к файлу для записи.
            data: Словарь или список для сохранения.
        
        Raises:
            IOError: В случае ошибки записи файла.
        """
        try:
            # Гарантируем, что директория data существует
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Данные успешно сохранены в {file_path}")
        except Exception as e:
            logger.error(f"Не удалось сохранить данные в {file_path}: {e}", exc_info=True)
            raise

    def save_users_data(self, users_data_dict: dict):
        """
        Сохраняет словарь с данными пользователей в `users.json`.

        Args:
            users_data_dict: Полный словарь с данными всех пользователей,
                который будет записан в файл, затерев старое содержимое.
        """
        logger.info(f"Сохранение данных {len(users_data_dict)} пользователей в {self.users_file_path}.")
        try:
            self._save_json_data(self.users_file_path, users_data_dict)
            logger.info(f"Данные пользователей успешно сохранены.")
        except Exception as e:
            # Ошибка уже залогирована в _save_json_data, здесь просто пробрасываем ее выше
            logger.error(f"Произошла ошибка при вызове save_users_data: {e}")