# Mishka Brain (Core)

## Описание
Центральный оркестратор системы на базе LangGraph. Принимает решения, вызывает инструменты, управляет диалогом и памятью.

## Архитектура
*   **Inputs**:
    *   RabbitMQ (`brain_tasks`): Задачи на генерацию ответа (от Gateway или Initiative).
*   **Outputs**:
    *   RabbitMQ (`bot_outbox`): Сгенерированный ответ.
    *   HTTP Calls: Вызовы инструментов (`tools/*`), памяти (`mishka-memory`) и LLM (`mishka-llm-provider`).

## Переменные окружения (Static)
| Переменная | Описание |
| :--- | :--- |
| `LLM_PROVIDER_URL` | URL сервиса LLM Provider. |
| `ENV` | `dev` или `prod`. |

## Динамические настройки (Dynamic)
Управляются через **Admin Panel**.

| Ключ | Тип | Описание |
| :--- | :--- | :--- |
| `llm_model` | string | Модель LLM (например, `gemini-2.0-flash`). |
| `system_prompt` | string | Основная инструкция для личности бота. |
| `temperature` | float | Креативность ответов (0.0 - 1.0). |
| `rag_fact_limit` | int | Количество фактов из памяти для подстановки в контекст. |
