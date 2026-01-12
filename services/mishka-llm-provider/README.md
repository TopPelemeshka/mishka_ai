# Mishka LLM Provider

## Описание
Унифицированный шлюз к нейросетям (Gemini API). Обеспечивает ротацию ключей, работу через прокси и единый интерфейс (OpenAI-like).

## Архитектура
*   **Inputs**:
    *   HTTP API (`POST /v1/chat/completions`)
    *   RabbitMQ (для получения обновлений конфига)
*   **Outputs**:
    *   Google Gemini API (Internet)

## Переменные окружения (Static)
| Переменная | Описание |
| :--- | :--- |
| `GOOGLE_API_KEYS` | Список ключей через запятую (API Key Rotation). |
| `LLM_PROXY` | HTTP/HTTPS прокси для доступа к Google API (обход блокировок). |

## Динамические настройки (Dynamic)
Управляются через **Admin Panel**.

| Ключ | Тип | Описание |
| :--- | :--- | :--- |
| `request_timeout` | float | Таймаут ожидания ответа от Google API (сек). |
| `default_model` | string | Модель по умолчанию, если не указана в запросе. |
