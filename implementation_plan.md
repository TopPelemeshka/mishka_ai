# План реализации Инфраструктуры и LLM Provider

Этот план описывает шаги по обновлению `docker-compose.yml` и реализации сервиса `mishka-llm-provider`.

## User Review Required
> [!IMPORTANT]
> Сервис LLM Provider будет использовать `http://host.docker.internal:12334` для доступа к прокси с локальной машины пользователя. Это стандартный подход для Docker Desktop, но на Linux может потребоваться дополнительная настройка (`extra_hosts`).

## Proposed Changes

### Infrastructure

#### [MODIFY] [docker-compose.yml](file:///d:/mishka_ai/docker-compose.yml)
- Добавление volumes для `postgres` и `qdrant` для сохранения данных.
- Обновление конфигурации сервисов.

### Mishka LLM Provider (services/mishka-llm-provider)

#### [MODIFY] [pyproject.toml](file:///d:/mishka_ai/services/mishka-llm-provider/pyproject.toml)
- Добавление зависимостей: `fastapi`, `uvicorn`, `google-generativeai`, `python-dotenv`, `requests`, `httpx`.

#### [NEW] [src/main.py](file:///d:/mishka_ai/services/mishka-llm-provider/src/main.py)
- Основной файл приложения FastAPI.
- Эндпоинт `/v1/chat/completions`.
- Инициализация клиента Gemini с использованием прокси.

#### [NEW] [src/config.py](file:///d:/mishka_ai/services/mishka-llm-provider/src/config.py)
- Загрузка переменных окружения.
- Логика замены `localhost` на `host.docker.internal` для прокси.

#### [MODIFY] [Dockerfile](file:///d:/mishka_ai/services/mishka-llm-provider/Dockerfile)
- Обновление для работы с `src/` структурой.
- Установка зависимостей.
- Change CMD to run uvicorn.

## Verification Plan

### Automated Tests
- Пока тестов нет, будем проверять вручную.

### Manual Verification
1. Запустить `docker-compose up -d postgres qdrant mishka-llm-provider`.
2. Проверить логи: `docker-compose logs -f mishka-llm-provider`.
3. Отправить CURL запрос к LLM Provider:
   ```bash
   curl -X POST http://localhost:8000/v1/chat/completions \
   -H "Content-Type: application/json" \
   -d '{"model": "gemini-pro", "messages": [{"role": "user", "content": "Hello!"}]}'
   ```
   (Примечание: порт 8000 нужно будет пробросить в docker-compose для теста, либо заходить внутрь контейнера, но лучше пробросить).

> [!NOTE]
> Добавлю проброс порта 8000 для `mishka-llm-provider` в `docker-compose.yml` для удобства тестирования.
