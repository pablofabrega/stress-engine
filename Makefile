COMPOSE=docker compose

.PHONY: up down logs backend-test migrate frontend-install

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

backend-test:
	cd backend && pytest

migrate:
	cd backend && alembic upgrade head

frontend-install:
	cd frontend && npm install

