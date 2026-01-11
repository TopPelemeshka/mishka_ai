FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml .

RUN pip install --no-cache-dir .

COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
