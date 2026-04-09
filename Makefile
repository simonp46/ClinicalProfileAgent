.PHONY: dev down logs api web worker test lint format seed fix-demo-email migrate makemigrations demo

dev:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

api:
	docker compose up --build api

web:
	docker compose up --build web

worker:
	docker compose up --build worker

migrate:
	docker compose run --rm api bash -lc "cd /app/apps/api && alembic upgrade head"

makemigrations:
	docker compose run --rm api bash -lc "cd /app/apps/api && alembic revision --autogenerate -m 'auto'"

seed:
	docker compose run --rm api bash -lc "cd /app/apps/api && python -m app.scripts.seed_demo"

fix-demo-email:
	docker compose run --rm api bash -lc "cd /app/apps/api && python -m app.scripts.fix_demo_email"

demo:
	docker compose run --rm api bash -lc "cd /app/apps/api && python -m app.scripts.run_demo_pipeline"

test:
	docker compose run --rm api bash -lc "cd /app/apps/api && pytest"
	docker compose run --rm web bash -lc "cd /app/apps/web && npm test"

lint:
	docker compose run --rm api bash -lc "cd /app/apps/api && ruff check . && black --check . && mypy app"
	docker compose run --rm web bash -lc "cd /app/apps/web && npm run lint"

format:
	docker compose run --rm api bash -lc "cd /app/apps/api && black . && ruff check --fix ."
	docker compose run --rm web bash -lc "cd /app/apps/web && npm run format"
