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
