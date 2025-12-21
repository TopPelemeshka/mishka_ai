# Mishka AI 🐻

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![Aiogram](https://img.shields.io/badge/aiogram-3.x-blue)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Gemini%20Flash-orange)
![License](https://img.shields.io/badge/license-MIT-green)

**Mishka AI** — это умный Telegram-бот с долговременной памятью и яркой индивидуальностью. Бот использует передовые LLM (Google Gemini) для ведения осмысленного диалога, помнит контекст общения и адаптируется под собеседника.

## 🚀 Технологический стек

*   **Язык:** Python 3.11
*   **Фреймворк:** [Aiogram 3.x](https://aiogram.dev/) (Асинхронный)
*   **API:** FastAPI (Вебхуки и Mini Apps)
*   **AI:** Google Gemini 3.0 Flash/Pro (через LangChain)
*   **Базы данных:**
    *   **PostgreSQL:** Хранение профилей и логов.
    *   **Redis:** Кэш, FSM, краткосрочная память.
    *   **Qdrant:** Векторная база знаний (RAG).
*   **Оркестрация:** LangGraph (Агентские циклы).

## 🛠 Установка и запуск

Проект полностью контейнеризирован. Для запуска требуется **Docker** и **Docker Compose**.

1.  **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/username/mishka_ai.git
    cd mishka_ai
    ```

2.  **Настройте окружение:**
    Создайте файл `.env` на основе примера:
    ```bash
    cp .env.example .env
    ```
    Откройте `.env` и укажите свои ключи (Telegram Token, Google API Key) и ваш `ALLOWED_CHAT_ID` (для безопасности).

3.  **Запустите проект:**
    ```bash
    docker-compose up -d --build
    ```

Бот автоматически применит миграции базы данных и запустится.

## 🛡 Безопасность

Бот защищен `ChatAuthMiddleware` и реагирует только на сообщения из разрешенного чата (`ALLOWED_CHAT_ID`).

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. Подробнее см. файл LICENSE.
