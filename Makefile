.PHONY: up down build logs

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

test-llm:
	docker-compose run --rm mishka-llm-provider python -m pytest tests/ -v --cov=src

test-memory:
	docker-compose run --rm mishka-memory python -m pytest tests/ -v --cov=src

test-gateway:
	docker-compose run --rm -e TELEGRAM_BOT_TOKEN="123456789:AABBCCDDEEFFaabbccddeeff1234567890" mishka-bot-gateway python -m pytest tests/ -v --cov=src

test-brain:
	docker-compose run --rm mishka-brain python -m pytest tests/ -v --cov=src
