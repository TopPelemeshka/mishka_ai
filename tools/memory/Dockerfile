FROM python:3.11-slim

WORKDIR /app

RUN pip install fastapi uvicorn httpx pydantic

COPY src/ /app/src/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
