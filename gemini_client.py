# mishka_ai/gemini_client.py
"""
Модуль для взаимодействия с API Google Gemini.

Содержит класс `GeminiClient`, который инкапсулирует логику отправки запросов,
обработки ответов, ротации API-ключей и автоматических повторных попыток
при сбоях сети или API.
"""
import google.generativeai as genai
import logging
import asyncio
import functools 
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import google.api_core.exceptions 
from typing import TYPE_CHECKING

# Используется для аннотации типов, чтобы избежать циклических импортов
if TYPE_CHECKING:
    from mishka_ai.api_key_manager import ApiKeyManager

logger = logging.getLogger(__name__)

# Кортеж исключений API, при которых имеет смысл делать повторные попытки
RETRYABLE_API_EXCEPTIONS = (
    google.api_core.exceptions.ResourceExhausted,   # Лимиты API исчерпаны (429)
    google.api_core.exceptions.DeadlineExceeded,    # Превышено время ожидания
    google.api_core.exceptions.ServiceUnavailable,  # Сервис временно недоступен (503)
    google.api_core.exceptions.InternalServerError, # Внутренняя ошибка сервера (500)
    google.api_core.exceptions.Aborted,             # Запрос был прерван
    google.api_core.exceptions.Unknown,             # Неизвестная ошибка
)

def _filter_history_for_gemini(history: list[dict]) -> list[dict]:
    """
    Фильтрует историю сообщений, оставляя только поля, совместимые с Gemini API.

    API Gemini ожидает, что каждый элемент истории будет словарем с ключами 'role' и 'parts'.
    Эта функция удаляет любые кастомные поля (например, 'user_name', 'user_id'),
    добавленные для внутренних нужд приложения.

    Args:
        history: Список словарей, представляющих историю диалога.

    Returns:
        Отфильтрованный список словарей, готовый для передачи в API.
    """
    if not history:
        return []
    
    filtered_history = []
    for message in history:
        filtered_message = {
            "role": message.get("role"),
            "parts": message.get("parts")
        }
        # Добавляем в историю только валидные сообщения
        if filtered_message["role"] is not None and filtered_message["parts"] is not None:
            filtered_history.append(filtered_message)
        else:
            logger.warning(f"Сообщение в истории пропущено из-за отсутствия 'role' или 'parts': {message}")
            
    return filtered_history

class GeminiClient:
    """
    Клиент для взаимодействия с Google Gemini API.

    Обеспечивает ротацию API-ключей через `ApiKeyManager` и автоматические
    повторные попытки при возникновении определенных ошибок.
    """
    def __init__(self, api_key_manager: 'ApiKeyManager', model_name: str = "gemini-1.5-flash-latest"):
        """
        Инициализирует GeminiClient.

        Args:
            api_key_manager: Экземпляр `ApiKeyManager` для управления ключами.
            model_name: Название модели Gemini для использования (например, "gemini-1.5-flash-latest").
        """
        self.api_key_manager = api_key_manager
        self.model_name = model_name
        self._model = None  # Экземпляр модели genai.GenerativeModel
        self._current_api_key = None  # Хранит ключ, с которым была инициализирована модель
        logger.info(f"GeminiClient инициализирован для модели: {self.model_name}")

    def _configure_api(self, api_key: str):
        """Конфигурирует библиотеку `genai` с предоставленным API-ключом."""
        try:
            genai.configure(api_key=api_key)
            logger.info(f"API ключ Google Gemini успешно сконфигурирован (ключ заканчивается на ...{api_key[-4:]}).")
        except Exception as e:
            logger.error(f"Ошибка при конфигурации API ключа Google Gemini: {e}", exc_info=True)

    async def _initialize_model(self):
        """
        Инициализирует или переинициализирует модель Gemini.

        Получает свежий API-ключ от менеджера. Если ключ изменился или модель
        еще не была создана, происходит (пере)конфигурация API и создание
        нового экземпляра модели.
        """
        new_api_key = self.api_key_manager.get_key()
        if not new_api_key:
            logger.error("Не удалось получить API ключ от менеджера. Инициализация модели невозможна.")
            self._model = None
            return

        # Переинициализация нужна, если ключ сменился или модель еще не создана
        if self._model is None or self._current_api_key != new_api_key:
            self._configure_api(new_api_key)
            self._current_api_key = new_api_key
            try:
                self._model = genai.GenerativeModel(self.model_name)
                logger.info(f"Модель Gemini '{self.model_name}' успешно инициализирована/переинициализирована.")
            except Exception as e:
                logger.error(f"Не удалось инициализировать модель Gemini '{self.model_name}': {e}", exc_info=True)
                self._model = None

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=1, max=10), 
        retry=retry_if_exception_type(RETRYABLE_API_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True 
    )
    async def _generate_content_with_retry(self, content_parts: list):
        """
        Внутренний метод для вызова API с логикой повторных попыток.
        
        Использует декоратор `retry` из библиотеки `tenacity` для автоматической
        обработки временных ошибок API.
        
        Raises:
            RuntimeError: Если модель не инициализирована.
            google.api_core.exceptions.*: Если все попытки не увенчались успехом.
        """
        if not self._model:
            await self._initialize_model()
            if not self._model:
                 logger.error("Модель Gemini не инициализирована, не могу выполнить _generate_content_with_retry.")
                 raise RuntimeError("Модель Gemini не инициализирована для _generate_content_with_retry")

        attempt_num = self._generate_content_with_retry.retry.statistics.get('attempt_number', 1)
        filtered_content_parts = _filter_history_for_gemini(content_parts)
        logger.debug(f"Вызов _generate_content_with_retry (попытка: {attempt_num}). Количество частей (после фильтрации): {len(filtered_content_parts)}")
        
        # Проверка на случай, если фильтрация удалила все сообщения
        if not filtered_content_parts and content_parts:
            logger.warning(f"После фильтрации content_parts для Gemini не осталось валидных сообщений. Исходное кол-во: {len(content_parts)}")

        return await self._model.generate_content_async(filtered_content_parts)


    async def generate_response(self, prompt_text: str, history: list = None) -> str | None:
        """
        Генерирует текстовый ответ от Gemini, управляя сессией и API-ключами.

        Args:
            prompt_text: Текст текущего запроса пользователя.
            history: Список сообщений для поддержания контекста диалога.

        Returns:
            Сгенерированный текст ответа или сообщение об ошибке.
        """
        await self._initialize_model()

        if self._model is None: 
            logger.error("Модель Gemini не инициализирована. Невозможно сгенерировать ответ.")
            return "Простите, у меня возникли технические шоколадки с подключением к моему разуму. Попробуйте позже."

        chat_session = None
        filtered_chat_history = _filter_history_for_gemini(history or [])

        # Пытаемся создать сессию чата, если есть история
        if filtered_chat_history and prompt_text: 
            try:
                loop = asyncio.get_running_loop()
                chat_starter = functools.partial(self._model.start_chat, history=filtered_chat_history) 
                chat_session = await loop.run_in_executor(None, chat_starter)
                logger.debug(f"Сессия чата Gemini создана с историей: {len(filtered_chat_history)} сообщений.")
            except Exception as e:
                logger.warning(f"Не удалось создать сессию чата Gemini: {e}. Будет использован generate_content.", exc_info=True)
                chat_session = None

        response_candidate = None
        try:
            if chat_session:
                logger.debug(f"Отправка запроса в Gemini (чат-сессия). Промпт: {prompt_text[:200]}...")
                try:
                    response_candidate = await chat_session.send_message_async(prompt_text)
                except RETRYABLE_API_EXCEPTIONS as e_chat:
                    logger.warning(f"Ошибка в чат-сессии Gemini: {type(e_chat).__name__} - {e_chat}. Попытка через generate_content с retry...")
                    chat_session = None # Откатываемся к простому вызову
                except Exception as e_chat_other:
                    logger.error(f"Непредвиденная ошибка в чат-сессии Gemini: {type(e_chat_other).__name__} - {e_chat_other}", exc_info=True)
                    chat_session = None # Откатываемся к простому вызову
            
            # Если сессии нет (изначально или после ошибки), используем `generate_content`
            if not chat_session:
                logger.debug(f"Отправка запроса в Gemini (generate_content с retry). Промпт: {prompt_text[:200] if prompt_text else 'История передана'}")
                
                full_content_parts = []
                if history:
                    full_content_parts.extend(filtered_chat_history if filtered_chat_history else _filter_history_for_gemini(history))
                
                if prompt_text:
                    full_content_parts.append({"role": "user", "parts": [prompt_text]})
                
                if not full_content_parts:
                    logger.warning("Нет данных для отправки в generate_content_async (после фильтрации и добавления промпта).")
                    return "Хм, ты ничего не спросил, и истории нет, или история была некорректной."
                
                response_candidate = await self._generate_content_with_retry(content_parts=full_content_parts)
            
            if response_candidate is None: 
                logger.warning("Ответ Gemini отсутствует (None).")
                return "Хм, я не смог ничего сгенерировать по твоему запросу."

            # Проверка, был ли запрос заблокирован системой безопасности
            if not response_candidate.candidates:
                if response_candidate.prompt_feedback and response_candidate.prompt_feedback.block_reason:
                    block_reason_msg = response_candidate.prompt_feedback.block_reason_message or str(response_candidate.prompt_feedback.block_reason)
                    logger.warning(f"Запрос к Gemini был заблокирован. Причина: {block_reason_msg}")
                    return "Мой ответ был заблокирован системой безопасности. Возможно, в запросе было что-то неоднозначное."
                else:
                    logger.warning("Ответ Gemini не содержит кандидатов (пустой ответ).")
                    return "Хм, на это у меня нет ответа. Попробуй переформулировать."

            # Извлечение текста из ответа
            final_text = ""
            if hasattr(response_candidate, 'text') and response_candidate.text:
                final_text = response_candidate.text
            elif response_candidate.candidates[0].content and response_candidate.candidates[0].content.parts:
                final_text = "".join(part.text for part in response_candidate.candidates[0].content.parts if hasattr(part, 'text'))
            
            if final_text:
                logger.info(f"Ответ от Gemini получен. Длина: {len(final_text)} символов.")
                return final_text.strip()
            else:
                logger.warning("Не удалось извлечь текст из ответа Gemini (response.text и parts пусты).")
                return "Я что-то сгенерировал, но не могу это произнести. Странно..."

        # Обработка исключений
        except RETRYABLE_API_EXCEPTIONS as e: 
            logger.error(f"Все попытки вызова Gemini API не увенчались успехом после retry: {type(e).__name__} - {e}", exc_info=True)
            return "Кажется, у меня временные неполадки с подключением к моему разуму. Пожалуйста, попробуй через пару минут."
        except genai.types.BlockedPromptException as e_block: 
            logger.warning(f"Запрос к Gemini заблокирован (BlockedPromptException): {e_block}")
            reason_message = "причина не указана"
            if hasattr(response_candidate, 'prompt_feedback') and response_candidate.prompt_feedback:
                 reason_message = response_candidate.prompt_feedback.block_reason_message or str(response_candidate.prompt_feedback.block_reason)
            logger.warning(f"Причина блокировки промпта: {reason_message}")
            return f"Ой, кажется, твой запрос нарушает какие-то мои внутренние правила (Причина: {reason_message}). Попробуй спросить иначе."
        except Exception as e_unhandled:
            logger.error(f"Непредвиденная ошибка при взаимодействии с Gemini API: {type(e_unhandled).__name__} - {e_unhandled}", exc_info=True)
            return "Упс! Кажется, у меня что-то сломалось внутри. Дай знать моему создателю, пожалуйста."