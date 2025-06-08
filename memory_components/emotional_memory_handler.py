# mishka_ai/memory_components/emotional_memory_handler.py
"""
Модуль для управления эмоциональной памятью бота.

Содержит класс `EmotionalMemoryHandler`, который отвечает за хранение,
обновление и консолидацию "эмоциональных заметок" о пользователях.
Данные хранятся в JSON-файле.
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from mishka_ai.config_loader import EMOTIONAL_MEMORY_FILE, DATA_DIR

logger = logging.getLogger(__name__)

# Значения по умолчанию для логики консолидации.
# Эти значения могут быть переопределены конфигурацией из .env.
DEFAULT_CONSOLIDATION_TRIGGER_COUNT = 7 # Порог "сырых" заметок для запуска консолидации.
DEFAULT_MAX_CONSOLIDATED_NOTES_COUNT = 4 # Максимальное количество заметок после консолидации.


class EmotionalMemoryHandler:
    """
    Управляет эмоциональными данными о пользователях, хранящимися в JSON-файле.

    Отвечает за загрузку, сохранение, обновление и очистку эмоциональных заметок.
    Реализует логику накопления "сырых" заметок и их последующей консолидации.
    """
    def __init__(self, emotional_memory_file_path: Path = EMOTIONAL_MEMORY_FILE):
        """
        Инициализирует обработчик эмоциональной памяти.

        Args:
            emotional_memory_file_path: Путь к JSON-файлу с данными.
        """
        self.file_path = emotional_memory_file_path
        # Убеждаемся, что директория для данных существует
        if not self.file_path.parent.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана директория для данных: {self.file_path.parent}")
        self.emotional_memory = self._load_emotional_data()

    def _load_json_data(self, file_path: Path, default: dict | list) -> dict | list:
        """Вспомогательная функция для безопасной загрузки данных из JSON-файла."""
        try:
            if file_path.exists() and file_path.stat().st_size > 0:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.info(f"Файл {file_path} не найден или пуст. Используется значение по умолчанию.")
            if default:
                 # Если указано значение по умолчанию, создаем файл с ним
                 self._save_json_data(file_path, default)
            return default.copy() 
        except json.JSONDecodeError:
            logger.warning(f"Ошибка декодирования JSON в файле {file_path}. Файл будет перезаписан при сохранении.")
            if default:
                self._save_json_data(file_path, default)
            return default.copy()
        except Exception as e:
            logger.error(f"Не удалось прочитать или инициализировать файл {file_path}: {e}. Возвращается значение по умолчанию.")
            return default.copy()

    def _save_json_data(self, file_path: Path, data: dict | list):
        """Вспомогательная функция для сохранения данных в JSON-файл."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Данные успешно сохранены в {file_path}")
        except Exception as e:
            logger.error(f"Не удалось сохранить данные в {file_path}: {e}", exc_info=True)
    
    def _load_emotional_data(self) -> dict:
        """Загружает данные эмоциональной памяти из файла."""
        return self._load_json_data(self.file_path, default={})

    def _save_emotional_data(self):
        """Сохраняет текущее состояние эмоциональной памяти в файл."""
        self._save_json_data(self.file_path, self.emotional_memory)

    def get_emotional_notes(self, user_id: str) -> dict | None:
        """
        Возвращает полную запись эмоциональной памяти для пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Словарь с данными пользователя или None, если пользователь не найден.
        """
        return self.emotional_memory.get(user_id)

    def update_emotional_notes(self, user_id: str, new_note_text: str = None, interaction_summary: str = None, user_name: str = None) -> int:
        """
        Обновляет эмоциональные заметки пользователя и возвращает количество "сырых" заметок.

        Если для пользователя нет записи, она создается.
        Счетчик `raw_notes_count` увеличивается, только если добавлена новая заметка.

        Args:
            user_id: ID пользователя.
            new_note_text: Текст новой "сырой" заметки.
            interaction_summary: Краткое резюме последнего взаимодействия.
            user_name: Имя пользователя для создания новой записи.

        Returns:
            Общее количество "сырых" заметок для данного пользователя после обновления.
        """
        if user_id not in self.emotional_memory:
            self.emotional_memory[user_id] = {
                "name": user_name or f"User_{user_id}",
                "notes": [], # Список "сырых" или консолидированных заметок
                "last_interaction_summary": "", # Общее впечатление/резюме
                "last_update": datetime.now().isoformat(),
                "raw_notes_count": 0 # Счетчик "сырых" заметок с момента последней консолидации
            }
        
        entry = self.emotional_memory[user_id]
        current_raw_notes_count = entry.get("raw_notes_count", 0)

        # Добавляем новую заметку и увеличиваем счетчик сырых заметок
        if new_note_text:
            entry["notes"].append(new_note_text)
            current_raw_notes_count += 1 
            entry["raw_notes_count"] = current_raw_notes_count
            logger.info(f"Новая эмоциональная заметка добавлена для user_id: {user_id}. Сырых заметок: {current_raw_notes_count}.")

        if interaction_summary:
            entry["last_interaction_summary"] = interaction_summary
        
        # Обновляем имя, если оно изменилось
        if user_name and entry.get("name") != user_name:
            entry["name"] = user_name
            
        entry["last_update"] = datetime.now().isoformat()
        self._save_emotional_data()
        return current_raw_notes_count

    def overwrite_emotional_data_after_consolidation(
        self, 
        user_id: str, 
        consolidated_notes: list[str], 
        new_overall_summary: str,
        user_name_if_missing: str = None
    ) -> bool:
        """
        Полностью перезаписывает данные пользователя результатами консолидации.

        Заменяет старый список заметок новым (консолидированным), обновляет общее
        резюме и, что важно, сбрасывает счетчик `raw_notes_count` в 0.

        Args:
            user_id: ID пользователя.
            consolidated_notes: Новый список обобщенных заметок.
            new_overall_summary: Новое общее резюме об отношениях.
            user_name_if_missing: Имя пользователя (на случай, если запись отсутствует).

        Returns:
            True в случае успешного сохранения, иначе False.
        """
        if user_id not in self.emotional_memory:
            # Этот блок для отказоустойчивости, хотя такого быть не должно
            logger.warning(f"overwrite_emotional_data: user_id {user_id} не найден. Создание новой записи.")
            self.emotional_memory[user_id] = {
                "name": user_name_if_missing or f"User_{user_id}",
                "notes": consolidated_notes,
                "last_interaction_summary": new_overall_summary,
                "last_update": datetime.now().isoformat(),
                "raw_notes_count": 0 
            }
        else:
            entry = self.emotional_memory[user_id]
            entry["notes"] = consolidated_notes
            entry["last_interaction_summary"] = new_overall_summary
            entry["last_update"] = datetime.now().isoformat()
            entry["raw_notes_count"] = 0 # Сброс счетчика сырых заметок
        
        try:
            self._save_emotional_data()
            logger.info(f"Эмоциональные данные для user_id: {user_id} перезаписаны после консолидации. Счетчик сырых заметок сброшен.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении данных после консолидации для user_id {user_id}: {e}", exc_info=True)
            return False

    def clear_user_emotional_data(self, user_id: str) -> bool:
        """
        Очищает эмоциональные данные для конкретного пользователя.

        Args:
            user_id: ID пользователя для очистки.

        Returns:
            True, если данные были удалены, иначе False.
        """
        if user_id in self.emotional_memory:
            del self.emotional_memory[user_id]
            self._save_emotional_data()
            logger.info(f"Эмоциональные данные для user_id: {user_id} очищены.")
            return True
        logger.warning(f"Попытка очистить эмоциональные данные для несуществующего user_id: {user_id}.")
        return False

    def clear_all_emotional_data(self) -> bool:
        """
        Очищает все эмоциональные данные для всех пользователей.

        Returns:
            True в случае успеха, иначе False.
        """
        try:
            self.emotional_memory = {}
            self._save_emotional_data()
            logger.warning("Все данные эмоциональной памяти были очищены.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при очистке всех данных эмоциональной памяти: {e}", exc_info=True)
            return False