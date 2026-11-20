.PHONY: install uninstall lint format typecheck test check

# Editable, so the installed `fand` runs from this checkout: it builds the agent's image from
# here and keeps .env and findings/ here.
install:
	uv sync --locked
	uv tool install --editable --force .

uninstall:
	uv tool uninstall fandian

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run ty check src

test:
	uv run pytest

check: lint typecheck test
