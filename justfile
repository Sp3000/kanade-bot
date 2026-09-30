default:
    @just --list

static:
    uv run --group dev ruff check .
    uv run --group dev mypy --strict .

fmt:
    uv run --group dev ruff format .

check:
    uv run --group dev ruff format --check .

lint: static check
