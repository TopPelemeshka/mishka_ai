FROM python:3.11-slim

# Установка переменных окружения для предотвращения создания .pyc файлов и буферизации вывода
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Установка рабочей директории
WORKDIR /app

# Установка системных зависимостей
# build-essential может понадобиться для сборки некоторых python пакетов
# curl пригодится для healthcheck-ов
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование файла зависимостей и их установка
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY . .

# Копируем скрипт запуска
COPY scripts/ scripts/
RUN chmod +x scripts/start.sh

# Запуск через скрипт (миграции + бот)
CMD ["/app/scripts/start.sh"]
