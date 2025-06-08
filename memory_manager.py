# mishka_ai/memory_manager.py
import logging
import uuid
from datetime import datetime, timezone 
import json 
import numpy as np 

from mishka_ai.memory_components.long_term_memory_chromadb import LongTermMemoryChromaDB, DEFAULT_LTM_COLLECTION_NAME
from mishka_ai.memory_components.fact_extractor import FactExtractor
from mishka_ai.memory_components.emotional_memory_handler import EmotionalMemoryHandler
from mishka_ai.memory_components.user_data_manager import UserDataManager

from mishka_ai.yandex_embedder import YandexEmbedder
from mishka_ai.config_loader import DATA_DIR 
from typing import TYPE_CHECKING, Optional, List, Any, Sequence
if TYPE_CHECKING:
    from mishka_ai.gemini_client import GeminiClient as GeminiClientType

logger = logging.getLogger(__name__)

DEFAULT_IMPORTANCE_SCORE = 1.0 
IMPORTANT_KEYWORDS_FOR_FACTS = {
    "запомни": 0.5, "важно": 0.5, "план": 0.4, "планы": 0.4, "решили": 0.4, "договорились": 0.4,
    "встреча": 0.3, "поездка": 0.3, "идея": 0.2, "факт": 0.2, "событие": 0.2
}


class NumpyEncoder(json.JSONEncoder):
    # ... (код без изменений) ...
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return obj.tolist() 
        if isinstance(obj, (np.float32, np.float64)): 
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)): 
            return int(obj)
        return json.JSONEncoder.default(self, obj)


class MemoryManager: 
    # ... (__init__ без изменений) ...
    def __init__(self, 
                 all_prompts_data: dict,
                 yc_config: dict,
                 chroma_persist_path_ltm: str = None 
                ):
        
        self.all_prompts = all_prompts_data
        self.yc_config = yc_config

        self.yandex_embedder = None
        yc_folder_id = self.yc_config.get("yc_folder_id")
        yc_auth_creds = self.yc_config.get("yc_api_key")
        yc_doc_model = self.yc_config.get("yc_model_embedding_doc", "text-search-doc")
        yc_query_model = self.yc_config.get("yc_model_embedding_query", "text-search-query")

        if yc_folder_id and yc_auth_creds:
            self.yandex_embedder = YandexEmbedder(
                folder_id=yc_folder_id, auth_credentials=yc_auth_creds,
                doc_model_name=yc_doc_model, query_model_name=yc_query_model
            )
            if not self.yandex_embedder.yc_sdk:
                 logger.error("MemoryManagerFacade: YandexEmbedder не смог инициализировать YCloudML SDK.")
                 self.yandex_embedder = None
            else: 
                logger.info(f"YandexEmbedder initialized with doc_model: '{yc_doc_model}', query_model: '{yc_query_model}'.")
        else:
            logger.warning("MemoryManagerFacade: Конфигурация для YandexEmbedder не полная.")

        if self.yandex_embedder:
            if chroma_persist_path_ltm:
                self.ltm_db = LongTermMemoryChromaDB(persist_path=chroma_persist_path_ltm)
            else:
                self.ltm_db = LongTermMemoryChromaDB() 
            
            if not self.ltm_db.collection: 
                logger.error("MemoryManagerFacade: Не удалось инициализировать LongTermMemoryChromaDB.")
                self.ltm_db = None 
            else: 
                try:
                    if self.ltm_db.collection.count() > 0:
                        sample_item = self.ltm_db.collection.peek(limit=1)
                        if sample_item and sample_item.get("embeddings") and sample_item["embeddings"] and sample_item["embeddings"][0]:
                            logger.info(f"ChromaDB collection '{self.ltm_db.collection_name}' existing embedding dimension: {len(sample_item['embeddings'][0])}")
                    else:
                        logger.info(f"ChromaDB collection '{self.ltm_db.collection_name}' is empty.")
                except Exception as e_chroma_meta:
                    logger.warning(f"Не удалось получить метаданные размерности коллекции ChromaDB: {e_chroma_meta}")
        else:
            logger.warning("MemoryManagerFacade: YandexEmbedder не инициализирован, LongTermMemoryChromaDB не будет использоваться.")
            self.ltm_db = None
            
        fact_extraction_prompt = self.all_prompts.get("fact_extraction_prompt")
        if not fact_extraction_prompt:
            logger.error("MemoryManagerFacade: Промпт 'fact_extraction_prompt' отсутствует! FactExtractor может работать некорректно.")
        self.fact_extractor = FactExtractor(fact_extraction_prompt_template=fact_extraction_prompt)

        self.emotional_memory_handler = EmotionalMemoryHandler()
        self.user_data_manager = UserDataManager()
        
        logger.info("MemoryManager (Фасад) инициализирован.")
        
    # ... (add_fact_to_ltm и get_relevant_facts_from_ltm без изменений) ...
    async def add_fact_to_ltm(self, 
                              fact_text: str, 
                              user_ids: list[str] = None, 
                              source_message_id: Optional[int] = None, 
                              timestamp: Optional[str] = None,
                              importance_score: float = DEFAULT_IMPORTANCE_SCORE
                             ) -> dict | None:
        if not self.ltm_db or not self.yandex_embedder:
            logger.error("add_fact_to_ltm: LTM DB или YandexEmbedder не инициализированы.")
            return None
        
        logger.debug(f"add_fact_to_ltm: Попытка добавить факт: '{fact_text[:100]}...' с важностью {importance_score:.2f}")
        
        cleaned_fact_text = fact_text.strip()
        if cleaned_fact_text.startswith("* "):
            cleaned_fact_text = cleaned_fact_text[2:]
        if not cleaned_fact_text or len(cleaned_fact_text.split()) < 2:
            logger.info(f"add_fact_to_ltm: Факт слишком короткий или пустой, пропущен: '{cleaned_fact_text}'")
            return None

        embedding = await self.yandex_embedder.get_embedding(cleaned_fact_text, model_type="doc")
        if embedding is None:
            logger.error(f"add_fact_to_ltm: Не удалось получить эмбеддинг для факта: '{cleaned_fact_text[:50]}...'.")
            return None
        logger.debug(f"Получен эмбеддинг для нового факта (перед добавлением), размерность: {len(embedding)}")


        fact_id = str(uuid.uuid4())
        ts_added = timestamp or datetime.now(timezone.utc).isoformat()
        
        metadata = {
            "text_original": cleaned_fact_text, 
            "user_ids_json": json.dumps(user_ids if user_ids is not None else []),
            "timestamp_added": ts_added, 
            "last_accessed_timestamp": ts_added, 
            "access_count": 0, 
            "importance_score": float(importance_score), 
        }
        if source_message_id is not None:
            metadata["source_message_id"] = int(source_message_id)
        
        success = self.ltm_db.add_fact(fact_id, cleaned_fact_text, embedding, metadata)
        if success:
            logger.info(f"Факт '{cleaned_fact_text[:50]}...' (ID: {fact_id}, Важность: {importance_score:.2f}) добавлен в LTM с метаданными.")
            return {
                "id": fact_id, 
                "text": cleaned_fact_text, 
                "user_ids": user_ids or [], 
                "timestamp_added": ts_added, 
                "last_accessed_timestamp": ts_added,
                "access_count": 0,
                "importance_score": importance_score,
                "source_message_id": source_message_id
            }
        else:
            logger.error(f"Не удалось добавить факт '{cleaned_fact_text[:50]}...' в LTM DB.")
            return None

    async def get_relevant_facts_from_ltm(self, query_text: str, user_ids: list[str] = None, N: int = 3, max_distance: float = 1.0) -> list[str]:
        if not self.ltm_db or not self.yandex_embedder:
            logger.warning("get_relevant_facts_from_ltm: LTM DB или YandexEmbedder не инициализированы.")
            return []
        if not query_text:
            logger.warning("get_relevant_facts_from_ltm: Пустой запрос для поиска.")
            return []

        logger.info(f"get_relevant_facts_from_ltm: Запрос: '{query_text}', N={N}, user_ids={user_ids}, max_distance={max_distance}")
        query_embedding = await self.yandex_embedder.get_embedding(query_text, model_type="query")
        if query_embedding is None:
            logger.error(f"get_relevant_facts_from_ltm: Не удалось получить эмбеддинг для запроса: '{query_text[:50]}...'.")
            return []
        logger.debug(f"get_relevant_facts_from_ltm: Query embedding dim: {len(query_embedding)}")

        num_results_to_query = N * 5 
        if self.ltm_db.collection.count() == 0: 
            logger.info("get_relevant_facts_from_ltm: Коллекция LTM пуста, поиск невозможен.")
            return []
            
        results_data = self.ltm_db.query_facts(
            query_embeddings=[query_embedding],
            n_results=min(num_results_to_query, self.ltm_db.collection.count()), 
            include=["documents", "metadatas", "embeddings", "distances"] 
        )
        
        try:
            results_data_log_str = json.dumps(results_data, indent=2, ensure_ascii=False, cls=NumpyEncoder)
            logger.debug(f"get_relevant_facts_from_ltm: Raw results_data from ChromaDB: {results_data_log_str}")
        except Exception as e_json_log:
            logger.error(f"Ошибка при логировании results_data (JSON): {e_json_log}")
            logger.debug(f"get_relevant_facts_from_ltm: Raw results_data (не удалось сериализовать): {results_data}")

        final_facts_texts = []
        updated_fact_ids_metadata_embeddings: List[dict] = [] 

        retrieved_ids: List[str] = []
        retrieved_metas: List[dict] = []
        retrieved_embeddings: Optional[List[Optional[List[float]]]] = None 
        retrieved_docs_from_query: List[str] = []
        retrieved_distances: List[float] = []
        
        can_update_metadata = False 

        if results_data:
            ids_outer = results_data.get("ids")
            if ids_outer and isinstance(ids_outer, (list, np.ndarray)) and len(ids_outer) > 0 and isinstance(ids_outer[0], (list, np.ndarray)):
                retrieved_ids = list(ids_outer[0])

            metas_outer = results_data.get("metadatas")
            if metas_outer and isinstance(metas_outer, (list, np.ndarray)) and len(metas_outer) > 0 and isinstance(metas_outer[0], (list, np.ndarray)):
                retrieved_metas = list(metas_outer[0])
            
            embeddings_outer = results_data.get("embeddings")
            if embeddings_outer and isinstance(embeddings_outer, (list, np.ndarray)) and len(embeddings_outer) > 0:
                potential_retrieved_embeddings_list = embeddings_outer[0]
                if isinstance(potential_retrieved_embeddings_list, (list, np.ndarray)):
                    if all( (isinstance(emb_vector, (list, np.ndarray)) and all(isinstance(f_val, (float, int, np.number)) for f_val in emb_vector)) or emb_vector is None 
                            for emb_vector in potential_retrieved_embeddings_list ):
                        retrieved_embeddings = [list(e) if e is not None else None for e in potential_retrieved_embeddings_list]
                        can_update_metadata = True
                        logger.debug(f"get_relevant_facts_from_ltm: Эмбеддинги получены, can_update_metadata=True. Кол-во: {len(retrieved_embeddings) if retrieved_embeddings else 'None'}")
                    else:
                        logger.warning(f"get_relevant_facts_from_ltm: 'embeddings[0]' содержит некорректные эмбеддинги. Обновление метаданных пропущено.")
                        can_update_metadata = False
                        retrieved_embeddings = None 
                else:
                    logger.warning(f"get_relevant_facts_from_ltm: 'embeddings[0]' не является списком/массивом. Обновление метаданных пропущено.")
                    can_update_metadata = False
            else:
                logger.warning("get_relevant_facts_from_ltm: 'embeddings' отсутствуют. Обновление метаданных пропущено.")
                can_update_metadata = False

            docs_outer = results_data.get("documents")
            if docs_outer and isinstance(docs_outer, (list, np.ndarray)) and len(docs_outer) > 0 and isinstance(docs_outer[0], (list, np.ndarray)):
                retrieved_docs_from_query = list(docs_outer[0])

            distances_outer = results_data.get("distances")
            if distances_outer and isinstance(distances_outer, (list, np.ndarray)) and len(distances_outer) > 0 and isinstance(distances_outer[0], (list, np.ndarray)):
                 retrieved_distances = list(distances_outer[0])
        
        if not retrieved_ids:
            logger.info("get_relevant_facts_from_ltm: Не получено ID из ChromaDB query_facts.")
            return []

        current_time_iso = datetime.now(timezone.utc).isoformat()
        
        lengths = [len(retrieved_ids)]
        if retrieved_metas: lengths.append(len(retrieved_metas))
        if retrieved_distances: lengths.append(len(retrieved_distances))
        if retrieved_embeddings and can_update_metadata: lengths.append(len(retrieved_embeddings))

        min_len = min(lengths) if lengths else 0
        
        logger.debug(f"get_relevant_facts_from_ltm: Длины списков: ids={len(retrieved_ids)}, metas={len(retrieved_metas)}, embs={len(retrieved_embeddings if retrieved_embeddings else [])}, dists={len(retrieved_distances)}. min_len={min_len}")

        if min_len < len(retrieved_ids):
             logger.warning("Обнаружена неконсистентность длин списков после извлечения из ChromaDB.")

        for i in range(min_len): 
            fact_id = retrieved_ids[i]
            meta = retrieved_metas[i] if retrieved_metas and i < len(retrieved_metas) else {} 
            embedding = retrieved_embeddings[i] if can_update_metadata and retrieved_embeddings and i < len(retrieved_embeddings) else None
            distance = retrieved_distances[i] if retrieved_distances and i < len(retrieved_distances) else float('inf')
            
            fact_display_text = meta.get("text_original", f"Текст для ID {fact_id} не найден")
            
            logger.info(f"  Кандидат ID: {fact_id}, Дистанция: {distance:.4f}, Текст: {fact_display_text[:50]}...")

            if distance > max_distance:
                logger.info(f"    -> Отброшен по дистанции ({distance:.4f} > {max_distance})")
                continue

            passes_user_filter = True
            if user_ids and meta:
                try:
                    stored_user_ids_json = meta.get("user_ids_json", "[]")
                    stored_user_ids = json.loads(stored_user_ids_json)
                    if stored_user_ids and not any(uid in stored_user_ids for uid in user_ids):
                        passes_user_filter = False
                        logger.info(f"    -> Отброшен по фильтру пользователей")
                except (json.JSONDecodeError, TypeError): pass
            
            if passes_user_filter:
                if len(final_facts_texts) < N:
                    final_facts_texts.append(fact_display_text)
                    logger.info(f"    -> Добавлен в релевантные факты.")
                
                if can_update_metadata and embedding: 
                    new_meta = meta.copy() 
                    new_meta["last_accessed_timestamp"] = current_time_iso
                    new_meta["access_count"] = new_meta.get("access_count", 0) + 1
                    updated_fact_ids_metadata_embeddings.append({"id": fact_id, "metadata": new_meta, "embedding": embedding})
                elif can_update_metadata and not embedding: 
                    logger.warning(f"Нет эмбеддинга для факта ID {fact_id} (индекс {i}).")
        
        if can_update_metadata and updated_fact_ids_metadata_embeddings and self.ltm_db and self.ltm_db.collection:
            if not all(item.get("embedding") for item in updated_fact_ids_metadata_embeddings):
                logger.error("Критическая ошибка: Попытка обновить метаданные с отсутствующими эмбеддингами. Обновление отменено.")
            else:
                self.update_ltm_facts_metadata(updated_fact_ids_metadata_embeddings)

        if not final_facts_texts:
            logger.info(f"get_relevant_facts_from_ltm: Не найдено релевантных фактов после фильтрации для запроса '{query_text}'.")
        
        return final_facts_texts[:N]

    # --- ИЗМЕНЕННЫЙ МЕТОД ---
    async def process_chat_history_for_facts(self, 
                                            chat_history_messages: list[dict], 
                                            gemini_analysis_client: 'GeminiClientType',
                                            all_users_data: dict # <-- НОВЫЙ АРГУМЕНТ
                                            ) -> list[dict]: 
        if not self.fact_extractor:
            logger.error("process_chat_history_for_facts: FactExtractor не инициализирован.")
            return []

        # --- НОВОЕ: Формируем контекст о пользователях для промпта ---
        known_users_context_parts = []
        for user_id, user_info in all_users_data.items():
            name = user_info.get("name", f"User_{user_id}")
            known_users_context_parts.append(f"- {name} (ID: {user_id})")
        known_users_context_str = "\\n".join(known_users_context_parts)

        extracted_items = await self.fact_extractor.extract_facts_from_history(
            chat_history_messages, 
            gemini_analysis_client,
            known_users_context_str=known_users_context_str # <-- Передаем контекст
        )
        
        added_facts_info = []
        if extracted_items:
            logger.info(f"Извлечено {len(extracted_items)} элементов. Попытка добавления в LTM...")
            
            user_message_texts = [
                msg.get("parts", [""])[0] 
                for msg in chat_history_messages if msg.get("role") == "user"
            ]
            full_user_text_for_analysis = " ".join(user_message_texts).lower()

            for item in extracted_items:
                fact_text = item.get("fact_text")
                user_ids_for_fact = item.get("user_ids", []) 
                
                if fact_text:
                    initial_importance = DEFAULT_IMPORTANCE_SCORE
                    
                    is_direct_instruction = False
                    for keyword in IMPORTANT_KEYWORDS_FOR_FACTS:
                        if keyword in full_user_text_for_analysis:
                            is_direct_instruction = True
                            initial_importance += IMPORTANT_KEYWORDS_FOR_FACTS[keyword]
                            logger.debug(f"Повышение важности факта из-за слова '{keyword}'. Текущая: {initial_importance:.2f}")
                            break 

                    if user_ids_for_fact:
                        initial_importance += 0.1
                        logger.debug(f"Повышение важности факта из-за привязки к user_ids. Текущая: {initial_importance:.2f}")
                    
                    initial_importance = min(initial_importance, 2.0)

                    added_fact_dict = await self.add_fact_to_ltm(
                        fact_text=fact_text, 
                        user_ids=user_ids_for_fact,
                        importance_score=initial_importance
                    )
                    if added_fact_dict:
                        added_facts_info.append(added_fact_dict)
        else:
            logger.info("Новых фактов для добавления в LTM не извлечено.")
            
        return added_facts_info
        
    # ... (остальные методы без изменений) ...
    def get_ltm_data(self, ids: list[str] = None, include: list[str] = None, where_filter: dict = None, limit: int = None, offset: int = None):
        return self.ltm_db.get_data(ids=ids, include=include, where_filter=where_filter, limit=limit, offset=offset) if self.ltm_db else None

    def count_ltm_facts(self) -> int:
        return self.ltm_db.count() if self.ltm_db else 0

    def delete_ltm_facts_by_ids(self, ids: list[str]) -> bool:
        return self.ltm_db.delete_data(ids=ids) if self.ltm_db else False

    def clear_all_ltm_facts(self) -> bool:
        if self.ltm_db:
            try:
                if self.ltm_db.client: 
                    existing_collections = [col.name for col in self.ltm_db.client.list_collections()]
                    if self.ltm_db.collection_name in existing_collections:
                        return self.ltm_db.clear_all_data() 
                    else: 
                        logger.info(f"Коллекция {self.ltm_db.collection_name} не найдена, очистка не требуется.")
                        self.ltm_db.collection = self.ltm_db.client.get_or_create_collection(name=self.ltm_db.collection_name)
                        return True 
                else:
                    logger.error("MemoryManager.clear_all_ltm_facts: LTM DB client не инициализирован.")
                    return False
            except Exception as e:
                 logger.error(f"Ошибка в MemoryManager.clear_all_ltm_facts: {e}", exc_info=True)
                 return False
        return False
        
    def update_ltm_facts_metadata(self, fact_updates: List[dict]) -> bool:
        if not self.ltm_db or not self.ltm_db.collection:
            logger.error("update_ltm_facts_metadata: LTM DB не инициализирована.")
            return False
        if not fact_updates:
            logger.info("update_ltm_facts_metadata: Нет фактов для обновления.")
            return True

        ids_to_update = [item['id'] for item in fact_updates]
        metadatas_to_update = [item['metadata'] for item in fact_updates]
        embeddings_to_update = [item['embedding'] for item in fact_updates]

        if not all(embeddings_to_update):
            logger.error("Критическая ошибка: Попытка обновить метаданные с отсутствующими эмбеддингами. Обновление отменено.")
            return False

        try:
            self.ltm_db.collection.update(ids=ids_to_update, embeddings=embeddings_to_update, metadatas=metadatas_to_update)
            logger.info(f"Метаданные для {len(ids_to_update)} фактов успешно обновлены в LTM.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении метаданных фактов в LTM: {e}", exc_info=True)
            return False

    def save_users_data(self, users_data_dict: dict):
        if self.user_data_manager:
            try:
                self.user_data_manager.save_users_data(users_data_dict)
            except Exception as e: 
                logger.error(f"MemoryManager: Ошибка при сохранении данных пользователя через UserDataManager: {e}")
        else:
            logger.error("MemoryManager: UserDataManager не инициализирован.")

    def get_emotional_notes(self, user_id: str) -> dict | None:
        return self.emotional_memory_handler.get_emotional_notes(user_id) if self.emotional_memory_handler else None

    def update_emotional_notes(self, user_id: str, new_note_text: str = None, interaction_summary: str = None, user_name: str = None) -> int:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.update_emotional_notes(user_id, new_note_text, interaction_summary, user_name)
        else:
            logger.error("MemoryManager: EmotionalMemoryHandler не инициализирован.")
            return 0 
            
    def overwrite_emotional_data_after_consolidation(
        self, 
        user_id: str, 
        consolidated_notes: list[str], 
        new_overall_summary: str,
        user_name_if_missing: str = None
    ) -> bool:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.overwrite_emotional_data_after_consolidation(
                user_id, consolidated_notes, new_overall_summary, user_name_if_missing
            )
        else:
            logger.error("MemoryManager: EmotionalMemoryHandler не инициализирован. Не удалось перезаписать эмоциональные данные.")
            return False

    def clear_user_emotional_data(self, user_id: str) -> bool:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.clear_user_emotional_data(user_id)
        else:
            logger.error("MemoryManager: EmotionalMemoryHandler не инициализирован. Не удалось очистить эмоциональные данные пользователя.")
            return False

    def clear_all_emotional_data(self) -> bool:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.clear_all_emotional_data()
        else:
            logger.error("MemoryManager: EmotionalMemoryHandler не инициализирован. Не удалось очистить всю эмоциональную память.")
            return False