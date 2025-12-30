FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml .

# For now just install basics, will use poetry or pip later
RUN pip install --no-cache-dir .

COPY . .

CMD ["python", "-m", "mishka_brain"]
