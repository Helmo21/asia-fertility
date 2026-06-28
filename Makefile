.PHONY: install format format-check lint lint-check test test-fast test-slow test-integration cov build clean reproduce

install:
	uv venv
	uv sync --all-extras
	uv run pre-commit install

format:
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check . --fix
	uv run mypy src/asia_fertility

lint-check:
	uv run ruff check .
	uv run mypy src/asia_fertility

test:
	uv run pytest -q -m "not slow and not integration"

test-fast:
	uv run pytest -q -m "not slow and not integration" --no-cov

test-slow:
	uv run pytest -q -m "slow"

test-integration:
	uv run pytest -q -m "integration"

cov:
	uv run pytest --cov=asia_fertility --cov-report=html --cov-report=term-missing

build:
	uv build

reproduce:
	uv run asia-fertility reproduce

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -not -path "./legacy_v01/*" -not -path "./fertiscope-web/*" -not -path "./token_degradation_fertility/*" -exec rm -rf {} +
