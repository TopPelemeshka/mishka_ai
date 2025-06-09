# mishka_ai/memory_components/fact_extractor.py
"""
Модуль для извлечения структурированных фактов из истории диалога.
"""
import logging
import json
# Используется для аннотации типов, чтобы избежать циклических импортов
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mishka_ai.gemini_client import GeminiClient as GeminiClientType

logger = logging.getLogger(__name__)

class FactExtractor:
    """
    Инкапсулирует логику извлечения фактов из диалога с помощью LLM.

    Формирует специальный промпт на основе истории сообщений и списка
    известных пользователей, отправляет его LLM и парсит JSON-ответ.
    """
    def __init__(self, fact_extraction_prompt_template: str):
        """
        Инициализирует экстрактор фактов.

        Args:
            fact_extraction_prompt_template: Шаблон промпта из `prompts.json`,
                который будет использоваться для задачи извлечения.
        """
        self.prompt_template = fact_extraction_prompt_template
        if not self.prompt_template:
            logger.error("FactExtractor: Шаблон промпта для извлечения фактов не предоставлен! Извлечение будет невозможно.")
            self.prompt_template = None 

    async def extract_facts_from_history(self, 
                                         chat_history_messages: list[dict], 
                                         gemini_client: 'GeminiClientType',
                                         known_users_context_str: str
                                         ) -> list[dict]:
        """
        Извлекает факты из истории чата с помощью LLM.

        Args:
            chat_history_messages: Список сообщений из краткосрочной памяти для анализа.
            gemini_client: Клиент Gemini для выполнения запроса.
            known_users_context_str: Строка с перечислением известных пользователей
                и их ID для помощи LLM в сопоставлении.

        Returns:
            Список словарей, где каждый словарь представляет факт и содержит
            ключи 'fact_text' и 'user_ids'.
        """
        if not self.prompt_template:
            logger.error("FactExtractor: Промпт для извлечения фактов не настроен. Извлечение отменено.")
            return []
        if not chat_history_messages:
            logger.debug("FactExtractor: История чата для извлечения фактов пуста.")
            return []

        # 1. Форматируем историю чата в текстовый вид для промпта.
        history_text_for_prompt = ""
        for msg in chat_history_messages:
            role_display = "Пользователь" if msg.get("role") == "user" else "Мишка"
            user_name_for_display = msg.get("user_name", "Неизвестный")
            user_id_for_display = msg.get("user_id") 

            user_info_str = ""
            if role_display == "Пользователь":
                user_info_str = f" ({user_name_for_display}"
                if user_id_for_display:
                    user_info_str += f" ID: {user_id_for_display}"
                user_info_str += ")"
            
            text_parts = msg.get("parts", [])
            text = text_parts[0] if text_parts else "" 
            history_text_for_prompt += f"{role_display}{user_info_str}: {text}\n"
        
        history_text_for_prompt_stripped = history_text_for_prompt.strip()
        if not history_text_for_prompt_stripped:
            logger.debug("FactExtractor: Сформированный текст истории для извлечения фактов пуст.")
            return []

        # 2. Форматируем финальный промпт, подставляя историю и контекст пользователей.
        try:
            # Убедитесь, что в prompts.json есть плейсхолдеры {chat_history} и {known_users_context}
            prompt_for_gemini = self.prompt_template.format(
                chat_history=history_text_for_prompt_stripped,
                known_users_context=known_users_context_str
            )
        except KeyError as e:
            logger.error(f"FactExtractor: КРИТИЧЕСКАЯ ОШИБКА форматирования промпта. Отсутствует ключ: {e}. "
                         f"Убедитесь, что плейсхолдеры в prompts.json корректны.")
            return []
        except Exception as e_fmt: 
            logger.error(f"FactExtractor: НЕОЖИДАННАЯ ОШИБКА форматирования промпта: {e_fmt}.", exc_info=True)
            return []

        # 3. Вызываем LLM для анализа.
        logger.info(f"FactExtractor: Запрос к Gemini (модель: {gemini_client.model_name}) для извлечения фактов...")

        # ✅✅✅ ДОБАВЬТЕ ЭТУ СТРОКУ ✅✅✅
        logger.debug(f"===== ПОЛНЫЙ ПРОМПТ ДЛЯ GEMINI (EXTRACT_FACTS) =====\n{prompt_for_gemini}\n=====================================================")

        extracted_data_str = await gemini_client.generate_response(prompt_text=prompt_for_gemini, history=None)
        logger.info(f"FactExtractor: Ответ от Gemini (сырой, до 500 симв.): '{str(extracted_data_str)[:500]}'")

        if not extracted_data_str or extracted_data_str.strip() == "[]":
            logger.info("FactExtractor: Gemini не извлек фактов или вернул пустой массив.")
            return []

        # 4. Парсим JSON-ответ от LLM.
        extracted_facts_with_users = []
        try:
            # Очищаем ответ от возможных ```json ``` оберток
            clean_json_str = extracted_data_str.strip()
            if clean_json_str.startswith("```json"):
                clean_json_str = clean_json_str[len("```json"):]
            if clean_json_str.startswith("```"):
                 clean_json_str = clean_json_str[len("```"):]
            if clean_json_str.endswith("```"):
                clean_json_str = clean_json_str[:-len("```")]
            clean_json_str = clean_json_str.strip()

            if not clean_json_str:
                logger.info("FactExtractor: Ответ Gemini стал пустым после очистки.")
                return []

            logger.debug(f"FactExtractor: Строка для парсинга JSON после очистки: '{clean_json_str[:500]}'")
            parsed_data = json.loads(clean_json_str)

            # 5. Валидируем извлеченные данные.
            if isinstance(parsed_data, list):
                for item_idx, item in enumerate(parsed_data):
                    if isinstance(item, dict):
                        fact_text = item.get("fact_text", "").strip()
                        user_ids = item.get("user_ids", [])
                        
                        # Приводим user_ids к списку строк
                        if not isinstance(user_ids, list):
                            logger.warning(f"FactExtractor: 'user_ids' в элементе #{item_idx} не является списком. Факт: '{fact_text}'.")
                            user_ids = []
                        else:
                            user_ids = [str(uid) for uid in user_ids if uid is not None] 
                        
                        if fact_text: 
                            extracted_facts_with_users.append({"fact_text": fact_text, "user_ids": user_ids})
                        else:
                            logger.warning(f"FactExtractor: Пустой 'fact_text' в элементе #{item_idx} от Gemini: {item}")
                    else:
                        logger.warning(f"FactExtractor: Элемент #{item_idx} в JSON-массиве не является словарем: {item}")
            else:
                logger.warning(f"FactExtractor: Ответ Gemini не является JSON-массивом, а {type(parsed_data)}.")

        except json.JSONDecodeError:
            logger.error(f"FactExtractor: Не удалось распарсить JSON из ответа Gemini. Строка: '{clean_json_str[:500]}'")
        except Exception as e_parse:
            logger.error(f"FactExtractor: Непредвиденная ошибка при парсинге ответа Gemini: {e_parse}", exc_info=True)

        if extracted_facts_with_users:
            logger.info(f"FactExtractor: Успешно извлечено {len(extracted_facts_with_users)} фактов с привязкой к пользователям.")
        else:
            logger.info("FactExtractor: Факты не были извлечены или не прошли валидацию после парсинга.")
            
        return extracted_facts_with_users