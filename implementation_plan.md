# План реализации: RAG (Retrieval Augmented Generation)

Цель: Долгосрочная память для Мишки на базе векторного поиска.

## 1. LLM Provider (`mishka-llm-provider`)
Модель: `models/text-embedding-004`.
Размерность: 768.

### Changes
- `src/main.py`:
    - `POST /v1/embeddings`
    - Payload: `{ content: str, task_type: "retrieval_query" | "retrieval_document" }`
    - Logic: `genai.embed_content(..., task_type=...)`

# Implementing Memory Tool (Self-Learning)

The goal is to allow the LLM to actively "remember" facts by calling a tool, which then saves the fact to the vector database.

## Proposed Changes

### [NEW] tools/memory
- **Service**: Small FastAPI app.
- **Port**: 8006 (Internal, mapped to host for testing).
- **Files**:
    - `Dockerfile`: Python 3.11 slim, install `fastapi`, `uvicorn`, `httpx`.
    - `src/main.py`:
        - `GET /manifest`: Returns tool definition (`remember_fact`).
        - `POST /run`: Accepts `{"text": "..."}`, calls `mishka-memory/facts/add`.

### [MODIFY] [docker-compose.yml](file:///d:/mishka_ai/docker-compose.yml)
- Add `tool-memory` service definition.
- Expose on port 8006.
- Ensure it waits for `mishka-memory`.

### [MODIFY] [mishka-memory/src/database.py](file:///d:/mishka_ai/services/mishka-memory/src/database.py)
- Create a migration/script to register the tool in the `tools` table.
- OR use a SQL script in `init.sql`.

## Verification Plan

### Automated Tests
- Test adding a fact via tool endpoint:
  ```bash
  curl -X POST http://localhost:8006/run -d '{"text": "Test Fact"}'
  ```

### Manual Verification
- Chat with bot: "Меня зовут Влад, и я люблю суши" -> Bot calls `remember_fact`.
- Chat with bot: "Что я люблю?" -> Bot retrieves "Влад любит суши".

## 2. Memory Service (`mishka-memory`)
База: Qdrant (уже есть в docker-compose).

### Changes
- `pyproject.toml`: Add `qdrant-client`.
- `src/qdrant.py`:
    - `init_collection()`: Создает `mishka_facts` (Cosine, 768 dim).
    - `upload_fact(vector, payload)`
    - `search_facts(vector, limit=5)`
- `src/main.py`:
    - `POST /facts/add`: Получает текст -> просит эмбеддинг у LLM Provider -> сохраняет в Qdrant.
    - `POST /facts/search`: Получает запрос -> просит эмбеддинг query у LLM Provider -> ищет в Qdrant.

## 3. Brain Service (`mishka-brain`)
Логика: Перед ответом пользователя, поискать похожие факты.

### Changes
- `src/graph.py`:
    - В `agent_node` (или перед ним):
    - Сделать запрос в `mishka-memory/facts/search` с текстом последнего сообщения пользователя (или сгенерированным query).
    - Если есть результаты с `score > 0.6`, добавить их в System Prompt:
      ```
      [Long Term Memory]
      - User likes sushi
      - User lives in Moscow
      ```

## 4. Verification
1.  Отправить запрос "Запомни: мой любимый цвет красный". -> (Manual trigger or logic) -> Save to Qdrant.
2.  Спросить "Какой мой любимый цвет?". -> Retrieve from Qdrant -> Answer "Красный".
