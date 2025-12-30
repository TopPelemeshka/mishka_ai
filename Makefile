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
	docker-compose run --rm mishka-llm-provider pytest tests/ -v --cov=src

test-gateway:
	docker-compose run --rm -e TELEGRAM_BOT_TOKEN="123456789:AABBCCDDEEFFaabbccddeeff1234567890" mishka-bot-gateway pytest tests/ -v --cov=src
