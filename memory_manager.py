# mishka_ai/memory_manager.py
import logging
import uuid
from datetime import datetime, timezone, timedelta
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
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return obj.tolist() 
        if isinstance(obj, (np.float32, np.float64)): 
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)): 
            return int(obj)
        return json.JSONEncoder.default(self, obj)


class MemoryManager: 
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
                 logger.error("MemoryManager: YandexEmbedder не смог инициализировать YCloudML SDK.")
                 self.yandex_embedder = None
            else: 
                logger.info(f"YandexEmbedder initialized with doc_model: '{yc_doc_model}', query_model: '{yc_query_model}'.")
        else:
            logger.warning("MemoryManager: Конфигурация для YandexEmbedder не полная.")

        if self.yandex_embedder:
            self.ltm_db = LongTermMemoryChromaDB(persist_path=chroma_persist_path_ltm or str(DATA_DIR / "chroma_db_mishka_ltm"))
            
            if not self.ltm_db.collection: 
                logger.error("MemoryManager: Не удалось инициализировать LongTermMemoryChromaDB.")
                self.ltm_db = None 
            else: 
                try:
                    if self.ltm_db.collection.count() > 0:
                        sample_item = self.ltm_db.collection.peek(limit=1)
                        # <--- ИСПРАВЛЕНИЕ 1: Безопасная проверка для numpy-массива
                        embeddings_list = sample_item.get("embeddings")
                        if embeddings_list and isinstance(embeddings_list, list) and len(embeddings_list) > 0 and embeddings_list[0] is not None:
                            logger.info(f"ChromaDB collection '{self.ltm_db.collection_name}' existing embedding dimension: {len(embeddings_list[0])}")
                        else:
                            logger.info(f"ChromaDB collection '{self.ltm_db.collection_name}' has items but embeddings are missing/empty in sample.")
                    else:
                        logger.info(f"ChromaDB collection '{self.ltm_db.collection_name}' is empty.")
                except Exception as e_chroma_meta:
                    logger.warning(f"Не удалось получить метаданные размерности коллекции ChromaDB: {e_chroma_meta}")
        else:
            logger.warning("MemoryManager: YandexEmbedder не инициализирован, LongTermMemoryChromaDB не будет использоваться.")
            self.ltm_db = None
            
        fact_extraction_prompt = self.all_prompts.get("fact_extraction_prompt")
        if not fact_extraction_prompt:
            logger.error("MemoryManager: Промпт 'fact_extraction_prompt' отсутствует! FactExtractor может работать некорректно.")
        self.fact_extractor = FactExtractor(fact_extraction_prompt_template=fact_extraction_prompt)

        self.emotional_memory_handler = EmotionalMemoryHandler()
        self.user_data_manager = UserDataManager()
        
        logger.info("MemoryManager (Фасад) инициализирован.")
        
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
        if not self.ltm_db or not self.yandex_embedder or self.ltm_db.collection.count() == 0:
            logger.warning("get_relevant_facts_from_ltm: LTM DB или YandexEmbedder не инициализированы или LTM пуста.")
            return []
        if not query_text:
            logger.warning("get_relevant_facts_from_ltm: Пустой запрос для поиска.")
            return []

        logger.info(f"get_relevant_facts_from_ltm: Запрос: '{query_text}', N={N}, user_ids={user_ids}, max_distance={max_distance}")
        query_embedding = await self.yandex_embedder.get_embedding(query_text, model_type="query")
        if query_embedding is None:
            logger.error(f"get_relevant_facts_from_ltm: Не удалось получить эмбеддинг для запроса: '{query_text[:50]}...'.")
            return []
        
        num_results_to_query = max(N * 5, 20)
        
        results_data = self.ltm_db.query_facts(
            query_embeddings=[query_embedding],
            n_results=min(num_results_to_query, self.ltm_db.collection.count()), 
            include=["documents", "metadatas", "embeddings", "distances"] 
        )
        
        final_facts_texts = []
        updated_fact_metadata = []
        
        if not results_data or not results_data.get("ids"):
            return []

        retrieved_ids = results_data["ids"][0]
        retrieved_metas = results_data["metadatas"][0]
        retrieved_distances = results_data["distances"][0]
        retrieved_embeddings = results_data["embeddings"][0]
        current_time_iso = datetime.now(timezone.utc).isoformat()
        
        for i, fact_id in enumerate(retrieved_ids):
            distance = retrieved_distances[i]
            meta = retrieved_metas[i]
            
            fact_display_text = meta.get("text_original", f"Текст для ID {fact_id} не найден")
            logger.info(f"  Кандидат ID: {fact_id}, Дистанция: {distance:.4f}, Текст: {fact_display_text[:50]}...")
            
            if distance > max_distance:
                logger.info(f"    -> Отброшен по дистанции ({distance:.4f} > {max_distance})")
                continue

            passes_user_filter = True
            if user_ids and meta:
                stored_user_ids = json.loads(meta.get("user_ids_json", "[]"))
                if stored_user_ids and not any(uid in stored_user_ids for uid in user_ids):
                    passes_user_filter = False
                    logger.info(f"    -> Отброшен по фильтру пользователей")

            if passes_user_filter:
                if len(final_facts_texts) < N:
                    final_facts_texts.append(fact_display_text)
                    logger.info(f"    -> Добавлен в релевантные факты.")

                new_meta = meta.copy()
                new_meta["last_accessed_timestamp"] = current_time_iso
                new_meta["access_count"] = new_meta.get("access_count", 0) + 1
                updated_fact_metadata.append({"id": fact_id, "metadata": new_meta, "embedding": retrieved_embeddings[i]})

        if updated_fact_metadata:
            self.update_ltm_facts_metadata(updated_fact_metadata)
            
        return final_facts_texts[:N]

    async def process_chat_history_for_facts(self, 
                                            chat_history_messages: list[dict], 
                                            gemini_analysis_client: 'GeminiClientType',
                                            all_users_data: dict
                                            ) -> list[dict]: 
        if not self.fact_extractor:
            logger.error("process_chat_history_for_facts: FactExtractor не инициализирован.")
            return []

        known_users_context_parts = []
        for user_id, user_info in all_users_data.items():
            name = user_info.get("name", f"User_{user_id}")
            known_users_context_parts.append(f"- {name} (ID: {user_id})")
        known_users_context_str = "\n".join(known_users_context_parts)

        extracted_items = await self.fact_extractor.extract_facts_from_history(
            chat_history_messages, 
            gemini_analysis_client,
            known_users_context_str=known_users_context_str
        )
        
        added_facts_info = []
        if extracted_items:
            logger.info(f"Извлечено {len(extracted_items)} элементов. Попытка добавления в LTM...")
            
            user_message_texts = [msg.get("parts", [""])[0] for msg in chat_history_messages if msg.get("role") == "user"]
            full_user_text_for_analysis = " ".join(user_message_texts).lower()

            for item in extracted_items:
                fact_text = item.get("fact_text")
                user_ids_for_fact = item.get("user_ids", []) 
                
                if fact_text:
                    initial_importance = DEFAULT_IMPORTANCE_SCORE
                    
                    for keyword, value in IMPORTANT_KEYWORDS_FOR_FACTS.items():
                        if keyword in full_user_text_for_analysis:
                            initial_importance += value
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
        
    def get_ltm_data(self, ids: list[str] = None, include: list[str] = None, where_filter: dict = None, limit: int = None, offset: int = None):
        return self.ltm_db.get_data(ids=ids, include=include, where_filter=where_filter, limit=limit, offset=offset) if self.ltm_db else None

    def count_ltm_facts(self) -> int:
        return self.ltm_db.count() if self.ltm_db else 0

    def delete_ltm_facts_by_ids(self, ids: list[str]) -> bool:
        return self.ltm_db.delete_data(ids=ids) if self.ltm_db else False

    def clear_all_ltm_facts(self) -> bool:
        return self.ltm_db.clear_all_data() if self.ltm_db else False
        
    def update_ltm_facts_metadata(self, fact_updates: List[dict]) -> bool:
        if not self.ltm_db or not self.ltm_db.collection:
            logger.error("update_ltm_facts_metadata: LTM DB не инициализирована.")
            return False
        if not fact_updates:
            return True

        ids_to_update = [item['id'] for item in fact_updates]
        metadatas_to_update = [item['metadata'] for item in fact_updates]
        embeddings_to_update = [item['embedding'] for item in fact_updates]

        try:
            self.ltm_db.collection.update(ids=ids_to_update, embeddings=embeddings_to_update, metadatas=metadatas_to_update)
            logger.info(f"Метаданные для {len(ids_to_update)} фактов успешно обновлены в LTM.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении метаданных фактов в LTM: {e}", exc_info=True)
            return False

    # <--- ИСПРАВЛЕНИЕ 2: НОВЫЙ МЕТОД ОБСЛУЖИВАНИЯ LTM ---
    async def perform_ltm_maintenance(self, config: dict) -> dict:
        if not self.ltm_db or not self.ltm_db.collection or not self.yandex_embedder:
            msg = "LTM DB или эмбеддер не инициализированы. Обслуживание LTM невозможно."
            logger.error(msg)
            return {"error": msg}
        
        logger.info(f"Начало обслуживания LTM с конфигурацией: {config}")
        results = {"deleted_duplicates": 0, "deleted_obsolete": 0, "updated_importance": 0, "total_deleted": 0}
        
        try:
            all_facts = self.ltm_db.get_data(include=["metadatas", "embeddings"])
            if not all_facts or not all_facts.get("ids"):
                logger.info("LTM пуста, обслуживание не требуется.")
                return results

            fact_ids = all_facts["ids"]
            metadatas = all_facts["metadatas"]
            embeddings = all_facts["embeddings"]
            
            # --- 1. Удаление дубликатов/схожих фактов ---
            ids_to_delete_for_similarity = set()
            for i in range(len(fact_ids)):
                if fact_ids[i] in ids_to_delete_for_similarity:
                    continue
                for j in range(i + 1, len(fact_ids)):
                    if fact_ids[j] in ids_to_delete_for_similarity:
                        continue
                    
                    vec1 = np.array(embeddings[i])
                    vec2 = np.array(embeddings[j])
                    similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
                    
                    if similarity > config.get("similarity_threshold", 0.95):
                        # Сравниваем важность и дату, чтобы решить, какой оставить
                        meta_i = metadatas[i]
                        meta_j = metadatas[j]
                        importance_i = meta_i.get("importance_score", 1.0)
                        importance_j = meta_j.get("importance_score", 1.0)
                        date_i = meta_i.get("timestamp_added", "")
                        date_j = meta_j.get("timestamp_added", "")

                        if importance_i > importance_j:
                            ids_to_delete_for_similarity.add(fact_ids[j])
                        elif importance_j > importance_i:
                            ids_to_delete_for_similarity.add(fact_ids[i])
                        else: # Если важность равна, удаляем более старый
                            if date_i <= date_j:
                                ids_to_delete_for_similarity.add(fact_ids[i])
                            else:
                                ids_to_delete_for_similarity.add(fact_ids[j])
            
            results["deleted_duplicates"] = len(ids_to_delete_for_similarity)

            # --- 2. Удаление устаревших и обновление важности ---
            now = datetime.now(timezone.utc)
            ids_to_delete_for_obsolescence = set()
            metadata_to_update = []
            
            for i, fact_id in enumerate(fact_ids):
                if fact_id in ids_to_delete_for_similarity: continue
                
                meta = metadatas[i]
                last_accessed_str = meta.get("last_accessed_timestamp", meta.get("timestamp_added"))
                last_accessed_dt = datetime.fromisoformat(last_accessed_str.replace("Z", "+00:00"))
                days_since_access = (now - last_accessed_dt).days
                
                # Обновление важности
                decay_check_days = config.get("days_for_decay_check", 14)
                if days_since_access > decay_check_days:
                    decay_factor = config.get("importance_decay_factor", 0.02)
                    current_importance = meta.get("importance_score", 1.0)
                    new_importance = max(0, current_importance - decay_factor)
                    if new_importance < current_importance:
                        updated_meta = meta.copy()
                        updated_meta["importance_score"] = new_importance
                        metadata_to_update.append({"id": fact_id, "metadata": updated_meta, "embedding": embeddings[i]})
                        results["updated_importance"] += 1
                        meta["importance_score"] = new_importance # Обновляем локальную копию для следующей проверки

                # Проверка на удаление
                is_obsolete = days_since_access > config.get("max_days_unaccessed", 90)
                is_unimportant = meta.get("importance_score", 1.0) < config.get("min_importance_for_retention", 0.5)
                
                if is_obsolete and is_unimportant:
                    ids_to_delete_for_obsolescence.add(fact_id)

            results["deleted_obsolete"] = len(ids_to_delete_for_obsolescence)
            
            # --- 3. Выполнение операций ---
            if metadata_to_update:
                self.update_ltm_facts_metadata(metadata_to_update)

            all_ids_to_delete = list(ids_to_delete_for_similarity.union(ids_to_delete_for_obsolescence))
            if all_ids_to_delete:
                self.delete_ltm_facts_by_ids(all_ids_to_delete)
                results["total_deleted"] = len(all_ids_to_delete)

            logger.info(f"Обслуживание LTM завершено. Результаты: {results}")
            return results
        except Exception as e:
            logger.error(f"Критическая ошибка во время обслуживания LTM: {e}", exc_info=True)
            return {"error": str(e)}

    def save_users_data(self, users_data_dict: dict):
        if self.user_data_manager: self.user_data_manager.save_users_data(users_data_dict)
        else: logger.error("MemoryManager: UserDataManager не инициализирован.")

    def get_emotional_notes(self, user_id: str) -> dict | None:
        return self.emotional_memory_handler.get_emotional_notes(user_id) if self.emotional_memory_handler else None

    def update_emotional_notes(self, user_id: str, new_note_text: str = None, interaction_summary: str = None, user_name: str = None) -> int:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.update_emotional_notes(user_id, new_note_text, interaction_summary, user_name)
        return 0 
            
    def overwrite_emotional_data_after_consolidation(self, user_id: str, consolidated_notes: list[str], new_overall_summary: str, user_name_if_missing: str = None) -> bool:
        if self.emotional_memory_handler:
            return self.emotional_memory_handler.overwrite_emotional_data_after_consolidation(user_id, consolidated_notes, new_overall_summary, user_name_if_missing)
        return False

    def clear_user_emotional_data(self, user_id: str) -> bool:
        return self.emotional_memory_handler.clear_user_emotional_data(user_id) if self.emotional_memory_handler else False

    def clear_all_emotional_data(self) -> bool:
        return self.emotional_memory_handler.clear_all_emotional_data() if self.emotional_memory_handler else False