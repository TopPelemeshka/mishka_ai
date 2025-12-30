---
trigger: always_on
---

# Архитектура проекта Mishka AI

Проект построен на микросервисной архитектуре с использованием Docker Compose.

## Структура сервисов:
1.  **mishka-brain (Core):** Оркестратор на базе LangGraph. Принимает решения.
2.  **mishka-bot-gateway (Gateway):** Интерфейс Telegram (Aiogram 3). Вебхуки/Поллинг.
3.  **mishka-llm-provider (LLM):** Единая точка доступа к нейросетям.
    *   **ВАЖНО:** Работает через прокси. URL прокси: `http://127.0.0.1:12334` (брать из ENV `LLM_PROXY`).
4.  **mishka-memory:** API для работы с БД (PostgreSQL + Qdrant).
5.  **tools/**: Отдельные сервисы для инструментов (browser, media, search).

## Принципы разработки:
- Каждый сервис имеет свой `Dockerfile`.
- Общение между сервисами: REST API (синхронно) и RabbitMQ (асинхронно).
- Все сервисы поднимаются через единый `docker-compose.yml` в корне.
- Используем `FastAPI` для HTTP сервисов.