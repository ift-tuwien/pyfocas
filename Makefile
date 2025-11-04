# -- Variables -----------------------------------------------------------------

PACKAGE := pyfocas

# -- Rules ---------------------------------------------------------------------

.PHONY: setup
setup:
	uv venv --allow-existing
	uv sync --all-extras

.PHONY: check
check:
	uv run flake8 .
	uv run mypy $(PACKAGE)
	uv run pylint .

.PHONY: test
test: check
	uv run pytest
