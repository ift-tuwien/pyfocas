# -- Variables -----------------------------------------------------------------

PACKAGE := pyfocas

# -- Rules ---------------------------------------------------------------------

.PHONY: check
check:
	uv run flake8 .
	uv run mypy $(PACKAGE)
	uv run pylint .

.PHONY: setup
setup:
	uv venv --allow-existing
	uv sync --all-extras

.PHONY: test
test:
	uv run pytest
