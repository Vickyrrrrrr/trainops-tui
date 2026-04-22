.PHONY: sync lint type test api worker tui migrate seed smoke

sync:
	uv sync --all-extras

lint:
	uv run ruff check .

type:
	uv run mypy apps packages tests

test:
	uv run pytest

api:
	uv run uvicorn trainops_api.main:app --reload --port 8080

worker:
	uv run python -m trainops_worker.worker

tui:
	uv run trainops-tui

migrate:
	uv run alembic -c infra/alembic.ini upgrade head

seed:
	uv run python scripts/seed_demo.py

smoke:
	uv run python scripts/smoke.py

