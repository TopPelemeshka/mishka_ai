FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml .

RUN pip install --no-cache-dir .

COPY . .

# Check config by printing it (optional debug)
RUN python -c "from src.config import get_proxy_url; print(f'Build time proxy check: {get_proxy_url()}')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
