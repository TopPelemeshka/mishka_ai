FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[dev]"

# Copy application
COPY . .

# Run application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
