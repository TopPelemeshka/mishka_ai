FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml .

RUN pip install --no-cache-dir ".[dev]"

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "src/main.py"]
