.PHONY: infra-up infra-down api web migrate test lint format
infra-up:
	docker compose up -d
infra-down:
	docker compose down
api:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000
web:
	cd apps/web && npm run dev
migrate:
	cd apps/api && uv run alembic upgrade head
test:
	cd apps/api && uv run pytest -v
lint:
	cd apps/api && uv run ruff check .
format:
	cd apps/api && uv run ruff format .

