# mishka_ai/bot.py
"""
Основной файл для запуска Telegram-бота Mishka AI.

Этот файл отвечает за:
- Инициализацию конфигурации и загрузку данных.
- Создание и настройку всех ключевых компонентов: клиентов API, менеджеров памяти.
- Регистрацию обработчиков команд и сообщений Telegram.
- Настройку и запуск фоновых задач (обслуживание памяти, сброс лимитов API).
- Корректный запуск и graceful shutdown бота.
"""
import logging
import logging.handlers # <--- ДОБАВИТЬ ЭТОТ ИМПОРТ
import os
import asyncio
import json
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импорт внутренних модулей проекта
from mishka_ai.config_loader import (
    load_app_config, initialize_and_load_data_files, DATA_DIR
)
from mishka_ai.gemini_client import GeminiClient
from mishka_ai.api_key_manager import ApiKeyManager
from mishka_ai.short_term_memory import ShortTermMemory
from mishka_ai.handlers.user_commands.general_commands import (
    start_command, help_command, chat_id_command
)
from mishka_ai.handlers.admin_commands.user_data_commands import (
    list_users_command, show_user_info_command
)
from mishka_ai.handlers.admin_commands.memory_commands import (
    memory_stats_command, list_facts_command, facts_page_callback,
    find_facts_command, delete_fact_command,
    clear_ltm_command, confirm_clear_ltm_callback,
    clear_emotional_user_command, confirm_clear_emotional_user_callback,
    clear_emotional_all_danger_command, confirm_clear_emotional_all_callback,
    maintain_ltm_command
)
from mishka_ai.handlers.admin_commands.general_admin_commands import toggle_bot_active_command
from mishka_ai.handlers.message_handler import handle_message
from mishka_ai.memory_manager import MemoryManager

class GrpcBlockFilter(logging.Filter):
    """
    Фильтр для логов, подавляющий специфичные и некритичные ошибки asyncio от gRPC.
    
    Иногда библиотека google-generativeai генерирует ошибку BlockingIOError,
    которая не влияет на работу, но засоряет логи. Этот фильтр скрывает ее.
    """
    def filter(self, record):
        is_asyncio_error = record.name == 'asyncio' and record.levelno == logging.ERROR
        is_grpc_blocking_error = 'BlockingIOError' in record.getMessage() and \
                                 'PollerCompletionQueue' in record.getMessage() and \
                                 'Resource temporarily unavailable' in record.getMessage()
        
        # Если это именно та ошибка, которую мы хотим скрыть, не пропускаем ее дальше
        if is_asyncio_error and is_grpc_blocking_error:
            return False 
        return True

# Начальная проверка доступности uvloop (будет использован, если найден)
UVLOOP_AVAILABLE = False
try:
    import uvloop
    uvloop.install()
    UVLOOP_AVAILABLE = True
except ImportError:
    pass

def setup_logging():
    """Настраивает продвинутое логирование в консоль и в ротируемые файлы."""
    log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    log_dir = "logs"
    
    # Создаем папку для логов, если ее нет
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 1. Основной обработчик для файла INFO
    info_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, "mishka_info.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setFormatter(log_formatter)
    info_handler.setLevel(logging.INFO)

    # 2. Обработчик для файла DEBUG (пишет все, включая инфо)
    debug_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, "mishka_debug.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    debug_handler.setFormatter(log_formatter)
    debug_handler.setLevel(logging.DEBUG)

    # 3. Обработчик для вывода в консоль (как раньше)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)

    # Получаем корневой логгер и настраиваем его
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Устанавливаем самый низкий уровень на корень
    root_logger.addHandler(console_handler)
    root_logger.addHandler(info_handler)
    root_logger.addHandler(debug_handler)

    # Применение фильтра к логгеру asyncio
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.addFilter(GrpcBlockFilter())
    asyncio_logger.setLevel(logging.WARNING)

    # Понижение уровня логирования для "шумных" библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
    logging.getLogger("telegram.bot").setLevel(logging.INFO)

# Вызываем нашу новую функцию для настройки логирования
setup_logging()
logger = logging.getLogger(__name__)

async def scheduled_ltm_maintenance_job(application: Application):
    """
    Задача, выполняемая по расписанию (ежедневно в 4:00) для обслуживания долгосрочной памяти (LTM).
    
    Задача удаляет дубликаты и устаревшие факты, а также обновляет "важность" фактов.
    Отправляет отчет о результатах администратору бота.
    """
    logger.info("Scheduler: Запуск планового обслуживания LTM...")
    memory_manager: MemoryManager = application.bot_data.get("memory_manager")
    admin_user_id = application.bot_data.get("admin_user_id")

    if not memory_manager:
        logger.error("Scheduler: MemoryManager не найден. Обслуживание LTM пропущено.")
        return

    # Загрузка параметров обслуживания из `bot_data`, куда они были помещены при запуске
    maintenance_config = {
        "similarity_threshold": 0.95,
        "max_days_unaccessed": 90,
        "min_access_for_retention": 1,
        "importance_decay_factor": application.bot_data.get("LTM_IMPORTANCE_DECAY_FACTOR_CONFIG", 0.02),
        "min_importance_for_retention": application.bot_data.get("LTM_MIN_IMPORTANCE_FOR_RETENTION_CONFIG", 0.5),
        "days_for_decay_check": application.bot_data.get("LTM_DAYS_FOR_IMPORTANCE_DECAY_CONFIG", 14)
    }

    try:
        results = await memory_manager.perform_ltm_maintenance(maintenance_config)
        
        # Отправка отчета администратору, если были произведены какие-либо изменения
        if admin_user_id and (results.get("total_deleted", 0) > 0 or results.get("updated_importance", 0) > 0):
            report_text = (
                f"⚙️ *Плановое обслуживание LTM завершено (auto)*\n\n"
                f"   *Отчет по оптимизации:*\n"
                f"   - Устранено дубликатов/схожих: {results.get('deleted_duplicates', 0)}\n"
                f"   - Удалено устаревших/неважных: {results.get('deleted_obsolete', 0)}\n"
                f"   - *Всего записей удалено:* {results.get('total_deleted', 0)}\n"
                f"   - *Пересчитана важность (decay):* {results.get('updated_importance', 0)} фактов."
            )
            await application.bot.send_message(chat_id=admin_user_id, text=report_text, parse_mode='Markdown')
        elif results.get("error"):
            logger.error(f"Scheduler: Ошибка во время обслуживания LTM: {results['error']}")
            if admin_user_id:
                await application.bot.send_message(chat_id=admin_user_id, text=f"Scheduler: Ошибка во время обслуживания LTM: {results['error']}")

    except Exception as e:
        logger.error(f"Scheduler: Критическая ошибка в задаче обслуживания LTM: {e}", exc_info=True)
        if admin_user_id:
            try:
                await application.bot.send_message(chat_id=admin_user_id, text=f"Scheduler: Критическая ошибка в задаче обслуживания LTM: {e}")
            except Exception as send_e:
                logger.error(f"Scheduler: Не удалось отправить сообщение об ошибке администратору: {send_e}")

async def scheduled_api_key_reset_job(application: Application):
    """
    Задача, выполняемая по расписанию (ежедневно в 00:01) для сброса счетчиков использования API-ключей.
    """
    logger.info("Scheduler: Запуск планового сброса счетчиков API ключей...")
    api_key_manager: ApiKeyManager = application.bot_data.get("gemini_api_key_manager")
    if api_key_manager:
        api_key_manager.reset_daily_counts()
    else:
        logger.error("Scheduler: ApiKeyManager не найден. Сброс счетчиков пропущен.")


async def run_bot():
    """Основная асинхронная функция для инициализации и запуска бота."""

    # 1. Загрузка конфигурации и данных
    # Загружаем переменные из .env и инициализируем файлы данных (prompts.json, users.json и т.д.)
    app_config = load_app_config()
    loaded_data = initialize_and_load_data_files() 
    
    mishka_system_prompt = loaded_data["mishka_system_prompt"]
    users_data_dict = loaded_data["users_data"] 
    all_prompts_data = loaded_data["prompts_data"]

    logger.info(f"bot.py: Загружен системный промпт: {mishka_system_prompt[:70]}...")
    logger.info(f"bot.py: Загружены данные пользователей: {len(users_data_dict)} записей.")

    # 2. Инициализация ключевых компонентов
    # Создаем менеджер API-ключей для их ротации
    gemini_api_key_manager = ApiKeyManager(
        api_keys=app_config["gemini_api_keys"],
        usage_limit=app_config["gemini_api_key_usage_limit"]
    )

    # Создаем два клиента для Gemini: один для генерации ответов, другой для анализа
    gemini_chat_client = GeminiClient(
        api_key_manager=gemini_api_key_manager, 
        model_name=app_config["gemini_chat_model_name"]
    )
    gemini_analysis_client = GeminiClient(
        api_key_manager=gemini_api_key_manager, 
        model_name=app_config["gemini_analysis_model_name"]
    )
    logger.info(f"Gemini чат-клиент: {app_config['gemini_chat_model_name']}, Gemini анализ-клиент: {app_config['gemini_analysis_model_name']}")

    # Инициализируем краткосрочную память (STM)
    short_term_memory = ShortTermMemory(max_length=app_config["short_term_memory_max_length"])
    
    # Конфигурация для Yandex эмбеддера
    yc_embedder_config = {
        "yc_folder_id": app_config.get("yc_folder_id"),
        "yc_api_key": app_config.get("yc_api_key"),
        "yc_model_embedding_doc": app_config.get("yc_model_embedding_doc"),
        "yc_model_embedding_query": app_config.get("yc_model_embedding_query")
    }
    
    # Инициализируем главный менеджер памяти, который является фасадом для всех операций с памятью
    memory_manager = MemoryManager(all_prompts_data=all_prompts_data, yc_config=yc_embedder_config)

    # 3. Создание и настройка Telegram-приложения
    application = Application.builder().token(app_config["telegram_bot_token"]).build()

    # Помещаем все созданные компоненты и конфигурацию в `application.bot_data`.
    # `bot_data` - это общий словарь, доступный во всех хендлерах через `context.bot_data`.
    # Он служит как центральное хранилище состояния и для внедрения зависимостей (dependency injection).
    application.bot_data["admin_user_id"] = app_config.get("admin_user_id")
    application.bot_data["target_chat_id"] = app_config.get("target_chat_id")
    application.bot_data["is_bot_active"] = True 
    application.bot_data["gemini_chat_client"] = gemini_chat_client
    application.bot_data["gemini_analysis_client"] = gemini_analysis_client
    application.bot_data["gemini_api_key_manager"] = gemini_api_key_manager
    application.bot_data["short_term_memory"] = short_term_memory
    application.bot_data["users_data_dict"] = users_data_dict 
    application.bot_data["mishka_system_prompt_template"] = mishka_system_prompt 
    application.bot_data["memory_manager"] = memory_manager
    application.bot_data["all_prompts"] = all_prompts_data
    # Счетчик сообщений для отложенного запуска извлечения фактов
    application.bot_data["user_message_count_for_fact_extraction_trigger"] = 0
    application.bot_data["last_response_timestamp"] = 0.0 # Время последнего ответа
    application.bot_data["response_cooldown_seconds"] = 3.0 # Кулдаун в секундах

    application.bot_data["emotional_analysis_msg_counters"] = {}

    # Перенос порогов и настроек из .env в bot_data для легкого доступа
    application.bot_data["USER_MESSAGES_THRESHOLD_FOR_FACT_EXTRACTION_CONFIG"] = app_config["user_messages_threshold_for_fact_extraction"]
    application.bot_data["CONVERSATION_CHUNK_SIZE_FOR_FACT_ANALYSIS_CONFIG"] = app_config["conversation_chunk_size_for_fact_analysis"]
    application.bot_data["EMOTIONAL_ANALYSIS_MESSAGE_THRESHOLD_CONFIG"] = app_config["emotional_analysis_message_threshold"]
    application.bot_data["EMOTIONAL_ANALYSIS_STM_WINDOW_SIZE_CONFIG"] = app_config["emotional_analysis_stm_window_size"]
    application.bot_data["EMOTIONAL_NOTES_CONSOLIDATION_TRIGGER_COUNT_CONFIG"] = app_config["emotional_notes_consolidation_trigger_count"]
    application.bot_data["MAX_CONSOLIDATED_EMOTIONAL_NOTES_CONFIG"] = app_config["max_consolidated_emotional_notes"]
    application.bot_data["LTM_MAX_RELEVANT_DISTANCE_CONFIG"] = app_config["ltm_max_relevant_distance"]
    application.bot_data["LTM_IMPORTANCE_DECAY_FACTOR_CONFIG"] = app_config["ltm_importance_decay_factor"]
    application.bot_data["LTM_MIN_IMPORTANCE_FOR_RETENTION_CONFIG"] = app_config["ltm_min_importance_for_retention"]
    application.bot_data["LTM_DAYS_FOR_IMPORTANCE_DECAY_CONFIG"] = app_config["ltm_days_for_importance_decay"]
    
    # 4. Регистрация обработчиков (хендлеров)
    # Пользовательские команды
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help_ai", help_command))
    application.add_handler(CommandHandler("chatid", chat_id_command))
    # Основной обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Админ-команды
    application.add_handler(CommandHandler("toggle_bot_active", toggle_bot_active_command))
    application.add_handler(CommandHandler("list_users", list_users_command))
    application.add_handler(CommandHandler("show_user_info", show_user_info_command))
    application.add_handler(CommandHandler("memory_stats", memory_stats_command))
    application.add_handler(CommandHandler("list_facts", list_facts_command)) 
    application.add_handler(CommandHandler("find_facts", find_facts_command)) 
    application.add_handler(CommandHandler("delete_fact", delete_fact_command))
    application.add_handler(CommandHandler("clear_ltm_admin_danger_zone", clear_ltm_command))
    application.add_handler(CommandHandler("maintain_ltm", maintain_ltm_command))
    application.add_handler(CommandHandler("clear_emo_user", clear_emotional_user_command))
    application.add_handler(CommandHandler("clear_emo_all_danger", clear_emotional_all_danger_command))
    # Обработчики нажатий на инлайн-кнопки (для пагинации и подтверждений)
    application.add_handler(CallbackQueryHandler(facts_page_callback, pattern='^facts_page_'))
    application.add_handler(CallbackQueryHandler(confirm_clear_ltm_callback, pattern='^confirm_clear_ltm_'))
    application.add_handler(CallbackQueryHandler(confirm_clear_emotional_user_callback, pattern='^confirm_clear_emo_user_'))
    application.add_handler(CallbackQueryHandler(confirm_clear_emotional_all_callback, pattern='^confirm_clear_emo_all_'))

    # 5. Настройка и запуск планировщика задач
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(scheduled_ltm_maintenance_job, 'cron', hour=4, minute=0, args=[application])
    scheduler.add_job(scheduled_api_key_reset_job, 'cron', hour=0, minute=1, args=[application])
    scheduler.start()
    logger.info("Планировщик задач запущен. Обслуживание LTM: 4:00. Сброс API ключей: 00:01.")

    # 6. Запуск и graceful shutdown бота
    try:
        logger.info("Инициализация приложения Telegram...")
        await application.initialize()
        logger.info("Запуск фоновых задач приложения...")
        await application.start()
        
        if application.updater:
            logger.info("Запуск поллинга обновлений...")
            await application.updater.start_polling(poll_interval=1.0) 
            logger.info("Бот запущен и принимает обновления. Нажмите Ctrl+C для остановки.")
            # Бесконечный цикл для поддержания работы
            while True: 
                await asyncio.sleep(3600)
        else:
            logger.error("Updater не был инициализирован.")
            return
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt. Остановка бота...")
    except Exception as e:
        logger.error(f"Ошибка во время работы бота: {e}", exc_info=True)
    finally:
        logger.info("Начало процесса остановки бота...")
        # Корректно завершаем все компоненты в обратном порядке
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Планировщик задач остановлен.")
        if application: 
            if application.updater and application.updater.running:
                logger.info("Остановка поллинга...")
                await application.updater.stop()
            if hasattr(application, 'running') and application.running: 
                 logger.info("Остановка приложения...")
                 await application.stop()
            logger.info("Освобождение ресурсов...")
            await application.shutdown()
        logger.info("Бот полностью остановлен.")

def main_sync():
    """Синхронная обертка для запуска асинхронного `run_bot`."""
    if UVLOOP_AVAILABLE:
        # uvloop - это быстрая замена стандартного цикла событий asyncio
        logger.info("Используется uvloop.")
    else:
        logger.info("uvloop не найден, используется стандартный asyncio event loop.")
    
    try:
        logger.info("Запуск бота...")
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt (верхний уровень). Завершение.")
    finally:
        logger.info("Программа завершена.")

# Точка входа в приложение
if __name__ == "__main__":
    main_sync()