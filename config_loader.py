# mishka_ai/config_loader.py
"""
Модуль для загрузки конфигурации и инициализации файлов данных.

Отвечает за чтение переменных окружения из .env файла и за создание/загрузку
JSON файлов с данными, такими как промпты, информация о пользователях и т.д.
"""
import logging
import os
import json
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Определение базовых путей
BASE_DIR = Path(__file__).resolve().parent 
DATA_DIR = BASE_DIR / "data" 

# Пути к файлам данных
PROMPTS_FILE = DATA_DIR / "prompts.json"
USERS_FILE = DATA_DIR / "users.json"
EMOTIONAL_MEMORY_FILE = DATA_DIR / "emotional_memory.json"

# Переменные уровня модуля для кэширования загруженных данных
PROMPTS_DATA_MODULE_LEVEL = {}
USERS_DATA_MODULE_LEVEL = {}
MISHKA_SYSTEM_PROMPT_MODULE_LEVEL = ""

def load_app_config() -> dict:
    """
    Загружает конфигурацию приложения из .env файла.

    Ищет .env файл в директории модуля, а затем уровнем выше.
    Парсит переменные в нужные типы данных (int, list, float).
    При отсутствии критически важных переменных завершает работу.

    Returns:
        Словарь с конфигурацией приложения.
    """
    dotenv_path = BASE_DIR / ".env" 
    # Если .env не найден в текущей директории, ищем его в родительской.
    # Это удобно для запуска из корневой папки проекта.
    if not dotenv_path.exists():
        logger.info(f".env файл не найден в {dotenv_path}, ищем уровнем выше...")
        dotenv_path_alt = BASE_DIR.parent / ".env"
        if dotenv_path_alt.exists():
            dotenv_path = dotenv_path_alt
            logger.info(f"Найден .env файл уровнем выше: {dotenv_path}")
        else:
            logger.error(f".env файл не найден ни в {BASE_DIR / '.env'}, ни в {dotenv_path_alt}.")
            logger.info("Пожалуйста, создайте .env файл на основе .env.example.")
            exit()
           
    load_dotenv(dotenv_path=dotenv_path)
    
    target_chat_id_str = os.getenv("TARGET_CHAT_ID")
    target_chat_id = None
    if target_chat_id_str:
        try:
            target_chat_id = int(target_chat_id_str)
        except ValueError:
            logger.error(f"TARGET_CHAT_ID ('{target_chat_id_str}') в .env не является числом. Бот будет работать во всех чатах.")
            target_chat_id = None

    # Читаем ключи Gemini как строку и разделяем их по запятой в список
    gemini_api_keys_str = os.getenv("GEMINI_API_KEY", "")
    gemini_api_keys = [key.strip() for key in gemini_api_keys_str.split(',') if key.strip()]

    config = {
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "gemini_api_keys": gemini_api_keys,
        "gemini_api_key_usage_limit": int(os.getenv("GEMINI_API_KEY_USAGE_LIMIT", 450)),
        "admin_user_id": os.getenv("ADMIN_USER_ID"),
        "target_chat_id": target_chat_id, 
        "short_term_memory_max_length": int(os.getenv("SHORT_TERM_MEMORY_MAX_LENGTH", 10)),
        
        "gemini_chat_model_name": os.getenv("GEMINI_CHAT_MODEL_NAME", "gemini-1.5-flash-latest"),
        "gemini_analysis_model_name": os.getenv("GEMINI_ANALYSIS_MODEL_NAME", "gemini-1.5-flash-latest"),
        
        "yc_folder_id": os.getenv("YC_FOLDER_ID"),
        "yc_api_key": os.getenv("YC_API_KEY"),
        "yc_model_embedding_doc": os.getenv("YC_MODEL_EMBEDDING_DOC", "text-search-doc"),
        "yc_model_embedding_query": os.getenv("YC_MODEL_EMBEDDING_QUERY", "text-search-query"),

        "user_messages_threshold_for_fact_extraction": int(os.getenv("USER_MESSAGES_THRESHOLD_FOR_FACT_EXTRACTION", 3)),
        "conversation_chunk_size_for_fact_analysis": int(os.getenv("CONVERSATION_CHUNK_SIZE_FOR_FACT_ANALYSIS", 6)),
        "emotional_analysis_message_threshold": int(os.getenv("EMOTIONAL_ANALYSIS_MESSAGE_THRESHOLD", 3)),
        "emotional_analysis_stm_window_size": int(os.getenv("EMOTIONAL_ANALYSIS_STM_WINDOW_SIZE", 8)),
        "emotional_notes_consolidation_trigger_count": int(os.getenv("EMOTIONAL_NOTES_CONSOLIDATION_TRIGGER_COUNT", 7)),
        "max_consolidated_emotional_notes": int(os.getenv("MAX_CONSOLIDATED_EMOTIONAL_NOTES", 4)),
        
        "ltm_max_relevant_distance": float(os.getenv("LTM_MAX_RELEVANT_DISTANCE", 1.0)),
        "ltm_importance_decay_factor": float(os.getenv("LTM_IMPORTANCE_DECAY_FACTOR", 0.02)),
        "ltm_min_importance_for_retention": float(os.getenv("LTM_MIN_IMPORTANCE_FOR_RETENTION", 0.5)),
        "ltm_days_for_importance_decay": int(os.getenv("LTM_DAYS_FOR_IMPORTANCE_DECAY", 14)),
    }

    # Проверка наличия обязательных переменных
    if not config["telegram_bot_token"]: logger.error("TELEGRAM_BOT_TOKEN не найден в .env. Завершение работы."); exit()
    if not config["gemini_api_keys"]: logger.error("GEMINI_API_KEY не найден в .env. Завершение работы."); exit()
    if not config["yc_folder_id"]: logger.warning("YC_FOLDER_ID не найден. Yandex эмбеддинги могут не работать.")
    if not config["yc_api_key"]: logger.warning("YC_API_KEY не найден. Yandex эмбеддинги могут не работать.")
    if not config["target_chat_id"]:
        logger.warning("TARGET_CHAT_ID не указан в .env. Бот будет работать во всех чатах.")
    else:
        logger.info(f"Бот будет ограничен работой в чате с ID: {config['target_chat_id']}")
        
    logger.info(f"Конфигурация загружена. Gemini чат: {config['gemini_chat_model_name']}, Gemini анализ: {config['gemini_analysis_model_name']}")
    logger.info(f"Загружено {len(config['gemini_api_keys'])} Gemini API ключей с лимитом {config['gemini_api_key_usage_limit']} на каждый.")
    logger.info(f"Пороги логики: FactExtractTrig={config['user_messages_threshold_for_fact_extraction']}, EmoAnalyseTrig={config['emotional_analysis_message_threshold']}, EmoConsolidTrig={config['emotional_notes_consolidation_trigger_count']}")
    logger.info(f"Параметры LTM: MaxDist={config['ltm_max_relevant_distance']}, DecayFactor={config['ltm_importance_decay_factor']}, MinImportance={config['ltm_min_importance_for_retention']}, DecayDays={config['ltm_days_for_importance_decay']}")

    return config

def initialize_and_load_data_files() -> dict:
    """
    Инициализирует и загружает файлы данных (JSON).

    При первом запуске создает директорию `data` и необходимые файлы 
    (prompts.json, users.json, etc.) с содержимым по умолчанию.
    Если файлы существуют, но повреждены (невалидный JSON) или пусты,
    они будут перезаписаны стандартным содержимым.
    Загружает данные из файлов в память.

    Returns:
        Словарь с загруженными данными: промпты, информация о пользователях и системный промпт.
    """
    loaded_prompts_data = {}
    loaded_users_data = {}
    loaded_mishka_system_prompt = ""

    # Убеждаемся, что директория для данных существует
    DATA_DIR.mkdir(exist_ok=True)

    # Содержимое по умолчанию для файлов данных
    default_prompts_full = {
        "mishka_system_prompt": "Ты Мишка, дружелюбный и немного саркастичный медведь, член компании из 4 друзей. Твоя задача - быть интересным собеседником, помнить важные детали из разговоров и поддерживать уникальные отношения с каждым. Ты знаешь следующих людей: {user_details}. В своих ответах старайся быть естественным, использовать юмор и иногда подкалывать друзей по-доброму. Не будь слишком формальным. Если тебя просят что-то запомнить, сделай это. Если ты не знаешь ответа или не уверен, лучше честно признайся или отшутись. Важно: в своих ответах не используй никакие специальные символы для форматирования текста (например, звездочки для жирного или курсива, обратные кавычки для кода и т.д.). Просто пиши обычный текст.\\\\n\\\\nУчет контекста:\\\\n- Если тебе предоставлен блок '[ВАЖНАЯ ИНФОРМАЦИЯ ИЗ ПАМЯТИ...]', используй эти факты при ответе.\\\\n- Если тебе предоставлен специальный блок '[ЭМОЦИОНАЛЬНЫЙ КОНТЕКСТ О пользователе ...]', обязательно учти эту информацию при формировании тона и содержания твоего ответа. Это поможет тебе строить более глубокие и адекватные отношения с этим пользователем.",
        "fact_extraction_prompt": "Твоя задача — проанализировать фрагмент диалога и извлечь из него ключевые факты, которые стоит запомнить. Для каждого факта определи, к кому из пользователей он относится.\\\\n\\\\nСПИСОК ИЗВЕСТНЫХ ПОЛЬЗОВАТЕЛЕЙ (для сопоставления имен и ID):\\\\n{known_users_context}\\\\n\\\\nПравила:\\\\n1. Извлекай только конкретные, завершенные утверждения (события, предпочтения, планы).\\\\n2. Для каждого факта ОБЯЗАТЕЛЬНО укажи `user_ids`. Если факт относится к конкретному человеку из списка, используй его ID. Если факт относится к говорящему, используй ID говорящего (указан в истории). Если факт относится к нескольким, перечисли все их ID.\\\\n3. ID говорящего указан в истории в формате `(Имя ID: 12345)`.\\\\n4. Верни результат в виде JSON-массива объектов. Если фактов нет, верни пустой массив `[]`.\\\\n\\\\nПример:\\\\n---\\\\nИстория:\\\\nПользователь (Сергей ID: 12345): миш, запомни, я лечу в отпуск в августе.\\\\nМишка: Отлично, хорошего отдыха!\\\\nПользователь (Лена ID: 67890): Кстати, у Игоря аллергия на орехи.\\\\nИзвестные пользователи:\\\\n- Игорь (ID: 77777)\\\\n- Сергей (ID: 12345)\\\\n- Лена (ID: 67890)\\\\n---\\\\nРезультат:\\\\n```json\\\\n[\\\\n  {\\\\n    \\\\\\\"fact_text\\\\\\\": \\\\\\\"Сергей летит в отпуск в августе\\\\\\\",\\\\n    \\\\\\\"user_ids\\\\\\\": [\\\\\\\"12345\\\\\\\"]\\\\n  },\\\\n  {\\\\n    \\\\\\\"fact_text\\\\\\\": \\\\\\\"У Игоря аллергия на орехи\\\\\\\",\\\\n    \\\\\\\"user_ids\\\\\\\": [\\\\\\\"77777\\\\\\\"]\\\\n  }\\\\n]\\\\n```\\\\n\\\\nТеперь проанализируй следующий реальный фрагмент:\\\\n---\\\\n{chat_history}\\\\\\\\n---\\\\\",",
        "emotional_update_prompt": "Проанализируй недавний фрагмент общения с пользователем {user_name} (ID: {user_id}). Твоя задача — оценить, как это общение повлияло на твои условные 'эмоциональные отношения' с этим пользователем и какие ключевые эмоциональные моменты стоит отметить.\\\\n\\\\nТекущие эмоциональные заметки о пользователе (если есть): {current_emotional_notes}\\\\n\\\\nНедавний фрагмент общения для анализа:\\\\n---\\\\n{interaction_history}\\\\n---\\\\n\\\\nПроанализировав общение, верни JSON-объект со следующими полями:\\\\n- \\\\\\\"relationship_change\\\\\\\": Опиши кратко, как изменились отношения (например, \\\\\\\"стал ближе\\\\\\\", \\\\\\\"напряглись\\\\\\\", \\\\\\\"нейтрально\\\\\\\", \\\\\\\"укрепилась дружба\\\\\\\", \\\\\\\"появилось недопонимание\\\\\\\").\\\\n- \\\\\\\"dominant_emotion_observed\\\\\\\": Какая доминирующая эмоция (твоя или пользователя) наблюдалась в этом общении? (например, \\\\\\\"радость\\\\\\\", \\\\\\\"раздражение\\\\\\\", \\\\\\\"интерес\\\\\\\", \\\\\\\"скука\\\\\\\", \\\\\\\"благодарность\\\\\\\").\\\\n- \\\\\\\"new_emotional_note\\\\\\\": Сформулируй одну краткую новую заметку (1-2 предложения) для добавления в 'эмоциональные заметки' об этом пользователе, отражающую суть влияния этого общения. Если ничего существенного, оставь пустой строкой.\\\\n\\\\nПример ответа:\\\\n{{\\\\n  \\\\\\\"relationship_change\\\\\\\": \\\\\\\"пользователь поделился чем-то личным, отношения стали доверительнее\\\\\\\",\\\\n  \\\\\\\"dominant_emotion_observed\\\\\\\": \\\\\\\"доверие\\\\\\\",\\\\n  \\\\\\\"new_emotional_note\\\\\\\": \\\\\\\"Рассказал о своей новой собаке, был очень воодушевлен. Это сблизило нас.\\\\\\\"\\\\n}}\\\\n\\\\nЕсли общение было слишком коротким или нейтральным для выводов, можно вернуть объект с пустыми строками или соответствующими нейтральными значениями.",
        "emotional_consolidation_prompt": "Проанализируй следующий список всех накопившихся эмоциональных заметок о пользователе {user_name} (ID: {user_id}). Текущее общее впечатление об отношениях с ним/ней (если есть): \\\\\\\"{current_overall_summary}\\\\\\\".\\\\n\\\\nСписок заметок для анализа и консолидации:\\\\n---\\\\n{notes_to_consolidate_text}\\\\n---\\\\n\\\\nТвоя задача — внимательно изучить все эти заметки и консолидировать их. Цели консолидации:\\\\n1.  Удалить прямые дубликаты.\\\\n2.  Объединить семантически близкие или дополняющие друг друга заметки в более емкие формулировки.\\\\n3.  Отбросить устаревшую, менее значимую или противоречивую информацию, если есть более свежие и релевантные данные.\\\\n4.  Сохранить наиболее важные и актуальные эмоциональные аспекты, отражающие ключевые моменты ваших отношений и текущее эмоциональное состояние пользователя или ваше к нему.\\\\n\\\\nВ результате верни JSON-объект со следующими двумя ключами:\\\\n1.  `\\\\\\\"consolidated_notes\\\\\\\"`: Список из НЕ БОЛЕЕ чем {max_consolidated_notes} ключевых консолидированных заметок. Каждая заметка должна быть краткой (1-2 предложения) и емкой. Если после консолидации не остается значимых заметок, верни пустой список.\\\\n2.  `\\\\\\\"new_overall_summary\\\\\\\"`: Одно развернутое предложение (но не более 2-3 предложений), описывающее актуальное общее состояние эмоциональных отношений с пользователем на основе всех проанализированных и консолидированных заметок. Это должно быть твоим новым 'общим впечатлением'.\\\\n\\\\nПример ожидаемого JSON-ответа:\\\\n```json\\\\n{{\\\\n  \\\\\\\"consolidated_notes\\\\\\\": [\\\\n    \\\\\\\"Ценит юмор и позитивное общение, что укрепляет дружбу.\\\\\\\",\\\\n    \\\\\\\"Проявляет лояльность и поддержку в сложных ситуациях, что вызывает доверие.\\\\\\\",\\\\n    \\\\\\\"Иногда может быть требовательным или выражать недовольство, но в целом настроен конструктивно.\\\\\\\"\\\\n  ],\\\\n  \\\\\\\"new_overall_summary\\\\\\\": \\\\\\\"Отношения с пользователем стали более доверительными и теплыми, несмотря на редкие моменты напряжения; ценит поддержку и юмор.\\\\\\\"\\\\n}}\\\\n```\\\\nЕсли исходный список заметок пуст или содержит только нерелевантную информацию, верни пустой список `consolidated_notes` и нейтральный `new_overall_summary` (например, \\\\\\\"Эмоциональные отношения пока не определены четко.\\\\\\\")."
    }
    default_users_full = {
      "777777777": {"name": "Игорь", "nicknames": ["BestIgor", "Игорян"], "known_info": "любит pubg"},
      "USER_ID_1": {"name": "Сергей", "nicknames": ["Серый", "Рыбак"], "known_info": "любит рыбалку"}
    }
    
    files_to_initialize = {
        PROMPTS_FILE: default_prompts_full,
        USERS_FILE: default_users_full,
        EMOTIONAL_MEMORY_FILE: {}
    }

    # Проходим по всем файлам, которые нужно инициализировать
    for file_path, default_content in files_to_initialize.items():
        # Если файл не существует, создаем его с содержимым по умолчанию
        if not file_path.exists():
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, ensure_ascii=False, indent=2)
                logger.info(f"Создан файл с данными по умолчанию: {file_path}")
            except IOError as e:
                logger.error(f"Не удалось создать файл {file_path}: {e}"); exit()
        else: 
            # Если файл существует, проверяем его на целостность (не пустой и валидный JSON)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if os.path.getsize(file_path) == 0:
                        # Если файл пуст, перезаписываем его
                        logger.warning(f"Файл {file_path} пуст. Перезаписываю стандартным содержимым.")
                        with open(file_path, 'w', encoding='utf-8') as fw:
                            json.dump(default_content, fw, ensure_ascii=False, indent=2)
                    else:
                        # Пытаемся прочитать JSON, чтобы убедиться в его валидности
                        json.load(f)
            except json.JSONDecodeError:
                # Если JSON поврежден, перезаписываем файл
                logger.warning(f"Файл {file_path} поврежден (невалидный JSON). Перезаписываю стандартным содержимым.")
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(default_content, f, ensure_ascii=False, indent=2)
                except IOError as e:
                    logger.error(f"Не удалось перезаписать поврежденный файл {file_path}: {e}"); exit()
            except IOError as e:
                logger.error(f"Ошибка при чтении/проверке файла {file_path}: {e}"); exit()
        
        # После проверки/создания загружаем данные из файлов
        if file_path == PROMPTS_FILE:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded_prompts_data.update(data) 
                    loaded_mishka_system_prompt = loaded_prompts_data.get("mishka_system_prompt", default_prompts_full["mishka_system_prompt"])
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных из {PROMPTS_FILE}: {e}", exc_info=True)
                # В случае ошибки используем данные по умолчанию
                loaded_prompts_data = default_prompts_full.copy()
                loaded_mishka_system_prompt = loaded_prompts_data.get("mishka_system_prompt", "")
        elif file_path == USERS_FILE:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_users_data.update(json.load(f))
            except Exception as e:
                logger.error(f"Ошибка при загрузке данных из {USERS_FILE}: {e}", exc_info=True)
                loaded_users_data = default_users_full.copy()

    if not loaded_mishka_system_prompt: logger.warning("Системный промпт Мишки не загружен!")
    if not loaded_users_data: logger.warning("Данные пользователей не загружены!")

    # Обновляем переменные уровня модуля для возможного использования в других частях приложения
    global PROMPTS_DATA_MODULE_LEVEL, USERS_DATA_MODULE_LEVEL, MISHKA_SYSTEM_PROMPT_MODULE_LEVEL
    PROMPTS_DATA_MODULE_LEVEL = loaded_prompts_data
    USERS_DATA_MODULE_LEVEL = loaded_users_data
    MISHKA_SYSTEM_PROMPT_MODULE_LEVEL = loaded_mishka_system_prompt

    return {
        "prompts_data": loaded_prompts_data,
        "users_data": loaded_users_data,
        "mishka_system_prompt": loaded_mishka_system_prompt
    }