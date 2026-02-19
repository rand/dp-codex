.PHONY: check test lint typecheck format format-check

check: lint typecheck test

test:
	PYTHONPATH=. uv run pytest -q

lint:
	uv run ruff check dp tests

typecheck:
	uv run mypy dp

format:
	uv run ruff format dp tests

format-check:
	uv run ruff format --check dp tests
