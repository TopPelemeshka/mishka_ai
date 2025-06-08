# mishka_ai/memory_components/long_term_memory_chromadb.py
"""
Модуль для взаимодействия с векторной базой данных ChromaDB.

Содержит класс `LongTermMemoryChromaDB`, который предоставляет
интерфейс для хранения, поиска и управления фактами (документами)
и их векторными представлениями (эмбеддингами).
"""
import logging
import chromadb
from pathlib import Path
from mishka_ai.config_loader import DATA_DIR 
from typing import Optional

logger = logging.getLogger(__name__)

# Путь по умолчанию для хранения файлов базы данных ChromaDB
DEFAULT_CHROMA_PERSIST_PATH_LTM = str(DATA_DIR / "chroma_db_mishka_ltm") 
# Имя по умолчанию для коллекции, в которой хранятся факты
DEFAULT_LTM_COLLECTION_NAME = "mishka_long_term_facts"

class LongTermMemoryChromaDB:
    """
    Класс-обертка для работы с ChromaDB в качестве долгосрочной памяти (LTM).

    Инкапсулирует инициализацию клиента и коллекции, а также все основные
    операции: добавление, получение, запрос (векторный поиск) и удаление данных.
    """
    def __init__(self, 
                 persist_path: str = DEFAULT_CHROMA_PERSIST_PATH_LTM, 
                 collection_name: str = DEFAULT_LTM_COLLECTION_NAME):
        """
        Инициализирует LTM на базе ChromaDB.

        Args:
            persist_path: Путь к директории для хранения файлов БД.
            collection_name: Имя коллекции для фактов.
        """
        self.persist_path = persist_path
        self.collection_name = collection_name
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None
        self._initialize_db()

    def _initialize_db(self):
        """
        Инициализирует постоянный клиент ChromaDB и получает/создает коллекцию.
        """
        try:
            # Создаем директорию для хранения, если она не существует
            Path(self.persist_path).mkdir(parents=True, exist_ok=True)
            # Инициализируем клиент, который будет сохранять данные на диск
            self.client = chromadb.PersistentClient(path=self.persist_path)
            logger.info(f"LTM ChromaDB PersistentClient инициализирован. Путь: {self.persist_path}")
            
            # Получаем коллекцию по имени. Если она не существует, ChromaDB создаст ее.
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            logger.info(f"LTM ChromaDB коллекция '{self.collection_name}' готова. Элементов: {self.collection.count() if self.collection else 'N/A'}")
        except Exception as e:
            logger.error(f"Ошибка инициализации LTM ChromaDB: {e}", exc_info=True)
            self.client = None
            self.collection = None

    def add_fact(self, fact_id: str, fact_text: str, embedding: list[float], metadata: dict) -> bool:
        """
        Добавляет один факт (документ) в коллекцию.

        Args:
            fact_id: Уникальный ID для факта.
            fact_text: Текстовое содержимое факта.
            embedding: Векторное представление (эмбеддинг) текста.
            metadata: Словарь с метаданными (дата, user_ids и т.д.).

        Returns:
            True в случае успеха, иначе False.
        """
        if not self.collection:
            logger.error("LTM ChromaDB коллекция не инициализирована. Факт не добавлен.")
            return False
        try:
            # Метод add требует, чтобы все аргументы были списками
            self.collection.add(
                ids=[fact_id],
                embeddings=[embedding],
                documents=[fact_text],
                metadatas=[metadata]
            )
            logger.debug(f"Факт ID {fact_id} добавлен в LTM ChromaDB: '{fact_text[:50]}...'.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении факта ID {fact_id} в LTM ChromaDB: {e}", exc_info=True)
            return False

    def get_data(self, 
                 ids: Optional[list[str]] = None, 
                 include: Optional[list[str]] = None, 
                 where_filter: Optional[dict] = None, 
                 limit: Optional[int] = None,
                 offset: Optional[int] = None
                ) -> dict | None:
        """
        Получает данные из коллекции по ID или фильтру.

        Args:
            ids: Список ID для получения.
            include: Список полей для включения в ответ (e.g., ["metadatas", "documents"]).
            where_filter: Фильтр по метаданным.
            limit: Максимальное количество возвращаемых записей.
            offset: Смещение для пагинации.

        Returns:
            Словарь с данными или None в случае ошибки.
        """
        if not self.collection:
            logger.error("LTM ChromaDB коллекция не инициализирована.")
            return None
        try:
            return self.collection.get(ids=ids, include=include, where=where_filter, limit=limit, offset=offset)
        except Exception as e:
            logger.error(f"Ошибка при получении данных из LTM ChromaDB: {e}", exc_info=True)
            return None
            
    def query_facts(self, 
                    query_embeddings: list[list[float]], 
                    n_results: int = 5, 
                    include: Optional[list[str]] = None, 
                    where_filter: Optional[dict] = None
                   ) -> dict | None:
        """
        Выполняет векторный поиск в коллекции.

        Args:
            query_embeddings: Список эмбеддингов для поиска.
            n_results: Количество ближайших соседей для возврата.
            include: Список полей для включения в ответ.
            where_filter: Фильтр по метаданным.

        Returns:
            Словарь с результатами поиска или None в случае ошибки.
        """
        if not self.collection:
            logger.error("LTM ChromaDB коллекция не инициализирована.")
            return None
        try:
            return self.collection.query(
                query_embeddings=query_embeddings,
                n_results=n_results,
                include=include,
                where=where_filter
            )
        except Exception as e:
            logger.error(f"Ошибка при запросе фактов из LTM ChromaDB: {e}", exc_info=True)
            return None

    def delete_data(self, ids: list[str] = None, where_filter: dict = None) -> bool:
        """
        Удаляет данные из коллекции по ID или фильтру.

        Args:
            ids: Список ID для удаления.
            where_filter: Фильтр по метаданным для удаления.

        Returns:
            True в случае успеха, иначе False.
        """
        if not self.collection:
            logger.error("LTM ChromaDB коллекция не инициализирована.")
            return False
        try:
            if ids:
                self.collection.delete(ids=ids)
                logger.info(f"Удалены факты из LTM ChromaDB по ID: {ids}")
            elif where_filter: 
                self.collection.delete(where=where_filter)
                logger.info(f"Удалены факты из LTM ChromaDB по фильтру: {where_filter}")
            else:
                logger.warning("Вызов delete_data без ID или фильтра. Ничего не удалено.")
                return False
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении данных из LTM ChromaDB: {e}", exc_info=True)
            return False

    def clear_all_data(self) -> bool:
        """
        Полностью очищает LTM, удаляя и пересоздавая коллекцию.
        
        Это опасная операция, которая приводит к необратимой потере всех фактов.

        Returns:
            True в случае успеха, иначе False.
        """
        if not self.client:
            logger.error("LTM ChromaDB клиент не инициализирован. Очистка невозможна.")
            return False
        try:
            logger.warning(f"Полная очистка LTM. Удаление коллекции '{self.collection_name}'...")
            # Проверяем, существует ли коллекция, чтобы избежать ошибок
            existing_collections = [col.name for col in self.client.list_collections()]
            if self.collection_name in existing_collections:
                self.client.delete_collection(name=self.collection_name)
                logger.info(f"Коллекция '{self.collection_name}' удалена.")
            else:
                logger.info(f"Коллекция '{self.collection_name}' не найдена, удаление не требуется.")

            # Немедленно пересоздаем пустую коллекцию
            self.collection = self.client.create_collection(name=self.collection_name)
            logger.info(f"Пустая коллекция '{self.collection_name}' успешно создана.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при полной очистке LTM ChromaDB: {e}", exc_info=True)
            # Попытка восстановить рабочее состояние после сбоя
            try:
                if not self.client:
                     self.client = chromadb.PersistentClient(path=self.persist_path)
                self.collection = self.client.get_or_create_collection(name=self.collection_name)
                logger.info(f"Коллекция LTM '{self.collection_name}' восстановлена или создана после ошибки очистки.")
            except Exception as e_recreate:
                logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: не удалось пересоздать коллекцию LTM после сбоя: {e_recreate}")
            return False
            
    def count(self) -> int:
        """
        Возвращает общее количество документов (фактов) в коллекции.

        Returns:
            Количество элементов в коллекции.
        """
        if not self.collection:
            # Попытка переподключиться к коллекции, если она была потеряна
            if self.client:
                try:
                    self.collection = self.client.get_collection(name=self.collection_name)
                    logger.info(f"Переподключение к коллекции {self.collection_name} для подсчета.")
                except Exception:
                    logger.warning(f"Коллекция {self.collection_name} не найдена при попытке подсчета.")
                    return 0
            else:
                return 0
        return self.collection.count()