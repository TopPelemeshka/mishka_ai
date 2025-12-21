#!/bin/bash
set -e

echo "Waiting for DB to be ready..."
# (Optional: add wait-for-it logic if needed, but usually retry is enough)

echo "Checking migrations..."
# Проверяем, есть ли файлы .py в versions (исключая __init__.py если есть)
count=$(find src/database/migrations/versions -name "*.py" | wc -l)

if [ "$count" -eq "0" ]; then
    echo "No migrations found. Generating initial migration..."
    # Используем -m "initial" для понятности
    alembic revision --autogenerate -m "initial_structure"
fi

echo "Applying migrations..."
alembic upgrade head

echo "Starting Mishka AI bot..."
python -m src.main
