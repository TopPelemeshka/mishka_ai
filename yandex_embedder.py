# mishka_ai/yandex_embedder.py
import logging
import asyncio
from yandex_cloud_ml_sdk import YCloudML 

logger = logging.getLogger(__name__)

class YandexEmbedder:
    def __init__(self, 
                 folder_id: str, 
                 auth_credentials: str, 
                 doc_model_name: str = "text-search-doc",  # Имя модели для документов
                 query_model_name: str = "text-search-query" # Имя модели для запросов
                ):
        self.folder_id = folder_id
        self.auth_credentials = auth_credentials
        
        self.doc_model_name_internal = doc_model_name
        self.query_model_name_internal = query_model_name

        self.yc_sdk = None
        self._model_cache = {} 

        if not self.folder_id or not self.auth_credentials:
            logger.error("YandexEmbedder: YC_FOLDER_ID или аутентификационные данные не установлены.")
            return

        try:
            self.yc_sdk = YCloudML(folder_id=self.folder_id, auth=self.auth_credentials) 
            logger.info("YandexEmbedder: YCloudML SDK инициализирован (или предпринята попытка).")
        except Exception as e:
            logger.error(f"YandexEmbedder: Ошибка инициализации YCloudML SDK: {e}", exc_info=True)
            self.yc_sdk = None
            
    def _get_model_from_cache(self, model_name_key: str): # model_name_key это doc_model_name_internal или query_model_name_internal
        if not self.yc_sdk:
            logger.error("Yandex SDK не был инициализирован в YandexEmbedder.")
            return None
        
        if model_name_key not in self._model_cache:
            try:
                # model_name_key уже должно быть правильным именем для YCloudML
                self._model_cache[model_name_key] = self.yc_sdk.models.text_embeddings(model_name=model_name_key, model_version="latest")
                logger.info(f"Yandex embedding model '{model_name_key}' initialized and cached.")
            except Exception as e:
                logger.error(f"Failed to initialize Yandex embedding model '{model_name_key}': {e}", exc_info=True)
                return None
        return self._model_cache[model_name_key]

    async def get_embedding(self, text: str, model_type: str = "doc") -> list[float] | None:
        """
        Получает эмбеддинг для текста.
        model_type: "doc" или "query", чтобы выбрать соответствующую модель.
        """
        if not self.yc_sdk:
            logger.error("Yandex SDK не инициализирован в YandexEmbedder. Невозможно получить эмбеддинг.")
            return None
        
        text_to_embed = " ".join(text.strip().split())
        if not text_to_embed:
            logger.warning("Попытка получить эмбеддинг для пустого текста.")
            return None

        actual_model_name_to_use = self.doc_model_name_internal if model_type == "doc" else self.query_model_name_internal
        
        loop = asyncio.get_running_loop()
        try:
            embedder_model = self._get_model_from_cache(actual_model_name_to_use)
            if not embedder_model:
                logger.error(f"Модель эмбеддинга '{actual_model_name_to_use}' (тип: {model_type}) не доступна.")
                return None

            def sync_embed_run(txt):
                return embedder_model.run(txt)
            
            result_object = await loop.run_in_executor(None, sync_embed_run, text_to_embed)

            if hasattr(result_object, 'embedding') and result_object.embedding:
                return list(result_object.embedding)
            else:
                logger.error(f"Yandex API не вернул эмбеддинг для текста: '{text_to_embed[:50]}...'. Result: {result_object}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении Yandex эмбеддинга для '{text_to_embed[:50]}...' (модель: '{actual_model_name_to_use}', тип: '{model_type}'): {e}", exc_info=True)
            return None