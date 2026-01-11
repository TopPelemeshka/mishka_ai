FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app

COPY pyproject.toml .

RUN pip install --no-cache-dir ".[dev]"

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
